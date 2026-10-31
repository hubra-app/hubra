"""Tenant management API — create / read / update / delete tenants.

These routes live at ``/api/v1/system/tenants`` and are NOT tenant-scoped —
they are used by the platform administrator (SystemUser with is_superadmin)
to manage the multi-tenant lifecycle.

Routes are guarded by ``@require_global_permission``, which checks the
caller's global roles (``user_id`` JWT claim).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, make_response, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
)
from sqlalchemy import func, select

from hubra.api.permissions import (
    check_global_grant,
    check_impersonation_restriction,
    get_user_global_permissions,
    held_roles,
    invalidate_member_permissions,
    require_global_permission,
)
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.models.tenant_request import TenantRequest
from hubra.core.models.user import User
from hubra.core.services import email_verification
from hubra.core.tenant.service import TenantService, TenantProvisioningError
from hubra.core.tenant.club_settings import (
    accepts_join_requests,
    club_logo,
    club_logo_version,
)

tenant_admin_bp = Blueprint("tenant_admin", __name__)

_log = logging.getLogger(__name__)


def _body_text(body: dict, key: str) -> str:
    """*key* from a JSON body as stripped text ("" if absent); 400 otherwise."""
    value = body.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise_error(400, "VALIDATION_ERROR", f"{key} must be text")
    return value.strip()


def _body_id(body: dict, key: str) -> int | None:
    """*key* as a positive id, None if absent; 400 otherwise."""
    value = body.get(key)
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise_error(400, "VALIDATION_ERROR", f"{key} must be an id")
    return value


def _body_keys(body: dict, key: str) -> list[str] | None:
    """*key* as a list of strings, None if absent; 400 otherwise."""
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise_error(400, "VALIDATION_ERROR", f"{key} must be a list of keys")
    return value


_VALID_STATUSES = {"active", "suspended", "archived"}
# A tuple: "in" then compares, so a list or object sent as plan is a 400,
# not a TypeError from hashing it.
_VALID_PLANS = ("starter", "growth", "enterprise")


# ── Routes ──────────────────────────────────────────────────────────────────


@tenant_admin_bp.route("/tenants", methods=["GET"])
@require_global_permission("tenants.read")
def list_tenants():
    """List all tenants with optional search, filtering, sorting, pagination."""
    args = request.args
    result = TenantService.list_tenants(
        search=args.get("search"),
        plan=args.get("plan"),
        status=args.get("status"),
        sort_by=args.get("sort_by", "created_at"),
        sort_dir=args.get("sort_dir", "asc"),
        page=int(args.get("page", 1)),
        per_page=min(int(args.get("per_page", 20)), 100),
        include_deleted=args.get("include_deleted", "0") == "1",
    )
    return jsonify(
        {
            "tenants": [_tenant_to_dict(t) for t in result["tenants"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
        }
    )


@tenant_admin_bp.route("/tenants", methods=["POST"])
@require_global_permission("tenants.create")
def provision_tenant():
    """Provision a new tenant (creates record + schema + seeds)."""
    data = request.get_json(silent=True) or {}

    name = str(data.get("name") or "").strip()
    slug = str(data.get("slug") or "").strip()
    plan = data.get("plan", "starter")
    admin_email = data.get("admin_email")
    admin_password = data.get("admin_password")

    if not name or not slug:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": "name and slug are required",
            }
        ), 422

    if not (3 <= len(slug) <= 64):
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": "slug must be between 3 and 64 characters",
            }
        ), 422

    if plan not in _VALID_PLANS:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": f"plan must be one of {sorted(_VALID_PLANS)}",
            }
        ), 422

    try:
        tenant = TenantService.provision_tenant(
            name=name,
            slug=slug,
            plan=plan,
            admin_email=admin_email,
            admin_password=admin_password,
        )
        return (
            jsonify(
                {
                    "tenant": _tenant_to_dict(tenant),
                    "provisioning_status_url": f"/api/v1/system/tenants/{tenant.id}/provisioning-status",
                }
            ),
            201,
        )
    except TenantProvisioningError as exc:
        return jsonify({"error": "PROVISION_FAILED", "message": str(exc)}), 422


@tenant_admin_bp.route("/tenants/<int:tenant_id>", methods=["GET"])
@require_global_permission("tenants.read")
def get_tenant(tenant_id: int):
    """Get a single tenant by ID, including usage summary."""
    tenant = TenantService.get_by_id(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    data = _tenant_to_dict(tenant)
    data["usage"] = TenantService.get_usage_stats(tenant_id)
    return jsonify({"tenant": data})


@tenant_admin_bp.route("/tenants/<int:tenant_id>", methods=["PATCH"])
@require_global_permission("tenants.update")
def update_tenant(tenant_id: int):
    """Update tenant attributes (name, plan, settings)."""
    data = request.get_json(silent=True) or {}

    name = _body_text(data, "name") if data.get("name") is not None else None
    if name is not None and not 0 < len(name) <= 255:
        raise_error(400, "VALIDATION_ERROR", "name must be 1 to 255 characters")
    plan = data.get("plan")
    settings = data.get("settings")
    if settings is not None and not isinstance(settings, dict):
        raise_error(400, "VALIDATION_ERROR", "settings must be an object")

    if plan is not None and plan not in _VALID_PLANS:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": f"plan must be one of {sorted(_VALID_PLANS)}",
            }
        ), 422

    if plan is not None:
        restriction = check_impersonation_restriction("change_plan")
        if restriction:
            return jsonify({"error": restriction[0], "message": restriction[1]}), 403

    tenant = TenantService.update_tenant(
        tenant_id,
        name=name,
        plan=plan,
        settings=settings,
    )
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>", methods=["DELETE"])
@require_global_permission("tenants.delete")
def delete_tenant(tenant_id: int):
    """Delete a tenant. Soft-delete by default; force=true for permanent deletion."""
    restriction = check_impersonation_restriction("delete_tenant")
    if restriction:
        return jsonify({"error": restriction[0], "message": restriction[1]}), 403

    force = request.args.get("force", "0") == "1"
    deleted = TenantService.delete_tenant(tenant_id, force=force)
    if not deleted:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    action = "permanently deleted" if force else "archived (soft-delete)"
    return jsonify({"message": f"Tenant {action}"}), 200


@tenant_admin_bp.route("/tenants/<int:tenant_id>/disable", methods=["POST"])
@require_global_permission("tenants.update")
def disable_tenant(tenant_id: int):
    """Suspend a tenant."""
    tenant = TenantService.suspend(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/enable", methods=["POST"])
@require_global_permission("tenants.update")
def enable_tenant(tenant_id: int):
    """Reactivate a tenant."""
    tenant = TenantService.activate(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/archive", methods=["POST"])
@require_global_permission("tenants.update")
def archive_tenant(tenant_id: int):
    """Archive a tenant."""
    tenant = TenantService.archive(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/status", methods=["PATCH"])
@require_global_permission("tenants.update")
def update_tenant_status(tenant_id: int):
    """Update tenant status (active / suspended / archived).

    Kept for backward compatibility with the original #133 endpoint.
    Prefer the dedicated /disable, /enable, /archive endpoints.
    """
    data = request.get_json(silent=True) or {}
    status = str(data.get("status") or "").strip()

    if status not in _VALID_STATUSES:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": f"status must be one of {sorted(_VALID_STATUSES)}",
            }
        ), 422

    tenant = TenantService.set_status(tenant_id, status)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/stats", methods=["GET"])
@require_global_permission("tenants.read")
def get_tenant_stats(tenant_id: int):
    """Get detailed usage statistics for a tenant."""
    tenant = TenantService.get_by_id(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    stats = TenantService.get_usage_stats(tenant_id)
    return jsonify({"stats": stats})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/provisioning-status", methods=["GET"])
@require_global_permission("tenants.read")
def get_provisioning_status(tenant_id: int):
    """Get async provisioning status for a tenant.

    Currently provisioning is synchronous, so the status is either 'complete'
    or 'not_found'.  When async provisioning is implemented, this endpoint
    will return progress information.
    """
    tenant = TenantService.get_by_id(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify(
        {
            "tenant_id": tenant_id,
            "status": "complete",
            "slug": tenant.slug,
        }
    )


# ── Impersonation ───────────────────────────────────────────────────────────

_IMPERSONATION_TIMEOUT_MINUTES = 30


@tenant_admin_bp.route("/tenants/<int:tenant_id>/impersonate", methods=["POST"])
@require_global_permission("impersonate")
def impersonate_tenant_user(tenant_id: int):
    """Start impersonating a user within a tenant.

    Requires System Admin. Issues a new JWT with impersonation claims.
    The original admin's identity is stored in ``impersonator_id`` and
    ``impersonator_user_id`` claims for restoration.
    """
    tenant = TenantService.get_by_id(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404

    if tenant.status != "active":
        return jsonify(
            {
                "error": "TENANT_INACTIVE",
                "message": "Cannot impersonate in an inactive tenant",
            }
        ), 422

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    target_user_id = data.get("user_id")

    if not reason:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": "A reason is required for impersonation",
            }
        ), 422

    claims = get_jwt()
    admin_user_id = claims.get("user_id")
    from hubra.api.auth.helpers import parse_identity

    admin_member_id = parse_identity(claims.get("sub", "0"))

    # Find the target member: either a specific user_id or the tenant's admin
    target_member = None

    if target_user_id is not None and not isinstance(target_user_id, int):
        try:
            target_user_id = int(target_user_id)
        except (TypeError, ValueError):
            return jsonify(
                {"error": "VALIDATION_ERROR", "message": "user_id must be a number"}
            ), 422

    if target_user_id:
        target_user = db.session.get(User, int(target_user_id))
        if target_user is None:
            return jsonify(
                {"error": "NOT_FOUND", "message": "Target user not found"}
            ), 404
        if target_user.is_superadmin:
            return jsonify(
                {
                    "error": "FORBIDDEN",
                    "message": "Cannot impersonate another system admin",
                }
            ), 403
        # Resolve member from user_id in this tenant
        target_member = _find_member_in_tenant(tenant_id, int(target_user_id))
    else:
        # Find the first member in this tenant
        target_member = _find_member_in_tenant(tenant_id, None)

    if target_member is None:
        return jsonify(
            {"error": "NOT_FOUND", "message": "No members found in this tenant"}
        ), 404

    # Platform staff can't be impersonated: their token would carry their
    # platform rights (superadmin flag or any global role).
    if target_member.user_id:
        from hubra.core.models.global_role import UserGlobalRole

        target_user = db.session.get(User, target_member.user_id)
        has_global_role = db.session.scalar(
            select(UserGlobalRole.id)
            .where(UserGlobalRole.user_id == target_member.user_id)
            .limit(1)
        )
        if (target_user and target_user.is_superadmin) or has_global_role:
            return jsonify(
                {
                    "error": "FORBIDDEN",
                    "message": "Cannot impersonate platform staff",
                }
            ), 403

    target_member_id = target_member.id
    target_user_id = target_member.user_id

    timeout = timedelta(minutes=_IMPERSONATION_TIMEOUT_MINUTES)
    expires_at = datetime.now(timezone.utc) + timeout

    # The member in this one club, nothing more: no user_id, so no other
    # club, no club switch and none of the person's platform rights. The
    # deadline is checked on every request (auth check_if_token_revoked).
    additional_claims = {
        "impersonator_id": admin_member_id,
        "impersonator_user_id": admin_user_id,
        "impersonation_reason": reason,
        "impersonation_expires_at": expires_at.isoformat(),
        "tenant_slug": tenant.slug,
    }
    access_token = create_access_token(
        identity=str(target_member_id),
        additional_claims=additional_claims,
        expires_delta=min(timeout, current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]),
    )
    refresh_token = create_refresh_token(
        identity=str(target_member_id),
        additional_claims=additional_claims,
        expires_delta=timeout,
    )

    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant_id,
            actor_id=admin_user_id,
            action="impersonation.start",
            target_type="Member",
            target_id=str(target_member_id),
            details={
                "reason": reason,
                "tenant_slug": tenant.slug,
                "target_user_id": target_user_id,
            },
        )
    )
    db.session.commit()

    response = make_response(
        jsonify(
            {
                "impersonating": True,
                "tenant_slug": tenant.slug,
                "member_id": target_member_id,
                "expires_at": expires_at.isoformat(),
            }
        ),
        200,
    )
    set_access_cookies(response, access_token)
    set_refresh_cookies(
        response, refresh_token, max_age=_IMPERSONATION_TIMEOUT_MINUTES * 60
    )
    return response


@tenant_admin_bp.route("/impersonation/stop", methods=["POST"])
@jwt_required()
def stop_impersonation():
    """Stop impersonating and give the platform user back their own session.

    The impersonation token holds only the club member, so the permission
    check runs on ``impersonator_user_id``: that user must still be allowed
    to impersonate.
    """
    claims = get_jwt()
    impersonator_member_id = claims.get("impersonator_id")
    impersonator_user_id = claims.get("impersonator_user_id")

    if impersonator_member_id is None or not impersonator_user_id:
        return jsonify(
            {
                "error": "NOT_IMPERSONATING",
                "message": "You are not impersonating anyone",
            }
        ), 400

    admin_user = db.session.get(User, int(impersonator_user_id))
    if admin_user is None or admin_user.is_disabled:
        return jsonify(
            {"error": "UNAUTHORIZED", "message": "Original user not found"}
        ), 401
    perms = get_user_global_permissions(admin_user.id)
    if not admin_user.is_superadmin and not ({"impersonate", "*"} & perms):
        return jsonify(
            {"error": "FORBIDDEN", "message": "Permission 'impersonate' required"}
        ), 403

    tenant = TenantService.get_by_slug(claims.get("tenant_slug", ""))
    additional_claims = {"user_id": admin_user.id}
    restore_identity = f"user:{admin_user.id}"

    access_token = create_access_token(
        identity=restore_identity,
        additional_claims=additional_claims,
    )
    refresh_token = create_refresh_token(
        identity=restore_identity,
        additional_claims=additional_claims,
    )

    if tenant:
        db.session.add(
            GlobalAuditEntry(
                tenant_id=tenant.id,
                actor_id=impersonator_user_id,
                action="impersonation.end",
                target_type="Member",
                target_id=str(impersonator_member_id),
                details={"tenant_slug": tenant.slug},
            )
        )
        db.session.commit()

    response = make_response(
        jsonify(
            {
                "impersonating": False,
                "member_id": impersonator_member_id,
            }
        ),
        200,
    )
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token, max_age=30 * 24 * 3600)
    return response


# ── Tenant Requests ──────────────────────────────────────────────────────────


def _tenant_request_to_dict(req: TenantRequest) -> dict:
    return {
        "id": req.id,
        "user_id": req.user_id,
        "name": req.name,
        "slug": req.slug,
        "plan": req.plan,
        "status": req.status,
        "admin_note": req.admin_note,
        "reviewed_by": req.reviewed_by,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "updated_at": req.updated_at.isoformat() if req.updated_at else None,
    }


def _notify_requester(req: TenantRequest) -> bool:
    """Mail the requester that *req* was approved or rejected.  True when sent.

    The decision is already committed: a mail failure is logged, never raised.
    """
    from hubra.core.services import email as email_svc

    user = db.session.get(User, req.user_id)
    if user is None or not user.email:
        return False
    lang = user.language or "de-CH"
    try:
        if req.status == "approved":
            return email_svc.send_club_request_approved(
                user.email, user.name, req.name, lang=lang
            )
        return email_svc.send_club_request_rejected(
            user.email, user.name, req.name, req.slug, req.admin_note, lang=lang
        )
    except Exception:
        _log.exception("tenant_request_mail_failed request_id=%s", req.id)
        return False


@tenant_admin_bp.route("/tenant-requests", methods=["POST"])
@jwt_required()
def submit_tenant_request():
    """Submit a request for a new tenant (any authenticated user)."""
    body = request.get_json(silent=True) or {}
    name = _body_text(body, "name")
    slug = _body_text(body, "slug")
    plan = body.get("plan", "starter")

    if not name or not slug:
        raise_error(400, "VALIDATION_ERROR", "name and slug are required")

    from hubra.core.tenant.service import slug_problem

    # Checked now, not only when staff approve the request.
    problem = slug_problem(slug)
    if problem:
        raise_error(400, "VALIDATION_ERROR", problem)
    if len(name) > 255:
        raise_error(400, "VALIDATION_ERROR", "name is longer than 255 characters")

    if plan not in _VALID_PLANS:
        raise_error(
            400, "VALIDATION_ERROR", f"plan must be one of {sorted(_VALID_PLANS)}"
        )

    existing_tenant = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
    if existing_tenant is not None:
        raise_error(409, "CONFLICT", "A tenant with this slug already exists")

    existing_request = db.session.scalar(
        select(TenantRequest).where(
            TenantRequest.slug == slug,
            TenantRequest.status == "pending",
        )
    )
    if existing_request is not None:
        raise_error(409, "CONFLICT", "A pending request with this slug already exists")

    claims = get_jwt()
    user_id = claims.get("user_id")
    if not user_id:
        raise_error(401, "UNAUTHORIZED", "No user_id in token")

    req = TenantRequest(
        user_id=int(user_id),
        name=name,
        slug=slug,
        plan=plan,
        status="pending",
    )
    db.session.add(req)
    db.session.commit()

    return jsonify({"request": _tenant_request_to_dict(req)}), 201


@tenant_admin_bp.route("/tenant-requests", methods=["GET"])
@require_global_permission("requests.read.all")
def list_tenant_requests():
    """List all tenant requests (superadmin only)."""
    status_filter = request.args.get("status")
    query = select(TenantRequest).order_by(TenantRequest.created_at.desc())
    if status_filter:
        query = query.where(TenantRequest.status == status_filter)

    requests = db.session.scalars(query).all()
    return jsonify({"requests": [_tenant_request_to_dict(r) for r in requests]})


@tenant_admin_bp.route("/tenant-requests/mine", methods=["GET"])
@jwt_required()
def list_my_tenant_requests():
    """List the current user's tenant requests."""
    claims = get_jwt()
    user_id = claims.get("user_id")
    if not user_id:
        raise_error(401, "UNAUTHORIZED", "No user_id in token")

    requests = db.session.scalars(
        select(TenantRequest)
        .where(TenantRequest.user_id == int(user_id))
        .order_by(TenantRequest.created_at.desc())
    ).all()
    return jsonify({"requests": [_tenant_request_to_dict(r) for r in requests]})


