"""Platform admins in Discord: buttons, /plattform, /wartung, digest,
release notes and security pings (``services.platform_bot``)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from hubra.core.models.connected_app import ExternalAccount
from hubra.core.models.platform_event import PlatformEvent
from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.models.tenant_request import TenantRequest
from hubra.core.services import (
    maintenance,
    platform_bot,
    platform_discord,
    platform_monitor,
    platform_settings,
)

GUILD = "900000000000000001"
CLUB_GUILD = "900000000000000002"
CHANNEL = "123456789012345678"
ADMIN_DISCORD = "700000000000000001"


class FakeRedis:
    """Just what platform_bot uses."""

    def __init__(self):
        self.data: dict = {}
        self.hashes: dict = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True

    def delete(self, key):
        self.data.pop(key, None)

    def incr(self, key):
        self.data[key] = int(self.data.get(key) or 0) + 1
        return self.data[key]

    def expire(self, key, seconds):
        return True

    def hset(self, name, key, value):
        self.hashes.setdefault(name, {})[key] = value

    def hgetall(self, name):
        return dict(self.hashes.get(name, {}))

    def hdel(self, name, key):
        self.hashes.get(name, {}).pop(key, None)


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.session.rollback()
    for model in (
        PlatformSetting,
        GlobalAuditEntry,
        ExternalAccount,
        TenantRequest,
        PlatformEvent,
    ):
        db.session.query(model).delete()
    db.session.commit()
    platform_bot._local.clear()
    maintenance.clear_cache()


@pytest.fixture
def redis():
    fake = FakeRedis()
    with patch.object(platform_bot, "_redis", return_value=fake):
        yield fake


@pytest.fixture
def bot(db, redis):
    """Log channel set, guild known, Discord's API recorded."""
    platform_settings.set_many(
        {
            "discord.bot_token": "bot-token",
            "discord.client_id": "555",
            "discord.log_channel_id": CHANNEL,
        }
    )
    db.session.commit()
    calls: list = []

    def fake_bot(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET" and "/messages/" in path:
            return {
                "id": path.rsplit("/", 1)[1],
                "embeds": [{"title": "tenant_request.submit", "fields": []}],
                "components": platform_bot.request_buttons(
                    GlobalAuditEntry(action="tenant_request.submit", target_id="1")
                ),
            }
        return {}

    with (
        patch.object(platform_bot, "guild_id", return_value=GUILD),
        patch.object(platform_bot, "_bot", side_effect=fake_bot),
    ):
        yield calls


@pytest.fixture
def admin(db, seeded_db):
    user = seeded_db["user"]
    user.is_superadmin = True
    db.session.add(
        ExternalAccount(user_id=user.id, provider="discord", external_id=ADMIN_DISCORD)
    )
    db.session.commit()
    with patch("hubra.api.auth.mfa.enabled", return_value=True):
        yield user


def _click(custom_id, *, user=ADMIN_DISCORD, guild=GUILD, message=None):
    return {
        "type": 3,
        "guild_id": guild,
        "token": "itok",
        "member": {"user": {"id": user}},
        "data": {"custom_id": custom_id},
        "message": message or {},
    }


def _command(cmd, sub, user=ADMIN_DISCORD, **options):
    return {
        "type": 2,
        "guild_id": GUILD,
        "member": {"user": {"id": user}},
        "data": {
            "name": cmd,
            "options": [
                {
                    "type": 1,
                    "name": sub,
                    "options": [{"name": k, "value": v} for k, v in options.items()],
                }
            ],
        },
    }


def _request(db, seeded_db, slug="neu"):
    req = TenantRequest(
        user_id=seeded_db["user"].id, name="Neuer Verein", slug=slug, plan="starter"
    )
    req.status = "pending"
    db.session.add(req)
    db.session.commit()
    return req


# ── Routing ───────────────────────────────────────────────────────────────────


def test_only_platform_clicks_on_the_platform_server_are_ours(bot):
    assert platform_bot.is_platform_interaction(_click("p:al:ack:relay_down"))
    assert not platform_bot.is_platform_interaction(
        _click("p:al:ack:relay_down", guild=CLUB_GUILD)
    )
    # A club's own buttons on the platform server stay with the plugin.
    assert not platform_bot.is_platform_interaction(_click("register:4"))
    assert platform_bot.is_platform_interaction(_command("wartung", "ende"))
    assert not platform_bot.is_platform_interaction(_command("events", "x"))


# ── Who may click ─────────────────────────────────────────────────────────────


def test_unlinked_discord_account_is_refused(bot, admin):
    answer = platform_bot.handle(_click("p:al:ack:relay_down", user="123"))
    assert answer["type"] == 4
    assert answer["data"]["flags"] == platform_bot.EPHEMERAL
    assert "verknüpft" in answer["data"]["content"]


def test_two_factor_is_required(bot, admin):
    with patch("hubra.api.auth.mfa.enabled", return_value=False):
        answer = platform_bot.handle(_click("p:al:ack:relay_down"))
    assert "Zwei-Faktor" in answer["data"]["content"]


def test_platform_permission_is_required(bot, admin, db):
    admin.is_superadmin = False
    db.session.commit()
    answer = platform_bot.handle(_click("p:al:mute:relay_down"))
    assert "platform.settings" in answer["data"]["content"]
    assert platform_bot.muted_until("relay_down") is None


# ── Club requests ─────────────────────────────────────────────────────────────


def test_new_request_gets_buttons_and_message_is_tracked(bot, db):
    entry = GlobalAuditEntry(action="tenant_request.submit", target_id="7")
    ids = [
        c.get("custom_id") for c in platform_bot.request_buttons(entry)[0]["components"]
    ]
    assert ids[:2] == ["p:req:ok:7", "p:req:no:7"]
    assert (
        platform_bot.request_buttons(GlobalAuditEntry(action="tenant.provision"))
        is None
    )
    platform_bot.track_request(entry, {"id": "m1", "channel_id": CHANNEL})
    assert json.loads(platform_bot._get("platform_bot:req:7"))["id"] == "m1"


def test_reject_asks_for_a_reason_then_rejects(bot, admin, db, seeded_db):
    req = _request(db, seeded_db)
    platform_bot.track_request(
        GlobalAuditEntry(target_id=str(req.id)), {"id": "m1", "channel_id": CHANNEL}
    )
    modal = platform_bot.handle(_click(f"p:req:no:{req.id}"))
    assert modal["type"] == 9
    assert modal["data"]["custom_id"] == f"p:reqm:{req.id}"

    submit = {
        "type": 5,
        "guild_id": GUILD,
        "member": {"user": {"id": ADMIN_DISCORD}},
        "data": {
            "custom_id": f"p:reqm:{req.id}",
            "components": [
                {"type": 1, "components": [{"custom_id": "note", "value": "Doppelt"}]}
            ],
        },
    }
    with patch("hubra.core.services.club_requests.notify_requester", return_value=True):
        answer = platform_bot.handle(submit)
    assert "abgelehnt" in answer["data"]["content"]
    db.session.refresh(req)
    assert req.status == "rejected"
    assert req.admin_note == "Doppelt"
    entry = (
        db.session.query(GlobalAuditEntry)
        .filter_by(action="tenant_request.reject")
        .one()
    )
    assert entry.details["via"] == "discord"
    assert entry.actor_id == admin.id

    # The audit entry's post updates the request's own message.
    platform_bot.request_decided(entry)
    patch_call = [c for c in bot if c[0] == "PATCH"][-1]
    assert patch_call[1] == f"/channels/{CHANNEL}/messages/m1"
    field = patch_call[2]["embeds"][0]["fields"][-1]
    assert field["name"] == "Entscheid"
    assert "Abgelehnt" in field["value"] and "Doppelt" in field["value"]
    # No manage address set: no link button either, so no buttons are left.
    assert patch_call[2]["components"] == []
    assert platform_bot._get(f"platform_bot:req:{req.id}") is None


def test_approve_is_deferred_to_a_job(bot, admin, db, seeded_db):
    req = _request(db, seeded_db)
    with patch("hubra.core.tasks.platform_bot_tasks.approve_request.delay") as delay:
        answer = platform_bot.handle(_click(f"p:req:ok:{req.id}"))
    assert answer == {"type": 5, "data": {"flags": platform_bot.EPHEMERAL}}
    delay.assert_called_once_with(req.id, admin.id, "itok")


def test_approve_job_sets_the_club_up(app, bot, admin, db, seeded_db):
    req = _request(db, seeded_db)
    tenant = Tenant(name="Neuer Verein", slug="neu", plan="starter")
    db.session.add(tenant)
    db.session.commit()
    with (
        patch(
            "hubra.core.tenant.service.TenantService.provision_tenant",
            return_value=tenant,
        ) as provision,
        patch("hubra.core.services.club_requests.notify_requester", return_value=True),
    ):
        text = platform_bot.approve_now(req.id, admin.id)
    provision.assert_called_once()
    assert "eingerichtet" in text
    db.session.refresh(req)
    assert req.status == "approved"
    # A second click finds it decided.
    answer = platform_bot.handle(_click(f"p:req:ok:{req.id}"))
    assert "schon entschieden" in answer["data"]["content"]
    db.session.delete(tenant)
    db.session.commit()


# ── Alerts ────────────────────────────────────────────────────────────────────


def _alert_message(alert_type="relay_down"):
    return {
        "id": "a1",
        "channel_id": CHANNEL,
        "embeds": [{"title": "Main relay is down", "fields": []}],
        "components": platform_bot.alert_buttons(alert_type),
    }


def test_acknowledge_updates_the_message(bot, admin):
    answer = platform_bot.handle(
        _click("p:al:ack:relay_down", message=_alert_message())
    )
    assert answer["type"] == 7
    assert answer["data"]["embeds"][0]["fields"][-1]["name"] == "Bestätigt"
    ids = [c.get("custom_id") for c in answer["data"]["components"][0]["components"]]
    assert ids == ["p:al:mute:relay_down"]


def test_silence_mutes_the_type_for_an_hour(bot, admin):
    answer = platform_bot.handle(
        _click("p:al:mute:relay_down", message=_alert_message())
    )
    assert answer["type"] == 7
    assert platform_bot.muted_until("relay_down")
    assert platform_monitor.channels("relay_down")["reason"] == "muted"
    assert platform_monitor.channels("backup_failed")["reason"] != "muted"


def test_resolved_alert_turns_green(bot, redis):
    platform_bot.track_alert({"id": "a1", "channel_id": CHANNEL}, "relay_down")
    platform_bot.track_alert({"id": "a2", "channel_id": CHANNEL}, "system")  # untracked
    assert list(redis.hgetall(platform_bot._ALERTS_KEY)) == ["a1"]
    info = json.loads(redis.hashes[platform_bot._ALERTS_KEY]["a1"])
    info["at"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    redis.hashes[platform_bot._ALERTS_KEY]["a1"] = json.dumps(info)

    still_down = [{"id": "relay:relay", "level": "error", "title": "x"}]
    with patch.object(platform_monitor, "open_problems", return_value=still_down):
        assert platform_bot.resolve_alerts() == 0
    with patch.object(platform_monitor, "open_problems", return_value=[]):
        assert platform_bot.resolve_alerts() == 1
    edit = [c for c in bot if c[0] == "PATCH"][-1]
    assert edit[2]["embeds"][0]["color"] == platform_bot.COLOR_GOOD
    assert redis.hgetall(platform_bot._ALERTS_KEY) == {}


# ── Commands ──────────────────────────────────────────────────────────────────


def test_commands_are_installed_once_on_the_platform_server(bot):
    assert platform_bot.register_commands() is True
    assert platform_bot.register_commands() is False
    puts = [c for c in bot if c[0] == "PUT"]
    assert len(puts) == 1
    assert puts[0][1] == f"/applications/555/guilds/{GUILD}/commands"
    assert {c["name"] for c in puts[0][2]} == {"plattform", "wartung"}


def test_status_command(bot, admin):
    with patch.object(platform_monitor, "open_problems", return_value=[]):
        answer = platform_bot.handle(_command("plattform", "status"))
    embed = answer["data"]["embeds"][0]
    assert embed["title"] == "Hubra-Plattform"
    assert any(f["name"].startswith("Offene Probleme (0)") for f in embed["fields"])


def test_club_command(bot, admin, db):
    tenant = Tenant(name="FC Seeblick", slug="fc-seeblick", plan="starter")
    db.session.add(tenant)
    db.session.commit()
    with patch(
        "hubra.core.services.tenant_health.for_tenants",
        return_value={tenant.id: {"members": 12, "active_members": 10}},
    ):
        answer = platform_bot.handle(_command("plattform", "verein", name="seeblick"))
    embed = answer["data"]["embeds"][0]
    assert embed["title"] == "FC Seeblick (fc-seeblick)"
    assert any(f["value"] == "12 (10 aktiv)" for f in embed["fields"])
    db.session.delete(tenant)
    db.session.commit()


def test_backup_command_needs_superadmin(bot, admin, db):
    with patch("hubra.core.tasks.backup_tasks.create_backup_task.delay") as delay:
        delay.return_value.id = "task-1"
        answer = platform_bot.handle(_command("plattform", "backup"))
    delay.assert_called_once()
    assert "Backup gestartet" in answer["data"]["content"]
    assert (
        db.session.query(GlobalAuditEntry).filter_by(action="backup.create").count()
        == 1
    )


# ── Maintenance ───────────────────────────────────────────────────────────────


def test_parse_start():
    start = platform_bot._parse_start("2030-11-05 22:00")
    assert start.astimezone(timezone.utc).isoformat().startswith("2030-11-05T21:00")
    assert platform_bot._parse_start("05.11.2030 22:00") == start
    assert platform_bot._parse_start("22:00") > datetime.now(timezone.utc)
    assert platform_bot._parse_start("bald") is None


def test_plan_start_and_end_maintenance(bot, admin, db):
    with patch.object(platform_bot, "notify_clubs") as notify:
        answer = platform_bot.handle(
            _command(
                "wartung", "planen", start="2030-11-05 22:00", minuten=30, text="Update"
            )
        )
        assert "geplant" in answer["data"]["content"]
        state = maintenance.state(fresh=True)
        assert state["active"] is False
        assert state["planned"]["minutes"] == 30
        assert state["planned"]["message"] == "Update"
        notify.assert_called_with(
            "maintenance_planned", maintenance.notice_payload(state)
        )

        # Not yet due; then due.
        assert maintenance.start_due() is None
        due = datetime(2030, 11, 5, 21, 10, tzinfo=timezone.utc)
        started = maintenance.start_due(due)
        assert started["active"] is True
        assert started["message"] == "Update"
        assert started["planned"] is None

        answer = platform_bot.handle(_command("wartung", "ende"))
        assert answer["data"]["content"] == "Wartung beendet."
        notify.assert_called_with("maintenance_ended", {})
    assert maintenance.state(fresh=True)["active"] is False


def test_missed_window_is_dropped(db):
    maintenance.plan(datetime(2020, 1, 1, tzinfo=timezone.utc), 30)
    assert maintenance.start_due() is None
    assert maintenance.state(fresh=True)["planned"] is None


def test_cancel_planned_maintenance(bot, admin):
    with patch.object(platform_bot, "notify_clubs") as notify:
        platform_bot.handle(
            _command("wartung", "planen", start="2030-11-05 22:00", minuten=30)
        )
        answer = platform_bot.handle(_command("wartung", "abbrechen"))
    assert answer["data"]["content"] == "Geplante Wartung abgesagt."
    notify.assert_called_with("maintenance_cancelled", {})
    assert maintenance.state(fresh=True)["planned"] is None


def test_discord_interactions_pass_the_maintenance_gate(client, db):
    maintenance.turn_on("Update", 10)
    resp = client.post("/api/v1/discord/interactions", data=b"{}")
    assert resp.status_code != 503
    maintenance.turn_off()


# ── Digest, releases ──────────────────────────────────────────────────────────


def test_digest_lists_new_clubs_and_problems(bot, db):
    tenant = Tenant(name="Neu FC", slug="neu-fc", plan="starter")
    db.session.add(tenant)
    db.session.commit()
    problems = [
        {"id": "relay:relay", "level": "error", "title": "Main relay is down"},
        {"id": "perf:/api/x", "level": "warning", "title": "GET /api/x is slow"},
    ]
    with patch.object(platform_monitor, "open_problems", return_value=problems):
        embed = platform_bot.digest_embed()
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert "Neu FC (neu-fc)" in fields["Neue Vereine (1)"]
    assert "Main relay is down" in fields["Offene Probleme (1)"]
    assert "GET /api/x is slow" in fields["Langsame Endpunkte"]
    db.session.delete(tenant)
    db.session.commit()


def test_digest_only_when_the_category_is_on(bot, db):
    platform_settings.set_many({"discord.log_events": "alerts"})
    db.session.commit()
    with patch.object(platform_discord, "post") as post:
        assert platform_bot.send_digest() is False
    post.assert_not_called()


def test_release_is_announced_once(bot, db):
    with (
        patch.object(platform_discord, "post") as post,
        patch.object(platform_bot, "notify_clubs") as notify,
        patch(
            "hubra.api.version.services.VersionService.get_version",
            return_value="9.9.9",
        ),
    ):
        assert platform_bot.announce_release() is True
        platform_bot._local.clear()
        assert platform_bot.announce_release() is False
    post.assert_called_once()
    assert post.call_args.args[0]["title"] == "Hubra 9.9.9 läuft"
    assert notify.call_args.args[0] == "release"


# ── Security ──────────────────────────────────────────────────────────────────


def test_many_failed_logins_from_one_address(redis):
    with patch("hubra.core.tasks.platform_bot_tasks.post_security.delay") as delay:
        for _ in range(platform_bot.FAILED_LOGIN_THRESHOLD + 3):
            platform_bot.failed_login("203.0.113.9", "x@test.ch")
    delay.assert_called_once()
    assert "203.0.113.9" in delay.call_args.args[1][0]


def test_staff_losing_two_factor_is_a_ping(db, seeded_db):
    user = seeded_db["user"]
    with patch.object(platform_bot, "security") as ping:
        platform_bot.staff_mfa_off(user)  # not staff
        ping.assert_not_called()
        user.is_superadmin = True
        platform_bot.staff_mfa_off(user)
    ping.assert_called_once()
    assert ping.call_args.kwargs["level"] == "error"


def test_staff_new_device_is_a_ping(db, seeded_db):
    user = seeded_db["user"]
    user.is_superadmin = True
    with patch.object(platform_bot, "security") as ping:
        platform_bot.staff_new_device(user, "203.0.113.9", "Firefox", "Linux")
    assert "203.0.113.9" in ping.call_args.args[1][2]


def test_security_posts_only_with_the_category(bot, db):
    with patch.object(platform_discord, "post") as post:
        assert platform_bot.post_security_now("t", ["x"]) is True
        platform_settings.set_many({"discord.log_events": "alerts"})
        db.session.commit()
        assert platform_bot.post_security_now("t", ["x"]) is False
    post.assert_called_once()


def test_key_reminder_monthly(bot, db):
    with (
        patch.object(platform_bot, "old_keys", return_value=["p", "c4"]),
        patch.object(platform_discord, "post") as post,
    ):
        assert platform_bot.key_reminder() is True
        assert platform_bot.key_reminder() is False
    text = post.call_args.args[0]["description"]
    assert "Plattform-Schlüssel" in text and "1 Vereins-Schlüssel" in text


def test_tick_runs_without_discord(db):
    from hubra.core.tasks.platform_bot_tasks import tick

    with patch.object(platform_bot, "resolve_alerts") as resolve:
        tick.run()
    resolve.assert_not_called()


def test_alert_posts_carry_buttons(bot, db):
    resp = MagicMock(status=200)
    resp.read.return_value = json.dumps({"id": "m9", "channel_id": CHANNEL}).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    with (
        patch(
            "hubra.core.services.platform_discord.urllib.request.urlopen",
            return_value=resp,
        ) as urlopen,
        patch.object(platform_bot, "track_alert") as track,
    ):
        assert platform_discord.post_alert({"title": "x"}, "relay_down") is True
    body = json.loads(urlopen.call_args.args[0].data)
    assert body["components"][0]["components"][0]["custom_id"] == "p:al:ack:relay_down"
    track.assert_called_once_with({"id": "m9", "channel_id": CHANNEL}, "relay_down")


def test_release_embed_lists_sections():
    embed = platform_bot.release_embed(
        "1.2.3",
        {
            "date": "2026-11-02",
            "sections": {"Neu": [f"Punkt {i}" for i in range(10)], "Behoben": []},
        },
    )
    assert embed["fields"] == [
        {
            "name": "Neu",
            "value": "\n".join(f"• Punkt {i}" for i in range(8)) + "\n… und 2 weitere",
        }
    ]
    assert embed["description"] == "Veröffentlicht am 2026-11-02"
