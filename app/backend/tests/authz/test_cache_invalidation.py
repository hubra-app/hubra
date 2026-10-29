"""Redis cache tests for the permission system.

Covers IID 153: Add Redis fallback and cache invalidation tests.

Tests that:
  - Permission cache hit returns correct permissions
  - Cache is invalidated when a role's permissions are changed
  - Cache is invalidated when a member's roles change
  - Fallback to DB works when Redis is unavailable
  - invalidate_role_permissions clears the role cache
  - invalidate_member_permissions clears the member cache
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock


from hubra.api.permissions import (
    _get_role_permission_keys,
    _get_member_permission_keys,
    invalidate_role_permissions,
    invalidate_member_permissions,
    _get_redis_client,
    _mark_redis_down,
)
from hubra.core.models.member import Member
from hubra.core.models.role import Role, Permission, RolePermission
from hubra.core.models.user import User


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


def _create_role_with_perms(db, keys: list[str], name: str = "CacheRole") -> Role:
    role = Role(name=name, is_default=False, is_admin=False)
    db.session.add(role)
    db.session.flush()
    for key in keys:
        perm = _seed_perm(db, key)
        db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.session.flush()
    return role


# ── DB fallback (no Redis) ────────────────────────────────────────────────────


class TestDBFallback:
    """When Redis is unavailable, permission lookups fall back to DB."""

    def test_get_role_permission_keys_without_redis(self, db, seeded_db):
        """_get_role_permission_keys returns correct keys from DB when Redis is down."""
        role = _create_role_with_perms(
            db, ["members.members.read", "groups.groups.read"]
        )

        # Force Redis to be unavailable
        with patch("hubra.api.permissions._get_redis_client", return_value=None):
            keys = _get_role_permission_keys(role.id)
        assert keys == {"members.members.read", "groups.groups.read"}

    def test_get_member_permission_keys_without_redis(self, db, seeded_db):
        """_get_member_permission_keys returns correct keys from DB."""
        role = _create_role_with_perms(
            db, ["members.members.read", "events.events.create"]
        )

        member_user = User(
            email="cache@test.ch",
            first_name="Cache",
            last_name="Test",
            private_email_verified=True,
        )
        member_user.set_password("password123")
        db.session.add(member_user)
        db.session.flush()

        member = Member(
            user_id=member_user.id,
            status="active",
            tier_id=seeded_db["tier"].id,
        )
        member.roles = [role]
        db.session.add(member)
        db.session.commit()

        with patch("hubra.api.permissions._get_redis_client", return_value=None):
            keys = _get_member_permission_keys(member)
        assert keys == {"members.members.read", "events.events.create"}

    def test_empty_role_returns_empty_set_without_redis(self, db, seeded_db):
        """A role with no permissions returns empty set (no Redis)."""
        role = Role(name="EmptyRole", is_default=False, is_admin=False)
        db.session.add(role)
        db.session.commit()

        with patch("hubra.api.permissions._get_redis_client", return_value=None):
            keys = _get_role_permission_keys(role.id)
        assert keys == set()


# ── Redis cache hit ───────────────────────────────────────────────────────────


class TestCacheHit:
    """When Redis has cached permissions, they're returned without DB access."""

    def test_cached_role_permissions_returned_from_redis(self, db, seeded_db):
        """_get_role_permission_keys returns cached set from Redis."""
        role = _create_role_with_perms(db, ["members.members.read"])

        mock_client = MagicMock()
        mock_client.smembers.return_value = {
            b"members.members.read",
            b"groups.groups.read",
        }

        with patch("hubra.api.permissions._get_redis_client", return_value=mock_client):
            keys = _get_role_permission_keys(role.id)

        assert keys == {"members.members.read", "groups.groups.read"}
        mock_client.smembers.assert_called_once_with(f"perms:public:{role.id}")

    def test_cached_member_permissions_returned_from_redis(self, db, seeded_db):
        """_get_member_permission_keys returns cached set from Redis."""
        role = _create_role_with_perms(db, ["members.members.read"])
        member_user = User(
            email="cachemember@test.ch",
            first_name="Cache",
            last_name="Member",
        )
        member_user.set_password("password123")
        db.session.add(member_user)
        db.session.flush()

        member = Member(
            user_id=member_user.id,
            status="active",
            tier_id=seeded_db["tier"].id,
        )
        member.roles = [role]
        db.session.add(member)
        db.session.commit()

        mock_client = MagicMock()
        mock_client.smembers.return_value = {b"members.members.read"}

        with patch("hubra.api.permissions._get_redis_client", return_value=mock_client):
            keys = _get_member_permission_keys(member)

        assert keys == {"members.members.read"}


