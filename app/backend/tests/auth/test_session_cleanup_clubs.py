"""Old revoked sessions are cleaned up in every club, not only in public.

A sign-in to a club records its session in the club's schema, and the
daily cleanup only looked at the public schema.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text


def test_cleanup_reaches_club_schemas(db, seeded_db):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("club schemas need Postgres")

    from hubra.core.models.tenant import Tenant
    from hubra.core.tasks.session_tasks import cleanup_revoked_sessions
    from hubra.core.tenant.schema_manager import create_tenant_schema, drop_tenant_schema

    tenant = Tenant(name="Cleanup Club", slug="cleanup-club", status="active")
    db.session.add(tenant)
    db.session.commit()
    # Tests build the schema with create_all, so there is no migration row.
    db.session.execute(
        text(
            "CREATE TABLE IF NOT EXISTS public.alembic_version"
            " (version_num varchar(32) PRIMARY KEY)"
        )
    )
    create_tenant_schema(tenant.id)
    db.session.commit()
    schema = f"tenant_{tenant.id}"
    old = datetime.now(timezone.utc) - timedelta(days=200)
    try:
        db.session.execute(text("SET session_replication_role = replica"))
        db.session.execute(
            text(
                f"INSERT INTO {schema}.devices (id, member_id, fingerprint, created_at, last_seen_at)"
                " VALUES (990001, 1, 'fp', now(), now())"
            )
        )
        db.session.execute(
            text(
                f"INSERT INTO {schema}.sessions (device_id, jti, created_at, last_active_at, revoked_at)"
                " VALUES (990001, 'old-jti', :old, :old, :old),"
                " (990001, 'live-jti', now(), now(), NULL)"
            ),
            {"old": old},
        )
        db.session.execute(text("SET session_replication_role = DEFAULT"))
        db.session.commit()

        assert cleanup_revoked_sessions() >= 1
        left = db.session.execute(text(f"SELECT jti FROM {schema}.sessions")).scalars().all()
        assert left == ["live-jti"]
    finally:
        db.session.rollback()
        drop_tenant_schema(tenant.id)
        db.session.commit()
