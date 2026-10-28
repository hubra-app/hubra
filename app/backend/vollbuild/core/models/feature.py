"""Feature catalog and per-tenant feature grants.

Feature is a public-schema catalog of all available features.
TenantFeature links a Tenant to a Feature with an explicit enabled flag
and optional config JSONB, overriding the catalog's default_enabled.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from vollbuild.extensions import db


class Feature(db.Model):
    __tablename__ = "features"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Feature {self.code} default_enabled={self.default_enabled}>"


class TenantFeature(db.Model):
    __tablename__ = "tenant_features"
    __table_args__ = (
        UniqueConstraint("tenant_id", "feature_code", name="uq_tenant_feature"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("features.code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    config: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TenantFeature tenant={self.tenant_id} feature={self.feature_code!r} enabled={self.enabled}>"
