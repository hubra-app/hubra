"""Hourly job: read every club's Stripe subscription again, so a missed
webhook only delays a club's billing status (``hubra.core.billing``)."""

from __future__ import annotations

from hubra.core.tasks import celery_app


@celery_app.task(name="hubra.core.tasks.billing_tasks.reconcile_billing")
def reconcile_billing() -> dict:
    from hubra.core.billing import service

    return service.reconcile()
