"""Fee run preview: what the daily invoice run would bill, before it does."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from hubra.core.models.member import Member
from tests.helpers import add_member

URL = "/api/v1/finance/invoices/fee-run-preview"


def test_preview_matches_what_the_run_bills(app, billable_tier_db):
    from hubra.api.finance.fee_run import preview
    from hubra.core.tasks.finance_tasks import generate_invoices_task

    with app.app_context():
        before = preview(date.today())
        assert before["count"] == 1
        assert before["total"] == 99.0
        assert before["tiers"] == [
            {
                "tierId": billable_tier_db["billable_tier"].id,
                "tier": "Premium",
                "count": 1,
                "total": 99.0,
            }
        ]
        line = before["lines"][0]
        assert line["memberId"] == billable_tier_db["member_billed"].id
        assert line["amount"] == 99.0
        assert line["noEmail"] is False
        assert before["skipped"] == {}  # members without a tier are not counted
        assert before["dueOn"] == (date.today() + timedelta(days=30)).isoformat()

        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            result = generate_invoices_task.run()
        assert result["created"] == before["count"]

        after = preview(date.today())
        assert after["count"] == 0
        assert after["total"] == 0.0
        assert after["skipped"].get("invoice_exists_for_period") == 1
        assert after["lastTwelveMonths"] == {"count": 1, "total": 99.0}


def test_preview_writes_nothing(app, billable_tier_db):
    from hubra.api.finance.fee_run import preview
    from hubra.core.extensions import db
    from hubra.core.models.finance import Invoice
    from sqlalchemy import func, select

    with app.app_context():
        preview(date.today())
        assert db.session.scalar(select(func.count(Invoice.id))) == 0


def _yearly_member(client, db, auth_headers, seeded_db):
    tier = seeded_db["tier"]
    tier.price_chf = Decimal("120")
    tier.price_type = "fixed"
    tier.billing_cycle = "yearly"
    db.session.commit()
    created = add_member(
        client,
        auth_headers,
        email="anna@test.ch",
        first_name="Anna",
        last_name="Student",
        status="active",
        tier=tier.name,
    )
    assert created.status_code == 200, created.get_json()
    member = db.session.get(Member, int(created.get_json()["id"]))
    member.tier_id = tier.id
    member.joined = date(2020, 1, 1)
    member.status = "active"
    db.session.commit()
    return member.id


def test_route_returns_the_preview(client, db, auth_headers, seeded_db):
    anna = _yearly_member(client, db, auth_headers, seeded_db)
    res = client.get(URL, headers=auth_headers)
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert anna in [line["memberId"] for line in body["lines"]]
    assert body["on"] == date.today().isoformat()
    assert body["truncated"] is False

    later = client.get(f"{URL}?on=2030-01-15", headers=auth_headers).get_json()
    assert later["on"] == "2030-01-15"


def test_route_rejects_a_bad_date(client, auth_headers):
    res = client.get(f"{URL}?on=tomorrow", headers=auth_headers)
    assert res.status_code == 400


def test_route_needs_sign_in(client, seeded_db):
    assert client.get(URL).status_code == 401


def test_route_needs_the_bulk_invoice_right(client, db, auth_headers, seeded_db):
    _yearly_member(client, db, auth_headers, seeded_db)
    client.post(
        "/api/v1/auth/login",
        json={"email": "anna@test.ch", "password": "Member-Pass-123!"},
    )
    assert client.get(URL).status_code == 403