@tenant_admin_bp.route("/tenant-requests/<int:req_id>/approve", methods=["POST"])
@require_global_permission("requests.approve")
def approve_tenant_request(req_id: int):
    """Approve a tenant request and provision the tenant (superadmin only)."""
    req = db.session.get(TenantRequest, req_id)
    if req is None:
        raise_error(404, "NOT_FOUND", "Tenant request not found")

    if req.status != "pending":
        raise_error(409, "CONFLICT", f"Request is already {req.status}")

    claims = get_jwt()
    reviewer_id = claims.get("user_id")

    try:
        tenant = TenantService.provision_tenant(
            name=req.name,
            slug=req.slug,
            plan=req.plan,
            admin_email=None,
            admin_password=None,
            admin_user_id=req.user_id,
        )
    except TenantProvisioningError as exc:
        raise_error(422, "PROVISION_FAILED", str(exc))

    req.status = "approved"
    req.reviewed_by = int(reviewer_id) if reviewer_id else None
    db.session.commit()
    notified = _notify_requester(req)

    return jsonify(
        {
            "request": _tenant_request_to_dict(req),
            "notified": notified,
            "tenant": {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "plan": tenant.plan,
                "status": tenant.status,
            },
        }
    ), 200


@tenant_admin_bp.route("/tenant-requests/<int:req_id>/reject", methods=["POST"])
@require_global_permission("requests.approve")
def reject_tenant_request(req_id: int):
    """Reject a tenant request (superadmin only)."""
    body = request.get_json(silent=True) or {}
    note = (body.get("note") or "").strip() or None

    req = db.session.get(TenantRequest, req_id)
    if req is None:
        raise_error(404, "NOT_FOUND", "Tenant request not found")

    if req.status != "pending":
        raise_error(409, "CONFLICT", f"Request is already {req.status}")

    claims = get_jwt()
    reviewer_id = claims.get("user_id")

    req.status = "rejected"
    req.admin_note = note
    req.reviewed_by = int(reviewer_id) if reviewer_id else None
    db.session.commit()
    notified = _notify_requester(req)

    return jsonify({"request": _tenant_request_to_dict(req), "notified": notified}), 200


