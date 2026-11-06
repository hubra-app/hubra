"""Retrying a failed webhook delivery (hubra.core.webhooks).

A failed delivery schedules its next try with a Celery countdown. The
delivery row in the club's database is what counts, though: ``sweep``
(every five minutes) tries every pending delivery whose next try is more
than five minutes overdue, so a retry lost with Redis (a restart, a flush)
still happens. Receivers already get the same ``X-Hubra-Delivery`` id on
every try, should a late countdown and the sweep ever both send.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hubra.core.extensions import db
from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app

# How late a countdown may be before the sweep takes over.
SWEEP_GRACE = timedelta(minutes=5)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def due_at(delivery) -> datetime | None:
    """When *delivery*'s next try is due, or None when it has none left."""
    from hubra.core import webhooks

    if delivery.status != "pending" or not delivery.last_attempt_at:
        return None
    if delivery.attempts > len(webhooks.RETRY_DELAYS):
        return None
    delay = webhooks.RETRY_DELAYS[max(delivery.attempts, 1) - 1]
    return _aware(delivery.last_attempt_at) + timedelta(seconds=delay)


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


@celery_app.task(
    name="hubra.core.tasks.webhook_tasks.sweep",
    ignore_result=True,
)
@per_tenant_job("webhooks")
def sweep() -> dict:
    """Try the pending deliveries whose countdown didn't come."""
    from sqlalchemy import select

    from hubra.core.models.webhook import WebhookDelivery

    now = datetime.now(timezone.utc)
    rows = db.session.scalars(
        select(WebhookDelivery).where(WebhookDelivery.status == "pending")
    ).all()
    late = [r.id for r in rows if (d := due_at(r)) and d + SWEEP_GRACE <= now]
    db.session.commit()
    for delivery_id in late:
        retry_delivery.run(delivery_id)
    return {"retried": len(late)}
