"""Backwards-compatible re-export from vollbuild.core.tenant.schema_manager."""

from vollbuild.core.tenant.schema_manager import (
    annotations,
    text,
    db,
    _log,
    TABLES_TO_CLONE,
    create_tenant_schema,
    drop_tenant_schema,
    schema_exists,
    _create_tenant_indexes,
    _init_alembic_version,
)
