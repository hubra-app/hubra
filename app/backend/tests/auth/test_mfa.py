"""Two-factor sign-in with an authenticator app (TOTP) and recovery codes."""

from __future__ import annotations

import time

import pytest

from hubra.api.auth import mfa

PASSWORD = "password123"


def _user(db, email="solo@test.ch", **fields):
    from hubra.core.models.user import User

    user = User(email=email, first_name="Solo", last_name="User", **fields)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def _code(secret: str, steps_ahead: int = 0) -> str:
    return mfa._code_at(secret, int(time.time() // 30) + steps_ahead)


def _sign_in(client, email="solo@test.ch"):
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _turn_on(client) -> tuple[str, list[str]]:
    """Set up two-factor for the signed-in account: (secret, recovery codes)."""
    resp = client.post(
        "/api/v1/account/mfa/totp/setup", json={"currentPassword": PASSWORD}
    )
    assert resp.status_code == 200, resp.get_json()
    setup = resp.get_json()
    assert setup["uri"].startswith("otpauth://totp/Hubra:")
    assert setup["qrSvg"].lstrip().startswith("<")
    resp = client.post(
        "/api/v1/account/mfa/totp/enable", json={"code": _code(setup["secret"])}
    )
    assert resp.status_code == 200, resp.get_json()
    return setup["secret"], resp.get_json()["recoveryCodes"]


@pytest.fixture
def enrolled(app, db):
    """An account with two-factor on, and a fresh browser: (secret, codes)."""
    _user(db)
    client = app.test_client()
    _sign_in(client)
    secret, codes = _turn_on(client)
    return secret, codes


def test_setting_up_turns_it_on_and_gives_ten_codes(app, db):
    _user(db)
    client = app.test_client()
    _sign_in(client)
    assert client.get("/api/v1/account/mfa").get_json()["enabled"] is False

    _, codes = _turn_on(client)

    assert len(codes) == 10 and len(set(codes)) == 10
    status = client.get("/api/v1/account/mfa").get_json()
    assert status["enabled"] is True
    assert status["recoveryCodesLeft"] == 10


def test_setup_needs_the_password_and_a_right_code(app, db):
    user = _user(db)
    client = app.test_client()
    _sign_in(client)

    resp = client.post("/api/v1/account/mfa/totp/setup", json={"currentPassword": "x"})
    assert resp.status_code == 400
    client.post("/api/v1/account/mfa/totp/setup", json={"currentPassword": PASSWORD})
    resp = client.post("/api/v1/account/mfa/totp/enable", json={"code": "000000"})
    assert resp.status_code == 400
    db.session.refresh(user)
    assert not mfa.enabled(user)


def test_the_secret_is_stored_encrypted(app, db, enrolled):
    from hubra.core.models.user import User

    secret, codes = enrolled
    user = db.session.query(User).filter_by(email="solo@test.ch").one()
    assert secret not in user.totp_secret
    assert not set(codes) & set(user.recovery_codes)


def test_password_alone_no_longer_signs_in(app, db, enrolled):
    client = app.test_client()
    body = _sign_in(client)

    assert body["mfaRequired"] is True and body["mfaToken"]
    assert client.get("/api/v1/account/profile").status_code == 401


def test_password_and_app_code_sign_in(app, db, enrolled):
    secret, _ = enrolled
    client = app.test_client()
    token = _sign_in(client)["mfaToken"]

    resp = client.post(
        "/api/v1/auth/login/mfa", json={"mfaToken": token, "code": _code(secret, 1)}
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["user"]["email"] == "solo@test.ch"
    assert client.get("/api/v1/account/profile").status_code == 200


def test_an_app_code_works_once(app, db, enrolled):
    secret, _ = enrolled
    code = _code(secret, 1)
    first = app.test_client()
    first.post(
        "/api/v1/auth/login/mfa",
        json={"mfaToken": _sign_in(first)["mfaToken"], "code": code},
    )
    second = app.test_client()
    resp = second.post(
        "/api/v1/auth/login/mfa",
        json={"mfaToken": _sign_in(second)["mfaToken"], "code": code},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "MFA_INVALID"


def test_a_recovery_code_works_once(app, db, enrolled):
    _, codes = enrolled

    def use(code):
        client = app.test_client()
        return client.post(
            "/api/v1/auth/login/mfa",
            json={"mfaToken": _sign_in(client)["mfaToken"], "code": code.upper()},
        )

    assert use(codes[0]).status_code == 200
    assert use(codes[0]).status_code == 400
    client = app.test_client()
    _sign_in(client)  # still needs the second step


def test_five_wrong_codes_lock_the_account(app, db, enrolled):
    client = app.test_client()
    token = _sign_in(client)["mfaToken"]
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login/mfa", json={"mfaToken": token, "code": "123456"}
        )
        assert resp.status_code == 400
    resp = client.post(
        "/api/v1/auth/login", json={"email": "solo@test.ch", "password": PASSWORD}
    )
    assert resp.get_json()["error"] == "ACCOUNT_LOCKED"


def test_a_forged_or_old_challenge_is_refused(app, db, enrolled):
    secret, _ = enrolled
    client = app.test_client()
    resp = client.post(
        "/api/v1/auth/login/mfa", json={"mfaToken": "forged", "code": _code(secret)}
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "MFA_EXPIRED"


def test_turning_it_off_needs_the_password(app, db):
    _user(db)
    client = app.test_client()
    _sign_in(client)
    _turn_on(client)

    resp = client.post(
        "/api/v1/account/mfa/totp/disable", json={"currentPassword": "x"}
    )
    assert resp.status_code == 400
    resp = client.post(
        "/api/v1/account/mfa/totp/disable", json={"currentPassword": PASSWORD}
    )
    assert resp.status_code == 200
    assert resp.get_json()["enabled"] is False
    assert "mfaRequired" not in _sign_in(app.test_client())


def test_new_recovery_codes_replace_the_old(app, db):
    _user(db)
    client = app.test_client()
    _sign_in(client)
    _, old = _turn_on(client)

    resp = client.post(
        "/api/v1/account/mfa/recovery-codes", json={"currentPassword": PASSWORD}
    )
    new = resp.get_json()["recoveryCodes"]
    assert not set(new) & set(old)
    other = app.test_client()
    resp = other.post(
        "/api/v1/auth/login/mfa",
        json={"mfaToken": _sign_in(other)["mfaToken"], "code": old[0]},
    )
    assert resp.status_code == 400


def test_club_sign_in_asks_for_the_code_too(app, seeded_db, db):
    client = app.test_client()
    _sign_in(client, "admin@test.ch")
    secret, _ = _turn_on(client)

    other = app.test_client()
    token = _sign_in(other, "admin@test.ch")["mfaToken"]
    resp = other.post(
        "/api/v1/auth/login/mfa", json={"mfaToken": token, "code": _code(secret, 1)}
    )
    assert resp.status_code == 200
    assert resp.get_json()["member"] is not None


def test_staff_need_it_before_the_platform_answers(app, db, monkeypatch):
    monkeypatch.setitem(app.config, "MFA_REQUIRED_FOR_STAFF", True)
    _user(db, is_superadmin=True)
    client = app.test_client()
    _sign_in(client)

    resp = client.get("/api/v1/system/tenants")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MFA_SETUP_REQUIRED"
    assert client.get("/api/v1/account/mfa").get_json()["required"] is True

    secret, _ = _turn_on(client)
    assert client.get("/api/v1/system/tenants").status_code == 200


def test_members_are_not_made_to(app, db, monkeypatch):
    monkeypatch.setitem(app.config, "MFA_REQUIRED_FOR_STAFF", True)
    _user(db)
    client = app.test_client()
    _sign_in(client)
    assert client.get("/api/v1/account/mfa").get_json()["required"] is False


def test_reset_mfa_command(app, db, enrolled):
    from hubra.core.models.user import User

    result = app.test_cli_runner().invoke(args=["reset-mfa", "--email", "solo@test.ch"])
    assert result.exit_code == 0, result.output
    user = db.session.query(User).filter_by(email="solo@test.ch").one()
    db.session.refresh(user)
    assert not mfa.enabled(user)
