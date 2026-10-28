"""Cross-tenant authorization isolation tests.

Covers IID 154: Add cross-tenant permission isolation tests.

Tests that:
  - A user's role permissions are scoped to their own tenant context
  - switch-tenant reissues JWTs with the target tenant_slug claim
  - A user cannot access resources in a tenant they don't belong to
  - Role permissions from Tenant A do not grant access in Tenant B

Note: The schema-per-tenant system uses PostgreSQL search_path which doesn't
work with SQLite in the test suite. These tests validate auth-level isolation
(JWT tenant claims, UserTenant membership checks) rather than schema-level
isolation.
"""

from __future__ import annotations

from vollbuild.core.models.tenant import Tenant
from vollbuild.core.models.role import Permission, RolePermission


def _seed_perm(db, key: str) -> Permission:
    parts = key.split(".")
    p = Permission(
        key=key,
        display_name=key,
        resource=parts[1] if len(parts) > 1 else key,
        action=parts[2] if len(parts) > 2 else key,
        blueprint=parts[0] if "." in key else "",
    )
    db.session.add(p)
    db.session.flush()
    return p


# ── switch-tenant authz ───────────────────────────────────────────────────────


class TestSwitchTenantAuthz:
    """Authorization checks on the switch-tenant endpoint itself."""

    def test_switch_to_unauthorized_tenant_rejected(self, client, tenant_pair, db):
        """User cannot switch to a tenant they have no UserTenant link for."""
        tenant_c = Tenant(
            name="Tenant C", slug="tenant-c", plan="starter", status="active"
        )
        db.session.add(tenant_c)
        db.session.commit()

        # Login as the multi-tenant user
        client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.ch", "password": "password123"},
        )

        resp = client.post(
            "/api/v1/auth/switch-tenant",
            json={"tenantSlug": "tenant-c"},
        )
        assert resp.status_code == 403
        assert resp.get_json().get("error") == "FORBIDDEN"

    def test_switch_to_nonexistent_tenant_returns_404(self, client, tenant_pair):
        """switch-tenant to a slug that doesn't exist returns 404."""
        client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.ch", "password": "password123"},
        )
        resp = client.post(
            "/api/v1/auth/switch-tenant",
            json={"tenantSlug": "ghost-tenant"},
        )
        assert resp.status_code == 404

    def test_switch_tenant_without_auth_returns_401(self, client, tenant_pair):
        """switch-tenant requires authentication."""
        resp = client.post(
            "/api/v1/auth/switch-tenant",
            json={"tenantSlug": "tenant-a"},
        )
        assert resp.status_code == 401

    def test_switch_tenant_empty_slug_returns_400(self, client, tenant_pair):
        client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.ch", "password": "password123"},
        )
        resp = client.post(
            "/api/v1/auth/switch-tenant",
            json={"tenantSlug": ""},
        )
        assert resp.status_code == 400


# ── JWT tenant claim ──────────────────────────────────────────────────────────


class TestJWTTenantClaim:
    """After switch-tenant, the JWT contains the target tenant_slug claim."""

    def test_jwt_has_tenant_slug_after_switch(self, app, client, tenant_pair):
        client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.ch", "password": "password123"},
        )

        resp = client.post(
            "/api/v1/auth/switch-tenant",
            json={"tenantSlug": "tenant-b"},
        )
        assert resp.status_code == 200

        from flask_jwt_extended import decode_token

        access_token = None
        for header in resp.headers.getlist("Set-Cookie"):
            if header.startswith("access_token_cookie="):
                access_token = header.split(";")[0].split("=", 1)[1]
                break
        assert access_token, "access_token_cookie must be set after switch"

        with app.app_context():
            decoded = decode_token(access_token)
            assert decoded.get("tenant_slug") == "tenant-b"


# ── find_user_tenants ─────────────────────────────────────────────────────────


class TestFindUserTenants:
    """AuthService.find_user_tenants returns only authorized tenants."""

    def test_returns_all_authorized_tenants(self, tenant_pair):
        from vollbuild.api.auth.services import AuthService

        user = tenant_pair["user"]
        tenants = AuthService.find_user_tenants(user.id)
        slugs = {t["tenant_slug"] for t in tenants}
        assert "tenant-a" in slugs
        assert "tenant-b" in slugs
        assert len(tenants) == 2

    def test_excludes_unauthorized_tenants(self, tenant_pair, db):
        from vollbuild.api.auth.services import AuthService

        tenant_c = Tenant(
            name="Tenant C", slug="tenant-c", plan="starter", status="active"
        )
        db.session.add(tenant_c)
        db.session.commit()

        user = tenant_pair["user"]
        tenants = AuthService.find_user_tenants(user.id)
        slugs = {t["tenant_slug"] for t in tenants}
        assert "tenant-c" not in slugs


# ── Permission scoping across tenants ─────────────────────────────────────────


class TestCrossTenantPermissionScoping:
    """Role permissions are scoped per tenant — a role in Tenant A does not
    grant permissions in Tenant B.

    Since the test suite uses SQLite (no schema-per-tenant), we validate this
    at the model level: roles are separate per tenant and a member's roles
    only apply to their own context.
    """

    def test_roles_are_separate_per_tenant(self, tenant_pair):
        """Roles created for Tenant A and Tenant B are separate entities."""
        role_a = tenant_pair["role_a"]
        role_b = tenant_pair["role_b"]
        assert role_a.id != role_b.id
        assert role_a.name != role_b.name

    def test_member_a_permissions_do_not_affect_member_b(self, tenant_pair, db):
        """Adding a permission to role_a does not give member_b that permission."""
        # Give role_a a permission
        perm = _seed_perm(db, "members.members.read")
        db.session.add(
            RolePermission(role_id=tenant_pair["role_a"].id, permission_id=perm.id)
        )
        db.session.commit()

        # member_a (with role_a) should have the permission
        from vollbuild.api.permissions import _get_member_permission_keys

        # Force DB fallback (no Redis in tests)
        from unittest.mock import patch

        with patch("vollbuild.api.permissions._get_redis_client", return_value=None):
            perms_a = _get_member_permission_keys(tenant_pair["member_a"])
            perms_b = _get_member_permission_keys(tenant_pair["member_b"])

        assert "members.members.read" in perms_a
        assert "members.members.read" not in perms_b

    def test_tenant_isolation_in_member_lookup(self, tenant_pair, db):
        """Members in different tenants are separate entities with different IDs."""
        member_a = tenant_pair["member_a"]
        member_b = tenant_pair["member_b"]
        assert member_a.id != member_b.id
        # Both members share the same global User (same email), but are
        # separate Member entities in different tenants.
        assert member_a.email == member_b.email
