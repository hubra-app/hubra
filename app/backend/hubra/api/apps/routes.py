"""Connected apps: /api/v1/apps (Einstellungen > Verbundene Apps).

Connecting is a round trip: the admin starts it here, signs in on the
outside service, comes back to ``/callback/<provider>`` (no Hubra sign-in
needed, the signed state and a browser cookie carry who started it), and
then confirms the connection in the club app. Only a confirmed connection
does anything.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, make_response, redirect, request
from urllib.parse import urlencode

from hubra.api.auth.helpers import get_current_member
from hubra.api.permissions import permission_required, refuse_during_impersonation
from hubra.api.utils import log_audit
from hubra.core import apps
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db
from hubra.core.modules import is_enabled
from hubra.core.tenant.context import current_tenant

apps_bp = Blueprint("apps_bp", __name__)


def _tenant_id() -> int:
    tenant = current_tenant()
    if tenant is None:
        raise_error(
            400, "NO_TENANT", "Connected apps belong to a club; pick a club first"
        )
    return tenant.id


def _member_name(member) -> str:
    return f"{member.first_name} {member.last_name}".strip()


def _connection_or_404(connection_id: int):
    conn = apps.get(connection_id, _tenant_id())
    if conn is None or conn.status == "revoked":
        raise_error(404, "NOT_FOUND", "Connection not found")
    return conn


def _provider_or_404(code: str):
    found = apps.provider(code)
    if found is None or not is_enabled(found[0].code):
        raise_error(404, "NOT_FOUND", f"No app '{code}' for this club")
    return found


def _audit(action: str, conn, extra: str = "") -> None:
    label = f"{conn.label or conn.provider}"
    if extra:
        label = f"{label} ({extra})"
    log_audit(get_current_member().id, action, "connected_app", conn.id, label)


@apps_bp.get("/")
@permission_required("apps", "manage", "Manage connected apps")
def list_apps():
    tid = _tenant_id()
    providers = []
    for module, app in apps.providers(tid):
        data = app.to_dict()
        data["module"] = module.code
        data["unavailable"] = apps.unavailable(app)
        providers.append(data)
    return jsonify(
        {
            "providers": providers,
            "connections": [apps.serialize(c) for c in apps.listed(tid)],
        }
    ), 200


@apps_bp.post("/<string:code>/connect")
@permission_required("apps", "manage", "Manage connected apps")
def start_connect(code: str):
    """Where to send the admin to sign in on the outside service."""
    refuse_during_impersonation()
    _module, app = _provider_or_404(code)
    reason = apps.unavailable(app)
    if reason:
        return api_error("APP_UNAVAILABLE", reason, 409)
    body = request.get_json(silent=True) or {}
    known = [s.key for s in app.scopes]
    scopes = body.get("scopes", known)
    if not isinstance(scopes, list) or any(s not in known for s in scopes):
        return api_error("VALIDATION_ERROR", "Unknown scope", 400)
    member = get_current_member()
    state, nonce = apps.make_state(code, _tenant_id(), member.id, scopes)
    redirect_uri = _callback_url(code)
    url = apps.hook(app, "authorize_url")(state, redirect_uri, scopes)
    response = make_response(jsonify({"url": url}), 200)
    response.set_cookie(
        apps.NONCE_COOKIE,
        nonce,
        max_age=apps.STATE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=current_app.config.get("JWT_COOKIE_SECURE", False),
    )
    return response


def _callback_url(code: str) -> str:
    base = current_app.config.get("API_PUBLIC_URL") or request.host_url
    return f"{base.rstrip('/')}/api/v1/apps/callback/{code}"


def _back_to_club(tenant, **params):
    """Send the browser back to the club's Verbundene Apps tab."""
    from hubra.core.services.email import _get_base_url

    base = _get_base_url()
    path = f"/{tenant.slug}/app/settings/apps" if tenant is not None else "/"
    query = f"?{urlencode(params)}" if params else ""
    response = make_response(
        redirect(f"{base}{path}{query}" if base else f"{path}{query}")
    )
    response.delete_cookie(apps.NONCE_COOKIE)
    return response


