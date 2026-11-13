"""Finance jobs of the app area: collected invoices for open items."""

from __future__ import annotations

from datetime import date

from hubra.api.finance import open_items
from hubra.core.extensions import db
from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app


@celery_app.task(
    name="hubra.api.finance.tasks.collect_open_items_task",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def collect_open_items_task(self) -> dict:
    """Collected invoices in every club with finance on."""
    return _collect_open_items()


@per_tenant_job("finance")
def _collect_open_items(today: date | None = None) -> dict:
    """On the first of the month (or quarter), one invoice per member for
    their open items (finance setting collect_items; open_items.py)."""
    today = today or date.today()
    if not open_items.is_billing_day(today, open_items.settings()["cycle"]):
        return {"invoices": 0}
    invoices = open_items.bill()
    db.session.commit()
    return {"invoices": len(invoices)}
