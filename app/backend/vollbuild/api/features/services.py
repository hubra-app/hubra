"""FeatureFlag service — tenant-aware feature catalog and grants.

is_enabled() checks TenantFeature grants first, then falls back to
Feature.default_enabled, then to the legacy FeatureFlag table for
backward compatibility during migration.
"""

from __future__ import annotations

from sqlalchemy import select

from vollbuild.errors import raise_error
from vollbuild.extensions import db
from vollbuild.core.models.feature_flag import FeatureFlag
from vollbuild.core.models.feature import Feature, TenantFeature


class FeatureFlagService:
    @staticmethod
    def is_enabled(key: str) -> bool:
        """Check if a feature is enabled for the current tenant.

        Resolution order:
        1. TenantFeature row for (current_tenant, key) — explicit grant/deny
        2. Feature.default_enabled — catalog default
        3. Legacy FeatureFlag table — backward compat during migration
        4. False — feature doesn't exist
        """
        # Try tenant-specific grant first
        try:
            from vollbuild.core.tenant.context import current_tenant

            tenant = current_tenant()
            if tenant is not None:
                grant = db.session.scalar(
                    select(TenantFeature)
                    .where(TenantFeature.tenant_id == tenant.id)
                    .where(TenantFeature.feature_code == key)
                )
                if grant is not None:
                    return grant.enabled
        except Exception:
            pass

        # Fall back to catalog default
        feature = db.session.get(Feature, key)
        if feature is not None:
            return feature.default_enabled

        # Legacy fallback: check old FeatureFlag table
        flag = db.session.get(FeatureFlag, key)
        return flag is not None and flag.enabled

    @staticmethod
    def is_enabled_sync(key: str) -> bool:
        """Same as is_enabled, safe inside Celery task context.

        Without a Flask request context, tenant resolution is skipped.
        Falls back to Feature.default_enabled or legacy FeatureFlag.
        """
        feature = db.session.get(Feature, key)
        if feature is not None:
            return feature.default_enabled

        flag = db.session.get(FeatureFlag, key)
        return flag is not None and flag.enabled

    @staticmethod
    def list() -> list:
        """List all features — catalog entries plus legacy flags."""
        features = list(
            db.session.scalars(select(Feature).order_by(Feature.code)).all()
        )
        if features:
            return features
        return list(
            db.session.scalars(select(FeatureFlag).order_by(FeatureFlag.key)).all()
        )

    @staticmethod
    def set_enabled(key: str, enabled: bool):
        """Toggle a feature for the current tenant.

        Creates or updates a TenantFeature grant. Falls back to
        FeatureFlag if no tenant context is available.
        """
        try:
            from vollbuild.core.tenant.context import current_tenant

            tenant = current_tenant()
            if tenant is not None:
                grant = db.session.scalar(
                    select(TenantFeature)
                    .where(TenantFeature.tenant_id == tenant.id)
                    .where(TenantFeature.feature_code == key)
                )
                if grant is None:
                    grant = TenantFeature(
                        tenant_id=tenant.id,
                        feature_code=key,
                        enabled=enabled,
                    )
                    db.session.add(grant)
                else:
                    grant.enabled = enabled
                db.session.flush()
                return grant
        except Exception:
            pass

        # Legacy fallback
        flag = db.session.get(FeatureFlag, key)
        if flag is None:
            raise_error(404, "NOT_FOUND", f"Feature flag '{key}' does not exist")
        flag.enabled = enabled
        db.session.flush()
        return flag

    # ── Catalog / Manager methods ────────────────────────────────────────

    @staticmethod
    def list_catalog() -> list[Feature]:
        """List all features in the catalog."""
        return list(db.session.scalars(select(Feature).order_by(Feature.code)).all())

    @staticmethod
    def list_tenant_features(tenant_id: int) -> list[TenantFeature]:
        """List all feature grants for a tenant."""
        return list(
            db.session.scalars(
                select(TenantFeature).where(TenantFeature.tenant_id == tenant_id)
            ).all()
        )

    @staticmethod
    def set_tenant_feature(
        tenant_id: int, feature_code: str, enabled: bool, config: dict | None = None
    ) -> TenantFeature:
        """Create or update a tenant feature grant."""
        grant = db.session.scalar(
            select(TenantFeature)
            .where(TenantFeature.tenant_id == tenant_id)
            .where(TenantFeature.feature_code == feature_code)
        )
        if grant is None:
            grant = TenantFeature(
                tenant_id=tenant_id,
                feature_code=feature_code,
                enabled=enabled,
                config=config,
            )
            db.session.add(grant)
        else:
            grant.enabled = enabled
            if config is not None:
                grant.config = config
        db.session.flush()
        return grant
