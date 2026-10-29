"""Marking an invoice's income as received pays the invoice."""

from tests.finance.test_invoices import _invoice_with_transaction


def test_completed_income_pays_the_invoice(client, auth_headers, seeded_db, db):
    from hubra.core.models.finance import Invoice

    invoice_id, tx_id = _invoice_with_transaction(client, auth_headers, seeded_db, db)
    url = f"/api/v1/finance/transactions/{tx_id}"

    assert client.patch(url, json={"status": "Completed"}, headers=auth_headers).status_code == 200
    db.session.expire_all()
    assert db.session.get(Invoice, invoice_id).status == "Paid"

    assert client.patch(url, json={"status": "Pending"}, headers=auth_headers).status_code == 200
    db.session.expire_all()
    assert db.session.get(Invoice, invoice_id).status == "Open"
