"""Tenant context helpers — current_tenant, search_path, tenant_required."""

from __future__ import annotations

from functools import wraps

from flask import current_app, g, has_app_context, jsonify
from sqlalchemy import event, text

from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant


def current_tenant() -> Tenant | None:
    """Return the resolved Tenant for the current request, or None."""
    return getattr(g, "tenant", None)


def single_club_slug() -> str | None:
    """Slug of the one club this install serves, or None in multi-club mode."""
    return current_app.config.get("SINGLE_CLUB") or None


def _apply_search_path(path: str) -> None:
    if db.session.get_bind().dialect.name == "sqlite":
        return
    # Remembered for the app context, so _restore_search_path can put it back
    # on whatever connection the next transaction gets.
    g._search_path = path
    db.session.execute(text(f"SET search_path TO {path}"))


def set_search_path(tenant_id: int) -> None:
    """Set the PostgreSQL search_path for the current DB session.

    Places the tenant schema first so domain-table queries resolve there,
    with public as fallback for global tables (tenants, domains, etc.).
    The path holds for the rest of the app context, across commits.

    No-op on SQLite (no schema support).
    """
    _apply_search_path(f"tenant_{tenant_id}, public")


def reset_search_path() -> None:
    """Reset the search_path to the default (public).

    No-op on SQLite (no schema support).
    """
    _apply_search_path("public")


def _restore_search_path(session, transaction, connection) -> None:
    """Give every new transaction the search_path this app context asked for.

    SET search_path sticks to the pooled connection, not to the request, and
    a rollback undoes a SET made inside it. So after a commit or rollback the
    next transaction can run on public (the club's rows look deleted) or on
    a schema another request left behind. Contexts that never set a path run
    on public.
    """
    if connection.dialect.name == "sqlite" or not has_app_context():
        return
    connection.exec_driver_sql(f"SET search_path TO {g.get('_search_path', 'public')}")


def install_search_path_guard() -> None:
    """Register _restore_search_path on the app's session (once per process)."""
    if not event.contains(db.session, "after_begin", _restore_search_path):
        event.listen(db.session, "after_begin", _restore_search_path)


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
