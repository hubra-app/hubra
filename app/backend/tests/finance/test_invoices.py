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
    from vollbuild.core.models.finance import Invoice
    from vollbuild.core.extensions import db

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
    from vollbuild.core.models.finance import Invoice
    from vollbuild.core.extensions import db

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

    with patch("vollbuild.core.tasks.email_tasks.send_email_task.delay") as mock_delay:
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
    from vollbuild.core.models.finance import Invoice
    from vollbuild.core.extensions import db

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
