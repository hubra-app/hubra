"""Delivering the contract outbox (hubra.core.contracts.outbox).

``deliver`` runs one row in its club (the ``tenant_id`` header), on the
default queue: club work, never platform work. ``sweep`` runs every minute
from beat and sends again whatever is due.
"""

from __future__ import annotations

from hubra.core.tasks import celery_app


@celery_app.task(
    name="hubra.core.tasks.contract_tasks.deliver",
    ignore_result=True,
)
def deliver(uid: str) -> str:
    from hubra.core.contracts import outbox

    return outbox.deliver(uid)


@celery_app.task(
    name="hubra.core.tasks.contract_tasks.sweep",
    ignore_result=True,
)
def sweep() -> dict:
    from hubra.core.contracts import outbox

    return outbox.sweep()
