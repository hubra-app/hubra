"""Linked outside accounts on the SSO account page (Discord)."""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from hubra.core.identity import DiscordIdentity, Identity, IdentityError
from hubra.core.models.connected_app import ExternalAccount
from hubra.core.models.user import User

BASE = "/api/v1/account/linked-accounts"


@pytest.fixture
def discord_config(app):
    app.config.update(DISCORD_CLIENT_ID="cid", DISCORD_CLIENT_SECRET="csecret")
    yield
    app.config.update(DISCORD_CLIENT_ID="", DISCORD_CLIENT_SECRET="")


def _start(client):
    resp = client.post(f"{BASE}/discord/start")
    assert resp.status_code == 200, resp.get_json()
    url = urlparse(resp.get_json()["url"])
    query = parse_qs(url.query)
    assert url.netloc == "discord.com"
    assert query["scope"] == ["identify"]
    return query["state"][0]


def _back(resp):
    assert resp.status_code == 302
    return parse_qs(urlparse(resp.headers["Location"]).query)


def test_list_without_platform_credentials(client, auth_headers):
    data = client.get(f"{BASE}/").get_json()
    assert data["providers"] == [
        {"code": "discord", "name": "Discord", "available": False}
    ]
    assert data["accounts"] == []
    assert client.post(f"{BASE}/discord/start").status_code == 409


def test_list_needs_sign_in(client, db):
    assert client.get(f"{BASE}/").status_code == 401


def test_link_round_trip(client, db, auth_headers, discord_config, seeded_db):
    state = _start(client)
    with (
        patch.object(
            DiscordIdentity, "identify", return_value=Identity("4242", "mike")
        ),
        patch("hubra.core.modules.emit") as emit,
    ):
        resp = client.get(f"{BASE}/discord/callback?state={state}&code=abc")
    assert _back(resp) == {"linked": ["discord"]}
    acc = db.session.query(ExternalAccount).one()
    assert (acc.user_id, acc.external_id, acc.username) == (
        seeded_db["user"].id,
        "4242",
        "mike",
    )
    data = client.get(f"{BASE}/").get_json()
    assert data["accounts"][0]["username"] == "mike"
    # The admin has no club rows in this test; no club to tell.
    assert emit.call_count == 0


def test_callback_needs_the_browser_that_started_it(
    client, db, auth_headers, discord_config
):
    state = _start(client)
    client.delete_cookie("hubra_link_account")
    with patch.object(DiscordIdentity, "identify") as identify:
        resp = client.get(f"{BASE}/discord/callback?state={state}&code=abc")
    assert _back(resp)["error"] == ["expired"]
    identify.assert_not_called()


def test_callback_lands_only_on_the_account_that_started_it(
    client, db, auth_headers, discord_config
):
    state = _start(client)
    other = User(
        email="o@test.ch", first_name="O", last_name="O", private_email_verified=True
    )
    other.set_password("password123")
    db.session.add(other)
    db.session.commit()
    client.post(
        "/api/v1/auth/login", json={"email": "o@test.ch", "password": "password123"}
    )
    with patch.object(DiscordIdentity, "identify", return_value=Identity("4242", "x")):
        resp = client.get(f"{BASE}/discord/callback?state={state}&code=abc")
    assert _back(resp)["error"] == ["signin"]
    assert db.session.query(ExternalAccount).count() == 0


def test_a_discord_account_links_to_one_person(
    client, db, auth_headers, discord_config
):
    other = User(
        email="o@test.ch", first_name="O", last_name="O", private_email_verified=True
    )
    other.set_password("password123")
    db.session.add(other)
    db.session.flush()
    db.session.add(
        ExternalAccount(user_id=other.id, provider="discord", external_id="4242")
    )
    db.session.commit()
    state = _start(client)
    with patch.object(DiscordIdentity, "identify", return_value=Identity("4242", "x")):
        resp = client.get(f"{BASE}/discord/callback?state={state}&code=abc")
    assert _back(resp)["error"] == ["taken"]


def test_failed_sign_in_on_discord(client, db, auth_headers, discord_config):
    state = _start(client)
    with patch.object(DiscordIdentity, "identify", side_effect=IdentityError("x")):
        resp = client.get(f"{BASE}/discord/callback?state={state}&code=abc")
    assert _back(resp)["error"] == ["failed"]


def test_unlink(client, db, auth_headers, seeded_db):
    db.session.add(
        ExternalAccount(
            user_id=seeded_db["user"].id, provider="discord", external_id="1"
        )
    )
    db.session.commit()
    assert client.delete(f"{BASE}/discord").status_code == 200
    assert db.session.query(ExternalAccount).count() == 0
    assert client.delete(f"{BASE}/discord").status_code == 404


def test_link_and_unlink_tell_each_club(client, db, tenant_pair, discord_config):
    client.post(
        "/api/v1/auth/login", json={"email": "user@test.ch", "password": "password123"}
    )
    state = _start(client)
    with (
        patch.object(DiscordIdentity, "identify", return_value=Identity("77", "u")),
        patch("hubra.core.modules.emit") as emit,
    ):
        client.get(f"{BASE}/discord/callback?state={state}&code=abc")
        assert [c.args[0] for c in emit.call_args_list] == ["account.linked"] * 2
        assert emit.call_args.kwargs["external_id"] == "77"
        emit.reset_mock()
        client.delete(f"{BASE}/discord")
        assert [c.args[0] for c in emit.call_args_list] == ["account.unlinked"] * 2
