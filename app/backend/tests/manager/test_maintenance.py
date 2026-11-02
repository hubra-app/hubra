"""Maintenance mode and the platform-wide alert switches."""

from unittest.mock import patch

import pytest

from hubra.core.models.platform_event import PlatformEvent
from hubra.core.services import email, maintenance, platform_monitor, platform_settings

BASE = "/api/v1/manager/platform"


@pytest.fixture(autouse=True)
def _fresh():
    maintenance.clear_cache()
    yield
    maintenance.clear_cache()


@pytest.fixture
def relay(db):
    platform_settings.set_many(
        {
            "mail.relay.host": "mail.example",
            "mail.system.sender_email": "noreply@hubra.example",
        }
    )
    db.session.commit()


def _alert_mails(deliver):
    return [c for c in deliver.call_args_list if "[Hubra]" in c.args[3]]


# ── Maintenance ───────────────────────────────────────────────────────────────


def test_club_api_answers_503_while_manage_keeps_working(client, staff_headers, db):
    assert client.get("/api/v1/maintenance").get_json()["active"] is False
    resp = client.put(
        f"{BASE}/maintenance", json={"on": True, "message": "Update", "minutes": 15}
    )
    assert resp.status_code == 200
    assert resp.get_json()["active"] is True
    assert resp.get_json()["until"]

    club = client.get("/api/v1/members/")
    assert club.status_code == 503
    assert club.get_json()["error"] == "MAINTENANCE"
    assert club.get_json()["message"] == "Update"
    assert club.headers["Retry-After"]

    public = client.get("/api/v1/maintenance").get_json()
    assert public == {"active": True, "message": "Update", "until": public["until"]}
    assert client.get(f"{BASE}/alerts/overview").status_code == 200
    assert client.get("/api/v1/health").status_code != 503

    client.put(f"{BASE}/maintenance", json={"on": False})
    assert client.get("/api/v1/members/").status_code != 503
    kinds = [e.message for e in db.session.query(PlatformEvent).all()]
    assert any("Maintenance mode on" in k for k in kinds)
    assert "Maintenance mode off" in kinds


def test_maintenance_ends_by_itself(db):
    platform_settings.set_many(
        {"maintenance.enabled": "on", "maintenance.until": "2020-01-01T00:00+00:00"}
    )
    db.session.commit()
    assert maintenance.state(fresh=True)["active"] is False


def test_only_settings_admins_switch_it(client, auth_headers):
    assert client.put(f"{BASE}/maintenance", json={"on": True}).status_code == 403


def test_bad_maintenance_bodies(client, staff_headers):
    for body in (
        {},
        {"on": "yes"},
        {"on": True, "minutes": 0},
        {"on": True, "minutes": "5"},
    ):
        assert client.put(f"{BASE}/maintenance", json=body).status_code == 400


def test_alerts_pause_in_maintenance(db, seeded_db, relay):
    seeded_db["user"].is_superadmin = True
    db.session.commit()
    maintenance.turn_on("Release", 10)
    with patch.object(email, "_deliver") as deliver:
        assert platform_monitor.alert("backup_failed", "x", ["y"]) is False
    assert _alert_mails(deliver) == []
    (event,) = db.session.query(PlatformEvent).filter_by(category="alert").all()
    assert event.details["paused"] == "maintenance"


def test_the_cli_switches_it(app, db):
    runner = app.test_cli_runner()
    out = runner.invoke(args=["maintenance", "on", "--minutes", "5"]).output
    assert "Maintenance on until" in out
    assert "Maintenance off" in runner.invoke(args=["maintenance", "off"]).output


# ── Alert switches ────────────────────────────────────────────────────────────


def test_switches_per_type_and_channel(client, staff_headers, db):
    data = client.get(f"{BASE}/alerts/switches").get_json()
    assert data["enabled"] is True
    assert data["types"]["backup_failed"] == {"mail": True, "discord": True}

    resp = client.put(
        f"{BASE}/alerts/switches",
        json={
            "types": {
                "backup_failed": {"mail": False},
                "plugin_updates": {"discord": False},
            }
        },
    )
    assert resp.status_code == 200
    types = resp.get_json()["types"]
    assert types["backup_failed"] == {"mail": False, "discord": True}
    assert types["plugin_updates"] == {"mail": True, "discord": False}
    assert platform_settings.get("alerts.mail_off") == "backup_failed"
    assert platform_monitor.channels("backup_failed") == {
        "mail": False,
        "discord": True,
        "reason": None,
    }

    client.put(f"{BASE}/alerts/switches", json={"enabled": False})
    assert platform_monitor.channels("relay_down")["reason"] == "alerts_off"

    for body in (
        {"types": {"nope": {"mail": False}}},
        {"types": {"system": {"sms": True}}},
        {"enabled": "no"},
    ):
        assert client.put(f"{BASE}/alerts/switches", json=body).status_code == 400


def test_a_type_off_for_mail_is_not_mailed(db, seeded_db, relay):
    seeded_db["user"].is_superadmin = True
    platform_settings.set_many({"alerts.mail_off": "backup_failed"})
    db.session.commit()
    with patch.object(email, "_deliver") as deliver:
        platform_monitor.deliver_alert("backup_failed", "x", ["y"], "error")
        assert _alert_mails(deliver) == []
        platform_monitor.deliver_alert("service_down", "x", ["y"], "error")
        assert len(_alert_mails(deliver)) == 1


def test_overview_shows_maintenance_and_switches(client, staff_headers):
    data = client.get(f"{BASE}/alerts/overview").get_json()
    assert data["maintenance"]["active"] is False
    assert "types" in data["switches"]
