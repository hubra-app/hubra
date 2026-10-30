"""The person's own account, as the SSO portal edits it.

Everything here belongs to the global User and works without a club: name,
avatar, language, password and the sessions of every club the person is
in.  Club-specific things (membership, payment plan, mail forwarding) stay
in the club app.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant
from hubra.core.tenant.context import in_club

LANGUAGES = ("de-CH", "en-GB")
THEMES = ("light", "dark", "auto")


def memberships(user_id: int) -> Iterator[tuple[Tenant, Member]]:
    """Each active club of the user with their Member there, in that club."""
    tenant_ids = db.session.scalars(
        select(UserTenant.tenant_id).where(UserTenant.user_id == user_id)
    ).all()
    for tenant_id in tenant_ids:
        tenant = db.session.get(Tenant, tenant_id)
        if tenant is None or tenant.status != "active":
            continue
        with in_club(tenant):
            member = db.session.scalar(
                select(Member).where(
                    Member.user_id == user_id, Member.archived_at.is_(None)
                )
            )
            if member is not None:
                yield tenant, member


def club(user_id: int, slug: str) -> Tenant:
    """One of the user's clubs by slug, or 404."""
    tenant = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
    linked = tenant is not None and db.session.scalar(
        select(UserTenant.id).where(
            UserTenant.user_id == user_id, UserTenant.tenant_id == tenant.id
        )
    )
    if not linked:
        raise_error(404, "NOT_FOUND", "Club not found")
    return tenant


@contextmanager
def as_member_of(user_id: int, slug: str) -> Iterator[Member]:
    """The user's Member in club *slug*, with that club's schema active."""
    tenant = club(user_id, slug)
    with in_club(tenant):
        member = db.session.scalar(select(Member).where(Member.user_id == user_id))
        if member is None:
            raise_error(404, "NOT_FOUND", "Club not found")
        yield member


def profile(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "emailVerified": user.private_email_verified,
        "name": user.name,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "avatarColor": user.avatar_color,
        "profileNote": user.profile_note,
        "language": user.language,
        "theme": user.theme,
        "isSuperadmin": user.is_superadmin,
        "mustChangePassword": user.must_change_password,
    }


def update_profile(user: User, updates: dict) -> None:
    """Apply the person's own changes.  Does NOT commit."""
    if "name" in updates:
        name = (updates["name"] or "").strip()
        if not name:
            raise_error(400, "VALIDATION_ERROR", "Name cannot be empty")
        first, _, last = name.partition(" ")
        if len(first) > 255 or len(last.strip()) > 255:
            raise_error(400, "VALIDATION_ERROR", "Name is too long")
        user.name = name
    for key, attr in (("firstName", "first_name"), ("lastName", "last_name")):
        if key in updates:
            value = (updates[key] or "").strip()
            if attr == "first_name" and not value:
                raise_error(400, "VALIDATION_ERROR", "First name cannot be empty")
            if len(value) > 255:
                raise_error(400, "VALIDATION_ERROR", f"{key} exceeds 255 characters")
            setattr(user, attr, value)
    if "avatarColor" in updates:
        color = updates["avatarColor"] or ""
        if not (len(color) == 7 and color.startswith("#")):
            raise_error(400, "VALIDATION_ERROR", "avatarColor must be #rrggbb")
        user.avatar_color = color
    if "profileNote" in updates:
        note = updates["profileNote"]
        if note is not None and len(str(note)) > 5000:
            raise_error(400, "VALIDATION_ERROR", "Profile note exceeds 5000 characters")
        user.profile_note = note
    if "language" in updates:
        if updates["language"] not in LANGUAGES:
            raise_error(400, "VALIDATION_ERROR", "Unknown language")
        user.language = updates["language"]
    if "theme" in updates:
        if updates["theme"] not in THEMES:
            raise_error(400, "VALIDATION_ERROR", "Unknown theme")
        user.theme = updates["theme"]


def change_password(user: User, current_password: str, new_password: str) -> None:
    """Check the current password and set the new one.  Does NOT commit."""
    from hubra.api.auth.services import _enforce_password_strength

    if not current_password or not new_password:
        raise_error(
            400, "VALIDATION_ERROR", "currentPassword and newPassword are required"
        )
    _enforce_password_strength(new_password)
    if not user.check_password(current_password):
        raise_error(401, "UNAUTHORIZED", "Current password is incorrect")
    user.set_password(new_password)
    user.must_change_password = False
    # Signed out everywhere; the route hands this browser a new session.
    user.end_sessions()
