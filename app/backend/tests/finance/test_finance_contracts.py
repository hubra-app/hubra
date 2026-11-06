"""What Finance offers plugins through contracts: the billing period and
marking an invoice paid (hubra/api/finance/contracts.py)."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from hubra.core.contracts import SYSTEM, ActionForbidden, Refused, call, query
from hubra.core.contracts import registry as creg
from hubra.core.models.finance import Invoice


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
