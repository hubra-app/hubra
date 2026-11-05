"""Retrying a failed webhook delivery (hubra.core.webhooks)."""

from __future__ import annotations

from hubra.core.extensions import db
from hubra.core.tasks import celery_app


@celery_app.task(
    name="hubra.core.tasks.webhook_tasks.retry_delivery",
    ignore_result=True,
)
def retry_delivery(delivery_id: int) -> bool:
    """Try a pending delivery again; schedules the next try if it fails."""
    from hubra.core import webhooks
    from hubra.core.models.webhook import Webhook, WebhookDelivery

    delivery = db.session.get(WebhookDelivery, delivery_id)
    if delivery is None or delivery.status != "pending":
        return False
    hook = db.session.get(Webhook, delivery.webhook_id)
    if hook is None or not hook.active:
        delivery.status = "failed"
        delivery.error = "The webhook is switched off"
        db.session.commit()
        return False
    ok = webhooks.attempt(delivery)
    db.session.commit()
    webhooks._schedule_retry(delivery)
    return ok
