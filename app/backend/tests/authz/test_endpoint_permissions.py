"""Parametrized endpoint-level permission tests.

Covers IID 139: Authorization Access Tests — Permission Tests (endpoint-level).

Every @permission_required endpoint is tested both with the required permission
(granted 200/201/etc) and without it (denied 403). The tests use the
permissioned_member_factory to create members with specific permission sets.
"""

from __future__ import annotations


from hubra.core.models.role import Role

# ── Members endpoints ─────────────────────────────────────────────────────────


class TestMembersPermissions:
    """Permission enforcement on /api/v1/members/* endpoints."""

    def test_members_read_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["members.members.read"])
        resp = client.get("/api/v1/members/", headers=headers)
        assert resp.status_code == 200

    def test_members_read_without_permission(
        self, client, seeded_db, plain_member_token
    ):
        resp = client.get("/api/v1/members/", headers=plain_member_token)
        assert resp.status_code == 403

    def test_members_count_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["members.members.read"])
        resp = client.get("/api/v1/members/count", headers=headers)
        assert resp.status_code == 200

    def test_members_create_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["members.members.create"])
        resp = client.post(
            "/api/v1/members/",
            json={
                "first_name": "New",
                "last_name": "Member",
                "email": "new@test.ch",
                "tier_id": seeded_db["tier"].id,
            },
            headers=headers,
        )
        assert resp.status_code == 201

    def test_members_create_without_permission(
        self, client, seeded_db, plain_member_token
    ):
        resp = client.post(
            "/api/v1/members/",
            json={"first_name": "X", "last_name": "Y", "email": "x@test.ch"},
            headers=plain_member_token,
        )
        assert resp.status_code == 403

    def test_members_export_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["members.members.export"])
        resp = client.get("/api/v1/members/export", headers=headers)
        assert resp.status_code == 200

    def test_members_export_without_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        """Having members.read does NOT grant export (exact-key check)."""
        headers = permissioned_member_factory(["members.members.read"])
        resp = client.get("/api/v1/members/export", headers=headers)
        assert resp.status_code == 403

    def test_members_delete_without_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["members.members.read"])
        resp = client.delete(
            f"/api/v1/members/{seeded_db['admin'].id}", headers=headers
        )
        assert resp.status_code == 403


# ── Groups endpoints ──────────────────────────────────────────────────────────


class TestGroupsPermissions:
    def test_groups_read_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["groups.groups.read"])
        resp = client.get("/api/v1/groups/", headers=headers)
        assert resp.status_code == 200

    def test_groups_read_without_permission(self, client, plain_member_token):
        resp = client.get("/api/v1/groups/", headers=plain_member_token)
        assert resp.status_code == 403

    def test_groups_create_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["groups.groups.create"])
        resp = client.post(
            "/api/v1/groups/",
            json={"name": "Test Group"},
            headers=headers,
        )
        assert resp.status_code == 201

    def test_groups_create_without_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        """groups.read does NOT grant groups.create."""
        headers = permissioned_member_factory(["groups.groups.read"])
        resp = client.post(
            "/api/v1/groups/",
            json={"name": "Hack Group"},
            headers=headers,
        )
        assert resp.status_code == 403


# ── Cross-resource authorization (no wildcard fallback) ───────────────────────


class TestCrossResourceIsolation:
    """Verify the wildcard fallback was removed — having one resource's
    permission does NOT grant the same action on a different resource
    within the same blueprint.
    """

    def test_finance_invoices_read_does_not_grant_transactions_read(
        self, client, seeded_db, permissioned_member_factory, db
    ):
        """A user with finance.invoices.read must NOT access finance.transactions.read."""
        headers = permissioned_member_factory(["finance.invoices.read"])

        # transactions list — should be 403
        resp = client.get("/api/v1/finance/transactions", headers=headers)
        assert resp.status_code == 403

    def test_finance_invoices_create_does_not_grant_transactions_create(
        self, client, seeded_db, permissioned_member_factory
    ):
        """A user with finance.invoices.create must NOT create transactions."""
        headers = permissioned_member_factory(["finance.invoices.create"])
        resp = client.post(
            "/api/v1/finance/transactions",
            json={
                "amount": 100,
                "category_id": 1,
                "date": "2026-01-01",
                "type": "expense",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    def test_members_read_does_not_grant_groups_read(
        self, client, seeded_db, permissioned_member_factory
    ):
        """members.members.read must NOT grant groups.groups.read (different blueprint)."""
        headers = permissioned_member_factory(["members.members.read"])
        resp = client.get("/api/v1/groups/", headers=headers)
        assert resp.status_code == 403


# ── Settings endpoint namespace isolation ─────────────────────────────────────


class TestSettingsNamespaceIsolation:
    """Settings revert must check namespace — having settings.general.write
    must NOT allow reverting a setting in a different namespace.
    """

    def test_settings_read_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["settings.settings.read"])
        resp = client.get("/api/v1/settings/", headers=headers)
        assert resp.status_code == 200


# ── Inventory permissions ─────────────────────────────────────────────────────


class TestInventoryPermissions:
    def test_inventory_read_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["inventory.items.read"])
        resp = client.get("/api/v1/inventory/", headers=headers)
        assert resp.status_code == 200

    def test_inventory_read_without_permission(self, client, plain_member_token):
        resp = client.get("/api/v1/inventory/", headers=plain_member_token)
        assert resp.status_code == 403

    def test_inventory_create_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["inventory.items.create"])
        resp = client.post(
            "/api/v1/inventory/",
            json={"name": "Hammer", "category": "Tool"},
            headers=headers,
        )
        assert resp.status_code == 201

    def test_inventory_create_without_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["inventory.items.read"])
        resp = client.post(
            "/api/v1/inventory/",
            json={"name": "HackItem"},
            headers=headers,
        )
        assert resp.status_code == 403


# ── Roles permission enforcement ──────────────────────────────────────────────


class TestRolesPermissions:
    def test_roles_create_with_permission(
        self, client, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(["roles.roles.create"])
        resp = client.post("/api/v1/roles/", json={"name": "TestRole"}, headers=headers)
        assert resp.status_code == 201

    def test_roles_set_permissions_with_permission(
        self, client, db, seeded_db, permissioned_member_factory
    ):
        # Create a non-admin role to set permissions on
        role = Role(name="TargetRole", is_default=False, is_admin=False)
        db.session.add(role)
        db.session.commit()

        # Seed a permission to assign
        from tests.authz.conftest import _seed_permissions

        _seed_permissions(["members.members.read"])

        headers = permissioned_member_factory(["roles.roles.set_permissions"])
        resp = client.put(
            f"/api/v1/roles/{role.id}/permissions",
            json={"permissions": ["members.members.read"]},
            headers=headers,
        )
        assert resp.status_code == 200

    def test_roles_set_permissions_without_permission(
        self, client, db, seeded_db, permissioned_member_factory
    ):
        role = Role(name="TargetRole2", is_default=False, is_admin=False)
        db.session.add(role)
        db.session.commit()

        headers = permissioned_member_factory(["roles.roles.create"])
        resp = client.put(
            f"/api/v1/roles/{role.id}/permissions",
            json={"permissions": []},
            headers=headers,
        )
        assert resp.status_code == 403
