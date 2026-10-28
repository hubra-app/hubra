"""Field-level RBAC tests — @can_update + filter_updatable_fields.

Covers IID 156/157: Add field-level RBAC permission tests.

Tests that:
  - Admin bypasses all field restrictions (g.updatable_fields = None)
  - Coarse {bp}.{resource}.update permission grants ALL fields
  - Field-level {bp}.{resource}.update.{field} grants only specific fields
  - filter_updatable_fields strips unauthorized fields from the request body
  - A member with only field-level perms cannot set fields they don't have
  - A member with no update permission at all gets 403
"""

from __future__ import annotations

from hubra.core.models.member import Member
from hubra.core.models.role import Role, Permission, RolePermission
from hubra.core.models.user import User
from hubra.api.permissions import filter_updatable_fields


# ── filter_updatable_fields unit tests ────────────────────────────────────────


class TestFilterUpdatableFields:
    """Unit-test the filter_updatable_fields helper directly."""

    def test_no_restriction_returns_all(self, app):
        """When g.updatable_fields is None (admin or coarse), all fields pass through."""
        with app.test_request_context():
            from flask import g

            g.updatable_fields = None
            data = {"first_name": "X", "last_name": "Y", "email": "z@test.ch"}
            result = filter_updatable_fields(data)
            assert result == data

    def test_field_level_filter_strips_unauthorized(self, app):
        """When g.updatable_fields is a set, only those fields pass through."""
        with app.test_request_context():
            from flask import g

            g.updatable_fields = {"email", "first_name"}
            data = {
                "first_name": "NewName",
                "email": "new@test.ch",
                "last_name": "ShouldBeStripped",
                "notes": "Also stripped",
            }
            result = filter_updatable_fields(data)
            assert "first_name" in result
            assert "email" in result
            assert "last_name" not in result
            assert "notes" not in result

    def test_empty_allowed_set_strips_everything(self, app):
        with app.test_request_context():
            from flask import g

            g.updatable_fields = set()
            data = {"first_name": "X", "email": "y@test.ch"}
            result = filter_updatable_fields(data)
            assert result == {}


# ── Integration: @can_update on PATCH /members/<id> ───────────────────────────


def _seed_field_perm(db, key: str) -> Permission:
    """Create or get a Permission row for the given key."""
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


