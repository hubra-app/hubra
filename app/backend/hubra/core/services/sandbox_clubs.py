"""Sandbox clubs: demo and test clubs that never touch real money.

A sandbox club always uses the platform's Stripe sandbox keys, for Online
payments and for Hubra's billing, whatever ``stripe.mode`` says
(``platform_settings.stripe_mode``).  Its billing revenue is left out of
manage's totals.  The flag is ``tenants.settings["sandbox"]``; platform
admins set it in manage › club or when creating the club.
"""

from __future__ import annotations

from sqlalchemy.orm.attributes import flag_modified

from hubra.core.models.tenant import Tenant

KEY = "sandbox"


def current() -> Tenant | None:
    """The club of this request, or None outside one."""
    from flask import g, has_app_context

    if not has_app_context():
        return None
    return getattr(g, "tenant", None)


def is_sandbox(tenant: Tenant | None) -> bool:
    return bool(tenant is not None and (tenant.settings or {}).get(KEY))


def set_sandbox(tenant: Tenant, on: bool) -> None:
    """Does NOT commit."""
    settings = dict(tenant.settings or {})
    if on:
        settings[KEY] = True
    else:
        settings.pop(KEY, None)
    tenant.settings = settings
    flag_modified(tenant, "settings")