# ── Cache invalidation ────────────────────────────────────────────────────────


class TestCacheInvalidation:
    """Cache invalidation functions clear the correct Redis keys."""

    def test_invalidate_role_permissions_deletes_key(self, db, seeded_db):
        """invalidate_role_permissions deletes the role cache key."""
        role = _create_role_with_perms(db, ["members.members.read"])

        mock_client = MagicMock()
        with patch("hubra.api.permissions._get_redis_client", return_value=mock_client):
            invalidate_role_permissions(role.id)

        mock_client.delete.assert_any_call(f"perms:public:{role.id}")

    def test_invalidate_member_permissions_deletes_key(self, db, seeded_db):
        """invalidate_member_permissions deletes the member cache key."""
        mock_client = MagicMock()
        with patch("hubra.api.permissions._get_redis_client", return_value=mock_client):
            invalidate_member_permissions(42)

        mock_client.delete.assert_called_once_with("perms:public:member:42")

    def test_invalidate_role_permissions_clears_member_caches(self, db, seeded_db):
        """invalidate_role_permissions also clears member caches for members holding the role."""

        role = _create_role_with_perms(db, ["members.members.read"])
        member_user = User(
            email="invalidate@test.ch",
            first_name="Invalidate",
            last_name="Test",
        )
        member_user.set_password("password123")
        db.session.add(member_user)
        db.session.flush()

        member = Member(
            user_id=member_user.id,
            status="active",
            tier_id=seeded_db["tier"].id,
        )
        member.roles = [role]
        db.session.add(member)
        db.session.commit()

        mock_client = MagicMock()
        with patch("hubra.api.permissions._get_redis_client", return_value=mock_client):
            invalidate_role_permissions(role.id)

        # Verify both role and member caches were deleted
        delete_calls = mock_client.delete.call_args_list
        all_deleted = []
        for call in delete_calls:
            args = call[0]
            all_deleted.extend(args)
        assert f"perms:public:{role.id}" in all_deleted
        assert f"perms:public:member:{member.id}" in all_deleted

    def test_invalidate_with_no_redis_is_silent(self, db, seeded_db):
        """Cache invalidation doesn't raise when Redis is unavailable."""
        with patch("hubra.api.permissions._get_redis_client", return_value=None):
            # Should not raise
            invalidate_role_permissions(999)
            invalidate_member_permissions(999)


# ── Redis down negative cache ─────────────────────────────────────────────────


class TestRedisDownNegativeCache:
    """When Redis fails, the negative cache suppresses further attempts."""

    def test_mark_redis_down_suppresses_subsequent_calls(self, db, seeded_db):
        """After _mark_redis_down, _get_redis_client returns None for a window."""
        _mark_redis_down()

        # _get_redis_client should return None during the negative-cache window
        result = _get_redis_client()
        assert result is None

    def test_permission_lookup_succeeds_during_redis_outage(self, db, seeded_db):
        """Permission lookup still works (via DB) during Redis outage."""
        role = _create_role_with_perms(db, ["members.members.read"])

        _mark_redis_down()  # Simulate Redis outage

        keys = _get_role_permission_keys(role.id)
        assert keys == {"members.members.read"}


def test_cache_keys_are_per_club(app):
    """Role and member ids restart in every club schema: club A's member 5
    must not read club B's cached permissions for member 5."""
    from flask import g

    from hubra.api.permissions import _member_cache_key, _role_cache_key

    keys = set()
    try:
        for path in ("tenant_1, public", "tenant_2, public"):
            g._search_path = path
            keys.add((_role_cache_key(5), _member_cache_key(5)))
    finally:
        g.pop("_search_path", None)
    assert keys == {
        ("perms:tenant_1:5", "perms:tenant_1:member:5"),
        ("perms:tenant_2:5", "perms:tenant_2:member:5"),
    }


def test_cache_keys_follow_the_resolved_club_without_postgres(app):
    from types import SimpleNamespace

    from flask import g

    from hubra.api.permissions import _member_cache_key

    g.tenant = SimpleNamespace(id=7, slug="seven")
    try:
        assert _member_cache_key(5) == "perms:tenant_7:member:5"
    finally:
        g.tenant = None
