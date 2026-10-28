"""Cross-tenant authentication tests — tenant scoping, switch-tenant, isolation.

Covers issue #131 — Security Tests for Authentication, cross-tenant section:
- switch-tenant to an authorized tenant succeeds
- switch-tenant to an unauthorized tenant is rejected (403)
- switch-tenant to a non-existent tenant returns 404
- JWT contains tenant_slug claim after switch
- find_user_tenants returns all tenants for a multi-tenant user
"""

from __future__ import annotations

from hubra.core.models.tenant import Tenant
from hubra.api.auth.services import AuthService


# ── switch-tenant ─────────────────────────────────────────────────────────────


def test_switch_tenant_to_authorized_tenant(client, tenant_pair):
    """User can switch to a tenant they belong to via UserTenant."""
    # Login as the multi-tenant user
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.ch", "password": "password123"},
    )
    assert resp.status_code == 200

    # Switch to tenant-b
    resp = client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenantSlug": "tenant-b"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tenantSlug"] == "tenant-b"


def test_switch_tenant_to_unauthorized_tenant_rejected(client, tenant_pair, db):
    """switch-tenant to a tenant the user does NOT belong to returns 403."""
    # Create a third tenant the user has no membership in
    tenant_c = Tenant(name="Tenant C", slug="tenant-c", plan="starter", status="active")
    db.session.add(tenant_c)
    db.session.commit()

    # Login
    client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.ch", "password": "password123"},
    )

    # Try to switch to tenant-c — should be 403
    resp = client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenantSlug": "tenant-c"},
    )
    assert resp.status_code == 403


def test_switch_tenant_to_nonexistent_tenant_returns_404(client, tenant_pair):
    """switch-tenant to a slug that doesn't exist returns 404."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.ch", "password": "password123"},
    )

    resp = client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenantSlug": "does-not-exist"},
    )
    assert resp.status_code == 404


def test_switch_tenant_empty_slug_returns_400(client, tenant_pair):
    """switch-tenant with empty tenantSlug returns 400."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.ch", "password": "password123"},
    )

    resp = client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenantSlug": ""},
    )
    assert resp.status_code == 400


# ── JWT tenant_slug claim ─────────────────────────────────────────────────────


def test_jwt_contains_tenant_slug_after_switch(app, client, tenant_pair):
    """After switch-tenant, the new access token has the target tenant_slug."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.ch", "password": "password123"},
    )

    resp = client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenantSlug": "tenant-b"},
    )
    assert resp.status_code == 200

    # Extract access token from cookies and decode
    from flask_jwt_extended import decode_token

    access_token = None
    for header in resp.headers.getlist("Set-Cookie"):
        if header.startswith("access_token_cookie="):
            access_token = header.split(";")[0].split("=", 1)[1]
            break
    assert access_token, "access_token_cookie must be set after switch-tenant"

    with app.app_context():
        decoded = decode_token(access_token)
        assert decoded.get("tenant_slug") == "tenant-b"


# ── find_user_tenants ─────────────────────────────────────────────────────────


def test_find_user_tenants_returns_all_tenants(tenant_pair, db):
    """AuthService.find_user_tenants returns all tenants for a multi-tenant user."""
    user = tenant_pair["user"]
    tenants = AuthService.find_user_tenants(user.id)

    # Should return both tenants
    slugs = {t["tenant_slug"] for t in tenants}
    assert "tenant-a" in slugs
    assert "tenant-b" in slugs
    assert len(tenants) == 2


def test_find_user_tenants_excludes_unauthorized(tenant_pair, db):
    """find_user_tenants does not include tenants the user has no membership in."""
    tenant_c = Tenant(name="Tenant C", slug="tenant-c", plan="starter", status="active")
    db.session.add(tenant_c)
    db.session.commit()

    user = tenant_pair["user"]
    tenants = AuthService.find_user_tenants(user.id)
    slugs = {t["tenant_slug"] for t in tenants}
    assert "tenant-c" not in slugs


# ── switch-tenant without authentication ──────────────────────────────────────


def test_switch_tenant_without_auth_returns_401(client, tenant_pair):
    """switch-tenant without a valid JWT returns 401."""
    resp = client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenantSlug": "tenant-a"},
    )
    assert resp.status_code == 401


def test_login_with_tenant_choice_can_switch_tenant(client, tenant_pair, db):
    """A user whose memberships live only in club schemas gets the tenant
    picker, and the session that comes with it lets switch-tenant run.

    In PostgreSQL the Member rows sit in each club's schema, so login finds no
    member in the public schema; SQLite tests model that with a user that has
    UserTenant links but no Member row.
    """
    from hubra.core.models.user import User
    from hubra.core.models.user_tenant import UserTenant

    user = User(
        email="picker@test.ch",
        first_name="Pick",
        last_name="Er",
        private_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    db.session.add(UserTenant(user_id=user.id, tenant_id=tenant_pair["tenant_b"].id))
    db.session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "picker@test.ch", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["requiresTenantSelection"] is True
    assert [t["tenant_slug"] for t in data["tenants"]] == ["tenant-b"]

    resp = client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenantSlug": "tenant-b"},
    )
    assert resp.status_code != 401


def test_tenant_resolved_from_jwt_claim_without_header(client, tenant_pair):
    """After switch-tenant the token's tenant_slug picks the club; the SPAs
    send no X-Tenant-Slug header."""
    from flask import g

    client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.ch", "password": "password123"},
    )
    client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "tenant-b"})

    with client:
        client.get("/api/v1/account/permissions")
        assert g.tenant is not None
        assert g.tenant.slug == "tenant-b"
