"""Payment plans per tier: pricing, periods, API and invoice generation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.finance import Invoice
from hubra.core.models.payment_plan import PaymentPlan
from hubra.core.pricing import apply_plan, billing_cycle_for, period_window


def _tier(price="120", cycle="yearly", tid=1):
    return SimpleNamespace(
        id=tid, price_chf=Decimal(price), billing_cycle=cycle, price_type="fixed"
    )


def test_apply_plan_splits_and_rounds_to_5_rappen():
    tier = _tier("100")
    quarterly = SimpleNamespace(tier_id=1, interval="quarterly", surcharge_pct=3)
    # 100 * 1.03 / 4 = 25.75
    assert apply_plan(Decimal("100"), tier, quarterly) == Decimal("25.75")
    monthly = SimpleNamespace(tier_id=1, interval="monthly", surcharge_pct=0)
    # 100 / 12 = 8.333 → 8.35
    assert apply_plan(Decimal("100"), tier, monthly) == Decimal("8.35")
    # Monthly tier of 10 → yearly plan 120.
    yearly = SimpleNamespace(tier_id=1, interval="yearly", surcharge_pct=0)
    assert apply_plan(Decimal("10"), _tier("10", "monthly"), yearly) == Decimal("120")


def test_plan_of_another_tier_is_ignored():
    tier = _tier()
    member = SimpleNamespace(
        payment_plan=SimpleNamespace(tier_id=99, interval="monthly")
    )
    assert billing_cycle_for(member, tier) == "yearly"


@pytest.mark.parametrize(
    "cycle,start,end",
    [
        ("quarterly", date(2026, 4, 1), date(2026, 6, 30)),
        ("half_yearly", date(2026, 1, 1), date(2026, 6, 30)),
        ("monthly", date(2026, 5, 1), date(2026, 5, 31)),
        ("yearly", date(2026, 1, 1), date(2026, 12, 31)),
    ],
)
def test_period_window(cycle, start, end):
    assert period_window(date(2026, 5, 17), cycle) == (start, end)


@pytest.fixture
def tier(db, seeded_db):
    t = seeded_db["tier"]
    t.price_chf = Decimal("120")
    t.price_type = "fixed"
    t.billing_cycle = "yearly"
    db.session.commit()
    return t


def test_plan_crud_and_member_choice(client, db, auth_headers, tier, seeded_db):
    resp = client.post(
        f"/api/v1/tiers/{tier.id}/plans",
        json={"name": "Quarterly", "interval": "quarterly", "surcharge_pct": 5},
    )
    assert resp.status_code == 201
    plan_id = resp.get_json()["id"]
    hidden = client.post(
        f"/api/v1/tiers/{tier.id}/plans",
        json={"name": "Monthly", "interval": "monthly", "visible": False},
    ).get_json()["id"]
    assert (
        client.post(
            f"/api/v1/tiers/{tier.id}/plans", json={"name": "x", "interval": "weekly"}
        ).status_code
        == 400
    )

    tiers = client.get("/api/v1/tiers/").get_json()
    assert [p["name"] for p in tiers[0]["payment_plans"]] == ["Quarterly", "Monthly"]

    options = client.get("/api/v1/tiers/my-plan").get_json()
    assert options["tier"]["amount"] == 120.0
    assert [(p["name"], p["amount"]) for p in options["plans"]] == [("Quarterly", 31.5)]

    assert (
        client.put("/api/v1/tiers/my-plan", json={"plan_id": hidden}).status_code == 403
    )
    chosen = client.put("/api/v1/tiers/my-plan", json={"plan_id": plan_id})
    assert chosen.get_json()["current_plan_id"] == plan_id

    # An admin can put a member on a hidden plan.
    admin_id = seeded_db["admin"].id
    resp = client.put(
        f"/api/v1/tiers/members/{admin_id}/plan", json={"plan_id": hidden}
    )
    assert resp.get_json()["current_plan_id"] == hidden

    # Deleting the plan moves the member back to the tier cycle.
    assert client.delete(f"/api/v1/tiers/plans/{hidden}").status_code == 204
    assert client.get("/api/v1/tiers/my-plan").get_json()["current_plan_id"] is None


def test_invoice_generation_uses_plan(app, db, tier, seeded_db):
    from hubra.core.tasks.finance_tasks import _generate_invoices

    plan = PaymentPlan(tier_id=tier.id, name="Q", interval="quarterly")
    db.session.add(plan)
    db.session.flush()
    member = seeded_db["admin"]
    member.status = "active"
    member.payment_plan_id = plan.id
    db.session.commit()

    with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
        first = _generate_invoices()
        again = _generate_invoices()
    assert first["created"] == 1 and again["created"] == 0
    amounts = db.session.scalars(
        select(Invoice.amount).where(Invoice.member_id == member.id)
    ).all()
    assert amounts == [Decimal("30.00")]


def test_cost_preview_refuses_a_tier_id_that_is_not_an_id(
    client, auth_headers, tier
):
    for tier_id in ({"a": 1}, [1], True):
        resp = client.post("/api/v1/tiers/calculate-cost", json={"tier_id": tier_id})
        assert resp.status_code == 400, tier_id
    resp = client.post("/api/v1/tiers/calculate-cost", json={"tier_id": "1"})
    assert resp.status_code == 200