# ── Tenant member management ──────────────────────────────────────────────────


@tenant_admin_bp.route("/tenants/<int:tenant_id>/members", methods=["GET"])
@require_global_permission("tenants.members.read")
def list_tenant_members(tenant_id: int):
    """List all members in a tenant schema."""
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise_error(404, "NOT_FOUND", "Tenant not found")

    from hubra.core.tenant.context import set_search_path, reset_search_path

    try:
        set_search_path(tenant_id)
        members = db.session.scalars(
            select(Member).where(Member.archived_at.is_(None)).order_by(Member.id)
        ).all()
    finally:
        reset_search_path()

    return jsonify({"members": [_member_to_dict(m) for m in members]})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/members", methods=["POST"])
@require_global_permission("tenants.members.write")
def add_tenant_member(tenant_id: int):
    """Add an existing User to a tenant as a Member.

    Body: ``{ "email": str }`` or ``{ "user_id": int }``.
    Creates a Member in the tenant schema + a UserTenant link if not
    already present. Returns 409 if the user is already a member.
    """
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise_error(404, "NOT_FOUND", "Tenant not found")

    body = request.get_json(silent=True) or {}
    email = _body_text(body, "email").lower()
    user_id_body = _body_id(body, "user_id")

    if email:
        user = db.session.scalar(select(User).where(User.email == email))
        if user is None:
            raise_error(404, "NOT_FOUND", f"No user found with email {email}")
    elif user_id_body:
        user = db.session.get(User, user_id_body)
        if user is None:
            raise_error(404, "NOT_FOUND", f"No user found with id {user_id_body}")
    else:
        raise_error(400, "VALIDATION_ERROR", "email or user_id is required")

    member_dict = _add_user_to_tenant(tenant, user)
    db.session.commit()

    return jsonify({"member": member_dict}), 201


