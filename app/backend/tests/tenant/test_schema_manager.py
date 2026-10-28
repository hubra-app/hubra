"""Tests for the tenant clone list — regression guard against name drift.

The list comes from the module manifests (``tables=``), so a new model
whose table no module claims fails here.
"""

from vollbuild.core.tenant.schema_manager import tables_to_clone

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
    """Every the clone list entry must correspond to a real SQLAlchemy table."""
    registered = set(db.metadata.tables.keys())

    for table_name in tables_to_clone():
        assert table_name in registered, (
            f"the clone list contains '{table_name}' but no model defines "
            f"that table. Check __tablename__ on the model class."
        )


def test_no_domain_tables_missing_from_clone_list(db):
    """Every registered domain table should be in the clone list (or be global-only)."""
    registered = set(db.metadata.tables.keys())
    cloned = set(tables_to_clone())

    missing = registered - cloned - _GLOBAL_ONLY_TABLES
    assert not missing, (
        f"These tables exist in the model registry but are NOT in the clone list "
        f"and are not in the global-only exclusion set: {sorted(missing)}"
    )
