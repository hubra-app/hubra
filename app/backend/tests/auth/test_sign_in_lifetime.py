"""A sign-in lasts a fixed time from the sign-in, not from the last refresh.

Before, every refresh handed out a new 30-day refresh token, so a browser
that came back within 30 days stayed signed in for good, and club switches
and "keep me signed in" left off still gave 30-day cookies.
"""

import time

from flask_jwt_extended import create_refresh_token, decode_token

DAY = 24 * 3600


def _cookie(resp, name):
    for header in resp.headers.getlist("Set-Cookie"):
        if header.startswith(f"{name}="):
            return header
    return None


def _max_age(header):
    for part in header.split(";"):
        part = part.strip()
        if part.startswith("Max-Age="):
            return int(part[len("Max-Age="):])
    raise AssertionError(f"no Max-Age in {header}")


def _token(header):
    return header.split(";")[0].split("=", 1)[1]


def _refresh(app, client, user, claims):
    with app.app_context():
        token = create_refresh_token(
            identity=f"user:{user.id}",
            additional_claims={"user_id": user.id, **claims},
        )
    client.set_cookie("refresh_token_cookie", token)
    return client.post("/api/v1/auth/refresh")


def test_refresh_does_not_restart_the_lifetime(app, client, seeded_db):
    started = int(time.time()) - 10 * DAY
    resp = _refresh(
        app, client, seeded_db["user"], {"keep": True, "signed_in_at": started}
    )
    assert resp.status_code == 200
    header = _cookie(resp, "refresh_token_cookie")
    assert abs(_max_age(header) - 20 * DAY) <= 5
    with app.app_context():
        claims = decode_token(_token(header))
    assert claims["signed_in_at"] == started
    assert abs(claims["exp"] - (started + 30 * DAY)) <= 5


def test_refresh_after_the_lifetime_signs_out(app, client, seeded_db):
    started = int(time.time()) - 31 * DAY
    resp = _refresh(
        app, client, seeded_db["user"], {"keep": True, "signed_in_at": started}
    )
    assert resp.status_code == 401


def test_short_sign_in_ends_after_a_day_even_when_active(app, client, seeded_db):
    user = seeded_db["user"]
    started = int(time.time()) - 2 * 3600
    resp = _refresh(app, client, user, {"keep": False, "signed_in_at": started})
    assert resp.status_code == 200
    assert abs(_max_age(_cookie(resp, "refresh_token_cookie")) - 22 * 3600) <= 5

    started = int(time.time()) - 25 * 3600
    resp = _refresh(app, client, user, {"keep": False, "signed_in_at": started})
    assert resp.status_code == 401


def test_token_from_before_the_change_gets_one_more_lifetime(app, client, seeded_db):
    resp = _refresh(app, client, seeded_db["user"], {"keep": True})
    assert resp.status_code == 200
    header = _cookie(resp, "refresh_token_cookie")
    with app.app_context():
        claims = decode_token(_token(header))
    assert abs(claims["signed_in_at"] - time.time()) <= 5
    assert abs(_max_age(header) - 30 * DAY) <= 5


def test_short_sign_in_also_shortens_the_account_token(client, seeded_db):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "password123",
            "keepSignedIn": False,
        },
    )
    assert resp.status_code == 200
    assert abs(_max_age(_cookie(resp, "account_token")) - DAY) <= 5


def test_club_switch_keeps_the_sign_in_lifetime(app, client, tenant_pair):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "user@test.ch",
            "password": "password123",
            "keepSignedIn": False,
        },
    )
    assert resp.status_code == 200
    with app.app_context():
        started = decode_token(_token(_cookie(resp, "refresh_token_cookie")))[
            "signed_in_at"
        ]

    resp = client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "tenant-b"})
    assert resp.status_code == 200
    header = _cookie(resp, "refresh_token_cookie")
    assert _max_age(header) <= DAY
    with app.app_context():
        claims = decode_token(_token(header))
    assert claims["signed_in_at"] == started
    assert claims["keep"] is False
