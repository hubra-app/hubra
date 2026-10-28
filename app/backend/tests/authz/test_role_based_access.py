"""Role-based access tests — admin vs board member vs plain member vs unauthenticated.

Covers IID 139: Authorization Access Tests — Role-Based Tests section.

Tests that:
  - Admin (is_admin=True) can access all protected endpoints across the system
  - Board member has elevated but limited access (can create events, can't delete members)
  - Plain member (no permissions) gets 403 on permission-gated endpoints but 200 on jwt_required-only
  - Unauthenticated requests to protected endpoints return 401
"""

from __future__ import annotations

import pytest

# ── Unauthenticated access ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/members/"),
        ("GET", "/api/v1/members/count"),
        ("POST", "/api/v1/members/"),
        ("GET", "/api/v1/groups/"),
        ("GET", "/api/v1/audit/"),
        ("GET", "/api/v1/roles/"),
        ("GET", "/api/v1/system/permissions"),
        ("GET", "/api/v1/settings/"),
    ],
)
def test_unauthenticated_gets_401(client, method, path):
    """Protected endpoints return 401 when no JWT cookie is present."""
    resp = client.open(path, method=method)
    assert resp.status_code == 401


def test_unauthenticated_post_members_gets_401(client):
    resp = client.post("/api/v1/members/", json={"first_name": "X", "last_name": "Y"})
    assert resp.status_code == 401


def test_unauthenticated_delete_member_gets_401(client, seeded_db):
    resp = client.delete(f"/api/v1/members/{seeded_db['admin'].id}")
    assert resp.status_code == 401


# ── Admin access ──────────────────────────────────────────────────────────────


