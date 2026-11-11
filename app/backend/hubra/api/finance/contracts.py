"""What Finance offers other modules through contracts (docs/contracts.md).

- ``finance.billing_period`` (query): the club's billing year around a day.
- ``finance.invoice.set_status`` (action): mark an invoice paid or open
  again, with everything that comes with it (mails, events, the audit log).
- ``finance.invoice.create`` / ``finance.invoice.delete`` (actions): an
  invoice to a member or an outside party, booked like one made in the app.
- ``finance.external_party.save`` (action): create an outside party, or keep
  one up to date.
- ``finance.transaction.create`` (action): a booking (income or expense) in
  the transactions table, checked and logged like one made in the books.

Plugins that offer a source for the fee basis do it the other way round:
they offer a query named ``<module>.fee_basis.<source>`` with the shapes
below, and ``fee_basis`` asks it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
    # Paid with no booking yet: announce the invoice first (invoice.created),
    # so whoever keeps the books (the Finances plugin) books its income and
    # the booking turns paid with it. Bank Import does this for a payment.
    book: bool = False


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
    if data.book and data.status == "Paid" and invoice.transaction_id is None:
        from hubra.api.finance.services import _link_pending_transaction

        _link_pending_transaction(invoice)
    if invoice.status != data.status:
        InvoiceService.update(invoice, {"status": data.status}, actor_id)
    return InvoiceStatus(id=invoice.id, status=invoice.status)


def _actor_id(ctx, given: int | None) -> int | None:
    if given is not None:
        return given
    return ctx.actor.id if ctx.actor is not None else None


class InvoiceIn(BaseModel):
    """An invoice to one member or one outside party."""

    member_id: int | None = None
    external_party_id: int | None = None
    issued: date
    due: date
    amount: Decimal
    purpose: str = "other"
    description: str | None = None
    # The category its income is booked in (none: the books pick one).
    category_id: int | None = None
    actor_id: int | None = None

    @model_validator(mode="after")
    def _one_recipient(self):
        if (self.member_id is None) == (self.external_party_id is None):
            raise ValueError("give exactly one of member_id and external_party_id")
        return self


class InvoiceOut(BaseModel):
    id: int
    status: str
    amount: Decimal
    member_id: int | None = None
    external_party_id: int | None = None


def create_invoice(ctx, data: InvoiceIn) -> InvoiceOut:
    from hubra.api.finance.services import InvoicesService

    fields = data.model_dump(exclude={"actor_id"})
    invoice = InvoicesService.create(fields, _actor_id(ctx, data.actor_id))
    return InvoiceOut(
        id=invoice.id,
        status=invoice.status,
        amount=invoice.amount,
        member_id=invoice.member_id,
        external_party_id=invoice.external_party_id,
    )


class InvoiceRef(BaseModel):
    invoice_id: int
    actor_id: int | None = None


class InvoiceDeleted(BaseModel):
    id: int


def delete_invoice(ctx, data: InvoiceRef) -> InvoiceDeleted:
    from hubra.api.finance.services import InvoiceService

    InvoiceService.delete(data.invoice_id, _actor_id(ctx, data.actor_id))
    return InvoiceDeleted(id=data.invoice_id)


class ExternalPartyIn(BaseModel):
    """An outside party. With ``external_party_id`` the party is kept up to
    date (only the fields given; a gone party is made again)."""

    external_party_id: int | None = None
    name: str
    email: str | None = None
    address_street: str | None = None
    address_house_no: str | None = None
    address_postal_code: str | None = None
    address_city: str | None = None
    address_country: str | None = None
    notes: str | None = None
    actor_id: int | None = None


class ExternalPartyOut(BaseModel):
    id: int
    name: str
    created: bool


def save_external_party(ctx, data: ExternalPartyIn) -> ExternalPartyOut:
    from hubra.api.finance.services import ExternalPartiesService, ExternalPartyService
    from hubra.core.extensions import db
    from hubra.core.models.external_party import ExternalParty

    actor_id = _actor_id(ctx, data.actor_id)
    fields = data.model_dump(
        exclude={"external_party_id", "actor_id"}, exclude_unset=True
    )
    party = (
        db.session.get(ExternalParty, data.external_party_id)
        if data.external_party_id
        else None
    )
    if party is None:
        if "address_country" in fields and fields["address_country"] is None:
            del fields["address_country"]
        party = ExternalPartiesService.create(fields, actor_id)
        return ExternalPartyOut(id=party.id, name=party.name, created=True)
    changed = {k: v for k, v in fields.items() if getattr(party, k) != v}
    if changed:
        ExternalPartyService.update(party, changed, actor_id)
    return ExternalPartyOut(id=party.id, name=party.name, created=False)


class TransactionIn(BaseModel):
    """A booking. ``amount`` is given positive; an expense is stored
    negative, as the books do."""

    date: date
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, lt=Decimal("10000000000"))
    type: Literal["income", "expense"]
    method: Literal["IBAN", "Cash", "Twint", "Card"]
    category_id: int | None = None
    member_id: int | None = None
    payee_name: str | None = Field(default=None, max_length=255)
    actor_id: int | None = None


class TransactionOut(BaseModel):
    id: int
    amount: Decimal
    type: str


def create_transaction(ctx, data: TransactionIn) -> TransactionOut:
    from sqlalchemy import select

    from hubra.core.contracts import Refused
    from hubra.core.extensions import db
    from hubra.core.models.finance import Transaction, TransactionCategory
    from hubra.core.models.member import Member
    from hubra.core.utils import log_audit

    if data.member_id is not None and (
        db.session.scalar(
            select(Member.id)
            .where(Member.id == data.member_id)
            .where(Member.archived_at.is_(None))
        )
        is None
    ):
        raise Refused(f"Member {data.member_id} not found", code="NOT_FOUND")
    if (
        data.category_id is not None
        and db.session.get(TransactionCategory, data.category_id) is None
    ):
        raise Refused(f"Category {data.category_id} not found", code="NOT_FOUND")
    amount = data.amount.quantize(Decimal("0.01"))
    tx = Transaction(
        date=data.date,
        description=data.description,
        category_id=data.category_id,
        member_id=data.member_id,
        payee_name=data.payee_name,
        amount=-amount if data.type == "expense" else amount,
        method=data.method,
        type=data.type,
    )
    db.session.add(tx)
    # A closed fiscal year refuses the booking here (the books' flush check).
    db.session.flush()
    log_audit(
        actor_id=_actor_id(ctx, data.actor_id),
        action="create_transaction",
        target_type="Transaction",
        target_id=tx.id,
        target_label=data.description,
    )
    return TransactionOut(id=tx.id, amount=tx.amount, type=tx.type)


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
    # Why there are no lines, as a code the page shows (NO_BUDGET: no
    # approved budget for the year); None when there is nothing to say.
    note: str | None = None
