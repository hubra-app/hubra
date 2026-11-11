"""What Finance offers plugins through contracts: the billing period and
marking an invoice paid (hubra/api/finance/contracts.py)."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from hubra.core.contracts import SYSTEM, ActionForbidden, Refused, call, query
from hubra.core.contracts import registry as creg
from hubra.core.contracts.base import ContractError
from hubra.core.models.finance import Invoice, Transaction, TransactionCategory


def test_finance_offers_its_contracts(app):
    offers = creg.offers()
    assert offers["finance.billing_period"].contract.kind == "query"
    assert offers["finance.invoice.set_status"].contract.kind == "action"
    assert (
        offers["finance.invoice.set_status"].contract.perm == "finance.invoices.update"
    )


def test_billing_period_follows_the_billing_date(app, db):
    config = {"fee_anchor_month": 7, "fee_anchor_day": 1}
    with patch("hubra.core.modules.get_config", return_value=config):
        period = query("finance.billing_period", on=date(2026, 10, 31))
    assert period == {"start": "2026-07-01", "end": "2027-06-30"}


@pytest.fixture
def invoice(db, billable_tier_db):
    row = Invoice(
        member_id=billable_tier_db["member_billed"].id,
        issued=date(2026, 10, 1),
        due=date(2026, 10, 31),
        amount=Decimal("120"),
        status="Open",
        purpose="other",
        description="Beitrag",
    )
    db.session.add(row)
    db.session.commit()
    return row


def test_set_status_marks_an_invoice_paid_and_open_again(app, db, invoice):
    assert call(
        "finance.invoice.set_status", invoice_id=invoice.id, status="Paid", actor=SYSTEM
    ) == {
        "id": invoice.id,
        "status": "Paid",
        "transaction_id": None,
    }
    assert db.session.get(Invoice, invoice.id).status == "Paid"
    call(
        "finance.invoice.set_status", invoice_id=invoice.id, status="Open", actor=SYSTEM
    )
    assert db.session.get(Invoice, invoice.id).status == "Open"


def test_set_status_refuses_an_unknown_invoice(app, db):
    with pytest.raises(Refused):
        call("finance.invoice.set_status", invoice_id=999, status="Paid", actor=SYSTEM)


def test_set_status_needs_the_invoice_right(app, db, invoice, billable_tier_db):
    member = billable_tier_db["member_billed"]
    with (
        patch("hubra.core.permissions.member_has_permission", return_value=False),
        pytest.raises(ActionForbidden),
    ):
        call(
            "finance.invoice.set_status",
            invoice_id=invoice.id,
            status="Paid",
            actor=member,
        )


def test_set_status_with_a_payment_books_what_arrived(app, db, invoice):
    db.session.add(TransactionCategory(name="Membership"))
    db.session.commit()
    out = call(
        "finance.invoice.set_status",
        invoice_id=invoice.id,
        status="Paid",
        payment={"on": "2026-10-20", "amount": "100.00", "method": "IBAN"},
        actor=SYSTEM,
    )
    tx = db.session.get(Transaction, out["transaction_id"])
    assert (tx.date, tx.amount, tx.method, tx.status, tx.type) == (
        date(2026, 10, 20),
        Decimal("100.00"),
        "IBAN",
        "Completed",
        "income",
    )
    assert db.session.get(Invoice, invoice.id).transaction_id == tx.id

    # A booking that is there already is brought in line, not doubled.
    call(
        "finance.invoice.set_status",
        invoice_id=invoice.id,
        status="Paid",
        payment={"on": "2026-10-21", "amount": "120.00"},
        actor=SYSTEM,
    )
    assert db.session.scalar(db.select(db.func.count()).select_from(Transaction)) == 1
    assert db.session.get(Transaction, tx.id).amount == Decimal("120.00")


def test_a_payment_only_goes_with_paid(app, db, invoice):
    with pytest.raises(ContractError):
        call(
            "finance.invoice.set_status",
            invoice_id=invoice.id,
            status="Open",
            payment={"on": "2026-10-20", "amount": "1"},
            actor=SYSTEM,
        )


@pytest.fixture
def category(db):
    row = TransactionCategory(name="Telefon")
    db.session.add(row)
    db.session.commit()
    return row


def test_create_transaction(app, db, category):
    out = call(
        "finance.transaction.create",
        booked_on="2026-10-27",
        description="Swisscom",
        category_id=category.id,
        amount="45.50",
        type="expense",
        payee_name="Swisscom",
        actor=SYSTEM,
    )
    tx = db.session.get(Transaction, out["id"])
    assert (tx.amount, tx.type, tx.status, tx.method, tx.category_id) == (
        Decimal("-45.50"),
        "expense",
        "Completed",
        "IBAN",
        category.id,
    )


def test_create_transaction_checks_its_input(app, db, category):
    with pytest.raises(Refused):
        call(
            "finance.transaction.create",
            booked_on="2026-10-27",
            description="x",
            category_id=9999,
            amount="1",
            type="income",
            actor=SYSTEM,
        )
    with pytest.raises(ContractError):
        call(
            "finance.transaction.create",
            booked_on="2026-10-27",
            description="x",
            category_id=category.id,
            amount="-5",
            type="income",
            actor=SYSTEM,
        )


def test_create_transaction_needs_the_right(app, db, category, billable_tier_db):
    with (
        patch("hubra.core.permissions.member_has_permission", return_value=False),
        pytest.raises(ActionForbidden),
    ):
        call(
            "finance.transaction.create",
            booked_on="2026-10-27",
            description="x",
            category_id=category.id,
            amount="1",
            type="income",
            actor=billable_tier_db["member_billed"],
        )
