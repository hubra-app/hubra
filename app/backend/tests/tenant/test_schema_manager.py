"""Tests for TABLES_TO_CLONE consistency — regression guard against name drift."""

from vollbuild.core.tenant.schema_manager import TABLES_TO_CLONE

# Tables that live in the public schema only and must NOT be cloned.
_GLOBAL_ONLY_TABLES = frozenset(
    {
        "tenants",
        "domains",
        "users",
        "user_tenants",
        "tenant_requests",
        "global_audit_logs",
        "alembic_version",
        "global_permissions",
        "global_roles",
        "global_role_permissions",
        "user_global_roles",
        "features",
        "tenant_features",
    }
)


def test_tables_to_clone_match_registered_models(db):
    """Every TABLES_TO_CLONE entry must correspond to a real SQLAlchemy table."""
    registered = set(db.metadata.tables.keys())

    for table_name in TABLES_TO_CLONE:
        assert table_name in registered, (
            f"TABLES_TO_CLONE contains '{table_name}' but no model defines "
            f"that table. Check __tablename__ on the model class."
        )


def test_no_domain_tables_missing_from_clone_list(db):
    """Every registered domain table should be in TABLES_TO_CLONE (or be global-only)."""
    registered = set(db.metadata.tables.keys())
    cloned = set(TABLES_TO_CLONE)

    missing = registered - cloned - _GLOBAL_ONLY_TABLES
    assert not missing, (
        f"These tables exist in the model registry but are NOT in TABLES_TO_CLONE "
        f"and are not in the global-only exclusion set: {sorted(missing)}"
    )
