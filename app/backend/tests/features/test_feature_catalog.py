"""Tests for FeatureFlagService with tenant-aware feature catalog."""

from vollbuild.api.features.services import FeatureFlagService
from vollbuild.core.models.feature import Feature
from vollbuild.core.models.feature_flag import FeatureFlag
from vollbuild.core.models.tenant import Tenant


def test_is_enabled_returns_true_for_default_enabled_feature(db):
    """Feature with default_enabled=True returns True when no tenant grant exists."""
    feature = Feature(code="test_on", name="Test On", default_enabled=True)
    db.session.add(feature)
    db.session.commit()
    assert FeatureFlagService.is_enabled("test_on") is True


def test_is_enabled_returns_false_for_default_disabled_feature(db):
    """Feature with default_enabled=False returns False when no tenant grant exists."""
    feature = Feature(code="test_off", name="Test Off", default_enabled=False)
    db.session.add(feature)
    db.session.commit()
    assert FeatureFlagService.is_enabled("test_off") is False


def test_is_enabled_returns_false_for_unknown_feature(db):
    """Unknown feature code returns False."""
    assert FeatureFlagService.is_enabled("nonexistent") is False


def test_is_enabled_falls_back_to_legacy_feature_flag(db):
    """When no Feature catalog entry exists, falls back to FeatureFlag."""
    flag = FeatureFlag(key="legacy_feat", enabled=True, label="Legacy")
    db.session.add(flag)
    db.session.commit()
    assert FeatureFlagService.is_enabled("legacy_feat") is True


def test_set_tenant_feature_creates_grant(db):
    """set_tenant_feature creates a new TenantFeature grant."""
    tenant = Tenant(name="Test", slug="test-grant")
    db.session.add(tenant)
    db.session.flush()

    feature = Feature(code="grant_feat", name="Grant", default_enabled=False)
    db.session.add(feature)
    db.session.flush()

    grant = FeatureFlagService.set_tenant_feature(tenant.id, "grant_feat", True)
    db.session.commit()

    assert grant.enabled is True
    assert grant.tenant_id == tenant.id
    assert grant.feature_code == "grant_feat"


def test_set_tenant_feature_updates_existing_grant(db):
    """set_tenant_feature updates an existing TenantFeature grant."""
    tenant = Tenant(name="Test2", slug="test-update")
    db.session.add(tenant)
    db.session.flush()

    feature = Feature(code="update_feat", name="Update", default_enabled=False)
    db.session.add(feature)
    db.session.flush()

    FeatureFlagService.set_tenant_feature(tenant.id, "update_feat", True)
    db.session.commit()

    updated = FeatureFlagService.set_tenant_feature(tenant.id, "update_feat", False)
    db.session.commit()

    assert updated.enabled is False


def test_list_catalog_returns_all_features(db):
    """list_catalog returns all Feature rows ordered by code."""
    db.session.add(Feature(code="z_feat", name="Z", default_enabled=False))
    db.session.add(Feature(code="a_feat", name="A", default_enabled=True))
    db.session.commit()

    catalog = FeatureFlagService.list_catalog()
    codes = [f.code for f in catalog]
    assert "a_feat" in codes
    assert "z_feat" in codes
    # Ordered by code
    assert codes.index("a_feat") < codes.index("z_feat")


def test_list_tenant_features_returns_grants(db):
    """list_tenant_features returns all grants for a tenant."""
    tenant = Tenant(name="Test3", slug="test-list")
    db.session.add(tenant)
    db.session.flush()

    db.session.add(Feature(code="list1", name="L1", default_enabled=True))
    db.session.add(Feature(code="list2", name="L2", default_enabled=False))
    db.session.flush()

    FeatureFlagService.set_tenant_feature(tenant.id, "list1", True)
    FeatureFlagService.set_tenant_feature(tenant.id, "list2", False)
    db.session.commit()

    grants = FeatureFlagService.list_tenant_features(tenant.id)
    assert len(grants) == 2
