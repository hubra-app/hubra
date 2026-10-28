"""Tests for account blueprint: GET/PATCH /api/v1/account/."""


# ── Account GET ───────────────────────────────────────────────────────────────


def test_get_account_authenticated(client, auth_headers):
    resp = client.get("/api/v1/account/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "email" in body
    assert body["email"] == "admin@test.ch"


def test_get_account_names_the_token_club(client, db, seeded_db):
    """The club app compares it with the URL to skip /auth/switch-tenant."""
    from hubra.core.models.tenant import Tenant

    db.session.add(Tenant(name="Club A", slug="club-a", status="active"))
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
        headers={"X-Tenant-Slug": "club-a"},
    )
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 200
    assert resp.get_json()["tenantSlug"] == "club-a"


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
