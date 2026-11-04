"""Platform log: the Hubra bot posts platform events to a Discord channel."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.services import alerts, platform_discord, platform_settings
from hubra.core.services.platform_settings import PlatformSettingError

CHANNEL = "123456789012345678"


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.session.rollback()
    db.session.query(PlatformSetting).delete()
    db.session.query(GlobalAuditEntry).delete()
    db.session.commit()
    platform_discord._local_last.clear()  # the remembered last post


@pytest.fixture
def log_on(db):
    platform_settings.set_many(
        {"discord.bot_token": "bot-token", "discord.log_channel_id": CHANNEL}
    )
    db.session.commit()


@pytest.fixture
def queued():
    with patch("hubra.core.tasks.after_commit.delay_after_commit") as delay:
        yield delay


@pytest.fixture
def discord_api():
    resp = MagicMock(status=200)
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    with patch(
        "hubra.core.services.platform_discord.urllib.request.urlopen",
        return_value=resp,
    ) as urlopen:
        yield urlopen


def _sent(urlopen):
    req = urlopen.call_args.args[0]
    return req, json.loads(req.data)


def _entry(db, action, **kw):
    entry = GlobalAuditEntry(action=action, **kw)
    db.session.add(entry)
    db.session.commit()
    return entry


@pytest.mark.parametrize(
    "action,cat",
    [
        ("tenant.provision", "clubs"),
        ("tenant.suspended", "clubs"),
        ("domain.expired", "clubs"),
        ("set_tenant_module", "clubs"),
        ("tenant_request.submit", "requests"),
        ("tenant.add_owner", "access"),
        ("tenant.remove_admin", "access"),
        ("global_role.assign", "access"),
        ("impersonation.start", "access"),
        ("tenant.add_member", "members"),
        ("tenant.invite_accepted", "members"),
        ("install_plugin", "plugins"),
        ("add_plugin_repository", "plugins"),
        ("backup.restore", "backups"),
        ("platform.settings.update", "platform"),
        ("platform.encryption.rotate", "platform"),
    ],
)
def test_categories(action, cat):
    assert platform_discord.category(action) == cat


def test_settings_defaults_and_validation(db):
    assert platform_settings.get("discord.log_channel_id") == ""
    assert platform_discord.enabled_categories() == set(platform_discord.CATEGORIES) - {
        "members"
    }
    with pytest.raises(PlatformSettingError):
        platform_settings.set_many({"discord.log_events": "clubs,nonsense"})
    with pytest.raises(PlatformSettingError):
        platform_settings.set_many({"discord.log_channel_id": "#general"})
    platform_settings.set_many({"discord.log_events": "clubs, alerts"})
    assert platform_discord.enabled_categories() == {"clubs", "alerts"}


def test_nothing_is_queued_without_a_channel(db, queued):
    _entry(db, "tenant.provision")
    queued.assert_not_called()


def test_audit_entry_is_queued_by_id_only(db, log_on, queued):
    entry = _entry(db, "tenant.provision")
    task, entry_id = queued.call_args.args
    assert task.name.endswith("post_platform_audit_entry")
    assert entry_id == entry.id


def test_audit_entry_post(db, log_on, discord_api, seeded_db):
    club = Tenant(name="Chess Club", slug="chess-log", plan="starter", status="active")
    db.session.add(club)
    db.session.commit()
    entry = _entry(
        db,
        "tenant.suspended",
        tenant_id=club.id,
        actor_id=seeded_db["user"].id,
        target_type="Tenant",
        target_id=str(club.id),
        details={"new_status": "suspended", "smtp_password": "hunter2"},
    )
    assert platform_discord.post_audit_entry(entry.id) is True
    req, body = _sent(discord_api)
    assert req.full_url == f"{platform_discord.API}/channels/{CHANNEL}/messages"
    assert req.get_header("Authorization") == "Bot bot-token"
    assert body["allowed_mentions"] == {"parse": []}
    embed = body["embeds"][0]
    assert embed["title"] == "🏠 Verein gesperrt"
    assert "tenant.suspended" in embed["footer"]["text"]
    assert embed["color"] == platform_discord.COLOR_BAD
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert club.slug in fields["Verein"]
    assert seeded_db["user"].email in fields["Von"]
    assert fields["New status"] == "suspended"
    assert fields["Smtp password"] == "***"
    assert "hunter2" not in json.dumps(body)
    db.session.query(GlobalAuditEntry).delete()
    db.session.delete(club)
    db.session.commit()


def test_category_off_is_not_posted(db, log_on, discord_api):
    entry = _entry(db, "tenant.add_member")  # members is off by default
    assert platform_discord.post_audit_entry(entry.id) is False
    discord_api.assert_not_called()


def test_task_never_raises(db, log_on):
    from urllib.error import HTTPError

    from hubra.core.tasks.platform_discord_tasks import post_platform_audit_entry

    entry = _entry(db, "tenant.provision")
    with patch(
        "hubra.core.services.platform_discord.urllib.request.urlopen",
        side_effect=HTTPError("u", 403, "Forbidden", {}, None),
    ):
        assert post_platform_audit_entry.run(entry.id) is False


def test_alerts_go_to_the_log(db, log_on, discord_api):
    assert alerts.alert_error("Task failed", "boom") is True
    _, body = _sent(discord_api)
    assert body["embeds"][0]["title"] == "🔴 Task failed"
    # A problem: acknowledge and silence.
    ids = [c.get("custom_id") for c in body["components"][0]["components"]]
    assert ids[:2] == ["p:al:ack:system", "p:al:mute:system"]
    assert body["embeds"][0]["color"] == alerts.COLOR_RED


def test_alerts_off(db, log_on, discord_api):
    platform_settings.set_many({"discord.log_events": "clubs"})
    db.session.commit()
    assert alerts.alert_error("Task failed", "boom") is False
    discord_api.assert_not_called()


def test_alerts_without_setup(db, discord_api):
    assert alerts.alert_error("Task failed", "boom") is False
    discord_api.assert_not_called()


# ── API ───────────────────────────────────────────────────────────────────────


@pytest.fixture
def superadmin(client, seeded_db, db):
    seeded_db["user"].is_superadmin = True
    db.session.commit()
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    yield
    seeded_db["user"].is_superadmin = False
    db.session.commit()


def test_api_test_message(client, superadmin, log_on, discord_api):
    resp = client.post("/api/v1/manager/platform/discord/test")
    assert resp.status_code == 200
    _, body = _sent(discord_api)
    assert "Test message" in body["embeds"][0]["description"]


def test_api_test_message_reports_discord_errors(client, superadmin, log_on):
    from urllib.error import HTTPError

    with patch(
        "hubra.core.services.platform_discord.urllib.request.urlopen",
        side_effect=HTTPError("u", 404, "Not Found", {}, None),
    ):
        resp = client.post("/api/v1/manager/platform/discord/test")
    assert resp.status_code == 502
    assert "no channel" in resp.get_json()["message"]


def test_api_test_message_needs_setup(client, superadmin):
    resp = client.post("/api/v1/manager/platform/discord/test")
    assert resp.status_code == 502


def test_club_requests_are_audited(client, db, seeded_db, queued, log_on):
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    resp = client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "Chess Club", "slug": "chess-club"},
    )
    assert resp.status_code == 201, resp.get_json()
    entry = (
        db.session.query(GlobalAuditEntry)
        .filter_by(action="tenant_request.submit")
        .one()
    )
    assert entry.details["slug"] == "chess-club"
    assert platform_discord.category(entry.action) == "requests"


# ── Audit channel ─────────────────────────────────────────────────────────────

AUDIT = "223456789012345678"


@pytest.fixture
def audit_on(db):
    platform_settings.set_many(
        {"discord.bot_token": "bot-token", "discord.audit_channel_id": AUDIT}
    )
    db.session.commit()


def _channels(urlopen):
    return [
        c.args[0].full_url.split("/channels/")[1].split("/")[0]
        for c in urlopen.call_args_list
    ]


def test_audit_channel_is_off_by_default(db):
    assert platform_settings.get("discord.audit_channel_id") == ""
    assert platform_discord.audit_channel() == ""


def test_audit_channel_alone_queues(db, audit_on, queued):
    entry = _entry(db, "tenant.provision")
    assert queued.call_args.args[1] == entry.id


def test_audit_channel_follows_the_categories(db, audit_on, discord_api):
    entry = _entry(db, "tenant.add_member")  # members is off by default
    assert platform_discord.post_audit_entry(entry.id) is False
    discord_api.assert_not_called()


def test_audit_entries_go_only_to_the_audit_channel(
    db, log_on, audit_on, discord_api, queued
):
    entry = _entry(db, "tenant.provision")
    assert platform_discord.post_audit_entry(entry.id) is True
    assert _channels(discord_api) == [AUDIT]


def test_alerts_stay_in_the_log_with_an_audit_channel(
    db, log_on, audit_on, discord_api
):
    assert alerts.alert_error("Task failed", "boom") is True
    assert _channels(discord_api) == [CHANNEL]


def test_without_audit_channel_entries_go_to_the_log(db, log_on, discord_api, queued):
    entry = _entry(db, "tenant.provision")
    platform_discord.post_audit_entry(entry.id)
    assert _channels(discord_api) == [CHANNEL]


def test_embed_links_to_manage(db, audit_on, discord_api):
    platform_settings.set_many({"alerts.manage_url": "https://manage.example.ch/"})
    db.session.commit()
    club = Tenant(
        name="Chess Club", slug="chess-links", plan="starter", status="active"
    )
    db.session.add(club)
    db.session.commit()
    entry = _entry(db, "tenant.add_admin", tenant_id=club.id)
    platform_discord.post_audit_entry(entry.id)
    _, body = _sent(discord_api)
    embed = body["embeds"][0]
    base = "https://manage.example.ch"
    assert embed["url"] == f"{base}/app/audit?entry={entry.id}"
    links = {f["name"]: f["value"] for f in embed["fields"]}["Links"]
    assert f"[Verein]({base}/app/tenants/{club.id})" in links
    assert f"[Vereinsadmins]({base}/app/clubs/{club.id}/admins)" in links
    db.session.query(GlobalAuditEntry).delete()
    db.session.delete(club)
    db.session.commit()


@pytest.mark.parametrize(
    "action,path",
    [
        ("tenant_request.approve", "/app/tenants/requests"),
        ("impersonation.start", "/app/support"),
        ("global_role.assign", "/app/roles"),
        ("backup.delete", "/app/platform/backups"),
        ("install_plugin", "/app/plugins"),
        ("support_case.merge", "/app/reports"),
        ("platform.maintenance.cancelled", "/app/platform/maintenance"),
    ],
)
def test_area_links(action, path):
    entry = GlobalAuditEntry(id=7, action=action)
    links = dict(platform_discord.audit_links(entry, "https://m.example"))
    assert links["Audit-Log"] == "https://m.example/app/audit?entry=7"
    assert path in [u.removeprefix("https://m.example") for u in links.values()]


def test_no_links_without_manage_address(db, audit_on, discord_api):
    entry = _entry(db, "tenant.provision")
    platform_discord.post_audit_entry(entry.id)
    embed = _sent(discord_api)[1]["embeds"][0]
    assert "url" not in embed
    assert "Links" not in {f["name"] for f in embed["fields"]}


def test_api_test_message_to_audit_channel(client, superadmin, audit_on, discord_api):
    resp = client.post(
        "/api/v1/manager/platform/discord/test", json={"channel": "audit"}
    )
    assert resp.status_code == 200
    req, body = _sent(discord_api)
    assert f"/channels/{AUDIT}/" in req.full_url
    assert body["embeds"][0]["title"] == "Hubra audit channel"


def test_api_test_audit_needs_channel(client, superadmin, log_on):
    resp = client.post(
        "/api/v1/manager/platform/discord/test", json={"channel": "audit"}
    )
    assert resp.status_code == 400


def test_audit_list_filters_by_id(client, superadmin, db):
    a = _entry(db, "tenant.provision")
    _entry(db, "tenant.update")
    resp = client.get(f"/api/v1/system/audit?id={a.id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1 and data["entries"][0]["id"] == a.id
    assert client.get("/api/v1/system/audit?id=x").status_code == 400


# ── Problems, notices and recoveries get different buttons ───────────────────


def _buttons(body) -> list[tuple[str, str]]:
    rows = body.get("components") or []
    return [
        (c["label"], c.get("custom_id") or c.get("url"))
        for row in rows
        for c in row["components"]
    ]


@pytest.fixture
def manage_url(db):
    platform_settings.set_many({"alerts.manage_url": "https://manage.example.ch"})
    db.session.commit()


@pytest.mark.parametrize(
    "alert_type,level,kind",
    [
        ("relay_down", "error", "problem"),
        ("relay_down", "info", "resolved"),
        ("service_down", "warning", "problem"),
        ("backup_failed", "error", "problem"),
        ("support_cases", "warning", "notice"),
        ("support_cases", "info", "notice"),
        ("plugin_updates", "info", "notice"),
        ("backup_deleted", "warning", "notice"),
        ("upgrades", "info", "notice"),
        ("upgrades", "warning", "problem"),  # stuck
        ("system", "info", "resolved"),
    ],
)
def test_message_kind(alert_type, level, kind):
    from hubra.core.services import platform_bot

    assert platform_bot.message_kind(alert_type, level) == kind


def test_a_problem_can_be_acknowledged_and_silenced(
    db, log_on, manage_url, discord_api
):
    with patch("hubra.core.services.platform_bot.track_alert") as track:
        assert alerts.send_alert(
            "Hubra: Main relay is down",
            "3 checks in a row failed.\nError: 535 auth failed\nSee manage › Mail.",
            staff=False,
            alert_type="relay_down",
            level="error",
        )
    body = _sent(discord_api)[1]
    embed = body["embeds"][0]
    assert embed["title"] == "🔴 Main relay is down"
    assert embed["description"] == "3 checks in a row failed."
    assert embed["fields"][0]["name"] == "Fehler"
    assert "535 auth failed" in embed["fields"][0]["value"]
    assert embed["footer"]["text"] == "Hubra · Warnung · Mail-Relay"
    assert "timestamp" in embed
    assert _buttons(body) == [
        ("Bestätigen", "p:al:ack:relay_down"),
        ("1 h stumm", "p:al:mute:relay_down"),
        ("In manage öffnen", "https://manage.example.ch/app/platform/mail/relay"),
    ]
    track.assert_called_once()


def test_a_notice_only_links_to_its_page(db, log_on, manage_url, discord_api):
    with patch("hubra.core.services.platform_bot.track_alert") as track:
        assert alerts.send_alert(
            "New problem report: Login broken",
            "From: Anna\n\nThe button does nothing.",
            color=alerts.COLOR_ORANGE,
            staff=False,
            alert_type="support_cases",
            level="warning",
        )
    body = _sent(discord_api)[1]
    embed = body["embeds"][0]
    assert embed["title"].startswith("📨 ")
    assert embed["color"] == platform_discord.COLOR_INFO
    assert embed["footer"]["text"] == "Hubra · Mitteilung · Meldungen und Ideen"
    assert _buttons(body) == [
        ("Meldung öffnen", "https://manage.example.ch/app/reports")
    ]
    track.assert_not_called()  # nothing to turn green later


def test_a_recovery_has_no_acknowledge(db, log_on, manage_url, discord_api):
    assert alerts.alert_resolved("Redis is back", "It answered again.")
    body = _sent(discord_api)[1]
    assert body["embeds"][0]["title"] == "✅ Redis is back"
    assert [label for label, _ in _buttons(body)] == ["In manage öffnen"]


def test_without_manage_address_a_notice_has_no_buttons(db, log_on, discord_api):
    alerts.send_alert(
        "Update finished",
        "All on 1.2.3.",
        staff=False,
        alert_type="upgrades",
        level="info",
    )
    assert "components" not in _sent(discord_api)[1]


def test_details_are_text_not_json():
    assert platform_discord._field_value(True) == "Ja"
    assert platform_discord._field_value(["a", "b"]) == "a, b"
    assert platform_discord._field_value({"oldPlan": "free", "new_plan": "club"}) == (
        "Old plan: free\nNew plan: club"
    )
    assert platform_discord._field_value(None) == "–"


def test_unknown_actions_are_spelled_out():
    assert platform_discord.action_label("tenant.provision") == "Verein erstellt"
    assert platform_discord.action_label("platform.encryption.rotate") == (
        "Platform: encryption rotate"
    )
