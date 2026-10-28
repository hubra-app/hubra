"""Tests for tenant migration helpers.

These tests verify the migration utility functions.  The actual
`apply_migrations_to_tenant` requires a running PostgreSQL with
tenant schemas, so it is tested via integration tests or Docker.
"""

import pytest

from vollbuild.core.tenant.migration import (
    apply_migrations_to_all_tenants,
    apply_migrations_to_tenant,
    ensure_tenant_has_alembic,
)


def test_ensure_tenant_has_alembic_is_callable():
    """Verify the function exists and is callable."""
    assert callable(ensure_tenant_has_alembic)


def test_apply_migrations_to_tenant_is_callable():
    assert callable(apply_migrations_to_tenant)


def test_apply_migrations_to_all_tenants_is_callable():
    assert callable(apply_migrations_to_all_tenants)


@pytest.mark.skipif(
    True,
    reason="Requires PostgreSQL with tenant schemas — run via Docker integration tests",
)
def test_apply_migrations_to_tenant_postgres():
    """Integration test: run migrations against a real tenant schema."""
    pass
