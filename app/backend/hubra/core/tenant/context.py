"""Tenant context helpers — current_tenant, search_path, tenant_required."""

from __future__ import annotations

from functools import wraps

from flask import g, jsonify
from sqlalchemy import text

from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant


def current_tenant() -> Tenant | None:
    """Return the resolved Tenant for the current request, or None."""
    return getattr(g, "tenant", None)


def set_search_path(tenant_id: int) -> None:
    """Set the PostgreSQL search_path for the current DB session.

    Places the tenant schema first so domain-table queries resolve there,
    with public as fallback for global tables (tenants, domains, etc.).

    No-op on SQLite (no schema support).
    """
    if db.session.get_bind().dialect.name == "sqlite":
        return
    db.session.execute(text(f"SET search_path TO tenant_{tenant_id}, public"))


def reset_search_path() -> None:
    """Reset the search_path to the default (public).

    No-op on SQLite (no schema support).
    """
    if db.session.get_bind().dialect.name == "sqlite":
        return
    db.session.execute(text("SET search_path TO public"))


def tenant_required(fn):
    """Decorator: reject the request if no tenant was resolved.

    Returns 404 with NO_TENANT error when the tenant slug is unknown
    or the tenant is not active.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_tenant() is None:
            return jsonify(
                {"error": "NO_TENANT", "message": "Unknown or inactive tenant"}
            ), 404
        return fn(*args, **kwargs)

    return wrapper
