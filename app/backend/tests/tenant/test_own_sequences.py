"""Every club counts its own ids: a new club's first invoice is number 1,
whatever other clubs did before."""

import pytest
from sqlalchemy import text


def _club(db, slug):
    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.schema_manager import create_tenant_schema

    tenant = Tenant(name=slug, slug=slug, status="active")
    db.session.add(tenant)
    db.session.commit()
    create_tenant_schema(tenant.id)
    db.session.commit()
    return tenant


def _new_tier_id(db, schema, name):
    return db.session.execute(
        text(
            f"INSERT INTO {schema}.membership_tiers (name) VALUES (:n) RETURNING id"
        ),
        {"n": name},
    ).scalar()


def test_each_club_has_its_own_counters(db, seeded_db):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("club schemas need Postgres")
    from hubra.core.tenant.schema_manager import drop_tenant_schema

    db.session.execute(
        text(
            "CREATE TABLE IF NOT EXISTS public.alembic_version"
            " (version_num varchar(32) PRIMARY KEY)"
        )
    )
    # Ids already drawn in public do not carry over to a new club.
    _new_tier_id(db, "public", "Public tier")
    first, second = _club(db, "seq-one"), _club(db, "seq-two")
    try:
        one, two = f"tenant_{first.id}", f"tenant_{second.id}"
        assert _new_tier_id(db, one, "A") == 1
        assert _new_tier_id(db, one, "B") == 2
        assert _new_tier_id(db, two, "A") == 1

        # No column of a club draws from a sequence in public any more.
        shared = db.session.execute(
            text(
                "SELECT table_name, column_default FROM information_schema.columns "
                "WHERE table_schema = :s AND column_default LIKE :p "
                "AND column_default NOT LIKE :own"
            ),
            {"s": one, "p": "nextval(%", "own": f"nextval('{one}.%"},
        ).all()
        assert shared == []
    finally:
        db.session.rollback()
        drop_tenant_schema(first.id)
        drop_tenant_schema(second.id)
        db.session.commit()
