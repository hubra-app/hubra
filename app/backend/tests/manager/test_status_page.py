"""The public status page: GET /api/v1/status."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from hubra.core.models.maintenance_window import MaintenanceWindow
from hubra.core.services import maintenance, platform_monitor, status_page

URL = "/api/v1/status"


@pytest.fixture(autouse=True)
def _fresh():
    status_page.clear_cache()
    maintenance.clear_cache()
    yield
    status_page.clear_cache()
    maintenance.clear_cache()


def _problems(*ids):
    return patch.object(
        platform_monitor, "open_problems", return_value=[{"id": i} for i in ids]
    )


def _relays(*configured):
    return patch.object(
        platform_monitor, "_relay_config", side_effect=lambda r: r in configured
    )


def test_all_working_without_login(client, db):
    with _problems():
        body = client.get(URL).get_json()
    assert body["overall"] == "operational"
    assert [c["id"] for c in body["components"]] == ["app", "mail", "notifications"]
    assert {c["level"] for c in body["components"]} == {"operational"}
    assert body["club"] is None and body["incidents"] == []


@pytest.mark.parametrize(
    "ids, relays, expected",
    [
        (("service:db",), ("relay",), {"app": "down"}),
        (("service:redis", "perf:slow"), ("relay",), {"app": "degraded"}),
        (("relay:relay",), ("relay", "fallback"), {"mail": "degraded"}),
        (("relay:relay",), ("relay",), {"mail": "down"}),
        (("relay:relay", "relay:fallback"), ("relay", "fallback"), {"mail": "down"}),
        (("relay:skipped",), ("relay", "fallback"), {"mail": "degraded"}),
        (("jobs",), ("relay",), {"notifications": "degraded"}),
        (("mail:failed", "backup:x", "discord:y"), ("relay",), {}),
    ],
)
def test_levels_from_open_problems(db, ids, relays, expected):
    with _relays(*relays):
        out = status_page.components_from([{"id": i} for i in ids])
    want = {"app": "operational", "mail": "operational", "notifications": "operational"}
    assert out == {**want, **expected}


def test_nothing_internal_leaks(client, db):
    problem = {
        "id": "relay:relay",
        "level": "error",
        "title": "Main relay is down",
        "detail": "smtp.infomaniak.ch:587 refused: 535 auth failed",
    }
    with (
        patch.object(platform_monitor, "open_problems", return_value=[problem]),
        _relays("relay"),
    ):
        text = client.get(URL).get_data(as_text=True)
    assert "infomaniak" not in text and "535" not in text
    assert '"overall":"down"' in text.replace(" ", "")


def test_history_pairs_outages(client, db):
    platform_monitor.record("service", "service.down", "x", details={"service": "db"})
    platform_monitor.record("service", "service.up", "x", details={"service": "db"})
    platform_monitor.record("relay", "relay.down", "x", details={"relay": "relay"})
    platform_monitor.record("service", "service.down", "x", details={"service": "imap"})
    db.session.commit()
    with _problems():
        body = client.get(URL).get_json()
    got = sorted(
        (i["component"], i["level"], i["ended_at"] is None) for i in body["incidents"]
    )
    # IMAP is internal; the relay outage still lasts.
    assert got == [("app", "down", False), ("mail", "degraded", True)]


def test_club_maintenance_and_past_windows(client, db, tenant_pair):
    a, b = tenant_pair["tenant_a"], tenant_pair["tenant_b"]
    now = datetime.now(timezone.utc)
    db.session.add_all(
        [
            MaintenanceWindow(
                starts_at=now - timedelta(minutes=5),
                ends_at=now + timedelta(minutes=25),
                message="Datenbank-Update",
                tenant_ids=[a.id],
                notice_hours=24,
            ),
            MaintenanceWindow(
                starts_at=now - timedelta(days=2),
                ends_at=now - timedelta(days=2) + timedelta(hours=1),
                message="Update",
                tenant_ids=None,
                notice_hours=24,
            ),
        ]
    )
    db.session.commit()
    maintenance.clear_cache()
    with _problems():
        mine = client.get(f"{URL}?club={a.slug}").get_json()
        other = client.get(f"{URL}?club={b.slug}").get_json()
        nobody = client.get(f"{URL}?club=gibts-nicht").get_json()
    assert mine["overall"] == "maintenance"
    assert mine["maintenance"]["message"] == "Datenbank-Update"
    assert mine["club"] == {"slug": a.slug, "name": "Tenant A"}
    assert len(mine["past_maintenance"]) == 2
    assert other["overall"] == "operational"
    assert [w["message"] for w in other["past_maintenance"]] == ["Update"]
    assert nobody["club"] is None


def test_answers_during_maintenance(client, db):
    with (
        patch.object(
            maintenance,
            "state",
            return_value={"active": True, "message": "Update", "until": None},
        ),
        _problems(),
    ):
        resp = client.get(URL)
    assert resp.status_code == 200
    assert resp.get_json()["overall"] == "maintenance"


def test_database_failure_shows_app_down(db):
    with patch.object(platform_monitor, "open_problems", side_effect=RuntimeError):
        out = status_page.page()
    assert {c["id"]: c["level"] for c in out["components"]}["app"] == "down"
