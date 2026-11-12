"""Per-club limits: plan defaults, a club's own limits, the member limit on
joining and the warnings (services/quotas.py)."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.notification import Notification
from hubra.core.models.platform_event import PlatformEvent
from hubra.core.models.role import Role
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.models.user_tenant import UserTenant
from hubra.core.services import platform_settings, quotas

H = {"X-Tenant-Slug": "club-a"}


@pytest.fixture
def club(db, seeded_db):
    tenant = Tenant(name="Club A", slug="club-a", status="active", settings={})
    db.session.add(tenant)
    db.session.flush()
    seeded_db["role"].is_default = False
    db.session.add(Role(name="Member", is_default=True))
    db.session.add(
        UserTenant(user_id=seeded_db["user"].id, tenant_id=tenant.id, is_owner=True)
    )
    db.session.commit()
    return tenant


def _plan(db, **values):
    from hubra.core.services import plans

    plans.update(plans.get("starter"), {f"limit_{k}": v for k, v in values.items()})
    db.session.commit()


def test_plan_limits_and_own_limits(db, club):
    assert quotas.limits_for(club) == {
        "members": None,
        "mail_month": None,
        "storage_mb": None,
    }
    _plan(db, members=50, mail_month=1000)
    assert quotas.limits_for(club) == {
        "members": 50,
        "mail_month": 1000,
        "storage_mb": None,
    }
    quotas.set_overrides(club, {"members": 80, "mail_month": None})
    assert quotas.limits_for(club) == {
        "members": 80,
        "mail_month": None,  # no limit for this club
        "storage_mb": None,
    }
    quotas.set_overrides(club, {"members": "plan"})
    assert quotas.limits_for(club)["members"] == 50


def test_bad_values_are_refused(db, club):
    for bad in ({"members": -1}, {"members": "10"}, {"members": True}, {"x": 1}):
        with pytest.raises(Exception) as err:
            quotas.set_overrides(club, bad)
        assert getattr(err.value, "status", None) == 400
    from hubra.core.services import plans

    with pytest.raises(Exception) as err:
        plans.update(plans.get("growth"), {"limit_members": "lots"})
    assert getattr(err.value, "status", None) == 400
    with pytest.raises(platform_settings.PlatformSettingError):
        platform_settings.set_many({"limits.warn_percent": "0"})
    # Settings written some other way that are not numbers are ignored.
    club.settings = {"limits": {"members": "ten", "storage_mb": 5}}
    assert quotas.overrides(club) == {"storage_mb": 5}


def test_status_levels(db, club):
    _plan(db, members=10, mail_month=100, storage_mb=50)
    s = quotas.status(club, {"members": 7, "mail_month": 80, "storage_mb": 60})
    rows = s["limits"]
    assert s["warn_percent"] == 80
    assert rows["members"]["level"] == "ok"
    assert rows["mail_month"] == {
        "used": 80,
        "limit": 100,
        "plan_limit": 100,
        "custom": False,
        "percent": 80,
        "level": "warning",
    }
    assert rows["storage_mb"]["level"] == "over"


def test_limits_api(sqlite_only, client, staff_headers, db, club):
    _plan(db, members=10)
    url = f"/api/v1/system/tenants/{club.id}/limits"
    body = client.get(url).get_json()
    assert body["plan"] == "starter"
    assert body["limits"]["members"]["limit"] == 10
    assert body["limits"]["members"]["used"] == 1

    resp = client.put(url, json={"members": 25, "storage_mb": None})
    assert resp.status_code == 200, resp.get_json()
    rows = resp.get_json()["limits"]
    assert rows["members"]["limit"] == 25 and rows["members"]["custom"] is True
    assert rows["members"]["plan_limit"] == 10
    assert rows["storage_mb"]["limit"] is None and rows["storage_mb"]["custom"]
    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.limits")
    )
    assert entry.details == {
        "before": {},
        "after": {"members": 25, "storage_mb": None},
    }

    assert client.put(url, json={"members": "many"}).status_code == 400
    assert client.put(url, json={}).status_code == 400
    assert client.get("/api/v1/system/tenants/9999/limits").status_code == 404


def test_limits_api_needs_platform_rights(client, auth_headers, club):
    url = f"/api/v1/system/tenants/{club.id}/limits"
    assert client.get(url).status_code in (401, 403)
    assert client.put(url, json={"members": 5}).status_code in (401, 403)


def test_a_full_club_takes_no_new_members(sqlite_only, app, client, db, seeded_db, club):
    club.settings = {"limits": {"members": 1}}  # the owner is the one member
    platform_settings.set_many({"limits.grace_days": "0"})  # a hard stop
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
        headers=H,
    )
    with patch("hubra.core.services.email._send") as send:
        resp = client.post("/api/v1/members/", json={"email": "new@test.ch"}, headers=H)
    assert resp.status_code == 202
    token = re.search(r"/invite#token=([\w-]+)", send.call_args.args[4]).group(1)

    person = app.test_client()
    assert (
        person.post(
            "/api/v1/auth/signup",
            json={
                "name": "Ines Invited",
                "email": "new@test.ch",
                "password": "VeryStrongPass123!",
            },
        ).status_code
        == 201
    )
    resp = person.post("/api/v1/system/invites/accept", json={"token": token})
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "MEMBER_LIMIT_REACHED"

    # Raised in manage: the same link works.
    club.settings = {"limits": {"members": 2}}
    db.session.commit()
    resp = person.post("/api/v1/system/invites/accept", json={"token": token})
    assert resp.status_code == 200, resp.get_json()


def _bell(db):
    return [
        (n.title, n.msg)
        for n in db.session.scalars(select(Notification).order_by(Notification.id))
    ]


def test_warnings_once_per_level(db, seeded_db, club):
    _plan(db, members=10)

    assert (
        quotas.check_tenant(club, {"members": 7, "mail_month": 0, "storage_mb": 0})
        == []
    )
    assert quotas.check_tenant(
        club, {"members": 8, "mail_month": 0, "storage_mb": 0}
    ) == [("members", "warning")]
    # Same level again: quiet.
    assert (
        quotas.check_tenant(club, {"members": 9, "mail_month": 0, "storage_mb": 0})
        == []
    )
    assert quotas.check_tenant(
        club, {"members": 10, "mail_month": 0, "storage_mb": 0}
    ) == [("members", "over")]
    # Back down to the warning level after "over": no new warning.
    assert (
        quotas.check_tenant(club, {"members": 9, "mail_month": 0, "storage_mb": 0})
        == []
    )
    db.session.commit()

    assert _bell(db) == [
        ("Club limit almost reached", "Members: 8 of 10."),
        ("Club limit reached", "Members: 10 of 10."),
    ]
    events = db.session.scalars(select(PlatformEvent).order_by(PlatformEvent.id)).all()
    assert [(e.category, e.kind, e.tenant_id) for e in events] == [
        ("system", "quota.warning", club.id),
        ("system", "quota.over", club.id),
    ]
    assert events[0].message == "Club A: Members: 8 of 10."

    # Below the warning level resets, so the next rise warns again.
    quotas.check_tenant(club, {"members": 2, "mail_month": 0, "storage_mb": 0})
    assert quotas.check_tenant(
        club, {"members": 8, "mail_month": 0, "storage_mb": 0}
    ) == [("members", "warning")]


def test_mail_warnings_start_again_each_month(db, seeded_db, club):
    from datetime import datetime, timezone

    _plan(db, mail_month=100)
    used = {"members": 1, "mail_month": 100, "storage_mb": 0}
    with patch.object(
        quotas, "_now", return_value=datetime(2026, 10, 30, tzinfo=timezone.utc)
    ):
        assert quotas.check_tenant(club, used) == [("mail_month", "over")]
        assert quotas.check_tenant(club, used) == []
    with patch.object(
        quotas, "_now", return_value=datetime(2026, 11, 2, tzinfo=timezone.utc)
    ):
        assert quotas.check_tenant(club, used) == [("mail_month", "over")]


def test_check_all_counts_mails_this_month(db, seeded_db, club):
    _plan(db, mail_month=2)
    for _ in range(2):
        db.session.add(
            PlatformEvent(
                category="mail",
                kind="mail.sent",
                level="info",
                tenant_id=club.id,
                message="sent",
            )
        )
    db.session.commit()
    result = quotas.check_all()
    assert result["changed"] == {"club-a": [("mail_month", "over")]}
    assert club.settings["limits_notified"]["mail_month"].endswith(":over")


def test_clubs_without_limits_are_skipped(db, club):
    assert quotas.check_all() == {"checked": 0, "changed": {}}


def test_bell_texts_are_translated():
    from hubra.core.services import notification_text

    assert notification_text.translate(
        "Club limit reached", "Storage: 61 MB of 50 MB.", "de-CH"
    ) == ("Vereinslimit erreicht", "Speicher: 61 MB von 50 MB.")
    assert notification_text.translate(
        "Club limit almost reached", "Mails this month: 80 of 100.", "de-CH"
    ) == ("Vereinslimit fast erreicht", "Mails diesen Monat: 80 von 100.")


# ── Largest file (file_mb) ───────────────────────────────────────────────────


def test_largest_file_comes_from_club_plan_or_default(app, db, club):
    from hubra.core.services import plans

    # No value anywhere: the platform's files.max_mb (25).
    assert quotas.file_limit(club) == {
        "limit": 25,
        "wanted": 25,
        "source": "default",
        "custom": False,
        "plan_limit": None,
        "default": 25,
        "ceiling": 100,
    }
    platform_settings.set_many({"files.max_mb": "10"})
    assert quotas.max_file_mb(club) == 10
    _plan(db, file_mb=50)
    assert quotas.file_limit(club)["source"] == "plan"
    assert quotas.max_file_mb(club) == 50
    quotas.set_overrides(club, {"file_mb": 5})
    assert quotas.file_limit(club)["source"] == "club"
    assert quotas.max_file_mb(club) == 5
    # The member/mail/storage limits are untouched by it.
    assert "file_mb" not in quotas.limits_for(club)
    quotas.set_overrides(club, {"file_mb": "plan"})
    assert quotas.max_file_mb(club) == 50
    # Capped at the server's upload ceiling.
    _plan(db, file_mb=500)
    app.config["MAX_UPLOAD_MB"] = 200
    try:
        row = quotas.file_limit(club)
        assert row["limit"] == 200 and row["wanted"] == 500
    finally:
        app.config["MAX_UPLOAD_MB"] = 100
    assert plans.plan_json(plans.get("starter"))["limits"]["file_mb"] == 500


def test_bad_file_sizes_are_refused(db, club):
    from hubra.core.services import plans

    for bad in (0, -1, None, "5", True, plans.MAX_FILE_MB + 1):
        with pytest.raises(Exception) as err:
            quotas.set_overrides(club, {"file_mb": bad})
        assert getattr(err.value, "status", None) == 400
    with pytest.raises(Exception) as err:
        plans.update(plans.get("growth"), {"limit_file_mb": 0})
    assert getattr(err.value, "status", None) == 400
    # Empty on the plan: back to the default.
    plans.update(plans.get("growth"), {"limit_file_mb": ""})
    assert plans.get("growth").limit_file_mb is None


def test_limits_api_sets_the_largest_file(sqlite_only, client, staff_headers, db, club):
    url = f"/api/v1/system/tenants/{club.id}/limits"
    body = client.get(url).get_json()
    assert body["file"]["limit"] == 25 and body["file"]["source"] == "default"
    resp = client.put(url, json={"file_mb": 40})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["file"]["limit"] == 40
    assert resp.get_json()["file"]["custom"] is True
    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.limits")
    )
    assert entry.details["after"] == {"file_mb": 40}
