"""Plans that build on another plan (each tier includes the one below it),
and custom plans offered to chosen clubs (services/plans.py)."""

from __future__ import annotations

import pytest

from hubra.core.errors import ApiError
from hubra.core.models.tenant import Tenant
from hubra.core.services import licenses, plans

P = "/api/v1/manager/platform"


def _codes(plan) -> dict[str, str | None]:
    return {m["code"]: m["inherited_from"] for m in plans.plan_json(plan)["modules"]}


def test_a_plan_includes_the_modules_of_the_plan_it_builds_on(db):
    starter = plans.get("starter")
    growth = plans.get("growth")
    enterprise = plans.get("enterprise")
    plans.update(starter, {"modules": [{"code": "polls"}]})
    plans.update(growth, {"modules": [{"code": "groups"}], "builds_on": "starter"})
    plans.update(
        enterprise,
        {
            "modules": [{"code": "posts", "price_chf": "3", "unit": "license"}],
            "builds_on": "growth",
        },
    )

    assert _codes(starter) == {"polls": None}
    assert _codes(growth) == {"polls": "starter", "groups": None}
    assert _codes(enterprise) == {
        "polls": "starter",
        "groups": "growth",
        "posts": None,
    }
    assert plans.plan_json(enterprise)["builds_on"] == "growth"
    # The add-on list and the public price list count inherited modules too.
    rows = {r["code"]: r["included_in"] for r in plans.addon_rows()}
    assert rows["polls"] == ["starter", "growth", "enterprise"]

    # A change on the lower plan reaches the plans above it.
    plans.update(starter, {"modules": [{"code": "polls"}, {"code": "events"}]})
    assert "events" in _codes(enterprise)


def test_own_entry_wins_over_the_inherited_one(db):
    plans.update(
        plans.get("starter"),
        {"modules": [{"code": "polls", "price_chf": "2", "unit": "member"}]},
    )
    growth = plans.get("growth")
    plans.update(growth, {"builds_on": "starter", "modules": [{"code": "polls"}]})
    (polls,) = plans.plan_json(growth)["modules"]
    assert polls["included"] and polls["inherited_from"] is None


def test_existing_plans_stand_alone(db):
    plans.update(plans.get("starter"), {"modules": [{"code": "polls"}]})
    growth = plans.get("growth")
    assert growth.builds_on is None
    assert plans.plan_json(growth)["modules"] == []
    # Turning it off again.
    plans.update(growth, {"builds_on": "starter"})
    assert _codes(growth) == {"polls": "starter"}
    plans.update(growth, {"builds_on": None})
    assert _codes(growth) == {}


@pytest.mark.parametrize(
    "key, base",
    [
        ("starter", "starter"),  # itself
        ("starter", "gold"),  # no such plan
        ("starter", "enterprise"),  # enterprise -> growth -> starter: a loop
        ("starter", 3),
    ],
)
def test_builds_on_is_checked(db, key, base):
    plans.update(plans.get("growth"), {"builds_on": "starter"})
    plans.update(plans.get("enterprise"), {"builds_on": "growth"})
    with pytest.raises(ApiError):
        plans.update(plans.get(key), {"builds_on": base})


def test_a_plan_others_build_on_is_not_deleted(client, staff_headers, db):
    resp = client.post(
        f"{P}/plans", json={"key": "basis", "name_de": "Basis"}, headers=staff_headers
    )
    assert resp.status_code == 201, resp.get_json()
    resp = client.patch(
        f"{P}/plans/growth", json={"builds_on": "basis"}, headers=staff_headers
    )
    assert resp.status_code == 200 and resp.get_json()["builds_on"] == "basis"
    resp = client.delete(f"{P}/plans/basis", headers=staff_headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "PLAN_IS_BASE"


def test_licences_count_inherited_paid_modules(db):
    tenant = Tenant(name="Club T", slug="club-t", status="active", settings={})
    db.session.add(tenant)
    plans.update(
        plans.get("starter"),
        {"modules": [{"code": "groups", "price_chf": "5", "unit": "license"}]},
    )
    plans.update(plans.get("growth"), {"builds_on": "starter"})
    tenant.plan = "growth"
    db.session.flush()
    assert licenses.licensed_modules(tenant) == {"groups": 1}


def test_custom_plan_lists_its_clubs(client, staff_headers, db):
    a = Tenant(name="Club A", slug="club-a", status="active", settings={})
    b = Tenant(name="Club B", slug="club-b", status="active", settings={})
    db.session.add_all([a, b])
    db.session.commit()
    resp = client.post(
        f"{P}/plans",
        json={"key": "deal-a", "name_de": "Deal A", "club_ids": [a.id, str(a.id)]},
        headers=staff_headers,
    )
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["club_ids"] == [a.id]
    plan = plans.get("deal-a")
    assert plans.offered_to(plan, a.id) and not plans.offered_to(plan, b.id)
    # Never on the website.
    keys = [p["key"] for p in client.get("/api/v1/public/pricing").get_json()["plans"]]
    assert "deal-a" not in keys

    bad = client.patch(
        f"{P}/plans/deal-a", json={"club_ids": [999999]}, headers=staff_headers
    )
    assert bad.status_code == 400
    bad = client.patch(
        f"{P}/plans/deal-a", json={"club_ids": "all"}, headers=staff_headers
    )
    assert bad.status_code == 400


def test_public_pricing_names_only_a_public_base(client, db):
    plans.update(plans.get("starter"), {"public": True})
    plans.update(plans.get("growth"), {"public": True, "builds_on": "starter"})
    plans.update(plans.get("enterprise"), {"public": True, "builds_on": "growth"})
    plans.update(plans.get("growth"), {"public": False})
    db.session.commit()
    rows = {
        p["key"]: p for p in client.get("/api/v1/public/pricing").get_json()["plans"]
    }
    assert rows["enterprise"]["builds_on"] is None
    plans.update(plans.get("growth"), {"public": True})
    db.session.commit()
