"""Tests for TenantService — provisioning, status transitions, audit logging.

Schema operations (CREATE SCHEMA, SET search_path) are mocked so these
tests run on SQLite.  Integration tests with real PostgreSQL live in
test_migration.py.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from vollbuild.core.models.tenant import Tenant, GlobalAuditEntry
from vollbuild.core.tenant.service import (
    TenantService,
    TenantProvisioningError,
    _validate_slug,
)


# ── Slug validation ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "slug",
    ["acm", "acme-corp", "my-club-123", "a-b-c-d-e-f-g"],
)
def test_valid_slugs(slug):
    _validate_slug(slug)


@pytest.mark.parametrize(
    "slug",
    ["ab", "-abc", "abc-", "ABC", "a_b", "a b", "", "x" * 70],
)
def test_invalid_slugs(slug):
    with pytest.raises(TenantProvisioningError, match="Invalid slug"):
        _validate_slug(slug)


# ── Status transitions ───────────────────────────────────────────────────────


def test_set_status_suspend(db):
    tenant = Tenant(name="Test", slug="test-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()

    result = TenantService.suspend(tenant.id)
    assert result is not None
    assert result.status == "suspended"

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.suspended")
    )
    assert entry is not None
    assert entry.tenant_id == tenant.id
    assert entry.details["old_status"] == "active"
    assert entry.details["new_status"] == "suspended"


def test_set_status_activate(db):
    tenant = Tenant(name="Test", slug="test-club", plan="starter", status="suspended")
    db.session.add(tenant)
    db.session.commit()

    result = TenantService.activate(tenant.id)
    assert result.status == "active"

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.active")
    )
    assert entry is not None


def test_set_status_archive(db):
    tenant = Tenant(name="Test", slug="test-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()

    result = TenantService.archive(tenant.id)
    assert result.status == "archived"


def test_set_status_nonexistent(db):
    result = TenantService.set_status(99999, "suspended")
    assert result is None


# ── Query helpers ────────────────────────────────────────────────────────────


def test_list_tenants(db):
    db.session.add_all(
        [
            Tenant(name="A", slug="club-a"),
            Tenant(name="B", slug="club-b"),
        ]
    )
    db.session.commit()

    result = TenantService.list_tenants()
    assert len(result["tenants"]) == 2
    assert result["total"] == 2


def test_get_by_slug(db):
    tenant = Tenant(name="Test", slug="find-me")
    db.session.add(tenant)
    db.session.commit()

    result = TenantService.get_by_slug("find-me")
    assert result is not None
    assert result.id == tenant.id


def test_get_by_slug_not_found(db):
    assert TenantService.get_by_slug("nope") is None


def test_get_by_id(db):
    tenant = Tenant(name="Test", slug="by-id")
    db.session.add(tenant)
    db.session.commit()

    result = TenantService.get_by_id(tenant.id)
    assert result is not None
    assert result.slug == "by-id"


def test_get_by_id_not_found(db):
    assert TenantService.get_by_id(99999) is None


# ── Provisioning (with mocked schema operations) ─────────────────────────────


@patch("vollbuild.core.tenant.service.create_tenant_schema")
@patch("vollbuild.core.tenant.service.drop_tenant_schema")
@patch("vollbuild.core.tenant.service.set_search_path", create=True)
@patch("vollbuild.core.tenant.service._seed_tenant")
def test_provision_tenant_basic(mock_seed, mock_set_sp, mock_drop, mock_create, db):
    """Provisioning creates Tenant record and calls schema creation + seeding."""
    tenant = TenantService.provision_tenant(name="Acme", slug="acme", plan="growth")
    assert tenant.name == "Acme"
    assert tenant.slug == "acme"
    assert tenant.plan == "growth"
    assert tenant.status == "active"

    mock_create.assert_called_once_with(tenant.id)
    mock_seed.assert_called_once()

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.provision")
    )
    assert entry is not None
    assert entry.details["name"] == "Acme"
    assert entry.details["slug"] == "acme"


@patch("vollbuild.core.tenant.service.create_tenant_schema")
@patch("vollbuild.core.tenant.service._seed_tenant")
def test_provision_tenant_duplicate_slug(mock_seed, mock_create, db):
    """Provisioning rejects a duplicate slug."""
    db.session.add(Tenant(name="Existing", slug="acme"))
    db.session.commit()

    with pytest.raises(TenantProvisioningError, match="already exists"):
        TenantService.provision_tenant(name="New", slug="acme")


@patch("vollbuild.core.tenant.service.create_tenant_schema")
@patch("vollbuild.core.tenant.service.drop_tenant_schema")
@patch(
    "vollbuild.core.tenant.service._seed_tenant", side_effect=RuntimeError("seed fail")
)
def test_provision_tenant_seed_failure_cleans_up(mock_seed, mock_drop, mock_create, db):
    """When seeding fails, schema is dropped and error is raised."""
    with pytest.raises(TenantProvisioningError, match="Failed to seed"):
        TenantService.provision_tenant(name="Fail", slug="fail-club")

    mock_drop.assert_called_once()
    mock_create.assert_called_once()


@patch(
    "vollbuild.core.tenant.service.create_tenant_schema",
    side_effect=RuntimeError("no db"),
)
def test_provision_tenant_schema_failure(mock_create, db):
    """When schema creation fails, error is raised without seeding."""
    with pytest.raises(TenantProvisioningError, match="Failed to create schema"):
        TenantService.provision_tenant(name="Fail", slug="fail-schema")


# ── Delete (with mocked schema operations) ───────────────────────────────────


@patch("vollbuild.core.tenant.service.drop_tenant_schema")
def test_delete_tenant_force(mock_drop, db):
    """Force delete permanently removes the tenant and drops the schema."""
    tenant = Tenant(name="Doomed", slug="doomed")
    db.session.add(tenant)
    db.session.commit()
    tid = tenant.id

    result = TenantService.delete_tenant(tid, force=True)
    assert result is True

    mock_drop.assert_called_once_with(tid)
    assert db.session.get(Tenant, tid) is None

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.delete")
    )
    assert entry is not None
    assert entry.details["slug"] == "doomed"


def test_delete_tenant_soft_delete(db):
    """Default delete (no force) performs a soft-delete."""
    tenant = Tenant(name="Doomed", slug="doomed")
    db.session.add(tenant)
    db.session.commit()
    tid = tenant.id

    result = TenantService.delete_tenant(tid)
    assert result is True

    # Record still exists
    tenant = db.session.get(Tenant, tid)
    assert tenant is not None
    assert tenant.deleted_at is not None
    assert tenant.status == "archived"

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.soft_delete")
    )
    assert entry is not None


@patch("vollbuild.core.tenant.service.drop_tenant_schema")
def test_delete_tenant_not_found(mock_drop, db):
    result = TenantService.delete_tenant(99999)
    assert result is False
    mock_drop.assert_not_called()
