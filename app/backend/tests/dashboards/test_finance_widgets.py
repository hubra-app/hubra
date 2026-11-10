"""Finance's dashboard widgets: invoice ageing and expected income."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from hubra.core.models.finance import Invoice
from tests.authz.conftest import (  # noqa: F401
    _login_member,
    permissioned_member_factory,
    plain_member_token,
)

URL = "/api/v1/app/dashboards/widgets"


def _invoice(db, due_in_days: int, amount: str, status: str = "Open") -> None:
    today = date.today()
    db.session.add(
        Invoice(
            issued=today - timedelta(days=120),
            due=today + timedelta(days=due_in_days),
            amount=Decimal(amount),
            status=status,
            purpose="other",
        )
    )


def test_invoice_ageing_groups_open_invoices(client, db, seeded_db, auth_headers):
    _invoice(db, 5, "50")
    _invoice(db, -10, "20")
    _invoice(db, -12, "30")
    _invoice(db, -100, "80")
    _invoice(db, -40, "999", status="Paid")
    db.session.commit()
    resp = client.post(
        f"{URL}/finance.invoices.ageing/data", json={}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.get_json()
    items = resp.get_json()["data"]["items"]
    labels = [i["label"] for i in items]
    assert len(items) == 3
    assert "2" in items[1]["sub"] and "50.00" in items[1]["sub"]
    assert labels[0] in ("Noch nicht fällig", "Not due yet")


def test_expected_income_counts_open_invoices_due_this_month(
    client, db, seeded_db, auth_headers
):
    _invoice(db, -3, "40")
    _invoice(db, 0, "60")
    _invoice(db, 60, "500")  # next months
    _invoice(db, 0, "999", status="Paid")
    db.session.commit()
    resp = client.post(
        f"{URL}/finance.invoices.expected/data", json={}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()["data"]
    assert data["value"] == "CHF 100.00"
    assert data["sub"].startswith("2 ")


def test_members_without_invoice_rights_get_no_finance_widgets(
    client,
    plain_member_token,  # noqa: F811
):
    names = {
        w["name"]
        for w in client.get(URL, headers=plain_member_token).get_json()["items"]
    }
    assert not names & {"finance.invoices.ageing", "finance.invoices.expected"}
    resp = client.post(
        f"{URL}/finance.invoices.expected/data", json={}, headers=plain_member_token
    )
    assert resp.status_code == 403
