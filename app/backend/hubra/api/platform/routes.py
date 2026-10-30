"""Platform settings for the manager portal.

``platform_bp`` (``/api/v1/manager/platform``): instance-wide settings such as the outbound
mail relay, which need the global permission ``platform.settings``, and the
diagnostics of the whole instance (system health, the shared mail server,
the API permission table), which need ``platform.diagnostics`` to look at
and ``platform.settings`` to change anything.
"""

from __future__ import annotations

import re
import time

from flask import Blueprint, g, jsonify, request

from hubra.api.permissions import require_global_permission
from hubra.core.errors import api_error
from hubra.core.extensions import db, limiter
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.services import email, mail_server, platform_settings
from hubra.core.services.platform_settings import PlatformSettingError

platform_bp = Blueprint("platform_bp", __name__)

_PERM = "platform.settings"
_DIAGNOSTICS = "platform.diagnostics"
_STALE_THRESHOLD = 60  # seconds — 3× the 20s beat interval
_OBJECTID_RE = re.compile(r"^[0-9a-fA-F]{24}$")


def _audit(action: str, target_type: str, target_id: str, details: dict | None = None):
    actor = getattr(g, "system_user", None)
    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=getattr(actor, "id", None),
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            ip_address=request.remote_addr,
        )
    )


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
    """Send a test mail from the system sender through the relay, or with
    ``via: "fallback"`` through the fallback relay, never both."""
    body = request.get_json(silent=True) or {}
    to = str(body.get("to") or "").strip()
    if "@" not in to:
        return api_error("VALIDATION_ERROR", "'to' must be an email address", 400)
    via = str(body.get("via") or "relay")
    if via not in ("relay", "fallback"):
        return api_error("VALIDATION_ERROR", "'via' must be relay or fallback", 400)

    relay = platform_settings.relay()
    host = (
        relay.host
        if via == "relay"
        else getattr(platform_settings.fallback_relay(), "host", "")
    )
    if not host or not relay.sender_email:
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
            via=via,
        )
    except email.EmailDeliveryError as exc:
        return api_error("SMTP_ERROR", f"The relay refused the mail: {exc}", 502)
    return jsonify({"ok": True, "to": to}), 200


# ── Diagnostics ───────────────────────────────────────────────────────────────


@platform_bp.get("/health")
@require_global_permission(_DIAGNOSTICS)
@limiter.exempt
def health_detailed():
    """Every service check with latencies, run now, plus the version.

    ``stale`` is true when the beat task that caches the public ``/health``
    status has not run for a while.  Always 200: this is for people, and the
    overall state is in ``status`` (load balancers use the public ``/health``).
    """
    from hubra.api.health.cache import HealthCache
    from hubra.api.health.services import HealthService
    from hubra.api.version.services import VersionService

    payload = HealthService.run_all_checks()
    payload["version"] = VersionService.get_version()

    cached = HealthCache.get()
    if cached is not None and "checked_at" in cached:
        payload["stale"] = time.time() - cached["checked_at"] > _STALE_THRESHOLD
        payload["checked_at"] = cached["checked_at"]
    else:
        payload["stale"] = True
    return jsonify(payload), 200


@platform_bp.get("/permissions")
@require_global_permission(_DIAGNOSTICS)
def list_permissions():
    """Every club API endpoint that a club permission guards, by path and method."""
    from hubra.api.system.services import SystemService

    return jsonify(SystemService.list_permissions()), 200


@platform_bp.get("/mail-server")
@require_global_permission(_DIAGNOSTICS)
def mail_server_live():
    """Every mailbox and alias on the shared mail server, with its club."""
    return jsonify({"data": mail_server.live()}), 200


@platform_bp.delete("/mail-server/<string:entry_type>/<string:entry_id>")
@require_global_permission(_PERM)
def mail_server_delete_orphan(entry_type: str, entry_id: str):
    """Delete a mailbox or alias that no club manages."""
    if entry_type not in ("mailbox", "alias"):
        return api_error("VALIDATION_ERROR", "Type must be 'mailbox' or 'alias'", 400)
    if not _OBJECTID_RE.match(entry_id):
        return api_error("VALIDATION_ERROR", f"Invalid ID format: {entry_id!r}", 400)

    label = mail_server.delete_orphan(entry_type, entry_id)
    _audit(
        f"platform.mail_server.delete_{entry_type}",
        f"wildduck_{entry_type}",
        entry_id,
        {"address": label},
    )
    db.session.commit()
    return jsonify({"ok": True, "type": entry_type, "id": entry_id}), 200


@platform_bp.post("/mail-server/reconcile")
@require_global_permission(_PERM)
@limiter.limit("10 per hour")
def mail_server_reconcile():
    """Reconcile every club's addresses with the mail server now."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    reconcile_mail.delay()
    return jsonify({"ok": True, "task": "reconcile_mail"}), 202


# ── Translation suggestions from clubs ──────────────────────────────────────


@platform_bp.get("/translation-requests")
@require_global_permission(_PERM)
def list_translation_requests():
    """Clubs' suggestions; ``?status=pending|accepted|rejected`` (all if left out)."""
    from hubra.api.i18n import requests as suggestions

    status = request.args.get("status") or None
    if status and status not in suggestions.STATUSES:
        return api_error("VALIDATION_ERROR", "Unknown status", 400)
    return jsonify(suggestions.listing(status)), 200


@platform_bp.post("/translation-requests/<int:request_id>")
@require_global_permission(_PERM)
def decide_translation_request(request_id: int):
    """Body: ``{"accept": bool, "value"?: str, "note"?: str}``.

    Accepting writes the text (``value`` if the admin reworded it) for every
    club; rejecting keeps the text and tells the club why in ``note``.
    """
    from hubra.api.i18n import requests as suggestions
    from hubra.core.models.translation_request import TranslationRequest

    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("accept"), bool):
        return api_error("VALIDATION_ERROR", "accept must be true or false", 400)
    value = body.get("value")
    note = body.get("note")
    if (value is not None and not isinstance(value, str)) or (
        note is not None and not isinstance(note, str)
    ):
        return api_error("VALIDATION_ERROR", "value and note must be text", 400)
    req = db.session.get(TranslationRequest, request_id)
    if req is None:
        return api_error("NOT_FOUND", "Translation request not found", 404)
    actor = getattr(g, "system_user", None)
    try:
        suggestions.decide(req, body["accept"], getattr(actor, "id", None), value, note)
    except suggestions.RequestError as exc:
        db.session.rollback()
        return api_error("CONFLICT", str(exc), 409)
    _audit(
        "accept_translation_request" if body["accept"] else "reject_translation_request",
        "TranslationRequest",
        str(req.id),
        {"locale": req.locale, "key": req.key, "tenant_id": req.tenant_id},
    )
    db.session.commit()
    return jsonify(req.to_dict()), 200
