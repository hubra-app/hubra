"""Platform settings for the manager portal.

``platform_bp`` (``/api/v1/manager/platform``, also at
``/api/v2/manager/platform``): instance-wide settings such as the outbound
mail relay.  Everything needs the global permission ``platform.settings``.
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from hubra.api.permissions import require_global_permission
from hubra.core.errors import api_error
from hubra.core.extensions import db, limiter
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.services import email, platform_settings
from hubra.core.services.platform_settings import PlatformSettingError

platform_bp = Blueprint("platform_bp", __name__)

_PERM = "platform.settings"


@platform_bp.get("/settings")
@require_global_permission(_PERM)
def list_settings():
    """Every platform setting with its value and where it comes from."""
    return jsonify({"settings": platform_settings.as_list()}), 200


@platform_bp.patch("/settings")
@require_global_permission(_PERM)
def update_settings():
    """Body: ``{"<key>": "<value>" | null, ...}``.  ``null`` resets to the env default."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body:
        return api_error("VALIDATION_ERROR", "Expected an object of settings", 400)

    actor = getattr(g, "system_user", None)
    try:
        platform_settings.set_many(body, actor_id=getattr(actor, "id", None))
    except PlatformSettingError as exc:
        details = exc.args[0]
        response = jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": "Invalid platform settings",
                "details": details if isinstance(details, dict) else {},
            }
        )
        response.status_code = 400
        return response

    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=getattr(actor, "id", None),
            action="platform.settings.update",
            target_type="platform_setting",
            target_id=",".join(sorted(body)),
            details={
                k: ("***" if platform_settings.spec(k).secret and v else v)
                for k, v in body.items()
            },
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    return jsonify({"settings": platform_settings.as_list()}), 200


@platform_bp.post("/mail/test")
@require_global_permission(_PERM)
@limiter.limit("10 per hour")
def send_test_mail():
    """Send a test mail through the relay from the system sender."""
    body = request.get_json(silent=True) or {}
    to = str(body.get("to") or "").strip()
    if "@" not in to:
        return api_error("VALIDATION_ERROR", "'to' must be an email address", 400)

    relay = platform_settings.relay()
    if not relay.host or not relay.sender_email:
        return api_error(
            "SERVICE_UNAVAILABLE",
            "Set the relay host and the system sender address first",
            503,
        )
    try:
        email._send_via_smtp(
            to,
            to,
            relay.sender_email,
            relay.sender_name,
            "Hubra test mail",
            "<p>This is a test mail from your Hubra platform relay.</p>",
            "This is a test mail from your Hubra platform relay.",
        )
    except email.EmailDeliveryError as exc:
        return api_error("SMTP_ERROR", f"The relay refused the mail: {exc}", 502)
    return jsonify({"ok": True, "to": to}), 200
