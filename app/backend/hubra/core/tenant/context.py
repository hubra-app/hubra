"""Tenant context helpers — current_tenant and search_path."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from flask import g, has_app_context
from sqlalchemy import event, text

from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant


def current_tenant() -> Tenant | None:
    """Return the resolved Tenant for the current request, or None."""
    return getattr(g, "tenant", None)


def _role_sql(role: str | None) -> str:
    return f'SET ROLE "{role}"' if role else "RESET ROLE"


def _apply_search_path(path: str, role: str | None = None) -> None:
    if db.session.get_bind().dialect.name == "sqlite":
        return
    # Remembered for the app context, so _restore_search_path can put it back
    # on whatever connection the next transaction gets.
    g._search_path = path
    g._db_role = role
    # One round trip for both.
    db.session.execute(text(f"SET search_path TO {path}; {_role_sql(role)}"))
    _mark(db.session.connection(), role)


def _mark(connection, role: str | None) -> None:
    """Note on the pooled connection whether it carries a club role, so
    :func:`_reset_role_on_return` drops it before anyone else gets it."""
    if role:
        connection.info["hubra_club_role"] = True
    else:
        connection.info.pop("hubra_club_role", None)


def set_search_path(tenant_id: int, as_club: bool = True) -> None:
    """Set the PostgreSQL search_path for the current DB session.

    Places the tenant schema first so domain-table queries resolve there,
    with public as fallback for global tables (tenants, domains, etc.).
    The path holds for the rest of the app context, across commits.

    With *as_club* (the default) the session also takes the club's own
    database role, when it has one (``db_roles``): no rights on other
    clubs' schemas. Migrations pass ``as_club=False`` and stay the app role.

    No-op on SQLite (no schema support).
    """
    # int() keeps anything but a number out of the SQL below.
    role = None
    if as_club and db.session.get_bind().dialect.name != "sqlite":
        from . import db_roles

        role = db_roles.active_role(db.session.connection(), int(tenant_id))
    _apply_search_path(f"tenant_{int(tenant_id)}, public", role)


def reset_search_path() -> None:
    """Reset the search_path to the default (public).

    No-op on SQLite (no schema support).
    """
    _apply_search_path("public")


@contextmanager
def in_club(tenant: Tenant) -> Iterator[None]:
    """Run as a request of *tenant*'s club, then go back."""
    previous = current_tenant()
    g.tenant = tenant
    set_search_path(tenant.id)
    try:
        yield
    finally:
        g.tenant = previous
        if previous is not None:
            set_search_path(previous.id)
        else:
            reset_search_path()


def _restore_search_path(session, transaction, connection) -> None:
    """Give every new transaction the search_path this app context asked for.

    SET search_path sticks to the pooled connection, not to the request, and
    a rollback undoes a SET made inside it. So after a commit or rollback the
    next transaction can run on public (the club's rows look deleted) or on
    a schema another request left behind. Contexts that never set a path run
    on public.
    """
    if connection.dialect.name == "sqlite":
        return
    if not has_app_context():
        return
    role = g.get("_db_role")
    connection.exec_driver_sql(
        f"SET search_path TO {g.get('_search_path', 'public')}; {_role_sql(role)}"
    )
    _mark(connection, role)


def _reset_role_on_return(dbapi_connection, connection_record, reset_state) -> None:
    """A connection going back to the pool leaves its club role behind, so
    the next user (a CLI command, ``engine.begin()``) starts as the app role."""
    if connection_record.info.pop("hubra_club_role", None):
        # Roll back first: whatever the last user left open is discarded,
        # as the pool would. Then drop the role and commit that alone, or
        # the pool's own rollback right after would undo it.
        dbapi_connection.rollback()
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("RESET ROLE")
        finally:
            cursor.close()
        dbapi_connection.commit()


def install_search_path_guard(app=None) -> None:
    """Register _restore_search_path on the app's session (once per process)."""
    if not event.contains(db.session, "after_begin", _restore_search_path):
        event.listen(db.session, "after_begin", _restore_search_path)
    if app is None:
        return
    with app.app_context():
        engine = db.engine
    if engine.dialect.name != "sqlite" and not event.contains(
        engine, "reset", _reset_role_on_return
    ):
        event.listen(engine, "reset", _reset_role_on_return)
