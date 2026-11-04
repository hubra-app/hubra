"""Plans and add-ons with list prices, set in manage, and the public pricing
and plugin list the website reads (services/plans.py)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.services import club_billing, plans, quotas

P = "/api/v1/manager/platform"


def test_defaults_exist(db):
    assert [p.key for p in plans.all_plans()] == ["starter", "growth", "enterprise"]
    assert plans.assignable("growth") and not plans.assignable("gold")


def test_create_edit_and_public_pricing(client, staff_headers, db):
    resp = client.post(
        f"{P}/plans",
        json={
            "key": "verein-plus",
            "name_de": "Verein Plus",
            "name_en": "Club Plus",
            "price_month_chf": "19.9",
            "price_year_chf": 199,
            "features": [{"de": "Bis 200 Mitglieder", "en": "Up to 200 members"}],
            "limit_members": 200,
            "public": True,
            "highlighted": True,
        },
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["price_month_chf"] == "19.90" and body["sort"] == 4
    assert body["limits"]["members"] == 200 and body["clubs"] == 0

    pub = client.get("/api/v1/public/pricing")
    assert pub.status_code == 200
    assert pub.headers["Access-Control-Allow-Origin"] == "*"
    assert "max-age" in pub.headers["Cache-Control"]
    keys = [p["key"] for p in pub.get_json()["plans"]]
    assert keys == ["verein-plus"]  # the built-in three are not public yet
    assert "clubs" not in pub.get_json()["plans"][0]

    client.patch(f"{P}/plans/verein-plus", json={"hidden": True})
    assert client.get("/api/v1/public/pricing").get_json()["plans"] == []
    assert not plans.assignable("verein-plus")
    actions = set(db.session.scalars(select(GlobalAuditEntry.action)).all())
    assert {"platform.plan.created", "platform.plan.updated"} <= actions


@pytest.mark.parametrize(
    "body",
    [
        {"key": "Gold", "name_de": "Gold"},
        {"key": "starter", "name_de": "Again"},
        {"key": "gold"},  # no name
        {"key": "gold", "name_de": "Gold", "price_month_chf": -1},
        {"key": "gold", "name_de": "Gold", "limit_members": "many"},
        {"key": "gold", "name_de": "Gold", "public": "yes"},
        {"key": "gold", "name_de": "Gold", "features": "all"},
        {"key": "gold", "name_de": "Gold", "colour": "gold"},
    ],
)
def test_bad_plans_are_refused(client, staff_headers, body):
    assert client.post(f"{P}/plans", json=body).status_code in (400, 409)


def test_plan_in_use_is_hidden_not_deleted(client, staff_headers, db):
    db.session.add(Tenant(name="A", slug="a", status="active", plan="growth"))
    db.session.commit()
    assert client.delete(f"{P}/plans/growth").status_code == 409
    client.post(f"{P}/plans", json={"key": "spare", "name_de": "Spare"})
    assert client.delete(f"{P}/plans/spare").status_code == 204
    assert plans.get("spare") is None


def test_plan_limits_and_price_reach_the_club(db):
    tenant = Tenant(name="A", slug="a", status="active", plan="starter", settings={})
    db.session.add(tenant)
    plans.update(plans.get("starter"), {"limit_members": 30, "price_month_chf": 25})
    db.session.commit()
    assert quotas.limits_for(tenant)["members"] == 30
    summary = club_billing.summary(tenant)
    assert summary["plan_price_chf"] == "25.00"


def test_club_can_get_a_private_plan(client, staff_headers, db):
    tenant = Tenant(name="A", slug="a", status="active", plan="starter", settings={})
    db.session.add(tenant)
    db.session.commit()
    client.post(f"{P}/plans", json={"key": "deal-a", "name_de": "Sonderpreis A"})
    resp = client.patch(f"/api/v1/system/tenants/{tenant.id}", json={"plan": "deal-a"})
    assert resp.status_code == 200, resp.get_json()
    choices = client.get("/api/v1/system/plans").get_json()["plans"]
    assert "deal-a" in [p["key"] for p in choices]
    assert client.patch(
        f"/api/v1/system/tenants/{tenant.id}", json={"plan": "nope"}
    ).status_code in (400, 422)


def test_addon_prices_and_public_list(client, staff_headers, db):
    rows = client.get(f"{P}/plans").get_json()["addons"]
    code = rows[0]["code"]
    resp = client.put(
        f"{P}/addons/{code}",
        json={"price_month_chf": "5", "public": True, "label_de": "Extra"},
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["price_month_chf"] == "5.00"
    addons = client.get("/api/v1/public/pricing").get_json()["addons"]
    assert addons == [
        {
            "code": code,
            "name_de": "Extra",
            "name_en": rows[0]["name"],
            "note_de": rows[0]["description"],
            "note_en": rows[0]["description"],
            "plugin": rows[0]["plugin"],
            "price_month_chf": "5.00",
            "price_unit": "flat",
            "included_in": [],
        }
    ]
    assert client.put(f"{P}/addons/nope", json={}).status_code == 404
    assert client.put(f"{P}/addons/{code}", json={"public": 1}).status_code == 400


def test_public_plugins_needs_no_sign_in(client):
    resp = client.get("/api/v1/public/plugins", headers={"Origin": "https://x.ch"})
    assert resp.status_code == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert isinstance(resp.get_json()["plugins"], list)


def test_public_pricing_answers_any_origin_without_cookies(client):
    resp = client.get(
        "/api/v1/public/pricing", headers={"Origin": "https://hubra.club"}
    )
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert "Access-Control-Allow-Credentials" not in resp.headers


def test_manage_routes_need_platform_rights(client, auth_headers):
    assert client.get(f"{P}/plans").status_code in (401, 403)
    assert client.post(f"{P}/plans", json={}).status_code in (401, 403)


def _two_modules(client):
    rows = client.get(f"{P}/plans").get_json()["addons"]
    return rows[0]["code"], rows[1]["code"]


def test_plan_includes_modules_with_or_without_a_price(client, staff_headers, db):
    free, paid = _two_modules(client)
    resp = client.patch(
        f"{P}/plans/starter",
        json={
            "public": True,
            "modules": [
                {"code": free},
                {"code": paid, "price_chf": "0.5", "unit": "member"},
            ],
        },
    )
    assert resp.status_code == 200, resp.get_json()
    mods = resp.get_json()["modules"]
    assert [(m["code"], m["included"], m["price_chf"], m["unit"]) for m in mods] == [
        (free, True, None, "flat"),
        (paid, False, "0.50", "member"),
    ]
    assert mods[0]["name_de"] and mods[0]["name_en"]

    # The add-on list says which plans include a module.
    rows = {a["code"]: a for a in client.get(f"{P}/plans").get_json()["addons"]}
    assert rows[free]["included_in"] == ["starter"]

    client.put(
        f"{P}/addons/{free}",
        json={"price_month_chf": "3", "price_unit": "license", "public": True},
    )
    pub = client.get("/api/v1/public/pricing").get_json()
    assert [m["code"] for m in pub["plans"][0]["modules"]] == [free, paid]
    addon = next(a for a in pub["addons"] if a["code"] == free)
    assert addon["price_unit"] == "license" and addon["included_in"] == ["starter"]

    # A plan that is not public does not show up in included_in publicly.
    client.patch(f"{P}/plans/starter", json={"public": False})
    pub = client.get("/api/v1/public/pricing").get_json()
    assert next(a for a in pub["addons"] if a["code"] == free)["included_in"] == []


@pytest.mark.parametrize(
    "modules",
    [
        "all",
        [{"code": "nope"}],
        [{"code": "@0"}, {"code": "@0"}],
        [{"code": "@0", "unit": "seat"}],
        [{"code": "@0", "price_chf": -2}],
        [{"code": "@0", "colour": "red"}],
    ],
)
def test_bad_plan_modules_are_refused(client, staff_headers, modules):
    code, _ = _two_modules(client)
    if isinstance(modules, list):
        modules = [
            {k: (code if v == "@0" else v) for k, v in m.items()} for m in modules
        ]
    resp = client.patch(f"{P}/plans/starter", json={"modules": modules})
    assert resp.status_code == 400


def test_addon_unit_is_validated(client, staff_headers):
    code, _ = _two_modules(client)
    assert (
        client.put(f"{P}/addons/{code}", json={"price_unit": "seat"}).status_code == 400
    )
    resp = client.put(f"{P}/addons/{code}", json={"price_unit": "member"})
    assert resp.get_json()["price_unit"] == "member"
