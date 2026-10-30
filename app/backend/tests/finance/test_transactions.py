"""Tests for finance transactions and overview endpoint.

Merged from test_finance.py (transaction/overview parts) and
test_m003_s03_transactions.py (PATCH status, overview balance filter).
"""

from datetime import date

import pytest
from hubra.core.models.finance import Transaction, TransactionCategory


# ── Helpers ───────────────────────────────────────────────────────────────────


def _seed_category(db):
    """Create and commit a TransactionCategory, return it."""
    cat = TransactionCategory(name="Membership Fees", color="#123456")
    db.session.add(cat)
    db.session.commit()
    return cat


def _tx_payload(category_id, **overrides):
    payload = {
        "date": date.today().isoformat(),
        "description": "Test transaction",
        "category_id": category_id,
        "amount": 50.0,
        "method": "Cash",
        "type": "income",
    }
    payload.update(overrides)
    return payload


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def category(db):
    """A minimal TransactionCategory for test transactions."""
    cat = TransactionCategory(name="Test Category", color="#123456")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture
def transaction(client, db, auth_headers, category):
    """Create a transaction via the API and return the response body."""
    resp = client.post(
        "/api/v1/finance/transactions",
        json={
            "date": date.today().isoformat(),
            "description": "Test transaction",
            "category_id": category.id,
            "amount": 100.0,
            "method": "Cash",
            "type": "income",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.get_json()


# ── List transactions ─────────────────────────────────────────────────────────


def test_list_transactions(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/finance/transactions", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "data" in body
    assert "total" in body


# ── Create transaction ────────────────────────────────────────────────────────


def test_create_transaction(client, auth_headers, seeded_db, db):
    cat = _seed_category(db)
    resp = client.post(
        "/api/v1/finance/transactions",
        json=_tx_payload(cat.id),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["description"] == "Test transaction"
    assert "id" in body


def test_create_transaction_invalid_category(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/finance/transactions",
        json=_tx_payload(category_id=999999),
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_create_transaction_without_category(client, auth_headers, seeded_db):
    payload = _tx_payload(category_id=None)
    del payload["category_id"]
    resp = client.post(
        "/api/v1/finance/transactions", json=payload, headers=auth_headers
    )
    assert resp.status_code == 201
    assert resp.get_json()["category_id"] is None


def test_patch_transaction_clears_category(client, auth_headers, transaction):
    resp = client.patch(
        f"/api/v1/finance/transactions/{transaction['id']}",
        json={"category_id": None},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["category_id"] is None


# ── PATCH transaction status ──────────────────────────────────────────────────


def test_patch_transaction_status_completed(client, db, auth_headers, transaction):
    tx_id = transaction["id"]
    resp = client.patch(
        f"/api/v1/finance/transactions/{tx_id}",
        json={"status": "Completed"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "Completed"


def test_patch_transaction_status_pending(client, db, auth_headers, transaction):
    tx_id = transaction["id"]
    resp = client.patch(
        f"/api/v1/finance/transactions/{tx_id}",
        json={"status": "Pending"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "Pending"


def test_patch_transaction_invalid_status(client, db, auth_headers, transaction):
    tx_id = transaction["id"]
    resp = client.patch(
        f"/api/v1/finance/transactions/{tx_id}",
        json={"status": "Invalid"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_patch_transaction_not_found(client, db, auth_headers):
    resp = client.patch(
        "/api/v1/finance/transactions/999999",
        json={"status": "Completed"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_patch_transaction_description(client, db, auth_headers, transaction):
    tx_id = transaction["id"]
    original_status = transaction["status"]
    resp = client.patch(
        f"/api/v1/finance/transactions/{tx_id}",
        json={"description": "Updated description"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["description"] == "Updated description"
    assert body["status"] == original_status


# ── Finance overview ──────────────────────────────────────────────────────────


def test_finance_overview(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/finance/overview", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    for key in (
        "balance",
        "incomeMTD",
        "expensesMTD",
        "netMTD",
        "months",
        "openInvoices",
    ):
        assert key in body, f"Missing key: {key}"
    assert isinstance(body["months"], list)
    assert "count" in body["openInvoices"]


def test_overview_balance_excludes_pending(client, db, auth_headers, category):
    # Create a Pending transaction — should not appear in balance
    tx = Transaction(
        date=date.today(),
        description="Pending transaction",
        category_id=category.id,
        amount=500.0,
        method="Cash",
        type="income",
        status="Pending",
    )
    db.session.add(tx)
    db.session.commit()

    resp = client.get("/api/v1/finance/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    # Balance must not include the pending 500
    assert data["balance"] == 0.0


def test_overview_balance_includes_completed(client, db, auth_headers, category):
    # Create a Completed transaction — should appear in balance
    tx = Transaction(
        date=date.today(),
        description="Completed transaction",
        category_id=category.id,
        amount=250.0,
        method="Cash",
        type="income",
        status="Completed",
    )
    db.session.add(tx)
    db.session.commit()

    resp = client.get("/api/v1/finance/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["balance"] == 250.0


def test_patch_expense_amount_stays_an_expense(client, db, auth_headers, category):
    """Amounts come in positive; an edited expense stays negative, and
    switching the type flips the sign."""
    resp = client.post(
        "/api/v1/finance/transactions",
        json=_tx_payload(category.id, amount=80.0, type="expense"),
        headers=auth_headers,
    )
    tx_id = resp.get_json()["id"]
    assert resp.get_json()["amount"] == -80.0

    resp = client.patch(
        f"/api/v1/finance/transactions/{tx_id}",
        json={"amount": 95.0, "type": "expense"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["amount"] == -95.0

    resp = client.patch(
        f"/api/v1/finance/transactions/{tx_id}",
        json={"type": "income"},
        headers=auth_headers,
    )
    assert resp.get_json()["amount"] == 95.0
