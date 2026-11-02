"""Manage › Diagnostics › Discord: the bot's state."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

from hubra.core.models.connected_app import ConnectedApp
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
