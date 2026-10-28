"""Tests for invoice API endpoints (/api/v1/finance/invoices).

Merged from test_finance.py (invoice CRUD) and test_s06_finance.py
(remind, mine, mark-paid).
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _invoice_payload(member_id, **overrides):
    today = date.today().isoformat()
    payload = {
        "member_id": member_id,
        "issued": today,
        "due": today,
        "amount": 45.0,
    }
    payload.update(overrides)
    return payload


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def billed_auth_headers(client, billable_tier_db):
    """Log in as the billed member and return auth headers."""
    client.post(
        "/api/v1/auth/login", json={"email": "alice@test.ch", "password": "password123"}
    )
    return {}


# ── List invoices ─────────────────────────────────────────────────────────────


def test_list_invoices(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/finance/invoices", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "data" in body
    assert "total" in body


# ── Create invoice ────────────────────────────────────────────────────────────


def test_create_invoice(client, auth_headers, seeded_db):
    member_id = seeded_db["admin"].id
    resp = client.post(
        "/api/v1/finance/invoices",
        json=_invoice_payload(member_id),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "Open"
    assert abs(body["amount"] - 45.0) < 0.01
    assert "id" in body


# ── Mark invoice paid ─────────────────────────────────────────────────────────


def test_mark_invoice_paid(client, auth_headers, seeded_db):
    """PATCH /invoices/:id with status=Paid via API-created invoice."""
    member_id = seeded_db["admin"].id
    created = client.post(
        "/api/v1/finance/invoices",
        json=_invoice_payload(member_id),
        headers=auth_headers,
    )
    invoice_id = created.get_json()["id"]

    resp = client.patch(
        f"/api/v1/finance/invoices/{invoice_id}",
        json={"status": "Paid"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "Paid"


def test_mark_invoice_paid_from_db_record(client, seeded_db, auth_headers):
    """PATCH /invoices/:id with status=Paid via DB-created invoice."""
    from hubra.core.models.finance import Invoice
    from hubra.core.extensions import db

    today = date.today()
    invoice = Invoice(
        member_id=seeded_db["admin"].id,
        issued=today,
        due=today + timedelta(days=30),
        amount=Decimal("45.00"),
        status="Open",
    )
    db.session.add(invoice)
    db.session.commit()
    invoice_id = invoice.id

    resp = client.patch(
        f"/api/v1/finance/invoices/{invoice_id}",
        json={"status": "Paid"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "Paid"


# ── Remind invoice ────────────────────────────────────────────────────────────


def test_remind_invoice_dispatches_email(client, seeded_db, auth_headers):
    """POST /invoices/:id/remind returns 200 and dispatches send_email_task.delay."""
    from hubra.core.models.finance import Invoice
    from hubra.core.extensions import db

    today = date.today()
    invoice = Invoice(
        member_id=seeded_db["admin"].id,
        issued=today,
        due=today + timedelta(days=30),
        amount=Decimal("45.00"),
        status="Open",
    )
    db.session.add(invoice)
    db.session.commit()
    invoice_id = invoice.id

    with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as mock_delay:
        resp = client.post(
            f"/api/v1/finance/invoices/{invoice_id}/remind", headers=auth_headers
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    mock_delay.assert_called_once()


def test_remind_invoice_not_found(client, seeded_db, auth_headers):
    """POST /invoices/:id/remind on unknown invoice returns 404."""
    resp = client.post("/api/v1/finance/invoices/99999/remind", headers=auth_headers)
    assert resp.status_code == 404


# ── My invoices ───────────────────────────────────────────────────────────────


def test_list_my_invoices_returns_own_invoices(
    client, billable_tier_db, billed_auth_headers
):
    """GET /invoices/mine returns only the authenticated member's invoices."""
    from hubra.core.models.finance import Invoice
    from hubra.core.extensions import db

    today = date.today()
    invoice = Invoice(
        member_id=billable_tier_db["member_billed"].id,
        issued=today,
        due=today + timedelta(days=30),
        amount=Decimal("99.00"),
        status="Open",
    )
    db.session.add(invoice)
    db.session.commit()

    resp = client.get("/api/v1/finance/invoices/mine", headers=billed_auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "data" in body
    assert len(body["data"]) >= 1
    for item in body["data"]:
        assert item["member_id"] == billable_tier_db["member_billed"].id


def test_list_my_invoices_requires_auth(client):
    """GET /invoices/mine without auth returns 401."""
    resp = client.get("/api/v1/finance/invoices/mine")
    assert resp.status_code == 401


def test_delete_invoice_that_was_mailed(client, auth_headers, seeded_db, db):
    """An invoice with send history (every generated invoice has one) can be
    deleted; its history goes with it."""
    from hubra.core.models.finance import Invoice
    from hubra.core.models.invoice_reminder import InvoiceReminderHistory

    invoice = Invoice(
        member_id=seeded_db["admin"].id,
        issued=date.today(),
        due=date.today() + timedelta(days=30),
        amount=Decimal("45.00"),
        status="Open",
    )
    db.session.add(invoice)
    db.session.flush()
    db.session.add(
        InvoiceReminderHistory(
            invoice_id=invoice.id,
            reminder_type="generation",
            recipient_email="admin@test.ch",
            recipient_name="Test Admin",
        )
    )
    db.session.commit()
    invoice_id = invoice.id

    resp = client.delete(f"/api/v1/finance/invoices/{invoice_id}", headers=auth_headers)
    assert resp.status_code == 204

    db.session.expunge_all()
    assert db.session.get(Invoice, invoice_id) is None
    assert (
        db.session.query(InvoiceReminderHistory).filter_by(invoice_id=invoice_id).count()
        == 0
    )


def test_delete_transaction_of_a_mailed_invoice(client, auth_headers, seeded_db, db):
    """Deleting a transaction deletes its invoice, and with it the invoice's
    send history."""
    from hubra.core.models.finance import Invoice, Transaction, TransactionCategory
    from hubra.core.models.invoice_reminder import InvoiceReminderHistory

    category = TransactionCategory(name="Beiträge", color="#123456")
    db.session.add(category)
    db.session.flush()
    tx = Transaction(
        category_id=category.id,
        date=date.today(),
        description="Beitrag",
        method="Bank Transfer",
        amount=Decimal("45.00"),
        type="income",
        status="Pending",
    )
    db.session.add(tx)
    db.session.flush()
    invoice = Invoice(
        member_id=seeded_db["admin"].id,
        issued=date.today(),
        due=date.today() + timedelta(days=30),
        amount=Decimal("45.00"),
        status="Open",
        transaction_id=tx.id,
    )
    db.session.add(invoice)
    db.session.flush()
    db.session.add(
        InvoiceReminderHistory(
            invoice_id=invoice.id,
            reminder_type="generation",
            recipient_email="admin@test.ch",
            recipient_name="Test Admin",
        )
    )
    db.session.commit()
    tx_id, invoice_id = tx.id, invoice.id

    resp = client.delete(f"/api/v1/finance/transactions/{tx_id}", headers=auth_headers)
    assert resp.status_code == 204

    db.session.expunge_all()
    assert db.session.get(Transaction, tx_id) is None
    assert db.session.get(Invoice, invoice_id) is None
    assert (
        db.session.query(InvoiceReminderHistory).filter_by(invoice_id=invoice_id).count()
        == 0
    )
