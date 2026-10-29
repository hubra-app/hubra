"""Who may download an invoice's QR-bill PDF."""

from datetime import date
from unittest.mock import patch

import pytest

from hubra.core.models.finance import Invoice


@pytest.fixture
def invoice(db, seeded_db):
    inv = Invoice(
        member_id=seeded_db["admin"].id,
        issued=date(2026, 10, 1),
        due=date(2026, 11, 30),
        amount=50,
        status="Open",
    )
    db.session.add(inv)
    db.session.commit()
    return inv


@patch("hubra.core.services.qr_bill.generate_invoice_pdf", return_value=b"%PDF")
def test_treasurer_downloads_a_members_invoice(
    _pdf, client, invoice, permissioned_member_factory
):
    permissioned_member_factory(["finance.invoices.read"])
    resp = client.get(f"/api/v1/finance/invoices/{invoice.id}/qr-bill.pdf")
    assert resp.status_code == 200


@patch("hubra.core.services.qr_bill.generate_invoice_pdf", return_value=b"%PDF")
def test_other_member_cannot(_pdf, client, invoice, plain_member_token):
    resp = client.get(f"/api/v1/finance/invoices/{invoice.id}/qr-bill.pdf")
    assert resp.status_code == 403
