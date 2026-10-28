"""Tests for auth refresh cookie cleanup when user/member is not found.

Verifies that POST /auth/refresh returns 401 and clears JWT cookies when
the identity's subject (User or Member) has been deleted from the database.
"""

from flask_jwt_extended import create_refresh_token


def test_refresh_clears_cookies_when_member_not_found(app, client, seeded_db):
    """Refresh returns 401 and clears cookies when the Member doesn't exist."""
    with app.app_context():
        token = create_refresh_token(identity="99999")
    client.set_cookie("refresh_token_cookie", token)

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    # The response should include Set-Cookie headers clearing JWT cookies
    set_cookie_headers = resp.headers.getlist("Set-Cookie")
    # unset_jwt_cookies sets cookies with empty values to clear them
    cleared_names = [c.split("=")[0] for c in set_cookie_headers]
    assert "access_token_cookie" in cleared_names
    assert "refresh_token_cookie" in cleared_names


def test_refresh_clears_cookies_when_user_not_found(app, client, seeded_db):
    """Refresh returns 401 and clears cookies for user: prefixed identity."""
    with app.app_context():
        token = create_refresh_token(identity="user:99999")
    client.set_cookie("refresh_token_cookie", token)

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    cookies = resp.headers.getlist("Set-Cookie")
    cookie_names = [c.split("=")[0] for c in cookies]
    assert "access_token_cookie" in cookie_names
    assert "refresh_token_cookie" in cookie_names


def test_refresh_works_when_member_exists(client, seeded_db):
    """Normal refresh still returns 200 when the member exists."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True


def test_refresh_user_identity_works_when_user_exists(app, client, seeded_db):
    """Refresh with user: prefix works when the user exists."""
    user = seeded_db["user"]
    with app.app_context():
        token = create_refresh_token(identity=f"user:{user.id}")
    client.set_cookie("refresh_token_cookie", token)

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True
