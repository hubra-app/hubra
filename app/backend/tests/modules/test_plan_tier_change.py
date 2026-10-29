"""Moving a member to another tier drops the old tier's payment plan."""

from __future__ import annotations

from decimal import Decimal

import pytest


@pytest.fixture
def tier(db, seeded_db):
    t = seeded_db["tier"]
    t.price_chf = Decimal("120")
    t.price_type = "fixed"
    t.billing_cycle = "yearly"
    db.session.commit()
    return t


def test_changing_tier_drops_the_old_tiers_plan(
    client, db, auth_headers, tier, seeded_db
):
    from hubra.core.models.member import MembershipTier

    plan_id = client.post(
        f"/api/v1/tiers/{tier.id}/plans",
        json={"name": "Quarterly", "interval": "quarterly"},
    ).get_json()["id"]
    assert (
        client.put("/api/v1/tiers/my-plan", json={"plan_id": plan_id}).status_code
        == 200
    )
    other = MembershipTier(
        name="Youth", price_chf=Decimal("60"), billing_cycle="yearly"
    )
    db.session.add(other)
    db.session.commit()

    admin_id = seeded_db["admin"].id
    resp = client.patch(f"/api/v1/members/{admin_id}", json={"tier_id": other.id})
    assert resp.status_code == 200
    assert client.get("/api/v1/tiers/my-plan").get_json()["current_plan_id"] is None

    # Saving the member again without a tier change keeps a chosen plan.
    youth_plan = client.post(
        f"/api/v1/tiers/{other.id}/plans",
        json={"name": "Half", "interval": "half_yearly"},
    ).get_json()["id"]
    client.put("/api/v1/tiers/my-plan", json={"plan_id": youth_plan})
    client.patch(f"/api/v1/members/{admin_id}", json={"tier_id": other.id})
    assert (
        client.get("/api/v1/tiers/my-plan").get_json()["current_plan_id"] == youth_plan
    )


def test_plan_visibility_must_be_a_boolean(client, auth_headers, seeded_db):
    """bool("false") is True: a string used to show a hidden plan to members."""
    resp = client.post(
        f"/api/v1/tiers/{seeded_db['tier'].id}/plans",
        json={"name": "Monthly", "interval": "monthly", "visible": "false"},
    )
    assert resp.status_code == 400
