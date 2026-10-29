"""Moving an invoice to another recipient moves its pending income too."""

from tests.finance.test_invoices_external import _ext_invoice_payload, _ext_party


def test_linked_income_follows_the_recipient(client, auth_headers, seeded_db, db):
    from hubra.core.models.finance import Invoice, Transaction, TransactionCategory

    db.session.add(TransactionCategory(name="Membership", color="#2596be"))
    db.session.commit()
    first = _ext_party(client, auth_headers, name="Erste AG")
    second = _ext_party(client, auth_headers, name="Zweite AG", email="z@example.com")
    invoice_id = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(first["id"]),
        headers=auth_headers,
    ).get_json()["id"]
    tx_id = db.session.get(Invoice, invoice_id).transaction_id
    url = f"/api/v1/finance/invoices/{invoice_id}"

    resp = client.patch(url, json={"external_party_id": second["id"]}, headers=auth_headers)
    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(Transaction, tx_id).payee_name == "Zweite AG"

    admin_id = seeded_db["admin"].id
    resp = client.patch(
        url,
        json={"member_id": admin_id, "external_party_id": None},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    db.session.expire_all()
    tx = db.session.get(Transaction, tx_id)
    assert (tx.member_id, tx.payee_name) == (admin_id, None)
