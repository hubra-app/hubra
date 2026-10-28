"""Tests for Phase 4 Feature catalog and TenantFeature models."""

from hubra.core.models.feature import Feature, TenantFeature
from hubra.core.models.tenant import Tenant


def test_feature_code_is_primary_key(db):
    feature = Feature(code="test_feat", name="Test Feature", default_enabled=True)
    db.session.add(feature)
    db.session.commit()
    assert feature.code == "test_feat"


def test_feature_default_enabled_defaults_false(db):
    feature = Feature(code="test_def", name="Test Default")
    db.session.add(feature)
    db.session.commit()
    assert feature.default_enabled is False


def test_tenant_feature_unique_constraint(db):
    tenant = Tenant(name="Test", slug="test-uniq")
    db.session.add(tenant)
    db.session.flush()

    feature = Feature(code="test_uniq_feat", name="Test")
    db.session.add(feature)
    db.session.flush()

    tf1 = TenantFeature(
        tenant_id=tenant.id, feature_code="test_uniq_feat", enabled=True
    )
    db.session.add(tf1)
    db.session.flush()

    tf2 = TenantFeature(
        tenant_id=tenant.id, feature_code="test_uniq_feat", enabled=False
    )
    db.session.add(tf2)
    try:
        db.session.flush()
        db.session.rollback()
        raise AssertionError("Should have raised unique constraint violation")
    except Exception:
        db.session.rollback()


def test_tenant_feature_config_jsonb_nullable(db):
    tenant = Tenant(name="Test2", slug="test-config")
    db.session.add(tenant)
    db.session.flush()

    feature = Feature(code="test_config_feat", name="Test Config")
    db.session.add(feature)
    db.session.flush()

    tf = TenantFeature(
        tenant_id=tenant.id,
        feature_code="test_config_feat",
        enabled=True,
        config={"key": "value"},
    )
    db.session.add(tf)
    db.session.commit()
    assert tf.config == {"key": "value"}


def test_tenant_feature_config_defaults_none(db):
    tenant = Tenant(name="Test3", slug="test-no-config")
    db.session.add(tenant)
    db.session.flush()

    feature = Feature(code="test_no_config", name="Test No Config")
    db.session.add(feature)
    db.session.flush()

    tf = TenantFeature(tenant_id=tenant.id, feature_code="test_no_config", enabled=True)
    db.session.add(tf)
    db.session.commit()
    assert tf.config is not None  # default=dict
