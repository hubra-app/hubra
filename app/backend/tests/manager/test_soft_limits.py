"""Soft member limit: a grace period at the limit and the plan that fits
(services/quotas.py, GET /app/billing/limits)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from hubra.core.errors import ApiError
from hubra.core.models.tenant import Tenant
from hubra.core.services import plans, platform_settings, quotas
from tests.authz.conftest import (  # noqa: F401
    _login_member,
    plain_member_token,
)


@pytest.fixture
def club(db):
    tenant = Tenant(
        name="Club A",
        slug="club-a",
        plan="starter",
        status="active",
        settings={},
    )
    db.session.add(tenant)
    plans.update(
        plans.get("starter"),
        {"limit_members": 10, "price_month_chf": "20", "selectable": True},
    )
    plans.update(
        plans.get("growth"),
        {"limit_members": 100, "price_month_chf": "60", "selectable": True},
    )
    plans.update(
        plans.get("enterprise"),
        {"limit_members": None, "price_month_chf": "200", "selectable": True},
    )
    db.session.commit()
    return tenant


def _full(monkeypatch, n=10):
    monkeypatch.setattr(quotas, "member_count", lambda tenant=None: n)
    monkeypatch.setattr(
        quotas,
        "usage",
        lambda tenants: {
            t.id: {"members": n, "mail_month": 0, "storage_mb": 0} for t in tenants
        },
    )


def test_grace_lets_members_join_then_stops(db, club, monkeypatch):
    _full(monkeypatch)
    start = quotas._now()
    quotas.ensure_room_for_member(club)  # starts the grace period
    until = quotas.grace_until(club)
    assert until == quotas._over_since(club) + timedelta(days=14)
    assert until > start
    quotas.ensure_room_for_member(club)  # still within it

    monkeypatch.setattr(quotas, "_now", lambda: until + timedelta(minutes=1))
    with pytest.raises(ApiError) as err:
        quotas.ensure_room_for_member(club)
    assert err.value.code == "MEMBER_LIMIT_REACHED"


def test_zero_days_is_a_hard_stop(db, club, monkeypatch):
    platform_settings.set_many({"limits.grace_days": "0"})
    _full(monkeypatch)
    with pytest.raises(ApiError):
        quotas.ensure_room_for_member(club)
    assert quotas.grace_until(club) is None


def test_under_the_limit_again_ends_the_grace(db, club, monkeypatch):
    _full(monkeypatch)
    quotas.ensure_room_for_member(club)
    assert quotas._over_since(club) is not None
    quotas.check_tenant(club, {"members": 5, "mail_month": 0, "storage_mb": 0})
    assert quotas._over_since(club) is None


def test_a_bigger_plan_ends_the_grace(db, club, monkeypatch):
    from hubra.core.billing import self_service

    _full(monkeypatch)
    quotas.ensure_room_for_member(club)
    assert self_service.choose_plan(club, "growth") is True
    assert quotas._over_since(club) is None


def test_bad_grace_days_are_refused(db):
    for bad in ("-1", "91", "two"):
        with pytest.raises(platform_settings.PlatformSettingError):
            platform_settings.set_many({"limits.grace_days": bad})


def test_suggests_the_cheapest_plan_that_fits(db, club, monkeypatch):
    _full(monkeypatch, 9)  # 90 %: near the limit
    suggestion = quotas.suggest_plan(club)
    assert suggestion["key"] == "growth"
    assert suggestion["limits"]["members"] == 100
    assert suggestion["price_month_chf"] == plans.month_price("growth")

    # Growth too small: enterprise (no limit) fits.
    _full(monkeypatch, 95)
    assert quotas.suggest_plan(club)["key"] == "enterprise"

    # Room left: nothing to suggest.
    _full(monkeypatch, 3)
    assert quotas.suggest_plan(club) is None


def test_plans_a_club_cannot_pick_are_not_suggested(db, club, monkeypatch):
    plans.update(plans.get("growth"), {"selectable": False})
    db.session.commit()
    _full(monkeypatch, 9)
    assert quotas.suggest_plan(club)["key"] == "enterprise"


def test_club_admins_read_their_limits(
    client,
    db,
    club,
    auth_headers,
    plain_member_token,  # noqa: F811
    monkeypatch,
):
    from hubra.api.billing import routes

    monkeypatch.setattr(routes, "current_tenant", lambda: club)
    _full(monkeypatch)
    quotas.ensure_room_for_member(club)
    db.session.commit()
    _login_member(client, "admin@test.ch")
    body = client.get("/api/v1/app/billing/limits").get_json()
    assert body["code"] == "LIMIT_NEAR"
    assert body["limits"]["members"]["level"] == "over"
    assert body["grace_days"] == 14 and body["grace_until"]
    assert body["suggestion"]["key"] == "growth"


def test_limits_need_the_billing_right(
    app,
    client,
    db,
    club,
    auth_headers,
    plain_member_token,  # noqa: F811
    monkeypatch,
):
    from hubra.api.billing import routes

    monkeypatch.setattr(routes, "current_tenant", lambda: club)
    assert app.test_client().get("/api/v1/app/billing/limits").status_code == 401
    _login_member(client, "plain@test.ch")
    assert client.get("/api/v1/app/billing/limits").status_code == 403
