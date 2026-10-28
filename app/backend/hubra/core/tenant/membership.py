"""Which clubs a user belongs to (``public.user_tenants``).

A Member row lives in the club's schema, but sign-in, switch-tenant and the
club list read ``user_tenants`` in the public schema. Every code path that
gives a user a Member in a club must also record the link here, or the user
can't open that club.
"""

from __future__ import annotations

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.user_tenant import UserTenant


def link_user_to_tenant(user_id: int, tenant_id: int | None = None) -> None:
    """Record that ``user_id`` belongs to the club (default: the current one).

    Does nothing when the link already exists, or when no club is active
    (tests and scripts that run without a tenant). ``user_tenants`` exists
    only in the public schema, so this works whatever the search_path is.
    """
    if tenant_id is None:
        from hubra.core.tenant.context import current_tenant

        tenant = current_tenant()
        if tenant is None:
            return
        tenant_id = tenant.id

    exists = db.session.scalar(
        select(UserTenant.id).where(
            UserTenant.user_id == user_id,
            UserTenant.tenant_id == tenant_id,
        )
    )
    if exists is None:
        db.session.add(UserTenant(user_id=user_id, tenant_id=tenant_id))


def club_manages_account(user) -> bool:
    """Whether the current club may change ``user``'s account itself.

    An account is the person's own login for every club and portal. A club
    may set its password, email or other personal details, or switch the
    whole account off, only when the account belongs to nobody else: it is
    in no other club and holds no platform role. Otherwise the person
    manages it themselves (and a platform manager can help).
    """
    if user is None:
        return False
    if user.is_superadmin:
        return False
    from hubra.core.models.global_role import UserGlobalRole

    if db.session.scalar(
        select(UserGlobalRole.id).where(UserGlobalRole.user_id == user.id).limit(1)
    ):
        return False
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    others = select(UserTenant.id).where(UserTenant.user_id == user.id)
    if tenant is not None:
        others = others.where(UserTenant.tenant_id != tenant.id)
    return db.session.scalar(others.limit(1)) is None


def require_club_manages_account(user) -> None:
    """403 unless the current club may change ``user``'s account."""
    if not club_manages_account(user):
        from hubra.core.errors import raise_error

        raise_error(
            403,
            "ACCOUNT_NOT_MANAGED",
            "This person's account is also used outside this club; "
            "they change it themselves",
        )
