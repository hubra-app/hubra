"""The income booking that follows each invoice.

Invoicing doesn't touch transactions itself: it emits ``invoice.created``,
``invoice.updated`` and ``invoice.deleted`` and these handlers keep the
linked income transaction in step. They run inside the caller's transaction,
so an invoice and its booking are saved together. Keeping them behind events
lets bookkeeping move into a plugin of its own later without invoicing
importing it (docs/plugins.md).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.external_party import ExternalParty
from hubra.core.models.finance import Invoice, Transaction, TransactionCategory


def _category(category_id: int | None) -> TransactionCategory | None:
    """The form's category, else "Membership", else the first one."""
    category = (
        db.session.get(TransactionCategory, category_id)
        if category_id is not None
        else None
    )
    if category is None:
        category = db.session.scalar(
            select(TransactionCategory).where(TransactionCategory.name == "Membership")
        )
    if category is None:
        category = db.session.scalar(select(TransactionCategory))
    return category


def _payee(invoice: Invoice) -> str | None:
    if invoice.external_party_id is None:
        return None
    party = db.session.get(ExternalParty, invoice.external_party_id)
    return party.name if party else None


def on_invoice_created(tenant_id=None, invoice_id=None, category_id=None, **_):
    """Book a Pending income transaction for a new invoice and link it.

    Without any transaction category the invoice stays unbooked.
    """
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None or invoice.transaction_id is not None:
        return
    category = _category(category_id)
    if category is None:
        return
    linked_tx = Transaction(
        date=invoice.issued,
        description=f"Invoice #{invoice.id}",
        category_id=category.id,
        member_id=invoice.member_id,
        payee_name=_payee(invoice),
        amount=invoice.amount,
        method="IBAN",
        type="income",
        status="Pending",
    )
    db.session.add(linked_tx)
    db.session.flush()
    invoice.transaction_id = linked_tx.id
    db.session.flush()


def on_invoice_updated(tenant_id=None, invoice_id=None, was_paid=False, changed=(), **_):
    """The linked income follows the invoice: paid → completed, and back to
    pending when a payment is taken back. Its amount follows while the money
    is still expected, and so does who pays."""
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None or invoice.transaction_id is None:
        return
    linked_tx = db.session.get(Transaction, invoice.transaction_id)
    if linked_tx is None:
        return
    if invoice.status == "Paid":
        linked_tx.status = "Completed"
    elif was_paid:
        linked_tx.status = "Pending"
    if "amount" in changed and linked_tx.status == "Pending":
        linked_tx.amount = abs(Decimal(str(invoice.amount)))
    if "member_id" in changed or "external_party_id" in changed:
        linked_tx.member_id = invoice.member_id
        linked_tx.payee_name = _payee(invoice)


def on_invoice_deleted(tenant_id=None, invoice_id=None, transaction_id=None, **_):
    """Delete the income transaction of an invoice that is gone."""
    if transaction_id is None:
        return
    linked_tx = db.session.get(Transaction, transaction_id)
    if linked_tx is not None:
        db.session.delete(linked_tx)
