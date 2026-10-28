"""Backwards-compatible re-export from vollbuild.core.tenant.migration."""

from vollbuild.core.tenant.migration import (
    annotations,
    select,
    text,
    db,
    Tenant,
    set_search_path,
    _log,
    apply_migrations_to_tenant,
    apply_migrations_to_all_tenants,
    ensure_tenant_has_alembic,
)
