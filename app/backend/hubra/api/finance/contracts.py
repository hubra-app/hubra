"""What Finance offers other modules through contracts (docs/contracts.md).

- ``finance.billing_period`` (query): the club's billing year around a day.
- ``finance.invoice.set_status`` (action): mark an invoice paid or open
  again, with everything that comes with it (mails, events, the audit log).

Plugins that offer a source for the fee basis do it the other way round:
they offer a query named ``<module>.fee_basis.<source>`` with the shapes
below, and ``fee_basis`` asks it.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class PeriodIn(BaseModel):
    on: date


class Period(BaseModel):
    start: date
    end: date


def billing_period(ctx, data: PeriodIn) -> Period:
    from hubra.api.finance.fee_basis import _billing_year

    start, end = _billing_year(data.on)
    return Period(start=start, end=end)


class InvoiceStatusIn(BaseModel):
    invoice_id: int
    status: Literal["Paid", "Open"]
    # Who made the change, for the audit log, when the action runs as
    # SYSTEM on a member's behalf (booking an invoice's income).
    actor_id: int | None = None


class InvoiceStatus(BaseModel):
    id: int
    status: str


def set_invoice_status(ctx, data: InvoiceStatusIn) -> InvoiceStatus:
    from hubra.api.finance.services import InvoiceService
    from hubra.core.contracts import Refused
    from hubra.core.extensions import db
    from hubra.core.models.finance import Invoice

    invoice = db.session.get(Invoice, data.invoice_id)
    if invoice is None:
        raise Refused(f"Invoice {data.invoice_id} not found", code="NOT_FOUND")
    actor_id = data.actor_id
    if actor_id is None and ctx.actor is not None:
        actor_id = ctx.actor.id
    if invoice.status != data.status:
        InvoiceService.update(invoice, {"status": data.status}, actor_id)
    return InvoiceStatus(id=invoice.id, status=invoice.status)


# ── Fee basis sources (offered by plugins, asked by fee_basis) ──────────────


class FeeBasisIn(BaseModel):
    on: date


class FeeBasisLine(BaseModel):
    category_id: int | None = None
    name: str | None = None
    color: str | None = None
    amount: float
    items: list[dict] = []


class FeeBasisOut(BaseModel):
    lines: list[FeeBasisLine]
    # Shown as is: {"from", "to"} or {"year"}; None when it has none.
    period: dict | None = None
