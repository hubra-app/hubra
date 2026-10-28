"""Tests for Phase 6 manager-plane endpoints.

Tests platform audit logs, feature catalog management, metrics,
and user management endpoints accessible via v2 manager namespace.
"""

import pytest

from vollbuild.core.extensions import db
from vollbuild.core.models.feature import TenantFeature
from vollbuild.core.models.tenant import GlobalAuditEntry, Tenant


@pytest.fixture
def superadmin_headers(client, seeded_db):
    """Login as superadmin (no tenant → user: prefixed JWT)."""
    # Promote seeded user to superadmin
    user = seeded_db["user"]
    user.is_superadmin = True
    db.session.commit()

    # Login — since admin is also a member, we need to use the
    # no-tenant login path. Delete the member to force user: JWT.
    from vollbuild.core.models.member import Member

    member = db.session.get(Member, seeded_db["admin"].id)
    if member:
        member.archived_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
        db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    return {}


# ── Platform audit log ────────────────────────────────────────────────────────


def test_list_global_audit(client, seeded_db, superadmin_headers):
    """GET /api/v2/manager/tenants/audit returns 200 with pagination."""
    # Create an audit entry
    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=1,
            action="test.action",
            target_type="Test",
            target_id="1",
        )
    )
    db.session.commit()

    resp = client.get("/api/v2/manager/tenants/audit", headers=superadmin_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "entries" in data
    assert "total" in data
    assert isinstance(data["entries"], list)


def test_list_global_audit_filters_by_action(client, seeded_db, superadmin_headers):
    """GET /api/v2/manager/tenants/audit?action=provision filters entries."""
    db.session.add(
        GlobalAuditEntry(actor_id=1, action="tenant.provision", target_type="Tenant")
    )
    db.session.add(
        GlobalAuditEntry(actor_id=1, action="tenant.suspended", target_type="Tenant")
    )
    db.session.commit()

    resp = client.get(
        "/api/v2/manager/tenants/audit?action=provision", headers=superadmin_headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    actions = [e["action"] for e in data["entries"]]
    assert all("provision" in a for a in actions)


# ── Feature catalog ──────────────────────────────────────────────────────────


def test_list_feature_catalog(client, seeded_db, superadmin_headers):
    """GET /api/v2/manager/features/catalog returns 200."""
    resp = client.get("/api/v2/manager/features/catalog", headers=superadmin_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    codes = [f["code"] for f in data]
    assert {"core", "members", "finance", "inventory"} <= set(codes)


def test_list_tenant_features(client, seeded_db, superadmin_headers):
    """GET /api/v2/manager/features/tenants/{id} returns 200."""
    tenant = Tenant(name="Test", slug="test-feat-tenant")
    db.session.add(tenant)
    db.session.flush()
    db.session.add(
        TenantFeature(tenant_id=tenant.id, feature_code="mail", enabled=True)
    )
    db.session.commit()

    resp = client.get(
        f"/api/v2/manager/features/tenants/{tenant.id}", headers=superadmin_headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_set_tenant_feature(client, seeded_db, superadmin_headers):
    """PUT /api/v2/manager/features/tenants/{id}/{code} creates grant."""
    tenant = Tenant(name="Test2", slug="test-set-feature")
    db.session.add(tenant)
    db.session.commit()

    resp = client.put(
        f"/api/v2/manager/features/tenants/{tenant.id}/inventory",
        json={"enabled": True},
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["enabled"] is True
    assert data["code"] == "inventory"


# ── Platform metrics ─────────────────────────────────────────────────────────


def test_platform_metrics(client, seeded_db, superadmin_headers):
    """GET /api/v2/manager/tenants/metrics returns 200."""
    resp = client.get("/api/v2/manager/tenants/metrics", headers=superadmin_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "total_calls" in data
    assert "total_errors" in data
    assert "error_rate" in data
    assert "tenants" in data


# ── User management ──────────────────────────────────────────────────────────


def test_list_users(client, seeded_db, superadmin_headers):
    """GET /api/v2/manager/tenants/users returns 200 with pagination."""
    resp = client.get("/api/v2/manager/tenants/users", headers=superadmin_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "users" in data
    assert "total" in data
    assert isinstance(data["users"], list)


def test_list_users_search(client, seeded_db, superadmin_headers):
    """GET /api/v2/manager/tenants/users?search=admin returns filtered results."""
    resp = client.get(
        "/api/v2/manager/tenants/users?search=admin", headers=superadmin_headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    emails = [u["email"] for u in data["users"]]
    assert all("admin" in e.lower() for e in emails)


def test_get_user_detail(client, seeded_db, superadmin_headers):
    """GET /api/v2/manager/tenants/users/{id} returns user with tenants."""
    user = seeded_db["user"]

    resp = client.get(
        f"/api/v2/manager/tenants/users/{user.id}", headers=superadmin_headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == user.id
    assert data["email"] == user.email
    assert "tenants" in data


def test_get_user_detail_not_found(client, seeded_db, superadmin_headers):
    """GET /api/v2/manager/tenants/users/99999 returns 404."""
    resp = client.get("/api/v2/manager/tenants/users/99999", headers=superadmin_headers)
    assert resp.status_code == 404


# ── Auth checks ──────────────────────────────────────────────────────────────


def test_audit_requires_auth(client, seeded_db):
    """Platform audit endpoint requires authentication."""
    resp = client.get("/api/v2/manager/tenants/audit")
    assert resp.status_code == 401


def test_feature_catalog_requires_auth(client, seeded_db):
    """Feature catalog endpoint requires authentication."""
    resp = client.get("/api/v2/manager/features/catalog")
    assert resp.status_code == 401
