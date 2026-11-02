"""The platform notification matrix: what goes where (mail, Discord)."""

from unittest.mock import patch

import pytest

from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.services import (
    email,
    platform_discord,
    platform_monitor,
    platform_settings,
)
from hubra.core.tasks.platform_discord_tasks import post_platform_audit_entry

BASE = "/api/v1/manager/platform"


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.session.rollback()
    db.session.query(PlatformSetting).delete()
    db.session.query(GlobalAuditEntry).delete()
    db.session.commit()


@pytest.fixture
def relay(db):
    platform_settings.set_many(
        {
            "mail.relay.host": "mail.example",
            "mail.system.sender_email": "noreply@hubra.example",
        }
    )
    db.session.commit()


def _matrix(client):
    return client.get(f"{BASE}/alerts/switches").get_json()


def test_matrix_has_events_and_alerts(client, staff_headers):
    data = _matrix(client)
    assert data["channels"] == ["mail", "discord"]
    assert "alerts" not in data["events"]
    # Defaults: events to Discord except members, no event mails.
    assert data["events"]["clubs"] == {"mail": False, "discord": True}
    assert data["events"]["members"] == {"mail": False, "discord": False}
    assert data["types"]["backup_failed"] == {"mail": True, "discord": True}


def test_events_by_mail_and_discord(client, staff_headers, db):
    resp = client.put(
        f"{BASE}/alerts/switches",
        json={"events": {"requests": {"mail": True}, "plugins": {"discord": False}}},
    )
    assert resp.status_code == 200, resp.get_json()
    events = resp.get_json()["events"]
    assert events["requests"] == {"mail": True, "discord": True}
    assert events["plugins"] == {"mail": False, "discord": False}
    assert platform_discord.mail_categories() == {"requests"}
    assert "plugins" not in platform_discord.enabled_categories()
    # Alerts still reach Discord.
    assert "alerts" in platform_discord.enabled_categories()


def test_all_discord_off_is_stored_empty(client, staff_headers, db):
    data = _matrix(client)
    body = {
        "events": {c: {"discord": False} for c in data["events"]},
        "types": {t: {"discord": False} for t in data["types"]},
    }
    resp = client.put(f"{BASE}/alerts/switches", json=body)
    assert resp.status_code == 200
    assert platform_settings.get("discord.log_events") == ""
    assert platform_discord.enabled_categories() == set()
    # One alert back on: only that one, not every type.
    resp = client.put(
        f"{BASE}/alerts/switches", json={"types": {"service_down": {"discord": True}}}
    )
    types = resp.get_json()["types"]
    assert types["service_down"]["discord"] is True
    assert types["backup_failed"]["discord"] is False


def test_alerts_category_off_shows_alerts_off(client, staff_headers, db):
    platform_settings.set_many({"discord.log_events": "clubs"})
    db.session.commit()
    data = _matrix(client)
    assert all(not v["discord"] for v in data["types"].values())


def test_bad_matrix_input(client, staff_headers):
    put = lambda body: client.put(f"{BASE}/alerts/switches", json=body)  # noqa: E731
    assert put({"events": {"nonsense": {"mail": True}}}).status_code == 400
    assert put({"events": {"clubs": {"push": True}}}).status_code == 400
    assert put({"events": {"clubs": {"mail": "yes"}}}).status_code == 400
    assert put({"events": []}).status_code == 400


def test_audit_entry_is_mailed_to_admins(db, seeded_db, relay):
    seeded_db["user"].is_superadmin = True
    platform_settings.set_many({"notify.mail_events": "requests"})
    db.session.commit()
    entry = GlobalAuditEntry(action="tenant_request.submit", details={"slug": "chess"})
    db.session.add(entry)
    db.session.commit()
    with patch.object(email, "_deliver") as deliver:
        post_platform_audit_entry.run(entry.id)
    mails = [c for c in deliver.call_args_list if "tenant_request.submit" in c.args[3]]
    assert len(mails) == 1
    assert mails[0].args[2] == seeded_db["user"].email
    assert "/app/audit?entry=" not in mails[0].args[3]  # no manage URL set
    seeded_db["user"].is_superadmin = False
    db.session.commit()


def test_category_not_ticked_is_not_mailed(db, seeded_db, relay):
    seeded_db["user"].is_superadmin = True
    platform_settings.set_many({"notify.mail_events": "requests"})
    db.session.commit()
    entry = GlobalAuditEntry(action="tenant.provision")
    db.session.add(entry)
    db.session.commit()
    assert platform_monitor.deliver_audit_mail(entry) == 0
    seeded_db["user"].is_superadmin = False
    db.session.commit()


def test_mail_events_queue_without_discord(db):
    platform_settings.set_many({"notify.mail_events": "clubs"})
    db.session.commit()
    with patch("hubra.core.tasks.after_commit.delay_after_commit") as delay:
        entry = GlobalAuditEntry(action="tenant.provision")
        db.session.add(entry)
        db.session.commit()
    assert delay.call_args.args[1] == entry.id
