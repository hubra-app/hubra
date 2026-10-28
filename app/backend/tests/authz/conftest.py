"""Shared fixtures for the authorization (authz) test suite.

Fixtures provided:
  - plain_member_token: authenticated member with NO permissions (just @jwt_required)
  - permissioned_member_token: member with a role that has specific RolePermission rows
  - board_member_token: member with an elevated but non-admin role (read + create on most domains)
  - seed_permissions(keys): helper fixture that creates Permission rows for given keys
"""

from __future__ import annotations

import pytest

from vollbuild.extensions import db as _db
from vollbuild.core.models.member import Member
from vollbuild.core.models.role import Permission, Role, RolePermission
from vollbuild.core.models.user import User


def _seed_permissions(keys: list[str]) -> dict[str, Permission]:
    """Create Permission rows for the given keys. Returns key→Permission dict."""
    perms: dict[str, Permission] = {}
    for key in keys:
        parts = key.split(".")
        resource = parts[1] if len(parts) > 1 else key
        action = parts[2] if len(parts) > 2 else key
        blueprint = parts[0] if "." in key else ""
        p = Permission(
            key=key,
            display_name=key,
            resource=resource,
            action=action,
            blueprint=blueprint,
        )
        _db.session.add(p)
        perms[key] = p
    _db.session.flush()
    return perms


def _create_member_with_role(
    email: str,
    role_name: str,
    tier_id: int,
    *,
    permission_keys: list[str] | None = None,
    is_admin: bool = False,
) -> tuple[Member, Role]:
    """Create a member with a role. If permission_keys are given, link RolePermission rows."""
    role = Role(name=role_name, is_default=False, is_admin=is_admin)
    _db.session.add(role)
    _db.session.flush()

    if permission_keys:
        perm_rows = _seed_permissions(permission_keys)
        for key in permission_keys:
            perm = perm_rows.get(key)
            if perm is not None:
                _db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        _db.session.flush()

    user = User(
        email=email,
        first_name="Test",
        last_name=role_name.replace(" ", ""),
        private_email_verified=True,
    )
    user.set_password("password123")
    _db.session.add(user)
    _db.session.flush()

    member = Member(
        user_id=user.id,
        status="active",
        tier_id=tier_id,
    )
    member.roles = [role]
    _db.session.add(member)
    _db.session.commit()
    return member, role


def _login_member(client, email: str) -> dict:
    """Log in as the given member and return empty headers (cookies auto-stored)."""
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    return {}


@pytest.fixture
def seed_permissions():
    """Return the _seed_permissions helper for ad-hoc permission creation in tests."""
    return _seed_permissions


@pytest.fixture
def plain_member_token(client, seeded_db):
    """Authenticated member with no permissions — role has no RolePermission rows."""
    tier = seeded_db["tier"]
    _create_member_with_role("plain@test.ch", "PlainMember", tier.id)
    return _login_member(client, "plain@test.ch")


@pytest.fixture
def permissioned_member_factory(client, seeded_db):
    """Factory fixture: create a member with a specific set of permissions.

    Usage:
        headers = permissioned_member_factory(["members.members.read", "members.members.create"])
    """
    tier = seeded_db["tier"]
    counter = [0]

    def _factory(keys: list[str], *, email: str | None = None) -> dict:
        counter[0] += 1
        addr = email or f"perm-member-{counter[0]}@test.ch"
        _create_member_with_role(
            addr, f"PermRole{counter[0]}", tier.id, permission_keys=keys
        )
        return _login_member(client, addr)

    return _factory


@pytest.fixture
def board_member_token(client, seeded_db):
    """Member with elevated but limited permissions (read on most, create on some).

    Simulates a 'Board Member' role: can read members/groups/events/polls,
    create events/polls, but cannot delete members or manage settings.
    """
    tier = seeded_db["tier"]
    keys = [
        "members.members.read",
        "groups.groups.read",
        "events.events.read",
        "events.events.create",
        "events.events.update",
        "polls.polls.read",
        "polls.polls.create",
        "polls.polls.vote",
        "posts.posts.read",
        "posts.posts.create",
        "posts.posts.comment",
        "posts.posts.like",
        "inventory.items.read",
        "inventory.items.instruct_self",
    ]
    _create_member_with_role(
        "board@test.ch", "BoardMember", tier.id, permission_keys=keys
    )
    return _login_member(client, "board@test.ch")
