"""RBAC integration tests: sync-permissions, fail-closed, is_admin bypass, cache invalidation.

Verifies:
- `flask sync-permissions` creates Permission rows for every decorated route.
- A role with zero permissions gets 403 on every @permission_required endpoint.
- A role with exactly one permission can access matching endpoints but is denied others.
- An is_admin role with no RolePermission rows bypasses all checks.
- invalidate_role_permissions() deletes the Redis cache key for a role.
"""

from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import select

from hubra.core.extensions import db as _db
from hubra.core.models.member import Member
from hubra.core.models.role import Role, RolePermission, Permission
from hubra.core.models.user import User

SETTINGS_URL = "/api/v1/settings/"
MEMBERS_URL = "/api/v1/members/"
ROLES_URL = "/api/v1/roles/"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_role_and_member(db, tier, *, name, is_admin=False, permission_keys=None):
    """Create a role + member, optionally granting permission keys. Returns auth headers."""
    role = Role(name=name, is_default=False, is_admin=is_admin)
    db.session.add(role)
    db.session.flush()

    if permission_keys:
        for key in permission_keys:
            perm = db.session.scalar(select(Permission).where(Permission.key == key))
            if perm is None:
                perm = Permission(
                    key=key,
                    display_name=key,
                    resource=key.split(".")[1] if "." in key else key,
                    action=key.split(".")[2]
                    if "." in key and len(key.split(".")) > 2
                    else key,
                    blueprint=key.split(".")[0] if "." in key else "",
                )
                db.session.add(perm)
                db.session.flush()
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

    user = User(
        email=f"{name.lower()}@test.ch",
        first_name="Test",
        last_name=name,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    member = Member(
        user_id=user.id,
        status="active",
        tier_id=tier.id,
    )
    member.roles = [role]
    db.session.add(member)
    db.session.commit()
    return member


def _login(client, email):
    """Log in and return auth headers (empty dict — cookies stored on client)."""
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    return {}


# ── 1. sync-permissions auto-discovery ────────────────────────────────────────


def test_sync_permissions_creates_rows(app, db):
    """`flask sync-permissions` creates a Permission row for every decorated route."""
    runner = app.test_cli_runner()
    result = runner.invoke(args=["sync-permissions"])
    assert result.exit_code == 0

    perms = db.session.scalars(select(Permission)).all()
    assert len(perms) > 0

    keys = {p.key for p in perms}
    assert "members.members.read" in keys
    assert "roles.roles.create" in keys

    for p in perms:
        assert p.display_name
        assert p.resource
        assert p.action
        assert p.blueprint
        assert p.is_active is True


def test_sync_permissions_idempotent(app, db):
    """Running sync twice doesn't create duplicates — second run updates 0."""
    runner = app.test_cli_runner()
    runner.invoke(args=["sync-permissions"])
    first_count = db.session.query(Permission).count()

    runner.invoke(args=["sync-permissions"])
    second_count = db.session.query(Permission).count()

    assert second_count == first_count


# ── 2. Fail-closed: role with no permissions ──────────────────────────────────


@pytest.fixture
def no_perm_headers(client, seeded_db):
    """A role with zero permissions — should get 403 on all protected endpoints."""
    _make_role_and_member(_db, seeded_db["tier"], name="NoPerms")
    return _login(client, "noperms@test.ch")


def test_no_permissions_settings_returns_empty(client, seeded_db, no_perm_headers):
    """No-perms user gets 200 with empty list on settings (authz done in-handler)."""
    resp = client.get(SETTINGS_URL, headers=no_perm_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_no_permissions_denied_members(client, seeded_db, no_perm_headers):
    resp = client.get(MEMBERS_URL, headers=no_perm_headers)
    assert resp.status_code == 403


def test_no_permissions_denied_roles_create(client, seeded_db, no_perm_headers):
    resp = client.post(ROLES_URL, json={"name": "X"}, headers=no_perm_headers)
    assert resp.status_code == 403


# ── 3. One permission grants matching endpoint, denies others ─────────────────


@pytest.fixture
def one_perm_headers(client, seeded_db, app, db):
    """Role with only settings.settings.read — can GET /settings but not /members."""
    # sync permissions first so Permission rows exist
    runner = app.test_cli_runner()
    runner.invoke(args=["sync-permissions"])

    _make_role_and_member(
        db,
        seeded_db["tier"],
        name="OnePerm",
        permission_keys=["settings.settings.read"],
    )
    return _login(client, "oneperm@test.ch")


def test_one_perm_can_access_matching_endpoint(client, seeded_db, one_perm_headers):
    resp = client.get(SETTINGS_URL, headers=one_perm_headers)
    assert resp.status_code == 200


def test_one_perm_denied_non_matching_endpoint(client, seeded_db, one_perm_headers):
    resp = client.get(MEMBERS_URL, headers=one_perm_headers)
    assert resp.status_code == 403


def test_one_perm_denied_other_action_on_same_resource(
    client, seeded_db, one_perm_headers
):
    """read on settings doesn't grant write."""
    resp = client.put(
        "/api/v1/settings/club.name",
        json={"value": "Hacked"},
        headers=one_perm_headers,
    )
    assert resp.status_code == 403


# ── 4. is_admin bypasses all checks ───────────────────────────────────────────


@pytest.fixture
def admin_no_perms_headers(client, seeded_db, app, db):
    """Role with is_admin=True and zero RolePermission rows."""
    # Sync so we know Permission rows exist but aren't granted
    runner = app.test_cli_runner()
    runner.invoke(args=["sync-permissions"])

    _make_role_and_member(db, seeded_db["tier"], name="AdminNoPerms", is_admin=True)
    return _login(client, "adminnoperms@test.ch")


def test_admin_no_perms_can_access_settings(client, seeded_db, admin_no_perms_headers):
    resp = client.get(SETTINGS_URL, headers=admin_no_perms_headers)
    assert resp.status_code == 200


def test_admin_no_perms_can_access_members(client, seeded_db, admin_no_perms_headers):
    resp = client.get(MEMBERS_URL, headers=admin_no_perms_headers)
    assert resp.status_code == 200


def test_admin_no_perms_can_create_roles(client, seeded_db, admin_no_perms_headers):
    resp = client.post(
        ROLES_URL, json={"name": "AdminCreated"}, headers=admin_no_perms_headers
    )
    assert resp.status_code == 201


# ── 5. Redis cache invalidation ───────────────────────────────────────────────


def test_invalidate_role_permissions_calls_redis_delete(app, db):
    """invalidate_role_permissions() deletes the cache key when Redis is available."""
    from hubra.api.permissions import invalidate_role_permissions

    mock_redis = MagicMock()
    with patch("hubra.api.permissions._get_redis_client", return_value=mock_redis):
        invalidate_role_permissions(42)

    mock_redis.delete.assert_called_once_with("perms:0:role:42")


def test_invalidate_role_permissions_noop_without_redis(app, db):
    """invalidate_role_permissions() is a no-op when Redis is unavailable (no exception)."""
    from hubra.api.permissions import invalidate_role_permissions

    with patch("hubra.api.permissions._get_redis_client", return_value=None):
        # Should not raise
        invalidate_role_permissions(99)
