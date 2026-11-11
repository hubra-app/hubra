"""Every club runs as its own database role: no rights on other clubs'
schemas or on the template tables in public (hubra/core/tenant/db_roles.py).

Needs Postgres (TEST_DATABASE_URL) and an app role that may create roles.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError


def _club(db, slug):
    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.schema_manager import create_tenant_schema

    tenant = Tenant(name=slug, slug=slug, status="active")
    db.session.add(tenant)
    db.session.commit()
    create_tenant_schema(tenant.id)
    db.session.commit()
    return tenant


@pytest.fixture
def clubs(app, db, seeded_db):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("club roles need Postgres")
    from hubra.core.tenant import db_roles
    from hubra.core.tenant.context import reset_search_path
    from hubra.core.tenant.schema_manager import drop_tenant_schema

    if not db_roles.available(db.session.connection()):
        pytest.skip("the test database role can't create roles")
    db.session.execute(
        text(
            "CREATE TABLE IF NOT EXISTS public.alembic_version"
            " (version_num varchar(32) PRIMARY KEY)"
        )
    )
    db.session.commit()
    a, b = _club(db, "role-a"), _club(db, "role-b")
    db.session.execute(
        text(f"INSERT INTO tenant_{b.id}.membership_tiers (name) VALUES ('B secret')")
    )
    db.session.commit()
    ids = (a.id, b.id)
    try:
        yield a, b
    finally:
        db.session.rollback()
        reset_search_path()
        db.session.commit()
        for tenant_id in ids:
            drop_tenant_schema(tenant_id)


def _current_user(db):
    return db.session.execute(text("SELECT current_user")).scalar()


def test_each_club_gets_its_own_role(db, clubs):
    from hubra.core.tenant import db_roles

    a, b = clubs
    conn = db.session.connection()
    assert db_roles.active_role(conn, a.id) == db_roles.role_name(conn, a.id)
    assert db_roles.active_role(conn, b.id) == db_roles.role_name(conn, b.id)


def test_a_club_reads_its_own_data_and_the_shared_tables(db, clubs):
    from hubra.core.models.member import MembershipTier
    from hubra.core.models.user import User
    from hubra.core.tenant.context import set_search_path

    a, _ = clubs
    set_search_path(a.id)
    assert _current_user(db).endswith(f"_club_{a.id}")
    db.session.add(MembershipTier(name="A tier"))
    db.session.flush()
    assert [t.name for t in db.session.query(MembershipTier).all()] == ["A tier"]
    # Shared tables in public stay reachable (users, tenants, ...).
    assert db.session.query(User).count() >= 1


def test_a_club_cannot_read_another_club(db, clubs):
    from hubra.core.tenant.context import set_search_path

    a, b = clubs
    set_search_path(a.id)
    with pytest.raises(ProgrammingError, match="permission denied"):
        db.session.execute(text(f"SELECT name FROM tenant_{b.id}.membership_tiers"))


def test_a_missing_club_table_does_not_fall_through_to_public(db, clubs):
    # The template copies in public are off limits: a club table missing
    # from the club's schema fails instead of using public's rows.
    from hubra.core.tenant.context import set_search_path

    a, _ = clubs
    set_search_path(a.id)
    with pytest.raises(ProgrammingError, match="permission denied"):
        db.session.execute(text("SELECT count(*) FROM public.membership_tiers"))


def test_the_role_survives_a_commit(db, clubs):
    from hubra.core.tenant.context import set_search_path

    a, _ = clubs
    set_search_path(a.id)
    db.session.commit()
    assert _current_user(db).endswith(f"_club_{a.id}")


def test_leaving_the_club_and_migrations_run_as_the_app_role(db, clubs):
    from hubra.core.tenant.context import reset_search_path, set_search_path

    a, b = clubs
    app_role = _current_user(db)
    set_search_path(a.id)
    reset_search_path()
    assert _current_user(db) == app_role
    set_search_path(b.id, as_club=False)
    assert _current_user(db) == app_role


def test_in_club_switches_between_clubs(app, db, clubs):
    from hubra.core.tenant.context import in_club

    a, b = clubs
    with in_club(a):
        assert _current_user(db).endswith(f"_club_{a.id}")
        with in_club(b):
            assert _current_user(db).endswith(f"_club_{b.id}")
        assert _current_user(db).endswith(f"_club_{a.id}")


def test_a_pooled_connection_gives_its_club_role_back(app, db, clubs):
    # The next user of the connection (a CLI command, engine.begin())
    # starts as the app role, not as the club the last request was in.
    from hubra.core.tenant.context import set_search_path

    a, _ = clubs
    a_id = a.id
    app_role = _current_user(db)
    set_search_path(a_id)
    db.session.commit()
    db.session.close()  # back to the pool
    with db.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT current_user").scalar() == app_role


def test_dropping_a_club_drops_its_role(db, clubs):
    from hubra.core.tenant import db_roles
    from hubra.core.tenant.schema_manager import drop_tenant_schema

    a, _ = clubs
    conn = db.session.connection()
    role = db_roles.role_name(conn, a.id)
    drop_tenant_schema(a.id)
    assert not db.session.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}
    ).scalar()


def test_sync_gives_existing_clubs_their_role(db, clubs):
    # A club from before club roles: its schema exists, its role doesn't.
    # The init step (flask sync-tenant-schemas) creates it.
    from hubra.core.tenant import db_roles
    from hubra.core.tenant.schema_manager import tables_to_clone

    a, _ = clubs
    conn = db.session.connection()
    db_roles.drop_club(conn, a.id)
    assert db_roles.active_role(conn, a.id) is None
    roles = db_roles.sync_all(conn, tables_to_clone())
    assert db_roles.role_name(conn, a.id) in roles
    assert db_roles.active_role(conn, a.id) == db_roles.role_name(conn, a.id)
