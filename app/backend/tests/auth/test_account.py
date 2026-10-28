"""Tests for account blueprint: GET/PATCH /api/v1/account/."""


# ── Account GET ───────────────────────────────────────────────────────────────


def test_get_account_authenticated(client, auth_headers):
    resp = client.get("/api/v1/account/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "email" in body
    assert body["email"] == "admin@test.ch"


def test_get_account_unauthenticated(client, seeded_db):
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 401


# ── Account PATCH ─────────────────────────────────────────────────────────────


def test_update_account_name(client, auth_headers):
    resp = client.patch(
        "/api/v1/account/", json={"name": "Renamed Admin"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Renamed Admin"


def test_update_account_empty_name(client, auth_headers):
    resp = client.patch("/api/v1/account/", json={"name": ""}, headers=auth_headers)
    assert resp.status_code == 400


def test_update_account_short_password(client, auth_headers):
    resp = client.patch(
        "/api/v1/account/", json={"password": "short"}, headers=auth_headers
    )
    assert resp.status_code == 400
