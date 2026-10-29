"""Expired blocklist entries are cleaned up in every club, not only in public.

A sign-out in a club records the token in the club's schema, and the daily
cleanup only looked at the public schema, so those tables only grew.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text


def test_blocklist_cleanup_reaches_club_schemas(db, seeded_db):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("club schemas need Postgres")

    from hubra.core.models.tenant import Tenant
    from hubra.core.tasks.mail_tasks import cleanup_token_blocklist
    from hubra.core.tenant.schema_manager import create_tenant_schema, drop_tenant_schema

    tenant = Tenant(name="Blocklist Club", slug="blocklist-club", status="active")
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
    old = datetime.now(timezone.utc) - timedelta(days=60)
    try:
        db.session.execute(
            text(
                f"INSERT INTO {schema}.token_blocklist (jti, type, created_at)"
                " VALUES ('old-jti', 'refresh', :old), ('new-jti', 'refresh', now())"
            ),
            {"old": old},
        )
        db.session.commit()

        assert cleanup_token_blocklist.run()["deleted"] >= 1
        left = db.session.execute(
            text(f"SELECT jti FROM {schema}.token_blocklist")
        ).scalars().all()
        assert left == ["new-jti"]
    finally:
        db.session.rollback()
        drop_tenant_schema(tenant.id)
        db.session.commit()