def _add_user_to_tenant(tenant: Tenant, user: User) -> dict:
    """Give ``user`` a Member (default role) in ``tenant``, linked in user_tenants.

    Raises 409 when the user is already a member. Leaves the commit to the
    caller and returns the new member as a dict.
    """
    from hubra.api.members.services import _default_role, _welcome_back
    from hubra.core.models.member import MembershipTier
    from hubra.core.models.user_tenant import UserTenant
    from hubra.core.tenant.context import reset_search_path, set_search_path
    from hubra.core.tenant.membership import link_user_to_tenant

    existing = db.session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == user.id,
            UserTenant.tenant_id == tenant.id,
        )
    )
    if existing is not None:
        raise_error(409, "CONFLICT", "User is already a member of this tenant")

    try:
        set_search_path(tenant.id)
        member = db.session.scalar(select(Member).where(Member.user_id == user.id))
        if member is not None and member.archived_at is None:
            # A Member without the user_tenants link (made before links were
            # kept for every new member): repair the link instead of failing.
            link_user_to_tenant(user.id, tenant.id)
            db.session.commit()
            raise_error(409, "CONFLICT", "User is already a member of this tenant")

        if member is not None:
            # Someone who left comes back as the member they were.
            _welcome_back(member, user.id, None, tenant.id)
        else:
            default_role = _default_role()
            tier = db.session.scalar(select(MembershipTier).limit(1))

            member = Member(
                tier_id=tier.id if tier else None,
                user_id=user.id,
                status="active",
            )
            if default_role:
                member.roles = [default_role]
            db.session.add(member)
        db.session.flush()

        # Build the dict while the search_path still points at the club, so
        # a later commit expiring the attributes can't break it.
        member_dict = _member_to_dict(member)
    finally:
        reset_search_path()

    link_user_to_tenant(user.id, tenant.id)
    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant.id,
            action="tenant.add_member",
            target_type="User",
            target_id=str(user.id),
            details={"email": user.email, "member_id": member_dict["id"]},
        )
    )
    return member_dict


# ── Club directory and join requests (any signed-in user) ─────────────────────


def _calling_user() -> User:
    user_id = get_jwt().get("user_id")
    user = db.session.get(User, int(user_id)) if user_id else None
    if user is None:
        raise_error(401, "UNAUTHORIZED", "No user_id in token")
    return user  # type: ignore[return-value]


def _can_add_members(user: User) -> bool:
    """True for platform managers, who join a club straight away."""
    if user.is_superadmin:
        return True
    perms = get_user_global_permissions(user.id)
    return "tenants.members.write" in perms or "*" in perms


def _active_club(slug: str) -> Tenant:
    tenant = db.session.scalar(
        select(Tenant).where(
            Tenant.slug == slug,
            Tenant.status == "active",
            Tenant.deleted_at.is_(None),
        )
    )
    if tenant is None:
        raise_error(404, "NOT_FOUND", "Club not found")
    return tenant  # type: ignore[return-value]


def _membership_in(tenant_id: int, user: User) -> str | None:
    """'member', 'pending' (an open application) or None, read in the club."""
    from hubra.core.models.application import Application
    from hubra.core.tenant.context import reset_search_path, set_search_path

    try:
        set_search_path(tenant_id)
        if db.session.scalar(
            select(Member.id).where(
                Member.user_id == user.id, Member.archived_at.is_(None)
            )
        ):
            return "member"
        if db.session.scalar(
            select(Application.id).where(Application.email == user.email)
        ):
            return "pending"
        return None
    finally:
        reset_search_path()


@tenant_admin_bp.route("/clubs", methods=["GET"])
@jwt_required()
def club_directory():
    """Active clubs the signed-in user can ask to join, with their status.

    Clubs they already belong to are left out: those are under "Meine
    Vereine" already. Everyone else has to search (2+ characters), so the full list of clubs
    isn't handed to anyone who signs up. Platform managers see every club.
    """
    from hubra.api.utils import escape_like
    from hubra.core.models.user_tenant import UserTenant

    user = _calling_user()
    can_join = _can_add_members(user)
    search = (request.args.get("search") or "").strip()
    if len(search) < 2 and not can_join:
        return jsonify({"clubs": [], "canJoinDirectly": False})

    linked = select(UserTenant.tenant_id).where(UserTenant.user_id == user.id)
    query = select(Tenant).where(
        Tenant.status == "active",
        Tenant.deleted_at.is_(None),
        Tenant.id.not_in(linked),
    )
    if search:
        like = f"%{escape_like(search)}%"
        query = query.where(
            Tenant.name.ilike(like, escape="\\") | Tenant.slug.ilike(like, escape="\\")
        )
    tenants = db.session.scalars(query.order_by(Tenant.name).limit(50)).all()

    clubs = []
    for t in tenants:
        membership = _membership_in(t.id, user)
        if membership == "member":
            continue
        clubs.append(
            {
                "slug": t.slug,
                "name": t.name,
                "membership": membership,
                "acceptsRequests": accepts_join_requests(t),
                "logoVersion": club_logo_version(t),
            }
        )
    return jsonify({"clubs": clubs, "canJoinDirectly": can_join})


@tenant_admin_bp.route("/join-requests/mine", methods=["GET"])
@jwt_required()
def my_join_requests():
    """The clubs the signed-in user asked to join that have not answered yet.

    Join requests are applications inside each club, so this looks in every
    active club the user is not linked to.
    """
    from hubra.core.models.user_tenant import UserTenant

    user = _calling_user()
    linked = set(
        db.session.scalars(
            select(UserTenant.tenant_id).where(UserTenant.user_id == user.id)
        ).all()
    )
    tenants = db.session.scalars(
        select(Tenant)
        .where(Tenant.status == "active", Tenant.deleted_at.is_(None))
        .order_by(Tenant.name)
    ).all()
    requests = [
        {"slug": t.slug, "name": t.name}
        for t in tenants
        if t.id not in linked and _membership_in(t.id, user) == "pending"
    ]
    return jsonify({"requests": requests})


def _club_tiers(tenant_id: int) -> list[dict]:
    """The membership tiers a person can ask for, read in the club."""
    from hubra.core.models.member import MembershipTier
    from hubra.core.tenant.context import reset_search_path, set_search_path

    try:
        set_search_path(tenant_id)
        tiers = db.session.scalars(
            select(MembershipTier).order_by(MembershipTier.name)
        ).all()
        return [{"id": t.id, "name": t.name} for t in tiers]
    finally:
        reset_search_path()


