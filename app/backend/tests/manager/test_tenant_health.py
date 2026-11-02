"""Club health at a glance: GET /api/v1/system/tenants/health."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hubra.core.models.platform_event import PlatformEvent
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant

URL = "/api/v1/system/tenants/health"


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
def clubs(db, seeded_db):
    quiet = Tenant(name="Quiet Club", slug="quiet", plan="starter", status="active")
    busy = Tenant(name="Busy Club", slug="busy", plan="growth", status="active")
    broken = Tenant(name="Broken Club", slug="broken", plan="starter", status="active")
    gone = Tenant(name="Gone", slug="gone", status="archived", deleted_at=_now())
    db.session.add_all([quiet, busy, broken, gone])
    db.session.flush()

    user = User(email="m@busy.ch", first_name="M", last_name="B", last_seen=_now())
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    db.session.add(UserTenant(user_id=user.id, tenant_id=busy.id))

    def event(tenant, kind, level="info", category="mail", ago=timedelta(hours=1)):
        db.session.add(
            PlatformEvent(
                created_at=_now() - ago,
                category=category,
                kind=kind,
                level=level,
                tenant_id=tenant.id,
                message=kind,
            )
        )

    event(busy, "mail.sent")
    event(busy, "mail.sent")
    event(busy, "mail.fallback")
    event(busy, "mail.sent", ago=timedelta(days=40))  # outside 30 days
    event(broken, "backup.failed", level="error", category="backup")
    event(broken, "mail.failed", level="warning")
    event(
        broken, "backup.failed", level="error", category="backup", ago=timedelta(days=2)
    )
    db.session.commit()
    return {"quiet": quiet, "busy": busy, "broken": broken}


def _by_slug(body):
    return {t["slug"]: t for t in body["tenants"]}


def test_health_columns(sqlite_only, client, staff_headers, clubs):
    resp = client.get(URL)
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    rows = _by_slug(body)
    assert "gone" not in rows

    busy = rows["busy"]["health"]
    assert busy["members"] == 1
    assert busy["active_members"] == 1
    assert busy["last_activity"] is not None
    assert busy["mail"] == {"sent": 3, "failed": 0}
    assert busy["alerts"] == {"warning": 0, "error": 0}
    assert busy["level"] == "ok"

    broken = rows["broken"]["health"]
    assert broken["alerts"] == {"warning": 1, "error": 1}
    assert broken["mail"]["failed"] == 1
    assert broken["level"] == "error"

    assert rows["quiet"]["health"]["level"] == "idle"
    assert body["counts"]["error"] == 1
    assert body["counts"]["idle"] >= 1


def test_filter_and_sort(client, staff_headers, clubs):
    body = client.get(URL, query_string={"health": "problems"}).get_json()
    assert [t["slug"] for t in body["tenants"]] == ["broken"]
    assert body["total"] == 1

    body = client.get(
        URL, query_string={"sort_by": "mail", "sort_dir": "desc", "per_page": 1}
    ).get_json()
    assert body["tenants"][0]["slug"] == "busy"
    assert body["per_page"] == 1

    assert client.get(URL, query_string={"sort_by": "nope"}).status_code == 400
    assert client.get(URL, query_string={"health": "nope"}).status_code == 400


def test_counts_plugins(client, staff_headers, clubs, db):
    from types import SimpleNamespace
    from unittest.mock import patch

    from hubra.core.models.feature import Feature, TenantFeature

    db.session.add(Feature(code="keys", name="Keys"))
    db.session.flush()
    db.session.add(TenantFeature(tenant_id=clubs["busy"].id, feature_code="keys"))
    db.session.commit()
    fake = [SimpleNamespace(code="keys", plugin="hubra-keys")]
    with patch("hubra.core.modules.registry.registry.all", return_value=fake):
        rows = _by_slug(client.get(URL).get_json())
    assert rows["busy"]["health"]["plugins"] == 1
    assert rows["quiet"]["health"]["plugins"] == 0


def test_needs_platform_rights(client, auth_headers, clubs):
    assert client.get(URL).status_code in (401, 403)


def test_event_log_filters_one_club(client, staff_headers, clubs):
    url = "/api/v1/manager/platform/events"
    body = client.get(
        url, query_string={"tenant_id": clubs["broken"].id, "level": "problems"}
    ).get_json()
    assert body["total"] == 3
    assert {e["tenant_id"] for e in body["entries"]} == {clubs["broken"].id}
    assert {e["level"] for e in body["entries"]} == {"warning", "error"}

    body = client.get(url, query_string={"tenant_id": clubs["busy"].id}).get_json()
    assert body["total"] == 4
    assert client.get(url, query_string={"tenant_id": "x"}).status_code == 400
