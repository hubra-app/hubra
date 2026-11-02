"""What a club pays: terms per club, the monthly sum, sponsor and add-ons
(services/club_billing.py).  Stored and shown only, nothing is charged."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from hubra.core.errors import ApiError
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.services import club_billing, plans

TODAY = date(2026, 11, 2)


@pytest.fixture
def club(db):
    tenant = Tenant(name="Club A", slug="club-a", status="active", settings={})
    db.session.add(tenant)
    db.session.commit()
    return tenant


def _price(db, plan="starter", value="40"):
    plans.update(plans.get(plan), {"price_month_chf": value})
    db.session.commit()


def test_defaults_without_terms(db, club):
    s = club_billing.summary(club, TODAY)
    assert s["status"] == "none"
    assert s["plan_price_chf"] is None
    assert s["total_chf"] == "0.00" and s["due_chf"] == "0.00"
    assert s["sponsorship_running"] is False


def test_list_price_discount_and_addons(db, club):
    _price(db, value="40")
    club_billing.update(
        club,
        {
            "status": "active",
            "discount_percent": 25,
            "addons": [
                {"code": "discord", "label": "Discord", "price_chf": 5},
                {"code": "bank-import", "price_chf": "7.5"},
            ],
        },
    )
    s = club_billing.summary(club, TODAY)
    assert s["plan_price_chf"] == "40.00"
    assert s["base_chf"] == "40.00"
    assert s["discount_chf"] == "10.00"  # not on the add-ons
    assert s["addons_chf"] == "12.50"
    assert s["total_chf"] == "42.50" and s["due_chf"] == "42.50"
    assert s["addons"][1] == {
        "code": "bank-import",
        "label": "",
        "price_chf": "7.50",
    }


def test_own_price_beats_list_price(db, club):
    _price(db, value="40")
    club_billing.update(club, {"status": "active", "price_chf": "19.999"})
    s = club_billing.summary(club, TODAY)
    assert s["price_chf"] == "20.00" and s["total_chf"] == "20.00"
    club_billing.update(club, {"price_chf": None})
    assert club_billing.summary(club, TODAY)["total_chf"] == "40.00"


def test_sponsored_club_pays_nothing_until_the_end(db, club):
    _price(db, value="40")
    club_billing.update(
        club,
        {
            "status": "active",
            "sponsored": True,
            "sponsor_name": "Kantonalbank",
            "sponsored_until": "2026-11-20",
        },
    )
    s = club_billing.summary(club, TODAY)
    assert s["sponsorship_running"] and s["sponsorship_days_left"] == 18
    assert s["sponsorship_ending_soon"] is True
    assert s["total_chf"] == "40.00" and s["due_chf"] == "0.00"

    later = club_billing.summary(club, date(2026, 11, 21))
    assert later["sponsorship_running"] is False
    assert later["sponsorship_ended"] is True
    assert later["due_chf"] == "40.00"

    club_billing.update(club, {"sponsored_until": None})  # open-ended
    s = club_billing.summary(club, date(2030, 1, 1))
    assert s["sponsorship_running"] and s["sponsorship_days_left"] is None
    assert s["sponsorship_ending_soon"] is False


def test_trial_days_left(db, club):
    club_billing.update(club, {"status": "trialing", "trial_ends": "2026-11-16"})
    assert club_billing.summary(club, TODAY)["trial_days_left"] == 14
    club_billing.update(club, {"status": "active"})
    assert club_billing.summary(club, TODAY)["trial_days_left"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"status": "free"},
        {"price_chf": -1},
        {"price_chf": "lots"},
        {"price_chf": True},
        {"price_chf": 1_000_000},
        {"discount_percent": 101},
        {"discount_percent": "10"},
        {"trial_ends": "next week"},
        {"sponsored": "yes"},
        {"sponsored": True},  # no sponsor name
        {"note": "x" * 1001},
        {"addons": "discord"},
        {"addons": [{"label": "no code"}]},
        {"addons": [{"code": "a"}, {"code": "a"}]},
        {"plan": "enterprise"},  # not a billing field
        [],
    ],
)
def test_bad_values_are_refused(db, club, body):
    with pytest.raises(ApiError) as err:
        club_billing.update(club, body)
    assert err.value.status == 400
    assert club_billing.stored(club) == club_billing.DEFAULTS


def test_billing_api(client, staff_headers, db, club):
    _price(db, value="40")
    url = f"/api/v1/system/tenants/{club.id}/billing"
    assert client.get(url).get_json()["status"] == "none"

    resp = client.patch(url, json={"status": "active", "discount_percent": 50})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["total_chf"] == "20.00"
    db.session.refresh(club)
    assert club.settings["billing"]["discount_percent"] == 50.0
    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.billing")
    )
    assert entry.tenant_id == club.id
    assert entry.details == {
        "status": {"before": "none", "after": "active"},
        "discount_percent": {"before": 0, "after": 50.0},
    }

    assert client.patch(url, json={"discount_percent": 200}).status_code == 400
    assert client.patch(url, json={}).status_code == 400
    assert client.get("/api/v1/system/tenants/9999/billing").status_code == 404


def test_billing_api_needs_platform_rights(client, auth_headers, club):
    url = f"/api/v1/system/tenants/{club.id}/billing"
    assert client.get(url).status_code in (401, 403)
    assert client.patch(url, json={"status": "active"}).status_code in (401, 403)


@pytest.mark.parametrize("bad", ["cheap", "-5", "nan", True, "200000"])
def test_plan_price_is_validated(db, bad):
    with pytest.raises(ApiError):
        plans.update(plans.get("starter"), {"price_month_chf": bad})


def test_plan_price_takes_francs_and_rappen(db, club):
    _price(db, value="29.5")
    assert club_billing.plan_price("starter") == "29.50"
    assert club_billing.plan_price("growth") is None
