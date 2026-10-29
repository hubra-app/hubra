"""Tests for external-party invoices and invoice purpose field."""

from datetime import date
from unittest.mock import patch


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ext_party(client, headers, name="External Co", email="ext@example.com"):
    payload: dict = {
        "name": name,
        "address_street": "Teststrasse",
        "address_house_no": "1",
        "address_postal_code": "1234",
        "address_city": "Teststadt",
        "address_country": "CH",
    }
    if email is not None:
        payload["email"] = email
    resp = client.post(
        "/api/v1/finance/external-parties",
        json=payload,
        headers=headers,
    )
    return resp.get_json()


def _member_invoice_payload(member_id, **overrides):
    today = date.today().isoformat()
    payload = {
        "member_id": member_id,
        "issued": today,
        "due": today,
        "amount": 45.0,
    }
    payload.update(overrides)
    return payload


def _ext_invoice_payload(ext_id, **overrides):
    today = date.today().isoformat()
    payload = {
        "external_party_id": ext_id,
        "issued": today,
        "due": today,
        "amount": 100.0,
        "purpose": "other",
    }
    payload.update(overrides)
    return payload


# ── Create external invoice ───────────────────────────────────────────────────


def test_create_external_invoice(client, auth_headers, seeded_db):
    ext = _ext_party(client, auth_headers)
    resp = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext["id"]),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["recipient_type"] == "external"
    assert body["purpose"] == "other"
    assert body["external_party_id"] == ext["id"]
    assert body["external_party_name"] == "External Co"
    assert body["member_id"] is None
    assert body["member_name"] == ""


