"""Tests for invoice-to-transaction auto-linkage (M003/S04)."""

import pytest
from datetime import date

from vollbuild.core.models.finance import Transaction, TransactionCategory


@pytest.fixture
def membership_category(db):
    """TransactionCategory named 'Membership' for the auto-link path."""
    cat = TransactionCategory(name="Membership", color="#00aaff")
    db.session.add(cat)
    db.session.commit()
    return cat


def _create_invoice(client, auth_headers, member_id, amount=100.0):
    return client.post(
        "/api/v1/finance/invoices",
        json={
            "member_id": member_id,
            "issued": date.today().isoformat(),
            "due": date.today().isoformat(),
            "amount": amount,
        },
        headers=auth_headers,
    )


def test_create_invoice_auto_creates_pending_transaction(
    client, db, auth_headers, seeded_db, membership_category
):
    """POST /invoices creates a Pending transaction and links it."""
    member_id = seeded_db["admin"].id
    resp = _create_invoice(client, auth_headers, member_id, amount=150.0)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["transaction_id"] is not None

    tx = db.session.get(Transaction, body["transaction_id"])
    assert tx is not None
    assert tx.status == "Pending"
    assert tx.type == "income"
    assert tx.method == "IBAN"
    assert float(tx.amount) == 150.0
    assert tx.member_id == member_id
    assert tx.description == f"Invoice #{body['id']}"


def test_create_invoice_links_membership_category(
    client, db, auth_headers, seeded_db, membership_category
):
    """The auto-created transaction uses the Membership category."""
    member_id = seeded_db["admin"].id
    resp = _create_invoice(client, auth_headers, member_id)
    assert resp.status_code == 201
    body = resp.get_json()
    tx = db.session.get(Transaction, body["transaction_id"])
    assert tx.category_id == membership_category.id


def test_create_invoice_falls_back_to_any_category(client, db, auth_headers, seeded_db):
    """Without a Membership category, fall back to the first available category."""
    fallback = TransactionCategory(name="General", color="#aabbcc")
    db.session.add(fallback)
    db.session.commit()

    member_id = seeded_db["admin"].id
    resp = _create_invoice(client, auth_headers, member_id)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["transaction_id"] is not None
    tx = db.session.get(Transaction, body["transaction_id"])
    assert tx.category_id == fallback.id


def test_create_invoice_no_category_skips_transaction(
    client, db, auth_headers, seeded_db
):
    """If no categories exist at all, invoice is still created (no transaction_id)."""
    member_id = seeded_db["admin"].id
    resp = _create_invoice(client, auth_headers, member_id)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["transaction_id"] is None


def test_patch_invoice_paid_completes_transaction(
    client, db, auth_headers, seeded_db, membership_category
):
    """PATCH /invoices/{id} status=Paid completes the linked transaction."""
    member_id = seeded_db["admin"].id
    create_resp = _create_invoice(client, auth_headers, member_id)
    assert create_resp.status_code == 201
    invoice_id = create_resp.get_json()["id"]
    tx_id = create_resp.get_json()["transaction_id"]
    assert tx_id is not None

    patch_resp = client.patch(
        f"/api/v1/finance/invoices/{invoice_id}",
        json={"status": "Paid"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200

    tx = db.session.get(Transaction, tx_id)
    assert tx.status == "Completed"


def test_patch_invoice_non_paid_does_not_complete_transaction(
    client, db, auth_headers, seeded_db, membership_category
):
    """PATCH /invoices/{id} with a status other than Paid leaves transaction Pending."""
    member_id = seeded_db["admin"].id
    create_resp = _create_invoice(client, auth_headers, member_id)
    assert create_resp.status_code == 201
    invoice_id = create_resp.get_json()["id"]
    tx_id = create_resp.get_json()["transaction_id"]

    patch_resp = client.patch(
        f"/api/v1/finance/invoices/{invoice_id}",
        json={"status": "Open"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200

    tx = db.session.get(Transaction, tx_id)
    assert tx.status == "Pending"


def test_get_transactions_shows_pending_entry_after_invoice_create(
    client, db, auth_headers, seeded_db, membership_category
):
    """GET /transactions lists the auto-created Pending entry after invoice creation."""
    member_id = seeded_db["admin"].id
    create_resp = _create_invoice(client, auth_headers, member_id, amount=200.0)
    assert create_resp.status_code == 201
    tx_id = create_resp.get_json()["transaction_id"]

    list_resp = client.get("/api/v1/finance/transactions", headers=auth_headers)
    assert list_resp.status_code == 200
    tx_ids = [t["id"] for t in list_resp.get_json()["data"]]
    assert tx_id in tx_ids


def test_pending_transaction_excluded_from_overview_balance(
    client, db, auth_headers, seeded_db, membership_category
):
    """GET /finance/overview balance excludes Pending transactions (S03 filter)."""
    member_id = seeded_db["admin"].id

    # Capture baseline balance before creating invoice
    baseline = client.get("/api/v1/finance/overview", headers=auth_headers)
    assert baseline.status_code == 200
    baseline_balance = baseline.get_json()["balance"]

    # Create an invoice — auto-creates a Pending transaction of 250.0
    resp = _create_invoice(client, auth_headers, member_id, amount=250.0)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["transaction_id"] is not None  # transaction was created

    # Balance must not change — Pending transactions are excluded
    overview = client.get("/api/v1/finance/overview", headers=auth_headers)
    assert overview.status_code == 200
    assert overview.get_json()["balance"] == baseline_balance
