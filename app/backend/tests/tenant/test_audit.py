"""Tests for GlobalAuditEntry — tenant lifecycle audit logging."""

from sqlalchemy import select

from vollbuild.core.models.tenant import Tenant, GlobalAuditEntry
from vollbuild.core.tenant.service import TenantService


def test_global_audit_entry_model(db):
    """GlobalAuditEntry can be created and queried."""
    entry = GlobalAuditEntry(
        action="test.action",
        target_type="TestTarget",
        target_id="1",
        details={"key": "value"},
    )
    db.session.add(entry)
    db.session.commit()

    result = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "test.action")
    )
    assert result is not None
    assert result.target_type == "TestTarget"
    assert result.details["key"] == "value"
    assert result.time is not None


def test_audit_entry_tenant_id_nullable(db):
    """GlobalAuditEntry.tenant_id is nullable (for system-wide events)."""
    entry = GlobalAuditEntry(
        action="system.event",
        tenant_id=None,
    )
    db.session.add(entry)
    db.session.commit()

    result = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "system.event")
    )
    assert result is not None
    assert result.tenant_id is None


def test_provision_creates_audit_entry(db):
    """Provisioning a tenant logs a tenant.provision audit entry."""
    from unittest.mock import patch

    with (
        patch("vollbuild.core.tenant.service.create_tenant_schema"),
        patch("vollbuild.core.tenant.service._seed_tenant"),
    ):
        tenant = TenantService.provision_tenant(name="Audited", slug="audited")

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(
            GlobalAuditEntry.action == "tenant.provision",
            GlobalAuditEntry.tenant_id == tenant.id,
        )
    )
    assert entry is not None
    assert entry.details["name"] == "Audited"
    assert entry.details["slug"] == "audited"


def test_status_change_creates_audit_entry(db):
    """Status transitions create audit entries with old/new status."""
    tenant = Tenant(name="Test", slug="audit-status")
    db.session.add(tenant)
    db.session.commit()

    TenantService.suspend(tenant.id)

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(
            GlobalAuditEntry.action == "tenant.suspended",
            GlobalAuditEntry.tenant_id == tenant.id,
        )
    )
    assert entry is not None
    assert entry.details["old_status"] == "active"
    assert entry.details["new_status"] == "suspended"
