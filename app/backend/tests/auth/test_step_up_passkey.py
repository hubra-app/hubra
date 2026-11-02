"""Confirming a platform action (step-up) with a passkey instead of the
password.

The challenge is tied to the account and to the sign-in (account session)
that asked for it, and has its own purpose: a sign-in challenge cannot
confirm an action and a step-up challenge cannot sign anyone in.  A success
opens the same ten-minute window (``sudo_until``) as the password.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.auth.test_passkeys import (
    ORIGIN,
    SoftAuthenticator,
    _add,
    _passkey_sign_in,
    _signed_in,
    _user,
)

GUARDED = "/api/v1/system/tenants/999/impersonate"


@pytest.fixture(autouse=True)
def _sso(app, monkeypatch):
    monkeypatch.setitem(app.config, "SSO_BASE_URL", ORIGIN)


def _admin_with_passkey(app, db, email="solo@test.ch"):
    _user(db, email=email, is_superadmin=True)
    key = SoftAuthenticator()
    client = _signed_in(app, email)
    assert _add(client, key).status_code == 201
    return client, key


def _options(client):
    resp = client.post("/api/v1/account/step-up/passkey/options", json={})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _confirm(client, start, credential):
    return client.post(
        "/api/v1/account/step-up/passkey",
        json={"state": start["state"], "credential": credential},
    )


def test_status_offers_a_passkey_only_with_one(app, db):
    _user(db, is_superadmin=True)
    client = _signed_in(app)
    body = client.get("/api/v1/account/step-up").get_json()
    assert body == {"sudoUntil": None, "passkey": False, "code": False}

    _add(client, SoftAuthenticator())
    body = client.get("/api/v1/account/step-up").get_json()
    assert body["passkey"] is True and body["sudoUntil"] is None


def test_confirm_with_a_passkey_opens_the_window(app, db):
    client, key = _admin_with_passkey(app, db)
    with patch.dict(app.config, {"STEP_UP_ENFORCED": True}):
        assert client.post(GUARDED, json={"reason": "x"}).status_code == 403

        start = _options(client)
        # Only this account's passkeys, and the person must be verified.
        assert [c["id"] for c in start["options"]["allowCredentials"]] == [key.id]
        assert start["options"]["userVerification"] == "required"
        resp = _confirm(client, start, key.get(start["options"]))
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["sudoUntil"]

        assert client.get("/api/v1/account/step-up").get_json()["sudoUntil"]
        # Past the gate: 404/422 because the club does not exist.
        assert client.post(GUARDED, json={"reason": "x"}).status_code in (404, 422)


def test_a_sign_in_challenge_cannot_confirm(app, db):
    client, key = _admin_with_passkey(app, db)
    start = client.post("/api/v1/auth/passkey/options", json={}).get_json()
    resp = _confirm(client, start, key.get(start["options"]))
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "PASSKEY_INVALID"
    assert client.get("/api/v1/account/step-up").get_json()["sudoUntil"] is None


def test_a_step_up_challenge_cannot_sign_in(app, db):
    client, key = _admin_with_passkey(app, db)
    start = _options(client)
    resp = app.test_client().post(
        "/api/v1/auth/passkey/login",
        json={"state": start["state"], "credential": key.get(start["options"])},
    )
    assert resp.status_code == 400


def test_another_accounts_passkey_is_refused(app, db):
    client, _key = _admin_with_passkey(app, db)
    _other_client, other_key = _admin_with_passkey(app, db, "other@test.ch")

    start = _options(client)
    resp = _confirm(client, start, other_key.get(start["options"]))
    assert resp.status_code == 400
    assert client.get("/api/v1/account/step-up").get_json()["sudoUntil"] is None


def test_the_challenge_belongs_to_the_sign_in_that_asked(app, db):
    """A challenge fetched by one sign-in (say, a stolen tab) does not
    confirm for another sign-in of the same account."""
    first, key = _admin_with_passkey(app, db)
    second = app.test_client()
    # Another browser: a sign-in from the same browser keeps its session row.
    second.environ_base["HTTP_USER_AGENT"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    )
    assert _passkey_sign_in(second, key).status_code == 200

    start = _options(first)
    resp = _confirm(second, start, key.get(start["options"]))
    assert resp.status_code == 400
    assert second.get("/api/v1/account/step-up").get_json()["sudoUntil"] is None
    assert first.get("/api/v1/account/step-up").get_json()["sudoUntil"] is None


def test_an_answer_works_once(app, db):
    client, key = _admin_with_passkey(app, db)
    start = _options(client)
    answer = key.get(start["options"])
    assert _confirm(client, start, answer).status_code == 200
    # A replayed answer is refused (Redis marks the challenge used; without
    # it, the signature counter stops the replay).
    assert _confirm(client, start, answer).status_code == 400


def test_without_a_passkey_there_are_no_options(app, db):
    _user(db, is_superadmin=True)
    client = _signed_in(app)
    resp = client.post("/api/v1/account/step-up/passkey/options", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "PASSKEYS_UNAVAILABLE"


def test_needs_a_sign_in(app, db):
    resp = app.test_client().post("/api/v1/account/step-up/passkey/options", json={})
    assert resp.status_code == 401
    assert app.test_client().get("/api/v1/account/step-up").status_code == 401