@tenant_admin_bp.route("/clubs/<slug>", methods=["GET"])
@jwt_required()
def club_page(slug: str):
    """One club for its join page on SSO: name, your status, the tiers."""
    user = _calling_user()
    tenant = _active_club(slug)
    return jsonify(
        {
            "slug": tenant.slug,
            "name": tenant.name,
            "membership": _membership_in(tenant.id, user),
            "tiers": _club_tiers(tenant.id),
            "canJoinDirectly": _can_add_members(user),
            "acceptsRequests": accepts_join_requests(tenant),
            "logoVersion": club_logo_version(tenant),
        }
    )


@tenant_admin_bp.route("/clubs/<slug>/logo", methods=["GET"])
def club_logo_image(slug: str):
    """The club's logo as an image, for <img> tags on every portal.

    Public like the club's name on its join page: an <img> can't send the
    access token. Links carry ?v=<version>, so it may be cached for a day.
    """
    logo = club_logo(_active_club(slug))
    if logo is None:
        raise_error(404, "NOT_FOUND", "Club has no logo")
    mime, data = logo  # type: ignore[misc]
    response = make_response(data)
    response.headers["Content-Type"] = mime
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["X-Content-Type-Options"] = "nosniff"
    # An SVG opened on its own must not run scripts on the API's origin.
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    )
    # The portals load it from another origin.
    response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    return response


@tenant_admin_bp.route("/clubs/<slug>/join", methods=["POST"])
@jwt_required()
def join_club(slug: str):
    """Join a club, or ask to join it.

    Platform managers (superadmins, ``tenants.members.write``) become a
    member straight away. Everyone else files a membership application in
    the club, optionally for a tier (``{"wantsTierId": 3}``), which its
    admins approve under Members → Applications; approving links the
    existing account, password unchanged.
    """
    from hubra.api.applications.services import ApplicationsService
    from hubra.core.tenant.context import reset_search_path, set_search_path
    from hubra.core.tenant.membership import link_user_to_tenant

    user = _calling_user()
    tenant = _active_club(slug)
    club = {"slug": tenant.slug, "name": tenant.name}

    # A club's admins approve the address they see, so it must be confirmed.
    if email_verification.required(user):
        db.session.commit()  # required() may have flagged a superadmin
        raise_error(
            403,
            "EMAIL_NOT_VERIFIED",
            "Confirm your email address before joining a club",
        )

    status = _membership_in(tenant.id, user)
    if status == "member":
        # Members made before every new member got a user_tenants link.
        link_user_to_tenant(user.id, tenant.id)
        db.session.commit()
        raise_error(409, "ALREADY_MEMBER", "You are already a member of this club")

    if _can_add_members(user):
        _add_user_to_tenant(tenant, user)
        db.session.commit()
        return jsonify({"status": "joined", "club": club}), 201

    if status == "pending":
        raise_error(409, "REQUEST_PENDING", "Your request to join this club is pending")

    if not accepts_join_requests(tenant):
        raise_error(
            403, "JOIN_REQUESTS_CLOSED", "This club takes new members by invite only"
        )

    wants_tier_id = (request.get_json(silent=True) or {}).get("wantsTierId")
    if wants_tier_id is not None and wants_tier_id not in {
        t["id"] for t in _club_tiers(tenant.id)
    }:
        raise_error(400, "VALIDATION_ERROR", "Unknown membership tier")

    try:
        set_search_path(tenant.id)
        ApplicationsService.submit(
            user.first_name or user.email.split("@")[0],
            user.last_name or "",
            user.email,
            wants_tier_id,
        )
        db.session.commit()
    finally:
        reset_search_path()

    return jsonify({"status": "requested", "club": club}), 201


# ── Club invites (a club adds people only by invite) ─────────────────────────


def _invite_from_body():
    from hubra.core.tenant.invites import open_invite

    token = str((request.get_json(silent=True) or {}).get("token") or "")
    invite = open_invite(token)
    if invite is None:
        raise_error(404, "INVITE_NOT_FOUND", "This invite is invalid or has expired")
    tenant = db.session.get(Tenant, invite.tenant_id)  # type: ignore[union-attr]
    if tenant is None or tenant.status != "active" or tenant.deleted_at is not None:
        raise_error(404, "INVITE_NOT_FOUND", "This invite is invalid or has expired")
    return invite, tenant


@tenant_admin_bp.route("/invites/lookup", methods=["POST"])
@jwt_required()
def lookup_invite():
    """The club and address behind an invite link, for the SSO accept page."""
    user = _calling_user()
    invite, tenant = _invite_from_body()
    return jsonify(
        {
            "club": {"slug": tenant.slug, "name": tenant.name},
            "email": invite.email,
            "invitedBy": invite.invited_by,
            "emailMatches": user.email.lower() == invite.email,
            "membership": _membership_in(tenant.id, user),
        }
    )


def _accept(invite, tenant: Tenant, user: User):
    """``user`` joins ``tenant`` through ``invite`` (their address was invited)."""
    from hubra.api.members.services import MembersService
    from hubra.core.tenant.context import in_club

    if user.email.lower() != invite.email:
        raise_error(
            403,
            "INVITE_EMAIL_MISMATCH",
            "This invite was sent to another email address",
        )
    club = {"slug": tenant.slug, "name": tenant.name}

    if _membership_in(tenant.id, user) != "member":
        with in_club(tenant):
            MembersService.add_account(user, invite.member_data)
    invite.accepted_at = datetime.now(timezone.utc)
    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant.id,
            action="tenant.invite_accepted",
            target_type="User",
            target_id=str(user.id),
            details={"email": user.email, "invited_by": invite.invited_by},
        )
    )
    db.session.commit()
    return jsonify({"status": "joined", "club": club}), 200


@tenant_admin_bp.route("/invites/accept", methods=["POST"])
@jwt_required()
def accept_invite():
    """Accept an invite: the signed-in account with the invited address joins."""
    user = _calling_user()
    invite, tenant = _invite_from_body()
    return _accept(invite, tenant, user)


def _live_club(tenant_id: int) -> Tenant | None:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None or tenant.status != "active" or tenant.deleted_at is not None:
        return None
    return tenant


@tenant_admin_bp.route("/invites/mine", methods=["GET"])
@jwt_required()
def my_invites():
    """Open invites to the signed-in account's confirmed address.

    The club picker shows them, so an invite still gets accepted when its
    link was lost on the way (signing up, then confirming the address in
    another tab or on another device).
    """
    from hubra.core.tenant.invites import open_invites_for

    user = _calling_user()
    invites = []
    for invite in open_invites_for(user):
        tenant = _live_club(invite.tenant_id)
        if tenant is None or _membership_in(tenant.id, user) == "member":
            continue
        invites.append(
            {
                "id": invite.id,
                "club": {"slug": tenant.slug, "name": tenant.name},
                "invitedBy": invite.invited_by,
                "expiresAt": invite.expires_at.isoformat(),
            }
        )
    return jsonify({"invites": invites})


@tenant_admin_bp.route("/invites/<int:invite_id>/accept", methods=["POST"])
@jwt_required()
def accept_my_invite(invite_id: int):
    """Accept one of :func:`my_invites` (no link needed: the address is confirmed)."""
    from hubra.core.tenant.invites import open_invites_for

    user = _calling_user()
    invite = next((i for i in open_invites_for(user) if i.id == invite_id), None)
    tenant = _live_club(invite.tenant_id) if invite else None
    if invite is None or tenant is None:
        raise_error(404, "INVITE_NOT_FOUND", "This invite is invalid or has expired")
    return _accept(invite, tenant, user)  # type: ignore[arg-type]


