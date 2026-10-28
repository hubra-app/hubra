"""Tests for system role protection — is_system roles cannot be modified or deleted."""

from vollbuild.core.extensions import db
from vollbuild.core.models.role import Role


def test_cannot_delete_system_role(client, seeded_db, auth_headers):
    """DELETE /roles/{id} on a system role returns 409."""
    role = Role(name="SystemRole1", is_system=True)
    db.session.add(role)
    db.session.commit()

    resp = client.delete(
        f"/api/v1/roles/{role.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "system role" in resp.get_json().get("message", "").lower()


def test_cannot_rename_system_role(client, seeded_db, auth_headers):
    """PATCH /roles/{id} name on a system role returns 409."""
    role = Role(name="SystemRole2", is_system=True)
    db.session.add(role)
    db.session.commit()

    resp = client.patch(
        f"/api/v1/roles/{role.id}",
        json={"name": "Renamed"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "system role" in resp.get_json().get("message", "").lower()


def test_cannot_set_permissions_on_system_role(client, seeded_db, auth_headers):
    """PUT /roles/{id}/permissions on a system role returns 409."""
    role = Role(name="SystemRole3", is_system=True, is_admin=True)
    db.session.add(role)
    db.session.commit()

    resp = client.put(
        f"/api/v1/roles/{role.id}/permissions",
        json={"permissions": ["members.members.read"]},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "system role" in resp.get_json().get("message", "").lower()


def test_can_delete_non_system_role(client, seeded_db, auth_headers):
    """DELETE on a custom (non-system) role still works."""
    role = Role(name="CustomRole1")
    db.session.add(role)
    db.session.commit()

    resp = client.delete(
        f"/api/v1/roles/{role.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204


def test_cannot_set_is_system_via_api(client, seeded_db, auth_headers):
    """PATCH /roles/{id} with is_system in body returns 403."""
    role = Role(name="CustomRole2")
    db.session.add(role)
    db.session.commit()

    resp = client.patch(
        f"/api/v1/roles/{role.id}",
        json={"is_system": True},
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_cannot_set_is_owner_via_api(client, seeded_db, auth_headers):
    """PATCH /roles/{id} with is_owner in body returns 403."""
    role = Role(name="CustomRole3")
    db.session.add(role)
    db.session.commit()

    resp = client.patch(
        f"/api/v1/roles/{role.id}",
        json={"is_owner": True},
        headers=auth_headers,
    )
    assert resp.status_code == 403
