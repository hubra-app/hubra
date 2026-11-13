"""What Finance offers other modules through contracts (docs/contracts.md).

- ``finance.billing_period`` (query): the club's billing year around a day.
- ``finance.invoice.set_status`` (action): mark an invoice paid or open
  again, with everything that comes with it (mails, events, the audit log).
  With ``payment`` the invoice's booking holds what arrived (Bank Import).
- ``finance.transaction.create`` (action): put one booking in the books.
- ``finance.invoice.create`` / ``finance.invoice.delete`` (actions): an
  invoice to a member or an outside party, booked like one made in the app.
- ``finance.external_party.save`` (action): create an outside party, or keep
  one up to date.
- ``finance.open_item.add`` / ``finance.open_item.remove`` (actions):
  something a member owes, for their next collected invoice
  (``open_items.py``), and taking it back before it is billed.

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


class PaymentIn(BaseModel):
    """What arrived for an invoice: the booking is brought in line with it."""

    on: date
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: str = Field("IBAN", min_length=1, max_length=50)


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
    # Paid by this payment: the invoice's booking gets its date, amount and
    # method and is completed; an invoice nobody booked (no Finances plugin)
    # gets an income booking. Only with status "Paid".
    payment: PaymentIn | None = None

    @model_validator(mode="after")
    def _payment_only_when_paid(self):
        if self.payment is not None and self.status != "Paid":
            raise ValueError("payment only goes with status Paid")
        return self


class InvoiceStatus(BaseModel):
    id: int
    status: str
    transaction_id: int | None = None


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
    if data.payment is not None:
        _book_payment(invoice, data.payment)
    return InvoiceStatus(
        id=invoice.id, status=invoice.status, transaction_id=invoice.transaction_id
    )


def _income_category_id() -> int | None:
    """The "Membership" category, else the first one, as invoice bookings use."""
    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.finance import TransactionCategory

    category = db.session.scalar(
        select(TransactionCategory).where(TransactionCategory.name == "Membership")
    ) or db.session.scalar(select(TransactionCategory).order_by(TransactionCategory.id))
    return category.id if category else None


def _book_payment(invoice, payment: PaymentIn) -> None:
    from hubra.core.extensions import db
    from hubra.core.models.finance import Transaction

    tx = (
        db.session.get(Transaction, invoice.transaction_id)
        if invoice.transaction_id is not None
        else None
    )
    if tx is None:
        # Nobody keeps the invoices' bookings: the payment books its income.
        tx = Transaction(
            description=f"Invoice #{invoice.id}",
            category_id=_income_category_id(),
            member_id=invoice.member_id,
            type="income",
        )
        db.session.add(tx)
    tx.date = payment.on
    tx.method = payment.method
    tx.status = "Completed"
    # The books hold what arrived; it may differ from the invoice (a
    # mismatch the treasurer accepted).
    tx.amount = payment.amount
    db.session.flush()
    invoice.transaction_id = tx.id


class TransactionIn(BaseModel):
    """One booking. ``amount`` is positive; an expense is stored negative,
    as the finance screens store it."""

    booked_on: date
    description: str = Field(min_length=1, max_length=255)
    # Optional: Kasse pays expense claims that have no category.
    category_id: int | None = None
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    type: Literal["income", "expense"]
    method: str = Field("IBAN", min_length=1, max_length=50)
    payee_name: str | None = Field(None, max_length=255)
    member_id: int | None = None
    actor_id: int | None = None


class TransactionOut(BaseModel):
    id: int


def create_transaction(ctx, data: TransactionIn) -> TransactionOut:
    from sqlalchemy import select

    from hubra.core.contracts import Refused
    from hubra.core.extensions import db
    from hubra.core.models.finance import Transaction, TransactionCategory
    from hubra.core.models.member import Member
    from hubra.core.utils import log_audit

    if (
        data.category_id is not None
        and db.session.get(TransactionCategory, data.category_id) is None
    ):
        raise Refused("Category not found", code="NOT_FOUND", status=404)
    if data.member_id is not None and (
        db.session.scalar(
            select(Member.id)
            .where(Member.id == data.member_id)
            .where(Member.archived_at.is_(None))
        )
        is None
    ):
        raise Refused("Member not found", code="NOT_FOUND", status=404)
    tx = Transaction(
        date=data.booked_on,
        description=data.description,
        category_id=data.category_id,
        payee_name=data.payee_name,
        member_id=data.member_id,
        amount=data.amount if data.type == "income" else -data.amount,
        method=data.method,
        type=data.type,
        status="Completed",
    )
    db.session.add(tx)
    db.session.flush()
    log_audit(
        _actor_id(ctx, data.actor_id),
        "create_transaction",
        "Transaction",
        tx.id,
        tx.description,
    )
    return TransactionOut(id=tx.id)


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


# ── Open items: one statement per member ─────────────────────────────────────


class OpenItemIn(BaseModel):
    """Something a member owes. ``source_ref`` is the caller's own
    reference (a tab id, a booking id): each is accepted once, and
    ``finance.open_item.remove`` takes it back by it."""

    member_id: int
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    text: str = Field(min_length=1, max_length=200)
    source_ref: str | None = Field(default=None, max_length=80)
    category_id: int | None = None
    day: date | None = None
    # With collecting off the item is billed at once: its invoice is due
    # after this many days (else the club's payment term). A collected
    # invoice always takes the club's term.
    due_days: int | None = Field(default=None, ge=0, le=365)
    actor_id: int | None = None


class OpenItemOut(BaseModel):
    id: int
    # Set when it was billed at once (collecting off).
    invoice_id: int | None = None


class OpenItemRef(BaseModel):
    source_ref: str = Field(min_length=1, max_length=80)


class OpenItemRemoved(BaseModel):
    removed: bool


def _item_source(ctx) -> str:
    """Who hands an open item over: the plugin's id ("kasse", "booking"),
    the same from every file of the plugin; "finance" for Hubra itself.
    (``ctx.caller`` is the calling Python module, e.g. hubra_kasse.routes.)"""
    from hubra.core.contracts.registry import plugin_of

    return plugin_of(ctx.caller or "") or "finance"


def add_open_item(ctx, data: OpenItemIn) -> OpenItemOut:
    from hubra.api.finance import open_items

    item = open_items.add(
        member_id=data.member_id,
        amount=data.amount,
        text=data.text,
        source=_item_source(ctx),
        source_ref=data.source_ref,
        category_id=data.category_id,
        day=data.day,
        due_days=data.due_days,
        actor_id=_actor_id(ctx, data.actor_id),
    )
    return OpenItemOut(id=item.id, invoice_id=item.invoice_id)


def remove_open_item(ctx, data: OpenItemRef) -> OpenItemRemoved:
    """False when there is none; Refused ALREADY_BILLED once it is billed."""
    from sqlalchemy import select

    from hubra.api.finance import open_items
    from hubra.core.extensions import db
    from hubra.core.models.finance import OpenItem

    item = db.session.scalar(
        select(OpenItem).where(
            OpenItem.source == _item_source(ctx),
            OpenItem.source_ref == data.source_ref,
        )
    )
    if item is None:
        return OpenItemRemoved(removed=False)
    open_items.remove(item)
    return OpenItemRemoved(removed=True)