# ── Club admins (the club's own admins, and platform managers) ────────────────
#
# A club's admins are the members holding its Admin or Owner role. Those
# admins manage this list themselves from the manager portal; platform
# managers (``tenants.members.write``) can manage it for any club. Only an
# owner (or a platform manager) can name or remove owners, and the last
# owner can't be removed.


def _club_roles() -> tuple:
    """(admin role, owner role) of the club the search_path points at."""
    from hubra.core.models.role import Role

    owner = db.session.scalar(select(Role).where(Role.is_owner.is_(True)).limit(1))
    admin = db.session.scalar(
        select(Role)
        .where(Role.is_admin.is_(True), Role.is_owner.is_(False))
        .order_by(Role.is_system.desc(), Role.id)
        .limit(1)
    )
    return admin, owner


def _admin_level(member: Member | None) -> str | None:
    """'owner', 'admin' or None for a member of the current club."""
    if member is None:
        return None
    roles = held_roles(member)  # an admin role through a function counts
    if any(r.is_owner for r in roles):
        return "owner"
    if any(r.is_admin for r in roles):
        return "admin"
    return None


def _club_admin_access(tenant: Tenant, user: User) -> str:
    """'platform', 'owner' or 'admin'; 403 for anyone else."""
    if _can_add_members(user):
        return "platform"
    from hubra.core.tenant.context import reset_search_path, set_search_path

    try:
        set_search_path(tenant.id)
        member = db.session.scalar(
            select(Member).where(
                Member.user_id == user.id, Member.archived_at.is_(None)
            )
        )
        # A member the club switched off manages nothing there.
        level = None if member is None or member.is_disabled else _admin_level(member)
    finally:
        reset_search_path()
    if level is None:
        raise_error(403, "FORBIDDEN", "Only the club's admins can do this")
    return level  # type: ignore[return-value]


def _admin_dict(member: Member) -> dict:
    user = member.user
    return {
        "user_id": member.user_id,
        "member_id": member.id,
        "name": user.name if user else "",
        "email": user.email if user else "",
        "level": _admin_level(member),
    }


def _club_or_404(tenant_id: int) -> Tenant:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None or tenant.deleted_at is not None:
        raise_error(404, "NOT_FOUND", "Club not found")
    return tenant  # type: ignore[return-value]


@tenant_admin_bp.route("/tenants/<int:tenant_id>/admins", methods=["GET"])
@jwt_required()
def list_club_admins(tenant_id: int):
    """The club's owners and admins, and what the caller may change."""
    from hubra.core.tenant.context import reset_search_path, set_search_path

    tenant = _club_or_404(tenant_id)
    access = _club_admin_access(tenant, _calling_user())
    try:
        set_search_path(tenant.id)
        members = db.session.scalars(
            select(Member).where(Member.archived_at.is_(None)).order_by(Member.id)
        ).all()
        admins = [_admin_dict(m) for m in members if _admin_level(m)]
    finally:
        reset_search_path()
    return jsonify(
        {
            "club": {"id": tenant.id, "slug": tenant.slug, "name": tenant.name},
            "admins": admins,
            "access": access,
            "canManageOwners": access in ("platform", "owner"),
        }
    ), 200


@tenant_admin_bp.route("/tenants/<int:tenant_id>/admins", methods=["POST"])
@jwt_required()
def add_club_admin(tenant_id: int):
    """Make an existing account an admin (or owner) of the club.

    Body: ``{"email": str, "level": "admin" | "owner"}``. Someone who isn't
    a member yet becomes one first.
    """
    from hubra.core.tenant.context import reset_search_path, set_search_path

    tenant = _club_or_404(tenant_id)
    caller = _calling_user()
    access = _club_admin_access(tenant, caller)

    body = request.get_json(silent=True) or {}
    email = str(body.get("email") or "").strip().lower()
    level = body.get("level") or "admin"
    if not email:
        raise_error(400, "VALIDATION_ERROR", "email is required")
    if level not in ("admin", "owner"):
        raise_error(400, "VALIDATION_ERROR", "level must be 'admin' or 'owner'")
    if level == "owner" and access == "admin":
        raise_error(403, "FORBIDDEN", "Only an owner can name another owner")

    user = db.session.scalar(select(User).where(User.email == email))
    is_member = user is not None and _membership_in(tenant.id, user) == "member"
    if not is_member and access != "platform":
        # A club's own admins name admins among its members: they can't pull
        # any account into the club, nor learn which emails have one.
        raise_error(
            404,
            "NOT_FOUND",
            f"{email} is not a member of this club; they join it first",
        )
    if user is None:
        raise_error(
            404,
            "NOT_FOUND",
            f"No Hubra account for {email}; they need to sign up first",
        )

    from hubra.core.tenant.membership import link_user_to_tenant

    if not is_member:
        _add_user_to_tenant(tenant, user)  # type: ignore[arg-type]
    link_user_to_tenant(user.id, tenant.id)  # type: ignore[union-attr]

    try:
        set_search_path(tenant.id)
        admin_role, owner_role = _club_roles()
        role = owner_role if level == "owner" else admin_role
        if role is None:
            raise_error(409, "CONFLICT", f"This club has no {level} role")
        member = db.session.scalar(
            select(Member).where(Member.user_id == user.id)  # type: ignore[union-attr]
        )
        if member.archived_at is not None:
            raise_error(
                409,
                "ARCHIVED",
                "This member is archived; restore them in the club first",
            )
        if role not in member.roles:
            member.roles = [*member.roles, role]
        db.session.flush()
        invalidate_member_permissions(member.id)
        result = _admin_dict(member)
    finally:
        reset_search_path()

    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant.id,
            actor_id=caller.id,
            action=f"tenant.add_{level}",
            target_type="User",
            target_id=str(user.id),  # type: ignore[union-attr]
            details={"email": email, "by": access},
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    return jsonify({"admin": result}), 201


@tenant_admin_bp.route(
    "/tenants/<int:tenant_id>/admins/<int:user_id>", methods=["DELETE"]
)
@jwt_required()
def remove_club_admin(tenant_id: int, user_id: int):
    """Take the admin and owner roles away; the person stays a member."""
    from hubra.core.tenant.context import reset_search_path, set_search_path

    tenant = _club_or_404(tenant_id)
    caller = _calling_user()
    access = _club_admin_access(tenant, caller)

    try:
        set_search_path(tenant.id)
        member = db.session.scalar(select(Member).where(Member.user_id == user_id))
        level = _admin_level(member)
        if level is None:
            raise_error(404, "NOT_FOUND", "Not an admin of this club")
        if level == "owner":
            if access == "admin":
                raise_error(403, "FORBIDDEN", "Only an owner can remove an owner")
            owners = [
                m
                for m in db.session.scalars(
                    select(Member).where(Member.archived_at.is_(None))
                ).all()
                if _admin_level(m) == "owner"
            ]
            if len(owners) <= 1:
                raise_error(409, "LAST_OWNER", "A club needs at least one owner")
        member.roles = [  # type: ignore[union-attr]
            r
            for r in member.roles  # type: ignore[union-attr]
            if not (r.is_admin or r.is_owner)
        ]
        db.session.flush()
        invalidate_member_permissions(member.id)  # type: ignore[union-attr]
    finally:
        reset_search_path()

    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant.id,
            actor_id=caller.id,
            action=f"tenant.remove_{level}",
            target_type="User",
            target_id=str(user_id),
            details={"by": access},
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    return "", 204