def _create_member_with_field_perms(
    db, tier_id: int, email: str, perm_keys: list[str]
) -> Member:
    """Create a member whose role has the given permission keys."""
    role = Role(name=f"FieldRole_{email}", is_default=False, is_admin=False)
    db.session.add(role)
    db.session.flush()

    for key in perm_keys:
        perm = _seed_field_perm(db, key)
        db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.session.flush()

    user = User(
        email=email,
        first_name="Field",
        last_name="Test",
        private_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    member = Member(
        user_id=user.id,
        status="active",
        tier_id=tier_id,
    )
    member.roles = [role]
    db.session.add(member)
    db.session.commit()
    return member


class TestCanUpdateFieldLevel:
    """Integration tests for @can_update on PATCH /members/<id>."""

    def test_admin_can_update_all_fields(self, client, seeded_db, auth_headers):
        """Admin bypasses field-level restrictions — all fields allowed."""
        member = seeded_db["admin"]
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"status": "active", "notes": "By admin"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_coarse_update_grants_all_fields(self, client, seeded_db, db):
        """Having members.members.update (coarse) grants ALL fields."""
        member = _create_member_with_field_perms(
            db, seeded_db["tier"].id, "coarse@test.ch", ["members.members.update"]
        )
        client.post(
            "/api/v1/auth/login",
            json={"email": "coarse@test.ch", "password": "password123"},
        )

        # Update the seeded admin's profile
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"status": "active", "notes": "Via coarse"},
        )
        assert resp.status_code == 200

    def test_field_level_update_grants_only_specific_fields(
        self, client, seeded_db, db
    ):
        """Having only members.members.update.notes grants ONLY notes updates."""
        member = _create_member_with_field_perms(
            db,
            seeded_db["tier"].id,
            "fieldlevel@test.ch",
            ["members.members.update.notes"],
        )
        client.post(
            "/api/v1/auth/login",
            json={"email": "fieldlevel@test.ch", "password": "password123"},
        )

        # Can update notes — should succeed
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"notes": "Key holder"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["notes"] == "Key holder"

    def test_field_level_strips_unauthorized_fields(self, client, seeded_db, db):
        """When member has only update.notes, PATCH with status gets silently stripped."""
        member = _create_member_with_field_perms(
            db,
            seeded_db["tier"].id,
            "strip@test.ch",
            ["members.members.update.notes"],
        )
        client.post(
            "/api/v1/auth/login",
            json={"email": "strip@test.ch", "password": "password123"},
        )

        # Send both notes (allowed) and status (not allowed)
        before = member.status
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"notes": "Allowed", "status": "suspended"},
        )
        assert resp.status_code == 200
        # notes should be updated
        assert resp.get_json()["notes"] == "Allowed"
        # status should NOT be updated
        db.session.refresh(member)
        assert member.status == before

    def test_no_update_permission_gets_403(self, client, seeded_db, db):
        """Member with members.read only gets 403 on PATCH /members/<id>."""
        member = _create_member_with_field_perms(
            db,
            seeded_db["tier"].id,
            "noupdate@test.ch",
            ["members.members.read"],
        )
        client.post(
            "/api/v1/auth/login",
            json={"email": "noupdate@test.ch", "password": "password123"},
        )

        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"first_name": "ShouldFail"},
        )
        assert resp.status_code == 403

    def test_field_level_update_does_not_grant_coarse(self, client, seeded_db, db):
        """Having members.members.update.status does NOT grant update on other fields."""
        member = _create_member_with_field_perms(
            db,
            seeded_db["tier"].id,
            "fieldonly@test.ch",
            ["members.members.update.status"],
        )
        client.post(
            "/api/v1/auth/login",
            json={"email": "fieldonly@test.ch", "password": "password123"},
        )

        # Can update status — should succeed
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"status": "active"},
        )
        assert resp.status_code == 200

        # Try to update notes — should be stripped (field-level only has status)
        resp2 = client.patch(
            f"/api/v1/members/{member.id}",
            json={"notes": "Should be stripped"},
        )
        assert resp2.status_code == 200  # request succeeds but notes unchanged
        db.session.refresh(member)
        assert member.notes is None


# ── Integration: @can_update on PATCH /groups/<id> ────────────────────────────


class TestCanUpdateGroups:
    def test_admin_can_update_group(self, client, seeded_db, auth_headers, db):
        from hubra.core.models.group import Group

        group = Group(name="TestGroup", description="Test")
        db.session.add(group)
        db.session.commit()

        resp = client.patch(
            f"/api/v1/groups/{group.id}",
            json={"name": "UpdatedGroup"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_field_level_group_update(self, client, seeded_db, db):
        """Member with groups.groups.update.name can only update name, not description."""
        from hubra.core.models.group import Group

        group = Group(name="GroupA", description="Original desc")
        db.session.add(group)
        db.session.commit()

        _create_member_with_field_perms(
            db,
            seeded_db["tier"].id,
            "groupfield@test.ch",
            ["groups.groups.update.name"],
        )
        client.post(
            "/api/v1/auth/login",
            json={"email": "groupfield@test.ch", "password": "password123"},
        )

        # Can update name
        resp = client.patch(
            f"/api/v1/groups/{group.id}",
            json={"name": "NewGroupName"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "NewGroupName"

        # Cannot update description — silently stripped
        resp2 = client.patch(
            f"/api/v1/groups/{group.id}",
            json={"description": "Hacked desc"},
        )
        assert resp2.status_code == 200
        db.session.refresh(group)
        assert group.description == "Original desc"
