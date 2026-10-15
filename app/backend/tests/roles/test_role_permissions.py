"""Tests for ISSUE-022: Member-role JWTs receive 403 on admin-only endpoints."""

import pytest

from vollbuild.core.extensions import db as _db
from vollbuild.core.models.member import Member
from vollbuild.core.models.role import Role
from vollbuild.core.models.user import User

SYSTEM_PERMISSIONS = "/api/v1/system/permissions"
SETTINGS = "/api/v1/settings/"
AUDIT = "/api/v1/audit/"
ROLES = "/api/v1/roles/"


@pytest.fixture
def member_token(client, seeded_db):
    """A member with no extra permissions — role has no RolePermission rows."""
    tier = seeded_db["tier"]

    role = Role(name="PlainMember", is_default=False)
    _db.session.add(role)
    _db.session.flush()

    user = User(
        email="plain@test.ch",
        first_name="Plain",
        last_name="Member",
    )
    user.set_password("password123")
    _db.session.add(user)
    _db.session.flush()

    member = Member(
        user_id=user.id,
        status="active",
        tier_id=tier.id,
    )
    member.roles = [role]
    _db.session.add(member)
    _db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "plain@test.ch", "password": "password123"},
    )
    return {}


# ── /system/permissions ───────────────────────────────────────────────────────


def test_system_permissions_member_gets_403(client, seeded_db, member_token):
    resp = client.get(SYSTEM_PERMISSIONS, headers=member_token)
    assert resp.status_code == 403


def test_system_permissions_admin_gets_200(client, seeded_db, auth_headers):
    resp = client.get(SYSTEM_PERMISSIONS, headers=auth_headers)
    assert resp.status_code == 200


# ── /settings ─────────────────────────────────────────────────────────────────


def test_settings_get_member_gets_empty_list(client, seeded_db, member_token):
    """Non-admin member with no settings permissions gets 200 with empty list."""
    resp = client.get(SETTINGS, headers=member_token)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_settings_put_member_gets_403(client, seeded_db, member_token):
    resp = client.put(
        "/api/v1/settings/club.name", json={"value": "VollBuild"}, headers=member_token
    )
    assert resp.status_code == 403


def test_settings_get_admin_gets_200(client, seeded_db, auth_headers):
    resp = client.get(SETTINGS, headers=auth_headers)
    assert resp.status_code == 200


# ── /audit ────────────────────────────────────────────────────────────────────


def test_audit_member_gets_403(client, seeded_db, member_token):
    resp = client.get(AUDIT, headers=member_token)
    assert resp.status_code == 403


def test_audit_admin_gets_200(client, seeded_db, auth_headers):
    resp = client.get(AUDIT, headers=auth_headers)
    assert resp.status_code == 200


# ── /roles ────────────────────────────────────────────────────────────────────


def test_roles_create_member_gets_403(client, seeded_db, member_token):
    resp = client.post(ROLES, json={"name": "HackerRole"}, headers=member_token)
    assert resp.status_code == 403


def test_roles_create_admin_gets_201(client, seeded_db, auth_headers):
    resp = client.post(ROLES, json={"name": "TestRole"}, headers=auth_headers)
    assert resp.status_code == 201


def test_roles_list_member_gets_200(client, seeded_db, member_token):
    """List roles is public to authenticated members (read-only)."""
    resp = client.get(ROLES, headers=member_token)
    assert resp.status_code == 200


# ── login response includes role ──────────────────────────────────────────────


def test_login_response_includes_role(client, seeded_db):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "member" in data
    assert data["member"]["roles"] is not None
    assert isinstance(data["member"]["roles"], list)
    assert data["member"]["roles"][0]["name"] == "Owner"