# ── Global RBAC management ───────────────────────────────────────────────────


@tenant_admin_bp.route("/global-roles", methods=["GET"])
@require_global_permission("roles.manage")
def list_global_roles():
    """List all global roles with their permissions."""
    from hubra.core.models.global_role import (
        GlobalRole,
        GlobalRolePermission,
        GlobalPermission,
    )

    roles = db.session.scalars(select(GlobalRole).order_by(GlobalRole.id)).all()
    result = []
    for role in roles:
        perms = (
            db.session.execute(
                select(GlobalPermission.key)
                .join(
                    GlobalRolePermission,
                    GlobalRolePermission.permission_id == GlobalPermission.id,
                )
                .where(GlobalRolePermission.role_id == role.id)
            )
            .scalars()
            .all()
        )
        result.append(
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system,
                "permissions": sorted(perms),
            }
        )
    return jsonify({"roles": result}), 200


def _global_role_keys(role_id: int) -> set[str]:
    """The platform permission keys a platform role grants."""
    from hubra.core.models.global_role import GlobalPermission, GlobalRolePermission

    return set(
        db.session.execute(
            select(GlobalPermission.key)
            .join(
                GlobalRolePermission,
                GlobalRolePermission.permission_id == GlobalPermission.id,
            )
            .where(GlobalRolePermission.role_id == role_id)
        ).scalars()
    )


def _audit_global_role(action: str, target_type: str, target_id, details: dict) -> None:
    """Record a platform role change (who may run the platform)."""
    from flask import g

    actor = getattr(g, "system_user", None)
    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=getattr(actor, "id", None),
            action=f"global_role.{action}",
            target_type=target_type,
            target_id=str(target_id),
            details=details,
            ip_address=request.remote_addr,
        )
    )


@tenant_admin_bp.route("/global-roles", methods=["POST"])
@require_global_permission("roles.manage")
def create_global_role():
    """Create a custom global role."""
    from hubra.core.models.global_role import GlobalRole

    body = request.get_json(silent=True) or {}
    name = _body_text(body, "name")
    description = _body_text(body, "description") or None
    permission_keys = _body_keys(body, "permissions") or []

    if not name:
        raise_error(400, "VALIDATION_ERROR", "name is required")
    check_global_grant(permission_keys)

    existing = db.session.scalar(select(GlobalRole).where(GlobalRole.name == name))
    if existing is not None:
        raise_error(409, "CONFLICT", "A role with this name already exists")

    role = GlobalRole(name=name, description=description, is_system=False)
    db.session.add(role)
    db.session.flush()

    from hubra.core.models.global_role import GlobalPermission, GlobalRolePermission

    for key in permission_keys:
        perm = db.session.scalar(
            select(GlobalPermission).where(GlobalPermission.key == key)
        )
        if perm:
            db.session.add(GlobalRolePermission(role_id=role.id, permission_id=perm.id))

    _audit_global_role(
        "create", "GlobalRole", role.id, {"name": name, "permissions": permission_keys}
    )
    db.session.commit()
    return jsonify(
        {
            "role": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": False,
                "permissions": sorted(permission_keys),
            }
        }
    ), 201


@tenant_admin_bp.route("/global-roles/<int:role_id>", methods=["PATCH"])
@require_global_permission("roles.manage")
def update_global_role(role_id: int):
    """Update a global role's permissions."""
    from hubra.core.models.global_role import (
        GlobalRole,
        GlobalRolePermission,
        GlobalPermission,
    )

    role = db.session.get(GlobalRole, role_id)
    if role is None:
        raise_error(404, "NOT_FOUND", "Role not found")

    body = request.get_json(silent=True) or {}
    permission_keys = _body_keys(body, "permissions")
    description = body.get("description")

    if description is not None:
        role.description = _body_text(body, "description") or None

    if permission_keys is not None:
        # Only what is added must be the actor's own; a role keeps rights the
        # actor lacks when its form is sent back unchanged.
        check_global_grant(set(permission_keys) - _global_role_keys(role.id))
        # Replace all permissions
        db.session.query(GlobalRolePermission).filter(
            GlobalRolePermission.role_id == role_id
        ).delete()
        for key in permission_keys:
            perm = db.session.scalar(
                select(GlobalPermission).where(GlobalPermission.key == key)
            )
            if perm:
                db.session.add(
                    GlobalRolePermission(role_id=role.id, permission_id=perm.id)
                )

    _audit_global_role(
        "update",
        "GlobalRole",
        role.id,
        {"name": role.name, "permissions": permission_keys},
    )
    db.session.commit()
    perms = sorted(
        db.session.execute(
            select(GlobalPermission.key)
            .join(
                GlobalRolePermission,
                GlobalRolePermission.permission_id == GlobalPermission.id,
            )
            .where(GlobalRolePermission.role_id == role.id)
        )
        .scalars()
        .all()
    )
    return jsonify(
        {
            "role": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system,
                "permissions": perms,
            }
        }
    ), 200


@tenant_admin_bp.route("/global-permissions", methods=["GET"])
@require_global_permission("roles.manage")
def list_global_permissions():
    """List all available global permissions."""
    from hubra.core.models.global_role import GlobalPermission

    perms = db.session.scalars(
        select(GlobalPermission).order_by(GlobalPermission.key)
    ).all()
    return jsonify(
        {
            "permissions": [
                {
                    "id": p.id,
                    "key": p.key,
                    "display_name": p.display_name,
                    "description": p.description,
                }
                for p in perms
            ]
        }
    ), 200


@tenant_admin_bp.route("/users/<int:user_id>/roles", methods=["GET"])
@require_global_permission("roles.manage")
def list_user_global_roles(user_id: int):
    """List a user's global role assignments."""
    from hubra.core.models.global_role import GlobalRole, UserGlobalRole

    user = db.session.get(User, user_id)
    if user is None:
        raise_error(404, "NOT_FOUND", "User not found")

    roles = (
        db.session.execute(
            select(GlobalRole)
            .join(UserGlobalRole, UserGlobalRole.role_id == GlobalRole.id)
            .where(UserGlobalRole.user_id == user_id)
        )
        .scalars()
        .all()
    )

    return jsonify(
        {
            "user_id": user_id,
            "email": user.email,
            "roles": [{"id": r.id, "name": r.name} for r in roles],
        }
    ), 200


@tenant_admin_bp.route("/users/<int:user_id>/roles", methods=["POST"])
@require_global_permission("roles.manage")
def assign_user_global_role(user_id: int):
    """Assign a global role to a user."""
    from hubra.core.models.global_role import GlobalRole, UserGlobalRole

    user = db.session.get(User, user_id)
    if user is None:
        raise_error(404, "NOT_FOUND", "User not found")

    body = request.get_json(silent=True) or {}
    role_id = _body_id(body, "role_id")
    if not role_id:
        raise_error(400, "VALIDATION_ERROR", "role_id is required")

    role = db.session.get(GlobalRole, role_id)
    if role is None:
        raise_error(404, "NOT_FOUND", "Role not found")

    check_global_grant(_global_role_keys(role.id))

    existing = db.session.scalar(
        select(UserGlobalRole).where(
            UserGlobalRole.user_id == user_id,
            UserGlobalRole.role_id == role.id,
        )
    )
    if existing is not None:
        raise_error(409, "CONFLICT", "User already has this role")

    db.session.add(UserGlobalRole(user_id=user_id, role_id=role.id))
    _audit_global_role(
        "assign", "User", user_id, {"email": user.email, "role": role.name}
    )
    db.session.commit()
    return jsonify(
        {"user_id": user_id, "role_id": role.id, "role_name": role.name}
    ), 201


