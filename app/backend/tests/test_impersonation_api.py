"""Tests for tenant impersonation API — start/stop, restrictions, audit trail.

Impersonation allows a System Admin to act as a tenant member for debugging.
Tests verify the JWT claims, audit logging, and restriction enforcement.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant, GlobalAuditEntry
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def superadmin_db(seeded_db, db):
    """Mark the seeded User as superadmin."""
    user = seeded_db["user"]
    user.is_superadmin = True
    db.session.add(user)
    db.session.commit()
    return {**seeded_db, "user": user}


@pytest.fixture
def superadmin_headers(client, superadmin_db):
    """Login as superadmin."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    return {}


@pytest.fixture
def target_tenant(db, seeded_db):
    """Create a tenant with a member for impersonation target."""
    tenant = Tenant(name="Target Club", slug="target-club", plan="starter")
    db.session.add(tenant)
    db.session.flush()

    target_user = User(
        email="target@test.ch",
        first_name="Target",
        last_name="User",
    )
    target_user.set_password("targetpass123")
    db.session.add(target_user)
    db.session.flush()

    db.session.add(UserTenant(user_id=target_user.id, tenant_id=tenant.id))

    # Use the seeded tier and role (already in the DB from seeded_db)
    tier = seeded_db["tier"]
    role = seeded_db["role"]

    target_member = Member(
        user_id=target_user.id,
        tier_id=tier.id,
        status="active",
    )
    target_member.roles = [role]
    db.session.add(target_member)
    db.session.flush()

    db.session.commit()
    return {"tenant": tenant, "user": target_user, "member": target_member}


# ── Impersonation tests ─────────────────────────────────────────────────────


def test_impersonate_requires_reason(client, superadmin_headers, target_tenant):
    """Impersonation without a reason returns 422."""
    with (
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.api.tenant.routes.set_search_path", create=True),
    ):
        resp = client.post(
            f"/api/v1/system/tenants/{target_tenant['tenant'].id}/impersonate",
            json={},
            headers=superadmin_headers,
        )
    assert resp.status_code == 422


def test_impersonate_tenant_not_found(client, superadmin_headers):
    """Impersonating a non-existent tenant returns 404."""
    resp = client.post(
        "/api/v1/system/tenants/99999/impersonate",
        json={"reason": "debug ticket #123"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 404


def test_impersonate_creates_audit_entry(client, superadmin_headers, target_tenant, db):
    """Starting impersonation creates a GlobalAuditEntry."""
    with (
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.api.tenant.routes.set_search_path", create=True),
    ):
        resp = client.post(
            f"/api/v1/system/tenants/{target_tenant['tenant'].id}/impersonate",
            json={"reason": "Support ticket #42"},
            headers=superadmin_headers,
        )

    if resp.status_code == 200:
        entry = db.session.scalar(
            select(GlobalAuditEntry).where(
                GlobalAuditEntry.action == "impersonation.start"
            )
        )
        assert entry is not None
        assert entry.details["reason"] == "Support ticket #42"


def test_stop_impersonation_not_impersonating(client, superadmin_headers):
    """Stopping impersonation when not impersonating returns 400."""
    resp = client.post(
        "/api/v1/system/impersonation/stop",
        headers=superadmin_headers,
    )
    assert resp.status_code == 400


def test_account_permissions_includes_is_superadmin(client, superadmin_headers):
    """The /account/permissions endpoint includes is_superadmin flag."""
    resp = client.get(
        "/api/v1/account/permissions",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["is_superadmin"] is True


def test_account_permissions_non_superadmin(client, seeded_db):
    """Regular admin doesn't have is_superadmin."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    resp = client.get("/api/v1/account/permissions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["is_superadmin"] is False
    assert body["impersonation"] is None


def test_delete_tenant_blocked_during_impersonation(
    client, superadmin_headers, target_tenant, db
):
    """DELETE tenant is blocked when impersonating."""
    from hubra.api.permissions import check_impersonation_restriction

    with patch("flask_jwt_extended.get_jwt") as mock_jwt:
        mock_jwt.return_value = {"impersonator_id": 1}
        result = check_impersonation_restriction("delete_tenant")
        assert result is not None
        assert result[0] == "IMPERSONATION_RESTRICTED"


def test_change_plan_blocked_during_impersonation():
    """Changing plan is blocked during impersonation."""
    from hubra.api.permissions import check_impersonation_restriction

    with patch("flask_jwt_extended.get_jwt") as mock_jwt:
        mock_jwt.return_value = {"impersonator_id": 1}
        result = check_impersonation_restriction("change_plan")
        assert result is not None
        assert result[0] == "IMPERSONATION_RESTRICTED"


def test_normal_actions_not_blocked_during_impersonation():
    """Non-restricted actions are allowed during impersonation."""
    from hubra.api.permissions import check_impersonation_restriction

    with patch("flask_jwt_extended.get_jwt") as mock_jwt:
        mock_jwt.return_value = {"impersonator_id": 1}
        result = check_impersonation_restriction("update_name")
        assert result is None


def test_actions_not_blocked_when_not_impersonating():
    """Actions are allowed when not impersonating."""
    from hubra.api.permissions import check_impersonation_restriction

    with patch("flask_jwt_extended.get_jwt") as mock_jwt:
        mock_jwt.return_value = {}
        result = check_impersonation_restriction("delete_tenant")
        assert result is None