def test_create_invoice_no_recipient_returns_400(client, auth_headers, seeded_db):
    today = date.today().isoformat()
    resp = client.post(
        "/api/v1/finance/invoices",
        json={"issued": today, "due": today, "amount": 50.0},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_create_invoice_both_recipients_returns_400(client, auth_headers, seeded_db):
    ext = _ext_party(client, auth_headers)
    today = date.today().isoformat()
    resp = client.post(
        "/api/v1/finance/invoices",
        json={
            "member_id": seeded_db["admin"].id,
            "external_party_id": ext["id"],
            "issued": today,
            "due": today,
            "amount": 50.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_create_membership_invoice_without_member_returns_400(
    client, auth_headers, seeded_db
):
    ext = _ext_party(client, auth_headers)
    today = date.today().isoformat()
    resp = client.post(
        "/api/v1/finance/invoices",
        json={
            "external_party_id": ext["id"],
            "issued": today,
            "due": today,
            "amount": 50.0,
            "purpose": "membership",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_create_member_invoice_purpose_other_with_category(
    client, auth_headers, seeded_db
):
    from hubra.core.models.finance import TransactionCategory
    from hubra.core.extensions import db

    cat = TransactionCategory(name="Events", color="#27ae60")
    db.session.add(cat)
    db.session.commit()

    resp = client.post(
        "/api/v1/finance/invoices",
        json=_member_invoice_payload(
            seeded_db["admin"].id, purpose="other", category_id=cat.id, amount=30.0
        ),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["purpose"] == "other"

    from hubra.core.models.finance import Invoice

    inv = db.session.get(Invoice, body["id"])
    db.session.get(
        TransactionCategory, inv.transaction.id if inv.transaction_id else None
    )
    assert inv.transaction is not None
    assert inv.transaction.category_id == cat.id


def test_create_member_invoice_purpose_membership_default_category(
    client, auth_headers, seeded_db
):
    from hubra.core.models.finance import TransactionCategory
    from hubra.core.extensions import db

    cat = TransactionCategory(name="Membership", color="#2596be")
    db.session.add(cat)
    db.session.commit()

    resp = client.post(
        "/api/v1/finance/invoices",
        json=_member_invoice_payload(seeded_db["admin"].id, purpose="membership"),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["purpose"] == "membership"

    from hubra.core.models.finance import Invoice

    inv = db.session.get(Invoice, body["id"])
    assert inv.transaction is not None
    assert inv.transaction.category_id == cat.id


def test_create_external_invoice_linked_tx_has_payee_name(
    client, auth_headers, seeded_db
):
    from hubra.core.models.finance import TransactionCategory
    from hubra.core.extensions import db

    cat = TransactionCategory(name="Membership", color="#2596be")
    db.session.add(cat)
    db.session.commit()

    ext = _ext_party(client, auth_headers, name="Linked Co")
    resp = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext["id"]),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    inv_id = resp.get_json()["id"]

    from hubra.core.models.finance import Invoice

    inv = db.session.get(Invoice, inv_id)
    assert inv.transaction is not None
    assert inv.transaction.payee_name == "Linked Co"
    assert inv.transaction.member_id is None


# ── Update external invoice ───────────────────────────────────────────────────


def test_update_external_invoice_amount(client, auth_headers, seeded_db):
    ext = _ext_party(client, auth_headers)
    created = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext["id"]),
        headers=auth_headers,
    )
    inv_id = created.get_json()["id"]

    resp = client.patch(
        f"/api/v1/finance/invoices/{inv_id}",
        json={"amount": 200.0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert abs(resp.get_json()["amount"] - 200.0) < 0.01


def test_update_invoice_external_party_id(client, auth_headers, seeded_db):
    ext1 = _ext_party(client, auth_headers, name="Party One")
    ext2 = _ext_party(client, auth_headers, name="Party Two")
    created = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext1["id"]),
        headers=auth_headers,
    )
    inv_id = created.get_json()["id"]

    resp = client.patch(
        f"/api/v1/finance/invoices/{inv_id}",
        json={"external_party_id": ext2["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["external_party_name"] == "Party Two"


# ── Purpose filter ────────────────────────────────────────────────────────────


def test_list_invoices_filter_by_purpose(client, auth_headers, seeded_db):
    member_id = seeded_db["admin"].id
    client.post(
        "/api/v1/finance/invoices",
        json=_member_invoice_payload(member_id, purpose="membership"),
        headers=auth_headers,
    )
    ext = _ext_party(client, auth_headers)
    client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext["id"]),
        headers=auth_headers,
    )

    resp = client.get("/api/v1/finance/invoices?purpose=other", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert all(inv["purpose"] == "other" for inv in body["data"])

    resp = client.get(
        "/api/v1/finance/invoices?purpose=membership", headers=auth_headers
    )
    body = resp.get_json()
    assert all(inv["purpose"] == "membership" for inv in body["data"])


# ── Reminder for external invoice ─────────────────────────────────────────────


def test_remind_external_invoice_dispatches_email(client, auth_headers, seeded_db):
    ext = _ext_party(client, auth_headers, email="external@test.example")
    created = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext["id"]),
        headers=auth_headers,
    )
    inv_id = created.get_json()["id"]

    with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as mock_delay:
        resp = client.post(
            f"/api/v1/finance/invoices/{inv_id}/remind", headers=auth_headers
        )

    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    mock_delay.assert_called_once()
    call_kwargs = mock_delay.call_args
    assert call_kwargs.kwargs["to_email"] == "external@test.example"


def test_remind_external_invoice_no_email(client, auth_headers, seeded_db):
    ext = _ext_party(client, auth_headers, email=None)
    created = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext["id"]),
        headers=auth_headers,
    )
    inv_id = created.get_json()["id"]

    with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as mock_delay:
        resp = client.post(
            f"/api/v1/finance/invoices/{inv_id}/remind", headers=auth_headers
        )

    # Nothing went out, so the treasurer is told; the attempt is kept.
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "REMINDER_NOT_SENT"
    mock_delay.assert_not_called()
    history = client.get(
        f"/api/v1/finance/invoices/{inv_id}/reminders", headers=auth_headers
    ).get_json()
    assert len(history) == 1


# ── Invoice schema output fields ──────────────────────────────────────────────


def test_invoice_schema_includes_purpose_and_recipient_fields(
    client, auth_headers, seeded_db
):
    member_id = seeded_db["admin"].id
    resp = client.post(
        "/api/v1/finance/invoices",
        json=_member_invoice_payload(member_id),
        headers=auth_headers,
    )
    body = resp.get_json()
    assert "purpose" in body
    assert "recipient_type" in body
    assert "recipient_name" in body
    assert "external_party_id" in body
    assert "external_party_name" in body
    assert body["recipient_type"] == "member"


def test_external_invoice_recipient_name(client, auth_headers, seeded_db):
    ext = _ext_party(client, auth_headers, name="Named Ext")
    resp = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext["id"]),
        headers=auth_headers,
    )
    body = resp.get_json()
    assert body["recipient_name"] == "Named Ext"
    assert body["recipient_type"] == "external"


def test_deleting_a_party_clears_it_on_its_invoices(client, auth_headers, seeded_db):
    # Club schemas have no foreign keys, so nothing else clears the id.
    ext = _ext_party(client, auth_headers)
    invoice_id = client.post(
        "/api/v1/finance/invoices",
        json=_ext_invoice_payload(ext["id"]),
        headers=auth_headers,
    ).get_json()["id"]
    resp = client.delete(
        f"/api/v1/finance/external-parties/{ext['id']}", headers=auth_headers
    )
    assert resp.status_code == 204

    body = client.get(
        f"/api/v1/finance/invoices/{invoice_id}", headers=auth_headers
    ).get_json()
    assert body["external_party_id"] is None
