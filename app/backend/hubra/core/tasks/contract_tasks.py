"""Delivering the contract outbox (hubra.core.contracts.outbox).

``deliver`` runs one row in its club (the ``tenant_id`` header), on the
default queue: club work, never platform work. ``sweep`` runs every minute
from beat and sends again whatever is due.
"""

from __future__ import annotations

from hubra.core.tasks import celery_app

# A run must end inside the outbox lease (outbox.LEASE, 5 min), so another
# worker never claims a row while its first run is still going.
DELIVER_SOFT_LIMIT = 240
DELIVER_HARD_LIMIT = 270


@celery_app.task(
    name="hubra.core.tasks.contract_tasks.deliver",
    ignore_result=True,
    # Inside the outbox lease (5 min), so a row is never claimed again while
    # its first run is still going.
    soft_time_limit=DELIVER_SOFT_LIMIT,
    time_limit=DELIVER_HARD_LIMIT,
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