@apps_bp.get("/callback/<string:code>")
def connect_callback(code: str):
    """The outside service sends the admin back here."""
    from hubra.core.models.member import Member
    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.context import in_club

    data = apps.read_state(
        request.args.get("state", ""), code, request.cookies.get(apps.NONCE_COOKIE)
    )
    if data is None:
        # No club to go back to: expired, tampered, or another browser.
        return _back_to_club(None, app=code, error="expired")
    tenant = db.session.get(Tenant, data["t"])
    if tenant is None or tenant.status != "active":
        return _back_to_club(None, app=code, error="expired")
    if request.args.get("error"):
        return _back_to_club(tenant, app=code, error="cancelled")

    with in_club(tenant):
        found = apps.provider(code)
        if found is None or not is_enabled(found[0].code):
            return _back_to_club(tenant, app=code, error="disabled")
        member = db.session.get(Member, data["m"])
        if member is None or member.archived_at is not None:
            return _back_to_club(tenant, app=code, error="expired")
        try:
            draft = apps.hook(found[1], "complete")(
                request.args.to_dict(), _callback_url(code)
            )
        except apps.AppError as exc:
            current_app.logger.info("connect %s failed: %s", code, exc)
            return _back_to_club(tenant, app=code, error="failed")
        conn = apps.create_pending(
            tenant.id, code, draft, data.get("s") or [], member.id, _member_name(member)
        )
        if apps.taken_elsewhere(conn):
            conn.status = "revoked"
            conn.revoked_by_name = "Already connected to another club"
            db.session.commit()
            return _back_to_club(tenant, app=code, error="taken")
        db.session.commit()
        return _back_to_club(tenant, app=code, confirm=conn.id)


@apps_bp.get("/connections/<int:connection_id>")
@permission_required("apps", "manage", "Manage connected apps")
def get_connection(connection_id: int):
    conn = _connection_or_404(connection_id)
    return jsonify(apps.serialize(conn, with_events=True)), 200


@apps_bp.post("/connections/<int:connection_id>/confirm")
@permission_required("apps", "manage", "Manage connected apps")
def confirm_connection(connection_id: int):
    """The admin's approval: only now does the connection do anything."""
    refuse_during_impersonation()
    conn = _connection_or_404(connection_id)
    if conn.status != "pending":
        return api_error("ALREADY_CONFIRMED", "This connection is already active", 409)
    try:
        apps.confirm(conn)
    except apps.AppError as exc:
        db.session.rollback()
        return api_error("CONNECT_FAILED", str(exc), 409)
    _audit("connect_app", conn, conn.provider)
    db.session.commit()
    return jsonify(apps.serialize(conn, with_events=True)), 200


@apps_bp.patch("/connections/<int:connection_id>")
@permission_required("apps", "manage", "Manage connected apps")
def update_connection(connection_id: int):
    refuse_during_impersonation()
    conn = _connection_or_404(connection_id)
    body = request.get_json(silent=True) or {}
    changed: list[str] = []

    if "label" in body:
        label = str(body["label"] or "").strip()[:200]
        if label != conn.label:
            conn.label = label
            changed.append("label")

    found = apps.provider(conn.provider)
    if "scopes" in body:
        known = [s.key for s in found[1].scopes] if found else []
        scopes = body["scopes"]
        if not isinstance(scopes, list) or any(s not in known for s in scopes):
            return api_error("VALIDATION_ERROR", "Unknown scope", 400)
        if sorted(scopes) != sorted(conn.scopes or []):
            conn.scopes = list(scopes)
            changed.append("scopes")

    if "config" in body:
        if not isinstance(body["config"], dict):
            return api_error("VALIDATION_ERROR", "config must be an object", 400)
        fn = apps.hook(found[1], "update_config") if found else None
        if fn is None:
            return api_error("VALIDATION_ERROR", "This app has no settings", 400)
        try:
            config = fn(conn, body["config"])
        except apps.AppError as exc:
            return api_error("VALIDATION_ERROR", str(exc), 400)
        before = conn.config or {}
        keys = sorted(
            k for k in set(before) | set(config) if before.get(k) != config.get(k)
        )
        if keys:
            conn.config = config
            changed.extend(keys)

    if changed:
        apps.record(conn, "changed", True, ", ".join(changed))
        _audit("update_app", conn, "changed: " + ", ".join(changed))
    db.session.commit()
    return jsonify(apps.serialize(conn, with_events=True)), 200


@apps_bp.post("/connections/<int:connection_id>/test")
@permission_required("apps", "manage", "Manage connected apps")
def test_connection(connection_id: int):
    conn = _connection_or_404(connection_id)
    if conn.status != "active":
        return api_error("NOT_CONFIRMED", "Confirm the connection first", 409)
    found = apps.provider(conn.provider)
    fn = apps.hook(found[1], "test") if found else None
    if fn is None:
        return api_error("VALIDATION_ERROR", "This app has no test", 400)
    try:
        message = fn(conn)
    except apps.AppError as exc:
        apps.record(conn, "test", False, str(exc))
        db.session.commit()
        return api_error("TEST_FAILED", str(exc), 502)
    apps.record(conn, "test", True, message or "")
    db.session.commit()
    return jsonify({"ok": True, "message": message or ""}), 200


@apps_bp.delete("/connections/<int:connection_id>")
@permission_required("apps", "manage", "Manage connected apps")
def disconnect(connection_id: int):
    refuse_during_impersonation()
    conn = _connection_or_404(connection_id)
    member = get_current_member()
    was_active = conn.status == "active"
    apps.revoke(conn, _member_name(member))
    if was_active:
        _audit("disconnect_app", conn, conn.provider)
    db.session.commit()
    return jsonify({"ok": True}), 200
