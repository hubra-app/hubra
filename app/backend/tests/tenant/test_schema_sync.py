"""Club schemas catch up with public: a migration that changed only the
template tables (0ac79fcc9933, ee771f92971b) left existing clubs without
``transactions.recurring_id``, ``invoices.period_start`` and the
``recurring_transactions`` table, and their finance pages failed."""

import pytest
from sqlalchemy import text


def _club(db, slug):
    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.schema_manager import create_tenant_schema

    db.session.execute(
        text(
            "CREATE TABLE IF NOT EXISTS public.alembic_version"
            " (version_num varchar(32) PRIMARY KEY)"
        )
    )
    tenant = Tenant(name=slug, slug=slug, status="active")
    db.session.add(tenant)
    db.session.commit()
    create_tenant_schema(tenant.id)
    db.session.commit()
    return tenant


def _columns(db, schema, table):
    return set(
        db.session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t"
            ),
            {"s": schema, "t": table},
        ).scalars()
    )


def test_old_club_gets_missing_tables_columns_and_indexes(db, seeded_db):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("club schemas need Postgres")
    from hubra.core.tenant.schema_manager import drop_tenant_schema, tables_to_clone
    from hubra.core.tenant.schema_sync import catch_up, catch_up_all

    tenant = _club(db, "sync-old")
    schema = f"tenant_{tenant.id}"
    try:
        # A club made before the two finance migrations.
        db.session.execute(text(f"DROP TABLE {schema}.recurring_transactions"))
        db.session.execute(
            text(f"ALTER TABLE {schema}.transactions DROP COLUMN recurring_id")
        )
        db.session.execute(
            text(
                f"ALTER TABLE {schema}.invoices "
                "DROP COLUMN period_start, DROP COLUMN period_end"
            )
        )
        db.session.commit()

        conn = db.session.connection()
        result = catch_up(conn, schema, tables_to_clone())
        assert result.tables == ["recurring_transactions"]
        assert set(result.columns) == {
            "transactions.recurring_id",
            "invoices.period_start",
            "invoices.period_end",
        }
        assert "ix_transactions_recurring_id" in result.indexes
        assert "recurring_id" in _columns(db, schema, "transactions")
        assert {"period_start", "period_end"} <= _columns(db, schema, "invoices")

        # The new table counts its own ids, not public's.
        default = db.session.execute(
            text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = 'recurring_transactions' "
                "AND column_name = 'id'"
            ),
            {"s": schema},
        ).scalar()
        assert default.startswith(f"nextval('{schema}.")

        # The query the finance page ran now works in the club's schema.
        db.session.execute(text(f"SET search_path TO {schema}, public"))
        db.session.execute(text("SELECT recurring_id FROM transactions")).all()
        db.session.execute(text("SELECT period_start FROM invoices")).all()
        db.session.execute(text("SET search_path TO public"))

        # Again: nothing left to do.
        assert not catch_up(conn, schema, tables_to_clone()).changed
        assert all(r.schema != schema for r in catch_up_all(conn, tables_to_clone()))
    finally:
        db.session.rollback()
        drop_tenant_schema(tenant.id)


def test_only_club_schemas():
    from hubra.core.tenant.schema_sync import catch_up

    with pytest.raises(ValueError):
        catch_up(None, "public", [])