@tenant_admin_bp.route("/users/<int:user_id>/roles/<int:role_id>", methods=["DELETE"])
@require_global_permission("roles.manage")
def remove_user_global_role(user_id: int, role_id: int):
    """Remove a global role from a user."""
    from hubra.core.models.global_role import UserGlobalRole

    link = db.session.scalar(
        select(UserGlobalRole).where(
            UserGlobalRole.user_id == user_id,
            UserGlobalRole.role_id == role_id,
        )
    )
    if link is None:
        raise_error(404, "NOT_FOUND", "Role assignment not found")
    # Taking a role away needs its rights too, so staff cannot strip those
    # with more reach than themselves.
    check_global_grant(_global_role_keys(role_id))

    db.session.delete(link)
    _audit_global_role("remove", "User", user_id, {"role_id": role_id})
    db.session.commit()
    return jsonify({"ok": True}), 200


@tenant_admin_bp.route("/users/search", methods=["GET"])
@require_global_permission("roles.manage")
def search_users():
    """Search users by email for role assignment."""
    query = (request.args.get("q") or "").strip().lower()
    if len(query) < 2:
        return jsonify({"users": []}), 200

    users = db.session.scalars(
        select(User).where(User.email.ilike(f"%{query}%")).limit(20)
    ).all()
    return jsonify(
        {"users": [{"id": u.id, "email": u.email, "name": u.name} for u in users]}
    ), 200


# ── Platform audit log ──────────────────────────────────────────────────────


def _page_args() -> tuple[int, int]:
    """``page`` (from 1) and ``per_page`` (1–100) from the query string;
    anything that is not a number falls back to the default."""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        per_page = min(max(1, int(request.args.get("per_page", 25))), 100)
    except ValueError:
        per_page = 25
    return page, per_page


@tenant_admin_bp.route("/audit", methods=["GET"])
@require_global_permission("audit.read")
def list_global_audit():
    """List platform-wide audit entries with pagination and filters."""
    page, per_page = _page_args()

    query = select(GlobalAuditEntry).order_by(
        GlobalAuditEntry.time.desc(), GlobalAuditEntry.id.desc()
    )

    tenant_id = request.args.get("tenant_id")
    if tenant_id:
        if not tenant_id.isdigit():
            raise_error(400, "VALIDATION_ERROR", "tenant_id must be a number")
        query = query.where(GlobalAuditEntry.tenant_id == int(tenant_id))

    action = request.args.get("action")
    if action:
        from hubra.api.utils import escape_like

        query = query.where(
            GlobalAuditEntry.action.ilike(f"%{escape_like(action)}%", escape="\\")
        )

    # Count what the filters leave, not the whole table.
    total = db.session.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    entries = list(
        db.session.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()
    )

    return jsonify(
        {
            "entries": [
                {
                    "id": e.id,
                    "tenant_id": e.tenant_id,
                    "actor_id": e.actor_id,
                    "action": e.action,
                    "target_type": e.target_type,
                    "target_id": e.target_id,
                    "details": e.details,
                    "ip_address": e.ip_address,
                    "time": e.time.isoformat() if e.time else None,
                }
                for e in entries
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    ), 200


# ── Platform metrics ────────────────────────────────────────────────────────


@tenant_admin_bp.route("/metrics", methods=["GET"])
@require_global_permission("audit.read")
def platform_metrics():
    """Aggregate platform metrics from Redis counters."""
    from hubra.api.metrics import get_metrics_summary

    summary = get_metrics_summary()
    return jsonify(summary), 200


# ── User management ─────────────────────────────────────────────────────────


@tenant_admin_bp.route("/users", methods=["GET"])
@require_global_permission("users.read")
def list_users():
    """List all users with pagination and search."""
    page, per_page = _page_args()
    search = (request.args.get("search") or "").strip().lower()

    query = select(User).order_by(User.id.desc())
    if search:
        from hubra.api.utils import escape_like

        query = query.where(User.email.ilike(f"%{escape_like(search)}%", escape="\\"))

    total = db.session.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    users = list(
        db.session.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()
    )

    return jsonify(
        {
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "name": u.name,
                    "is_superadmin": u.is_superadmin,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    ), 200


@tenant_admin_bp.route("/users/<int:user_id>", methods=["GET"])
@require_global_permission("users.read")
def get_user_detail(user_id: int):
    """Get a user's details including tenant memberships."""
    user = db.session.get(User, user_id)
    if user is None:
        raise_error(404, "NOT_FOUND", f"User {user_id} not found")

    from hubra.core.models.user_tenant import UserTenant

    memberships = list(
        db.session.scalars(
            select(UserTenant).where(UserTenant.user_id == user.id)
        ).all()
    )

    tenant_ids = [m.tenant_id for m in memberships]
    tenants = (
        list(db.session.scalars(select(Tenant).where(Tenant.id.in_(tenant_ids))).all())
        if tenant_ids
        else []
    )

    return jsonify(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_superadmin": user.is_superadmin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "tenants": [
                {
                    "tenant_id": t.id,
                    "slug": t.slug,
                    "name": t.name,
                    "status": t.status,
                    "is_owner": next(
                        (m.is_owner for m in memberships if m.tenant_id == t.id),
                        False,
                    ),
                }
                for t in tenants
            ],
        }
    ), 200


# ── Helpers ─────────────────────────────────────────────────────────────────


def _find_member_in_tenant(tenant_id: int, user_id: int | None) -> Member | None:
    """Find a member in a tenant schema.

    On PostgreSQL, sets the search_path to the tenant schema.
    On SQLite (tests), falls back to a simple query since all tables
    are in the single schema.
    """
    from hubra.core.tenant.context import set_search_path, reset_search_path

    try:
        set_search_path(tenant_id)
        if user_id is not None:
            member = db.session.scalar(
                select(Member).where(
                    Member.user_id == user_id,
                    Member.archived_at.is_(None),
                )
            )
        else:
            member = db.session.scalar(
                select(Member)
                .where(Member.archived_at.is_(None))
                .order_by(Member.id)
                .limit(1)
            )
    except Exception:
        member = None
    finally:
        try:
            reset_search_path()
        except Exception:
            pass
    return member


def _tenant_to_dict(tenant) -> dict:
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "status": tenant.status,
        "settings": tenant.settings or {},
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
        "deleted_at": tenant.deleted_at.isoformat() if tenant.deleted_at else None,
    }


def _member_to_dict(member) -> dict:
    user = member.user
    return {
        "id": member.id,
        "user_id": member.user_id,
        "name": user.name if user else "",
        "email": user.email if user else "",
        "status": member.status,
        "roles": [r.name for r in (member.roles or [])],
    }


# ── Helpers (existing) ──────────────────────────────────────────────────────
