"""Planned maintenance windows: for every club or some clubs, with a notice
before they start (services/maintenance.py)."""

from datetime import datetime, timedelta, timezone

import pytest

from hubra.core.models.platform_event import PlatformEvent
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.services import maintenance

BASE = "/api/v1/manager/platform/maintenance/windows"


@pytest.fixture(autouse=True)
def _fresh():
    maintenance.clear_cache()
    yield
    maintenance.clear_cache()


def _now():
    return datetime.now(timezone.utc)


def _iso(delta: timedelta) -> str:
    return (_now() + delta).isoformat()


def _plan(client, start: timedelta, end: timedelta, **body):
    resp = client.post(
        BASE,
        json={"starts_at": _iso(start), "ends_at": _iso(end), **body},
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["window"]


def test_planned_window_is_announced_then_runs(client, staff_headers, db):
    w = _plan(
        client,
        timedelta(hours=10),
        timedelta(hours=12),
        message="Datenbank-Update",
        notice_hours=24,
    )
    assert w["status"] == "announced"
    assert w["tenant_ids"] is None

    public = client.get("/api/v1/maintenance").get_json()
    assert public["active"] is False
    assert public["upcoming"]["id"] == w["id"]
    assert public["upcoming"]["message"] == "Datenbank-Update"
    assert client.get("/api/v1/members/").status_code != 503

    entry = db.session.query(GlobalAuditEntry).filter_by(
        action="platform.maintenance.scheduled"
    )
    assert entry.count() == 1
    assert any(
        "Maintenance planned for every club" in e.message
        for e in db.session.query(PlatformEvent).all()
    )


def test_notice_starts_only_notice_hours_before(client, staff_headers):
    _plan(client, timedelta(hours=30), timedelta(hours=31), notice_hours=24)
    assert client.get("/api/v1/maintenance").get_json()["upcoming"] is None
    windows = client.get(BASE).get_json()["current"]
    assert [w["status"] for w in windows] == ["planned"]


def test_running_window_for_every_club_is_maintenance_mode(client, staff_headers, db):
    from hubra.core.models.maintenance_window import MaintenanceWindow

    db.session.add(
        MaintenanceWindow(
            starts_at=_now() - timedelta(minutes=5),
            ends_at=_now() + timedelta(minutes=30),
            message="Umzug",
            notice_hours=24,
        )
    )
    db.session.commit()
    maintenance.clear_cache()

    assert maintenance.is_active() is True
    resp = client.get("/api/v1/members/")
    assert resp.status_code == 503
    assert resp.get_json()["message"] == "Umzug"
    assert client.get(BASE).status_code == 200  # manage keeps working

    # "Wartung beenden" ends it too.
    client.put("/api/v1/manager/platform/maintenance", json={"on": False})
    assert maintenance.state(fresh=True)["active"] is False
    assert client.get("/api/v1/members/").status_code != 503


def test_window_for_one_club_closes_only_that_club(app, db, tenant_pair):
    from hubra.core.models.maintenance_window import MaintenanceWindow

    a, b = tenant_pair["tenant_a"], tenant_pair["tenant_b"]
    db.session.add(
        MaintenanceWindow(
            starts_at=_now() - timedelta(minutes=1),
            ends_at=_now() + timedelta(hours=1),
            message="Nur A",
            tenant_ids=[a.id],
            notice_hours=0,
        )
    )
    db.session.commit()
    maintenance.clear_cache()

    assert maintenance.is_active() is False  # not platform-wide: alerts go on
    assert maintenance.club_state(a.id)["active"] is True
    assert maintenance.club_state(a.id)["message"] == "Nur A"
    assert maintenance.club_state(b.id)["active"] is False

    c = app.test_client()
    resp = c.get("/api/v1/members/", headers={"X-Tenant-Slug": a.slug})
    assert resp.status_code == 503
    assert resp.get_json()["error"] == "MAINTENANCE"
    assert c.get("/api/v1/maintenance", headers={"X-Tenant-Slug": a.slug}).get_json()[
        "active"
    ]
    assert (
        c.get("/api/v1/members/", headers={"X-Tenant-Slug": b.slug}).status_code != 503
    )
    assert not c.get(
        "/api/v1/maintenance", headers={"X-Tenant-Slug": b.slug}
    ).get_json()["active"]


def test_upcoming_only_for_covered_clubs(client, staff_headers, tenant_pair):
    a, b = tenant_pair["tenant_a"], tenant_pair["tenant_b"]
    w = _plan(
        client,
        timedelta(hours=2),
        timedelta(hours=3),
        tenant_ids=[a.id],
        notice_hours=24,
    )
    assert w["clubs"] == [{"id": a.id, "name": "Tenant A"}]
    assert maintenance.club_state(a.id)["upcoming"]["id"] == w["id"]
    assert maintenance.club_state(b.id)["upcoming"] is None


def test_cancel_and_end_early(client, staff_headers, db):
    from hubra.core.models.maintenance_window import MaintenanceWindow

    planned = _plan(client, timedelta(hours=2), timedelta(hours=3))
    resp = client.post(f"{BASE}/{planned['id']}/cancel")
    assert resp.status_code == 200
    assert resp.get_json()["window"]["status"] == "cancelled"
    assert client.post(f"{BASE}/{planned['id']}/cancel").status_code == 409
    assert client.get("/api/v1/maintenance").get_json()["upcoming"] is None
    body = client.get(BASE).get_json()
    assert body["current"] == []
    assert [w["status"] for w in body["past"]] == ["cancelled"]

    running = MaintenanceWindow(
        starts_at=_now() - timedelta(minutes=5),
        ends_at=_now() + timedelta(hours=1),
        message="",
        tenant_ids=None,
        notice_hours=0,
    )
    db.session.add(running)
    db.session.commit()
    resp = client.post(f"{BASE}/{running.id}/cancel")
    assert resp.status_code == 200
    assert resp.get_json()["window"]["status"] == "done"  # ended now
    assert maintenance.state(fresh=True)["active"] is False
    assert client.post(f"{BASE}/9999/cancel").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"starts_at": "soon", "ends_at": "later"},
        {"starts_at": _iso(timedelta(hours=2)), "ends_at": _iso(timedelta(hours=1))},
        {"starts_at": _iso(timedelta(days=-2)), "ends_at": _iso(timedelta(days=-1))},
        {"starts_at": _iso(timedelta(hours=1)), "ends_at": _iso(timedelta(days=9))},
        {
            "starts_at": _iso(timedelta(hours=1)),
            "ends_at": _iso(timedelta(hours=2)),
            "notice_hours": 5,
        },
        {
            "starts_at": _iso(timedelta(hours=1)),
            "ends_at": _iso(timedelta(hours=2)),
            "tenant_ids": [],
        },
        {
            "starts_at": _iso(timedelta(hours=1)),
            "ends_at": _iso(timedelta(hours=2)),
            "tenant_ids": [999],
        },
        {
            "starts_at": _iso(timedelta(hours=1)),
            "ends_at": _iso(timedelta(hours=2)),
            "tenant_ids": "all",
        },
        {
            "starts_at": _iso(timedelta(hours=1)),
            "ends_at": _iso(timedelta(hours=2)),
            "message": "x" * 501,
        },
    ],
)
def test_bad_windows_are_refused(client, staff_headers, body):
    assert client.post(BASE, json=body).status_code == 400


def test_only_settings_admins_plan(client, auth_headers):
    body = {"starts_at": _iso(timedelta(hours=1)), "ends_at": _iso(timedelta(hours=2))}
    assert client.post(BASE, json=body).status_code == 403
    assert client.post(f"{BASE}/1/cancel").status_code == 403
