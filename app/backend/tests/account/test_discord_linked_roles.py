"""Discord Linked Roles: the token kept at linking, the values sent, and
clearing on unlink. Also the app notification channel preferences."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from hubra.core.identity import DiscordIdentity, Identity
from hubra.core.models.connected_app import ExternalAccount
from hubra.core.services import discord_roles

BASE = "/api/v1/account/linked-accounts"


@pytest.fixture
def discord_config(app, db):
    from hubra.core.services import platform_settings

    keys = {
        "discord.client_id": "123",
        "discord.client_secret": "csecret",
        "discord.bot_token": "bot",
    }
    platform_settings.set_many(keys)
    db.session.commit()
    discord_roles._local.clear()
    with patch("hubra.core.redis_client.get_redis_client", return_value=None):
        yield
    platform_settings.set_many(dict.fromkeys(keys))
    db.session.commit()
    discord_roles._local.clear()


def _token(expires_in=3600):
    return {
        "access": "acc",
        "refresh": "ref",
        "expires_at": int(time.time()) + expires_in,
        "scope": "identify role_connections.write",
    }


def _link(client):
    resp = client.post(f"{BASE}/discord/start")
    state = parse_qs(urlparse(resp.get_json()["url"]).query)["state"][0]
    with (
        patch.object(
            DiscordIdentity,
            "identify",
            return_value=Identity("4242", "mike", token=_token()),
        ),
        patch(
            "hubra.core.tasks.connected_app_tasks.push_role_connection.delay"
        ) as push,
    ):
        resp = client.get(f"{BASE}/discord/callback?state={state}&code=abc")
    assert resp.status_code == 302
    return push


def test_link_keeps_the_token_encrypted(client, db, auth_headers, discord_config):
    push = _link(client)
    acc = db.session.query(ExternalAccount).one()
    assert acc.token_encrypted and "acc" not in acc.token_encrypted
    assert discord_roles.read_token(acc)["refresh"] == "ref"
    push.assert_called_once_with(acc.id)
    data = client.get(f"{BASE}/").get_json()
    assert data["accounts"][0]["linkedRoles"] is True


def test_unlink_clears_and_revokes(client, db, auth_headers, discord_config):
    _link(client)
    with (
        patch.object(discord_roles, "_call") as call,
        patch.object(DiscordIdentity, "revoke") as revoke,
    ):
        assert client.delete(f"{BASE}/discord").status_code == 200
    method, path, auth, body = call.call_args.args
    assert (method, auth, body["metadata"]) == ("PUT", "Bearer acc", {})
    assert path == "/users/@me/applications/123/role-connection"
    assert {c.args[0] for c in revoke.call_args_list} == {"acc", "ref"}


def _resp(payload=None):
    resp = MagicMock(status=200)
    resp.read.return_value = (
        json.dumps(payload).encode() if payload is not None else b""
    )
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_push_registers_metadata_once_and_sends_values(
    app, db, seeded_db, discord_config
):
    acc = ExternalAccount(
        user_id=seeded_db["user"].id, provider="discord", external_id="1"
    )
    discord_roles.store_token(acc, _token())
    db.session.add(acc)
    db.session.commit()
    seen = []

    def fake(req, timeout=10):
        seen.append((req.get_method(), req.full_url.split("/api/v10", 1)[1], req.data))
        return _resp({})

    with (
        patch(
            "hubra.core.services.discord_roles.urllib.request.urlopen", side_effect=fake
        ),
        patch.object(
            discord_roles,
            "values_for",
            return_value={"member": 1, "clubs": 2, "member_since": "2020-01-01"},
        ),
    ):
        assert discord_roles.push(acc) is True
        assert discord_roles.push(acc) is True
    paths = [p for _m, p, _d in seen]
    assert paths.count("/applications/123/role-connections/metadata") == 1
    body = json.loads(seen[-1][2])
    assert body == {
        "platform_name": "Hubra",
        "metadata": {"member": 1, "clubs": 2, "member_since": "2020-01-01"},
    }


def test_expired_token_is_refreshed(app, db, seeded_db, discord_config):
    acc = ExternalAccount(
        user_id=seeded_db["user"].id, provider="discord", external_id="2"
    )
    discord_roles.store_token(acc, _token(expires_in=-10))
    db.session.add(acc)
    db.session.commit()
    fresh = {**_token(), "access": "new"}
    with (
        patch.object(DiscordIdentity, "refresh", return_value=fresh) as refresh,
        patch.object(discord_roles, "_call") as call,
        patch.object(
            discord_roles, "values_for", return_value={"member": 0, "clubs": 0}
        ),
    ):
        assert discord_roles.push(acc) is True
    refresh.assert_called_once_with("ref")
    assert call.call_args.args[2] == "Bearer new"
    assert discord_roles.read_token(acc)["access"] == "new"


def test_refused_token_is_forgotten(app, db, seeded_db, discord_config):
    acc = ExternalAccount(
        user_id=seeded_db["user"].id, provider="discord", external_id="3"
    )
    discord_roles.store_token(acc, _token())
    db.session.add(acc)
    db.session.commit()
    with (
        patch.object(
            discord_roles,
            "_call",
            side_effect=[None, discord_roles.RoleConnectionError("401", 401)],
        ),
        patch.object(
            discord_roles, "values_for", return_value={"member": 0, "clubs": 0}
        ),
    ):
        assert discord_roles.push(acc) is False
    assert acc.token_encrypted is None


def test_values_for_a_member(monkeypatch):
    from datetime import date
    from types import SimpleNamespace as NS

    from hubra.core.services import account

    rows = [
        (None, NS(is_blocked=False, status="active", joined=date(2021, 5, 1))),
        (None, NS(is_blocked=False, status="active", joined=date(2023, 1, 9))),
        (None, NS(is_blocked=True, status="active", joined=date(2019, 1, 1))),
        (None, NS(is_blocked=False, status="inactive", joined=date(2018, 1, 1))),
    ]
    monkeypatch.setattr(account, "memberships", lambda _uid: rows)
    values = discord_roles.values_for(1)
    assert values == {"member": 1, "clubs": 2, "member_since": "2021-05-01"}
    monkeypatch.setattr(account, "memberships", lambda _uid: rows[2:])
    assert discord_roles.values_for(1) == {"member": 0, "clubs": 0}


# ── App notification channels (preferences) ──────────────────────────────────


def test_app_channels_are_off_until_turned_on():
    from hubra.api.notifications import prefs

    assert prefs.wants(None, "posts", "bell") is True
    assert prefs.wants(None, "posts", "discord") is False
    assert prefs.wants({"posts": {"discord": True}}, "posts", "discord") is True
    # Without a topic (security notices): bell yes, an app never.
    assert prefs.wants({"posts": {"discord": True}}, None, "discord") is False
    assert prefs.validate({"posts": {"discord": True}}) is not None
    assert prefs.validate({"posts": {"discord": True}}, ["discord"]) is None


def test_app_channel_choice_is_stored_only_when_on():
    from types import SimpleNamespace

    from hubra.api.notifications import prefs

    member = SimpleNamespace(notify_prefs=None)
    prefs.apply(member, {"posts": {"discord": True, "push": False}})
    assert member.notify_prefs == {"posts": {"discord": True, "push": False}}
    prefs.apply(member, {"posts": {"discord": False, "push": True}})
    assert member.notify_prefs is None
