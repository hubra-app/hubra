"""Problem reports, feature requests and the roadmap.

``support_bp`` (``/api/v1/support``): signed-in people send cases, follow
their own and vote on the roadmap.
``roadmap_bp`` (``/api/v1/roadmap``): the public roadmap, no sign-in.
``support_admin_bp`` (``/api/v1/manager/support``): platform staff with
``support.cases`` read, answer, close, merge and publish cases.
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import jwt_required

from hubra.api.auth.helpers import get_current_user_id
from hubra.api.permissions import require_global_permission
from hubra.api.support import services
from hubra.api.support.services import SupportError
from hubra.core.errors import api_error
from hubra.core.extensions import db, limiter
from hubra.core.models.support_case import SupportCase
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.models.user import User

support_bp = Blueprint("support_bp", __name__)
roadmap_bp = Blueprint("roadmap_bp", __name__)
support_admin_bp = Blueprint("support_admin_bp", __name__)

_PERM = "support.cases"


def _me() -> User | None:
    try:
        user = db.session.get(User, get_current_user_id())
    except (TypeError, ValueError):
        return None
    if user is None or user.is_disabled:
        return None
    return user


def _club_id() -> int | None:
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    return tenant.id if tenant is not None else None


# ── People: /support ──────────────────────────────────────────────────────────


@support_bp.post("/cases")
@jwt_required()
@limiter.limit("20 per hour")
def create_case():
    """Body: ``kind`` (bug | feature), ``title``, ``description``; bug:
    ``steps``, ``expected``, ``severity``; feature: ``useCase``; both:
    ``area``, ``page``, ``fingerprint`` (browser, OS, device, screen)."""
    user = _me()
    if user is None:
        return api_error("UNAUTHORIZED", "Sign in first", 401)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return api_error("VALIDATION_ERROR", "Expected an object", 400)
    try:
        case = services.submit(user.id, _club_id(), body)
    except SupportError as exc:
        db.session.rollback()
        return api_error("VALIDATION_ERROR", str(exc), 400)
    db.session.commit()
    services.alert_staff(case)
    return jsonify(
        services.as_dict(case, votes=1 if case.kind == "feature" else 0)
    ), 201


@support_bp.get("/cases")
@jwt_required()
def list_my_cases():
    user = _me()
    if user is None:
        return api_error("UNAUTHORIZED", "Sign in first", 401)
    return jsonify(services.mine(user.id)), 200


@support_bp.get("/cases/<int:case_id>")
@jwt_required()
def get_my_case(case_id: int):
    user = _me()
    case = services.own_case(user.id, case_id) if user else None
    if case is None:
        return api_error("NOT_FOUND", "Case not found", 404)
    item = services.as_dict(case)
    item["comments"] = services.comments_for(case, staff=False)
    item["commentCount"] = len(item["comments"])
    return jsonify(item), 200


@support_bp.post("/cases/<int:case_id>/comments")
@jwt_required()
@limiter.limit("60 per hour")
def comment_my_case(case_id: int):
    user = _me()
    case = services.own_case(user.id, case_id) if user else None
    if case is None:
        return api_error("NOT_FOUND", "Case not found", 404)
    if case.merged_into_id is not None:
        return api_error("CONFLICT", "This case was merged into another one", 409)
    body = request.get_json(silent=True) or {}
    try:
        comment = services.add_comment(case, user.id, body.get("body"), staff=False)
    except SupportError as exc:
        db.session.rollback()
        return api_error("VALIDATION_ERROR", str(exc), 400)
    db.session.commit()
    return jsonify(services.comment_dict(comment, user, staff_view=False)), 201


@support_bp.get("/roadmap")
@jwt_required()
def my_roadmap():
    user = _me()
    if user is None:
        return api_error("UNAUTHORIZED", "Sign in first", 401)
    return jsonify(services.roadmap(user.id)), 200


def _vote(case_id: int, on: bool):
    user = _me()
    if user is None:
        return api_error("UNAUTHORIZED", "Sign in first", 401)
    try:
        votes = services.vote(user.id, case_id, on)
    except LookupError:
        db.session.rollback()
        return api_error("NOT_FOUND", "Not on the roadmap", 404)
    db.session.commit()
    return jsonify({"id": case_id, "votes": votes, "voted": on}), 200


@support_bp.post("/roadmap/<int:case_id>/vote")
@jwt_required()
@limiter.limit("120 per hour")
def vote_for(case_id: int):
    return _vote(case_id, True)


@support_bp.delete("/roadmap/<int:case_id>/vote")
@jwt_required()
@limiter.limit("120 per hour")
def unvote(case_id: int):
    return _vote(case_id, False)


# ── Anyone: /roadmap ──────────────────────────────────────────────────────────


@roadmap_bp.get("")
@roadmap_bp.get("/")
@limiter.limit("120 per minute")
def public_roadmap():
    """The public roadmap: titles, descriptions, status and votes only."""
    return jsonify(services.roadmap()), 200


# ── Staff: /manager/support ───────────────────────────────────────────────────


def _actor_id() -> int | None:
    return getattr(getattr(g, "system_user", None), "id", None)


def _audit(action: str, case: SupportCase, details: dict | None = None) -> None:
    db.session.add(
        GlobalAuditEntry(
            tenant_id=case.tenant_id,
            actor_id=_actor_id(),
            action=action,
            target_type="SupportCase",
            target_id=str(case.id),
            details={"kind": case.kind, "title": case.title, **(details or {})},
            ip_address=request.remote_addr,
        )
    )


def _case_or_404(case_id: int):
    case = db.session.get(SupportCase, case_id)
    if case is None:
        return None, api_error("NOT_FOUND", "Case not found", 404)
    return case, None


@support_admin_bp.get("/cases")
@require_global_permission(_PERM)
def staff_list():
    """``?kind=bug|feature&status=active|<status>&q=&page=&per_page=``."""
    kind = request.args.get("kind") or None
    if kind and kind not in services.KINDS:
        return api_error("VALIDATION_ERROR", "Unknown kind", 400)
    status = request.args.get("status") or None
    if status and status != "active" and status not in services.STATUSES:
        return api_error("VALIDATION_ERROR", "Unknown status", 400)
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 25))))
    except ValueError:
        return api_error("VALIDATION_ERROR", "page and per_page must be numbers", 400)
    query = (request.args.get("q") or "").strip()[:100] or None
    return jsonify(
        services.staff_listing(
            kind=kind, status=status, query=query, page=page, per_page=per_page
        )
    ), 200


@support_admin_bp.get("/cases/<int:case_id>")
@require_global_permission(_PERM)
def staff_get(case_id: int):
    case, err = _case_or_404(case_id)
    if err:
        return err
    return jsonify(services.staff_detail(case)), 200


@support_admin_bp.patch("/cases/<int:case_id>")
@require_global_permission(_PERM)
def staff_update(case_id: int):
    """Body: any of ``status``, ``isPublic``, ``title``, ``description``,
    ``area``, and ``notify`` (default true: mail the reporter about a new
    status)."""
    case, err = _case_or_404(case_id)
    if err:
        return err
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return api_error("VALIDATION_ERROR", "Expected an object", 400)
    old_status = case.status
    try:
        changed = services.edit(case, body)
        if "status" in body and services.set_status(case, body["status"]):
            changed.append("status")
    except SupportError as exc:
        db.session.rollback()
        return api_error("VALIDATION_ERROR", str(exc), 400)
    if not changed:
        return jsonify(services.staff_detail(case)), 200
    details: dict = {"changed": changed}
    if "status" in changed:
        details["status"] = {"from": old_status, "to": case.status}
    if "isPublic" in changed:
        details["public"] = case.is_public
    _audit("support_case.update", case, details)
    db.session.commit()
    if "status" in changed and body.get("notify", True) is not False:
        services.mail_update(case, services.followers(case))
    return jsonify(services.staff_detail(case)), 200


@support_admin_bp.post("/cases/<int:case_id>/comments")
@require_global_permission(_PERM)
@limiter.limit("120 per hour")
def staff_comment(case_id: int):
    """Body: ``{"body": str, "internal"?: bool}``.  A visible answer is
    mailed to the reporter; an internal note is not shown to them."""
    case, err = _case_or_404(case_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    internal = body.get("internal", False)
    if not isinstance(internal, bool):
        return api_error("VALIDATION_ERROR", "internal must be true or false", 400)
    try:
        comment = services.add_comment(
            case, _actor_id(), body.get("body"), staff=True, internal=internal
        )
    except SupportError as exc:
        db.session.rollback()
        return api_error("VALIDATION_ERROR", str(exc), 400)
    db.session.commit()
    if not internal and case.user_id:
        reporter = db.session.get(User, case.user_id)
        if reporter is not None and not reporter.is_disabled:
            services.mail_update(case, [reporter], comment=comment.body)
    author = db.session.get(User, comment.user_id) if comment.user_id else None
    return jsonify(services.comment_dict(comment, author, staff_view=True)), 201


@support_admin_bp.post("/cases/<int:case_id>/merge")
@require_global_permission(_PERM)
def staff_merge(case_id: int):
    """Body: ``{"into": <case id>}``.  The case closes and points there; its
    votes (and its reporter's) move to the other case."""
    case, err = _case_or_404(case_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    into = body.get("into")
    if not isinstance(into, int) or isinstance(into, bool):
        return api_error("VALIDATION_ERROR", "into must be a case id", 400)
    target = db.session.get(SupportCase, into)
    if target is None:
        return api_error("NOT_FOUND", "Target case not found", 404)
    try:
        services.merge(case, target, _actor_id())
    except SupportError as exc:
        db.session.rollback()
        return api_error("VALIDATION_ERROR", str(exc), 400)
    _audit("support_case.merge", case, {"into": target.id, "into_title": target.title})
    db.session.commit()
    if case.user_id:
        reporter = db.session.get(User, case.user_id)
        if reporter is not None and not reporter.is_disabled:
            services.mail_update(case, [reporter], merged_into=target)
    return jsonify(services.staff_detail(target)), 200
