"""Outgoing webhooks of a club (docs/webhooks.md), for its admins.

``/api/v1/app/webhooks``; never with an API token (a token must not be
able to send the club's data to an address of its choosing).

* ``GET  /``                 the club's webhooks and the event names
* ``POST /``                 add one; the answer holds the secret, once
* ``PATCH /<id>``            name, url, events, active
* ``DELETE /<id>``           remove it
* ``POST /<id>/secret``      a new secret (the old one stops at once)
* ``POST /<id>/test``        send a ``ping`` now and answer how it went
* ``GET  /<id>/deliveries``  the latest deliveries
* ``POST /deliveries/<id>/retry`` send a failed delivery again
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from hubra.core import webhooks
from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.models.webhook import Webhook, WebhookDelivery
from hubra.core.permissions import require_admin
from hubra.core.utils import log_audit

webhooks_bp = Blueprint("webhooks_bp", __name__)


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _dump(hook: Webhook, secret: str | None = None) -> dict:
    out = {
        "id": hook.id,
        "name": hook.name,
        "url": hook.url,
        "events": list(hook.events or []),
        "active": hook.active,
        "failures": hook.failures,
        "disabledReason": hook.disabled_reason,
        "createdAt": hook.created_at.isoformat(),
        "lastDeliveryAt": hook.last_delivery_at.isoformat()
        if hook.last_delivery_at
        else None,
    }
    if secret is not None:
        out["secret"] = secret
    return out


def _dump_delivery(d: WebhookDelivery) -> dict:
    return {
        "id": d.id,
        "uid": d.uid,
        "event": d.event,
        "status": d.status,
        "attempts": d.attempts,
        "responseStatus": d.response_status,
        "error": d.error,
        "durationMs": d.duration_ms,
        "createdAt": d.created_at.isoformat(),
        "lastAttemptAt": d.last_attempt_at.isoformat() if d.last_attempt_at else None,
    }


def _audit(action: str, hook: Webhook) -> None:
    actor = get_current_member()
    log_audit(
        actor_id=actor.id if actor else None,
        action=action,
        target_type="Webhook",
        target_id=hook.id,
        target_label=hook.name,
    )


def _fields(data: dict, hook: Webhook | None):
    """Validated name, url and events from *data* (None: not given)."""
    name = data.get("name")
    if name is not None or hook is None:
        name = str(name or "").strip()[:100]
        if not name:
            return None, api_error("VALIDATION_ERROR", "A name is required", 400)
    url = data.get("url")
    if url is not None or hook is None:
        try:
            url = webhooks.check_url(str(url or ""))
        except webhooks.WebhookUrlError as exc:
            return None, api_error("WEBHOOK_URL", str(exc), 400)
    events = data.get("events")
    if events is not None or hook is None:
        if not isinstance(events, list) or not events:
            return None, api_error("VALIDATION_ERROR", "Pick at least one event", 400)
        unknown = sorted(set(map(str, events)) - set(webhooks.EVENTS))
        if unknown:
            return None, api_error(
                "VALIDATION_ERROR", f"Unknown events: {', '.join(unknown)}", 400
            )
        events = [e for e in webhooks.EVENTS if e in events]
    return {"name": name, "url": url, "events": events}, None


def _get(webhook_id: int) -> Webhook | None:
    return db.session.get(Webhook, webhook_id)


@webhooks_bp.get("/")
@require_admin
def list_webhooks():
    hooks = db.session.scalars(select(Webhook).order_by(Webhook.id)).all()
    return jsonify(
        {
            "items": [_dump(h) for h in hooks],
            "events": list(webhooks.EVENTS),
            "max": webhooks.MAX_WEBHOOKS,
        }
    ), 200


@webhooks_bp.post("/")
@require_admin
def create_webhook():
    count = db.session.scalar(select(func.count(Webhook.id))) or 0
    if count >= webhooks.MAX_WEBHOOKS:
        return api_error(
            "LIMIT_REACHED", f"At most {webhooks.MAX_WEBHOOKS} webhooks per club", 409
        )
    fields, error = _fields(_body(), None)
    if error is not None:
        return error
    secret = webhooks.new_secret()
    actor = get_current_member()
    hook = Webhook(
        **fields,
        secret=webhooks.seal(secret),
        created_by=actor.id if actor else None,
    )
    db.session.add(hook)
    db.session.flush()
    _audit("create_webhook", hook)
    db.session.commit()
    return jsonify(_dump(hook, secret)), 201


@webhooks_bp.patch("/<int:webhook_id>")
@require_admin
def update_webhook(webhook_id: int):
    hook = _get(webhook_id)
    if hook is None:
        return api_error("NOT_FOUND", "No such webhook", 404)
    data = _body()
    fields, error = _fields(data, hook)
    if error is not None:
        return error
    for key, value in fields.items():
        if value is not None:
            setattr(hook, key, value)
    if "active" in data:
        hook.active = bool(data["active"])
        if hook.active:
            hook.failures = 0
            hook.disabled_reason = None
    _audit("update_webhook", hook)
    db.session.commit()
    return jsonify(_dump(hook)), 200


@webhooks_bp.delete("/<int:webhook_id>")
@require_admin
def delete_webhook(webhook_id: int):
    hook = _get(webhook_id)
    if hook is None:
        return api_error("NOT_FOUND", "No such webhook", 404)
    _audit("delete_webhook", hook)
    db.session.query(WebhookDelivery).filter_by(webhook_id=hook.id).delete()
    db.session.delete(hook)
    db.session.commit()
    return "", 204


@webhooks_bp.post("/<int:webhook_id>/secret")
@require_admin
def roll_secret(webhook_id: int):
    hook = _get(webhook_id)
    if hook is None:
        return api_error("NOT_FOUND", "No such webhook", 404)
    secret = webhooks.new_secret()
    hook.secret = webhooks.seal(secret)
    _audit("roll_webhook_secret", hook)
    db.session.commit()
    return jsonify(_dump(hook, secret)), 200


@webhooks_bp.post("/<int:webhook_id>/test")
@require_admin
def test_webhook(webhook_id: int):
    hook = _get(webhook_id)
    if hook is None:
        return api_error("NOT_FOUND", "No such webhook", 404)
    delivery = webhooks.send(hook, webhooks.PING, {"webhookId": hook.id})
    return jsonify(_dump_delivery(delivery)), 200


@webhooks_bp.get("/<int:webhook_id>/deliveries")
@require_admin
def list_deliveries(webhook_id: int):
    if _get(webhook_id) is None:
        return api_error("NOT_FOUND", "No such webhook", 404)
    rows = db.session.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.id.desc())
        .limit(webhooks.KEEP_DELIVERIES)
    ).all()
    return jsonify({"items": [_dump_delivery(d) for d in rows]}), 200


@webhooks_bp.post("/deliveries/<int:delivery_id>/retry")
@require_admin
def retry(delivery_id: int):
    delivery = db.session.get(WebhookDelivery, delivery_id)
    if delivery is None:
        return api_error("NOT_FOUND", "No such delivery", 404)
    if delivery.status == "delivered":
        return api_error("ALREADY_DELIVERED", "This delivery arrived", 409)
    delivery.status = "pending"
    webhooks.attempt(delivery)
    if delivery.status == "pending":
        delivery.status = "failed"  # a manual retry doesn't queue more
    db.session.commit()
    return jsonify(_dump_delivery(delivery)), 200