def test_admin_can_list_members(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/members/", headers=auth_headers)
    assert resp.status_code == 200


def test_admin_can_create_member(client, seeded_db, auth_headers):
    resp = client.post(
        "/api/v1/members/",
        json={
            "first_name": "New",
            "last_name": "Member",
            "email": "new@test.ch",
            "tier_id": seeded_db["tier"].id,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201


def test_admin_can_delete_member(client, seeded_db, auth_headers, db):
    """Admin can delete a member (must be archived first per service logic)."""
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    # Create a separate member to delete (can't self-delete)
    target_user = User(
        email="delete-target@test.ch",
        first_name="Delete",
        last_name="Target",
    )
    target_user.set_password("password123")
    db.session.add(target_user)
    db.session.flush()

    target = Member(
        user_id=target_user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
    )
    target.archived_at = None
    db.session.add(target)
    db.session.commit()

    # Archive first (delete_permanent requires archived status)
    resp = client.post(f"/api/v1/members/{target.id}/archive", headers=auth_headers)
    assert resp.status_code == 204

    resp = client.delete(f"/api/v1/members/{target.id}", headers=auth_headers)
    assert resp.status_code == 204


def test_admin_can_read_audit(client, auth_headers):
    resp = client.get("/api/v1/audit/", headers=auth_headers)
    assert resp.status_code == 200


def test_admin_can_read_system_permissions(client, auth_headers):
    resp = client.get("/api/v1/system/permissions", headers=auth_headers)
    assert resp.status_code == 200


def test_admin_can_list_settings(client, auth_headers):
    resp = client.get("/api/v1/settings/", headers=auth_headers)
    assert resp.status_code == 200


def test_admin_can_create_role(client, auth_headers):
    resp = client.post(
        "/api/v1/roles/", json={"name": "TestAdminRole"}, headers=auth_headers
    )
    assert resp.status_code == 201


def test_admin_can_access_health_detailed(client, auth_headers):
    """Admin can access the health/detailed endpoint (not 403).

    The HTTP status may be 200 or 503 depending on whether mock services
    report as healthy — the authz test only verifies no 401/403.
    """
    resp = client.get("/api/v1/health/detailed", headers=auth_headers)
    assert resp.status_code in (200, 503)


def test_plain_member_cannot_access_health_detailed(client, plain_member_token):
    """Non-admin gets 403 on health/detailed (require_admin decorator)."""
    resp = client.get("/api/v1/health/detailed", headers=plain_member_token)
    assert resp.status_code == 403


# ── Plain member (no permissions) ─────────────────────────────────────────────


def test_plain_member_cannot_list_members(client, seeded_db, plain_member_token):
    resp = client.get("/api/v1/members/", headers=plain_member_token)
    assert resp.status_code == 403


def test_plain_member_cannot_create_member(client, seeded_db, plain_member_token):
    resp = client.post(
        "/api/v1/members/",
        json={
            "first_name": "Hack",
            "last_name": "Attempt",
            "email": "hack@test.ch",
        },
        headers=plain_member_token,
    )
    assert resp.status_code == 403


def test_plain_member_cannot_read_audit(client, plain_member_token):
    resp = client.get("/api/v1/audit/", headers=plain_member_token)
    assert resp.status_code == 403


def test_plain_member_cannot_read_system_permissions(client, plain_member_token):
    resp = client.get("/api/v1/system/permissions", headers=plain_member_token)
    assert resp.status_code == 403


def test_plain_member_cannot_create_role(client, plain_member_token):
    resp = client.post(
        "/api/v1/roles/", json={"name": "HackerRole"}, headers=plain_member_token
    )
    assert resp.status_code == 403


def test_plain_member_cannot_put_settings(client, plain_member_token):
    resp = client.put(
        "/api/v1/settings/club.name",
        json={"value": "Hacked"},
        headers=plain_member_token,
    )
    assert resp.status_code == 403


def test_plain_member_cannot_list_groups(client, plain_member_token):
    resp = client.get("/api/v1/groups/", headers=plain_member_token)
    assert resp.status_code == 403


def test_plain_member_can_list_roles(client, plain_member_token):
    """List roles is public to authenticated members (read-only, @jwt_required only)."""
    resp = client.get("/api/v1/roles/", headers=plain_member_token)
    assert resp.status_code == 200


def test_plain_member_can_access_account(client, plain_member_token):
    """Account endpoints use @jwt_required or @require_password_changed — any member passes."""
    resp = client.get("/api/v1/account/", headers=plain_member_token)
    assert resp.status_code == 200


def test_plain_member_can_get_own_permissions(client, plain_member_token):
    resp = client.get("/api/v1/account/permissions", headers=plain_member_token)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_admin"] is False
    assert data["permissions"] == []


# ── Board member (elevated but limited) ───────────────────────────────────────


def test_board_member_can_list_members(client, seeded_db, board_member_token):
    resp = client.get("/api/v1/members/", headers=board_member_token)
    assert resp.status_code == 200


def test_board_member_cannot_create_member(client, seeded_db, board_member_token):
    """Board member has members.read but NOT members.create."""
    resp = client.post(
        "/api/v1/members/",
        json={
            "first_name": "New",
            "last_name": "Person",
            "email": "board-new@test.ch",
        },
        headers=board_member_token,
    )
    assert resp.status_code == 403


def test_board_member_cannot_delete_member(client, seeded_db, board_member_token):
    resp = client.delete(
        f"/api/v1/members/{seeded_db['admin'].id}", headers=board_member_token
    )
    assert resp.status_code == 403


def test_board_member_can_list_groups(client, board_member_token):
    resp = client.get("/api/v1/groups/", headers=board_member_token)
    assert resp.status_code == 200


def test_board_member_cannot_read_audit(client, board_member_token):
    resp = client.get("/api/v1/audit/", headers=board_member_token)
    assert resp.status_code == 403


def test_board_member_cannot_manage_settings(client, board_member_token):
    resp = client.put(
        "/api/v1/settings/club.name",
        json={"value": "Board"},
        headers=board_member_token,
    )
    assert resp.status_code == 403
