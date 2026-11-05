"""Manage › Diagnostics › Discord: the bot's state."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

from hubra.core.models.connected_app import ConnectedApp, ConnectedAppEvent
from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.models.tenant import Tenant
from hubra.core.services import discord_status, platform_discord, platform_settings

CHANNEL = "123456789012345678"
GUILD = "999000111"


@pytest.fixture(autouse=True)
def _clean(db):
    discord_status._local.clear()
    platform_discord._local_last.clear()
    with patch("hubra.core.redis_client.get_redis_client", return_value=None):
        yield
    db.session.rollback()
    db.session.query(ConnectedAppEvent).delete()
    db.session.query(ConnectedApp).delete()
    db.session.query(PlatformSetting).delete()
    db.session.query(Tenant).filter_by(slug="dc-club").delete()
    db.session.commit()
    discord_status._local.clear()
    platform_discord._local_last.clear()


@pytest.fixture
def bot(db):
    platform_settings.set_many(
        {
            "discord.client_id": "4242",
            "discord.bot_token": "bot-token",
            "discord.log_channel_id": CHANNEL,
        }
    )
    db.session.commit()


def _resp(payload):
    resp = MagicMock(status=200)
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _discord(routes: dict):
    """urlopen stand-in answering by path; a value that is an int is an HTTP error."""

    def fake(req, timeout=10):
        path = req.full_url.split("/api/v10", 1)[1]
        assert req.get_header("Authorization") == "Bot bot-token"
        value = routes[path]
        if isinstance(value, int):
            raise HTTPError(req.full_url, value, "err", {}, None)
        return _resp(value)

    return patch(
        "hubra.core.services.discord_status.urllib.request.urlopen", side_effect=fake
    )


HEALTHY = {
    "/users/@me": {"id": "77", "username": "Hubra"},
    "/users/@me/guilds?limit=200": [{"id": GUILD}],
    "/applications/@me": {
        "id": "4242",
        "interactions_endpoint_url": "https://api.example.org/api/v1/discord/interactions",
    },
    f"/channels/{CHANNEL}": {"id": CHANNEL, "name": "platform-log"},
}


def test_not_set_up(db):
    s = discord_status.status()
    assert s["configured"] is False
    assert s["settings"] == {
        "clientId": False,
        "publicKey": False,
        "clientSecret": False,
        "botToken": False,
    }
    assert s["check"]["botOk"] is None
    assert discord_status.problems() == []


def test_healthy_bot(app, db, bot):
    app.config["API_PUBLIC_URL"] = "https://api.example.org"
    club = Tenant(name="DC Club", slug="dc-club", plan="starter", status="active")
    db.session.add(club)
    db.session.flush()
    db.session.add_all(
        [
            ConnectedApp(
                tenant_id=club.id,
                provider="discord",
                external_id=GUILD,
                label="DC",
                status="active",
            ),
            ConnectedApp(
                tenant_id=club.id,
                provider="discord",
                external_id="555",
                label="Gone",
                status="pending",
            ),
            ConnectedApp(
                tenant_id=club.id,
                provider="discord",
                external_id="666",
                status="revoked",
            ),
        ]
    )
    db.session.commit()
    try:
        with _discord(HEALTHY):
            s = discord_status.status()
    finally:
        app.config["API_PUBLIC_URL"] = ""
    assert s["check"]["botOk"] is True
    assert s["check"]["botUser"] == {"id": "77", "username": "Hubra"}
    assert s["check"]["guildCount"] == 1
    assert "guildIds" not in s["check"]
    assert s["check"]["channelName"] == "platform-log"
    assert s["interactions"]["actual"] == s["interactions"]["expected"]
    assert s["redirectUris"] == [
        "https://api.example.org/api/v1/apps/callback/discord",
        "https://api.example.org/api/v1/account/linked-accounts/discord/callback",
    ]
    assert "appIdMismatch" not in s["check"]
    servers = {srv["serverId"]: srv for srv in s["servers"]}
    assert set(servers) == {GUILD, "555"}  # revoked is left out
    assert servers[GUILD]["botOnServer"] is True
    assert servers["555"]["botOnServer"] is False
    assert "bot-token" not in json.dumps(s)
    assert discord_status.problems() == []


def test_check_is_cached_until_refresh(db, bot):
    with _discord(HEALTHY) as urlopen:
        discord_status.status()
        calls = urlopen.call_count
        discord_status.status()
        assert urlopen.call_count == calls
        discord_status.status(refresh=True)
        assert urlopen.call_count == 2 * calls


def test_bad_token_is_an_open_problem(db, bot):
    with _discord({**HEALTHY, "/users/@me": 401}):
        s = discord_status.status()
    assert s["check"]["botOk"] is False
    assert "bot token" in s["check"]["botError"]
    (problem,) = discord_status.problems()
    assert problem["id"] == "discord:bot"
    assert problem["level"] == "error"
    assert isinstance(problem["since"], float)


def test_unreachable_channel(db, bot):
    with _discord({**HEALTHY, f"/channels/{CHANNEL}": 403}):
        s = discord_status.status()
    assert s["check"]["channelOk"] is False
    assert [p["id"] for p in discord_status.problems()] == ["discord:channel"]


def test_failed_log_posts_until_one_succeeds(db, bot):
    with patch(
        "hubra.core.services.platform_discord.urllib.request.urlopen",
        side_effect=HTTPError("u", 403, "Forbidden", {}, None),
    ):
        with pytest.raises(platform_discord.DiscordPostError):
            platform_discord.post({"title": "x"})
    state = platform_discord.last_post_state()
    assert "cannot post" in state["lastError"]
    assert [p["id"] for p in discord_status.problems()] == ["discord:log"]

    ok = MagicMock(status=200)
    ok.__enter__ = MagicMock(return_value=ok)
    ok.__exit__ = MagicMock(return_value=False)
    with patch(
        "hubra.core.services.platform_discord.urllib.request.urlopen", return_value=ok
    ):
        platform_discord.post({"title": "x"})
    assert platform_discord.last_post_state()["lastOkAt"]
    assert discord_status.problems() == []


def test_problems_show_in_the_alerts_overview(db, bot):
    from hubra.core.services import platform_monitor

    with _discord({**HEALTHY, "/users/@me": 401}):
        discord_status.run_check()
    ids = {p["id"]: p for p in platform_monitor.open_problems()}
    assert ids["discord:bot"]["area"] == "discord"
    assert ids["discord:bot"]["link"] == "/app/platform/discord"


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


def test_api(client, superadmin, bot):
    with _discord(HEALTHY):
        resp = client.get("/api/v1/manager/platform/discord/status")
        assert resp.status_code == 200
        assert resp.get_json()["check"]["botOk"] is True
        resp = client.post("/api/v1/manager/platform/discord/check")
        assert resp.status_code == 200


def test_api_needs_diagnostics_permission(client, seeded_db):
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    assert client.get("/api/v1/manager/platform/discord/status").status_code in (
        401,
        403,
    )


# ── Picking the platform log server and channel ───────────────────────────────

ME = "4242"
ROLE = "777"
PICKER = {
    "/users/@me/guilds?limit=200": [
        {"id": GUILD, "name": "Hubra Team", "icon": "abc"},
        {"id": "888", "name": "another", "icon": None},
    ],
    f"/channels/{CHANNEL}": {"id": CHANNEL, "guild_id": GUILD, "name": "platform-log"},
    f"/guilds/{GUILD}/roles": [
        {"id": GUILD, "permissions": str(1 << 10 | 1 << 11 | 1 << 14)},
        {"id": ROLE, "permissions": "0"},
    ],
    f"/guilds/{GUILD}/members/{ME}": {"roles": [ROLE]},
    f"/guilds/{GUILD}/channels": [
        {"id": "10", "type": 4, "name": "Hubra", "position": 0},
        {
            "id": CHANNEL,
            "type": 0,
            "name": "platform-log",
            "parent_id": "10",
            "position": 1,
        },
        {
            "id": "12",
            "type": 0,
            "name": "secret",
            "position": 2,
            # @everyone may not see it and the bot has no overwrite: left out
            "permission_overwrites": [
                {"id": GUILD, "type": 0, "deny": str(1 << 10), "allow": "0"}
            ],
        },
        {
            "id": "13",
            "type": 0,
            "name": "staff",
            "position": 3,
            "permission_overwrites": [
                {"id": GUILD, "type": 0, "deny": str(1 << 10), "allow": "0"},
                {"id": ROLE, "type": 0, "deny": "0", "allow": str(1 << 10)},
            ],
        },
        {"id": "14", "type": 2, "name": "voice", "position": 4},
    ],
}


def test_servers_with_the_current_one(db, bot):
    with _discord(PICKER):
        data = discord_status.servers()
    assert [s["name"] for s in data["servers"]] == ["another", "Hubra Team"]
    assert data["servers"][1]["icon"].endswith(f"/icons/{GUILD}/abc.png?size=64")
    assert data["currentServerId"] == GUILD


def test_channels_the_bot_can_post_in(db, bot):
    with _discord(PICKER):
        found = discord_status.channels(GUILD)
    # Like Discord: channels without a category first.
    assert [(c["id"], c["category"]) for c in found] == [
        ("13", None),
        (CHANNEL, "Hubra"),
    ]


def test_picker_needs_a_token(db):
    with pytest.raises(discord_status.PickerError):
        discord_status.servers()
    with pytest.raises(discord_status.PickerError):
        discord_status.channels("not-a-number")


def test_picker_api(client, superadmin, bot):
    with _discord(PICKER):
        assert client.get("/api/v1/manager/platform/discord/servers").status_code == 200
        resp = client.get(f"/api/v1/manager/platform/discord/servers/{GUILD}/channels")
        assert resp.status_code == 200
        assert len(resp.get_json()["channels"]) == 2


# ── Manage › Discord › Vereinsserver ─────────────────────────────────────────


def _club_with_server(db):
    from hubra.core import apps

    club = Tenant(name="DC Club", slug="dc-club", plan="starter", status="active")
    db.session.add(club)
    db.session.flush()
    conn = ConnectedApp(
        tenant_id=club.id,
        provider="discord",
        external_id=GUILD,
        label="DC",
        status="active",
        scopes=["announce", "roles"],
        config={
            "guild_name": "DC Server",
            "channel_id": "1",
            "announce_polls": True,
            "role_map": [{"source": "group:1", "role_id": "2"}],
            "posted": {"e:1": [["1", "2"]]},
        },
    )
    db.session.add(conn)
    db.session.flush()
    apps.record(conn, "announced", True, "Event: Grillabend")
    apps.record(conn, "skipped", True, "Poll: off")
    apps.record(conn, "announced", False, "Missing Access")
    db.session.commit()
    return club, conn


def test_club_overview(db, bot):
    club, conn = _club_with_server(db)
    data = discord_status.server_overview()
    [srv] = data["servers"]
    assert srv["club"] == "DC Club" and srv["clubId"] == club.id
    assert srv["server"] == "DC Server"
    # Defaults on (events, posts), polls turned on; reminders off; roles
    # counted; no commands scope, so no buttons.
    assert srv["features"] == [
        "Anlässe",
        "Beiträge",
        "Umfragen",
        "1 Rollen-Zuordnungen",
    ]
    assert srv["week"] == {"ok": 2, "failed": 1}
    assert srv["lastPostAt"] is not None
    assert srv["liveMessages"] == 1
    assert srv["mainChannel"] is True and srv["logChannel"] is False
    assert srv["botOnServer"] is None  # not checked yet
    assert data["totals"] == {
        "servers": 1,
        "active": 1,
        "withErrors": 1,
        "botMissing": 0,
    }


def test_club_activity(db, bot):
    _, conn = _club_with_server(db)
    found = discord_status.server_activity(conn.id)
    assert found["club"] == "DC Club"
    assert [e["action"] for e in found["events"]] == [
        "announced",
        "skipped",
        "announced",
    ]
    assert found["events"][0]["ok"] is False  # newest first
    assert discord_status.server_activity(999999) is None


def test_club_overview_api(client, superadmin, bot, db):
    _, conn = _club_with_server(db)
    resp = client.get("/api/v1/manager/platform/discord/clubs")
    assert resp.status_code == 200
    assert resp.get_json()["servers"][0]["id"] == conn.id
    resp = client.get(f"/api/v1/manager/platform/discord/clubs/{conn.id}/activity")
    assert resp.status_code == 200 and len(resp.get_json()["events"]) == 3
    assert (
        client.get("/api/v1/manager/platform/discord/clubs/999999/activity").status_code
        == 404
    )


def test_channel_name():
    assert discord_status.channel_name("  Hubra Log!! ") == "hubra-log"
    assert discord_status.channel_name("Änderungen & Audit") == "änderungen-audit"
    assert discord_status.channel_name("---") == ""


def test_create_a_private_channel(db, bot):
    sent = {}

    def fake(method, path, body=None):
        sent.update(method=method, path=path, body=body)
        return {"id": "321", "name": body["name"]}

    with patch("hubra.core.services.platform_bot._bot", side_effect=fake):
        made = discord_status.create_channel(GUILD, "Hubra Audit")
    assert made == {"id": "321", "name": "hubra-audit"}
    assert sent["method"] == "POST" and sent["path"] == f"/guilds/{GUILD}/channels"
    overwrites = {o["id"]: o for o in sent["body"]["permission_overwrites"]}
    assert overwrites[GUILD]["deny"] == str(1 << 10)  # @everyone can't see it
    assert int(overwrites["4242"]["allow"]) & (1 << 11)  # the bot can post


def test_create_channel_without_the_right(db, bot):
    from hubra.core.services.platform_bot import BotError

    with patch(
        "hubra.core.services.platform_bot._bot",
        side_effect=BotError("Discord answered 403", 403),
    ):
        with pytest.raises(discord_status.PickerError, match="Manage Channels"):
            discord_status.create_channel(GUILD, "log")


def test_create_channel_api(client, superadmin, bot):
    with patch(
        "hubra.core.services.platform_bot._bot",
        return_value={"id": "321", "name": "hubra-log"},
    ):
        resp = client.post(
            f"/api/v1/manager/platform/discord/servers/{GUILD}/channels",
            json={"name": "hubra-log"},
        )
    assert resp.status_code == 201
    assert resp.get_json()["id"] == "321"


def test_token_request_host_is_not_the_public_address(app):
    """The Claude connector reads the status with an API token from inside
    the cluster: its host (platform-backend:5000) is no address for the
    Developer Portal, so without API_PUBLIC_URL the URLs are unknown."""
    from flask import g

    app.config["API_PUBLIC_URL"] = ""
    with app.test_request_context(base_url="http://platform-backend:5000"):
        assert discord_status.expected_interactions_url() == (
            "http://platform-backend:5000/api/v1/discord/interactions"
        )
        g.api_token = {"id": 1, "kind": "platform"}
        assert discord_status.expected_interactions_url() == ""
        assert discord_status.redirect_uris() == []
        app.config["API_PUBLIC_URL"] = "https://api.example.org"
        try:
            assert discord_status.expected_interactions_url() == (
                "https://api.example.org/api/v1/discord/interactions"
            )
        finally:
            app.config["API_PUBLIC_URL"] = ""
