"""Shared helpers for the auth module."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hubra.core.models.member import Member


def parse_identity(identity: str) -> int:
    """Parse a JWT identity string into a numeric user ID.

    JWT identities come in two forms:
    - ``"user:<id>"`` — global User identity (the standard after the refactor)
    - ``"<member_id>"`` — legacy tenant-scoped Member identity (old tokens)

    This helper strips the ``user:`` prefix when present and returns the
    integer ID. For legacy tokens the returned integer is a member_id, not
    a user_id — callers that need the user_id should use
    ``get_current_member()`` instead.
    """
    if isinstance(identity, str) and identity.startswith("user:"):
        return int(identity[5:])
    return int(identity)


def is_user_identity(identity: str) -> bool:
    """Return True if *identity* is a global User identity (``user:<id>``)."""
    return isinstance(identity, str) and identity.startswith("user:")


def get_current_member() -> Member:
    """Resolve the current JWT identity to a Member in the current tenant.

    The JWT identity is always ``user:<user_id>``. This helper:
    1. Parses the user_id from the JWT identity.
    2. Finds the Member record linked to that user in the current tenant
       (search_path must already be set to the tenant schema).
    3. Raises 403 if the user has no Member profile in this tenant.

    Use this in tenant-scoped routes that need the member_id for audit
    entries or service calls.
    """
    from flask_jwt_extended import get_jwt_identity

    from hubra.core.errors import raise_error
    from hubra.core.extensions import db
    from hubra.core.models.member import Member
    from sqlalchemy import select

    identity = get_jwt_identity()

    # For user: identities, parse the user_id and resolve to a Member
    if is_user_identity(identity):
        from hubra.core.tenant.context import current_tenant

        # Inside a club only the club token counts (see _current_member).
        if current_tenant() is not None:
            raise_error(401, "UNAUTHORIZED", "Open the club to continue")
        user_id = int(identity[5:])
        member = db.session.scalar(
            select(Member)
            .where(Member.user_id == user_id)
            .where(Member.archived_at.is_(None))
        )
        if member is None or member.is_disabled:
            raise_error(403, "FORBIDDEN", "No member profile in this tenant")
        return member

    # Legacy token: identity is a plain member_id
    member = db.session.get(Member, int(identity))
    if member is None:
        raise_error(403, "FORBIDDEN", "No member profile in this tenant")
    return member


def get_current_user_id() -> int:
    """Parse the current JWT identity and return the user_id.

    For ``user:<id>`` identities, returns the user_id directly.
    For legacy ``<member_id>`` identities, resolves the Member and
    returns its ``user_id``.
    """
    from flask_jwt_extended import get_jwt_identity

    from hubra.core.extensions import db
    from hubra.core.models.member import Member

    identity = get_jwt_identity()
    if is_user_identity(identity):
        return int(identity[5:])

    # Legacy token: resolve member to get user_id
    member = db.session.get(Member, int(identity))
    if member and member.user_id:
        return member.user_id
    raise ValueError("Cannot resolve user_id from legacy identity without user link")
