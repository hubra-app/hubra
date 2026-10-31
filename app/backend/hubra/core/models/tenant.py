"""Tenant and GlobalAuditEntry models — global tables in the public schema."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class Tenant(db.Model):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        db.String(255), unique=True, nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(db.String(50), nullable=False, default="starter")
    status: Mapped[str] = mapped_column(db.String(50), nullable=False, default="active")
    locale: Mapped[str] = mapped_column(
        String(10), nullable=False, default="de-CH", server_default="de-CH"
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Europe/Zurich",
        server_default="Europe/Zurich",
    )
    settings: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True, default=dict
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    # The club's own age public key: its backups are encrypted to it as
    # well as to the install's BACKUP_PUBLIC_KEY.
    backup_public_key: Mapped[str | None] = mapped_column(db.Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug!r} status={self.status!r}>"


class GlobalAuditEntry(db.Model):
    __tablename__ = "global_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    action: Mapped[str] = mapped_column(db.String(255), nullable=False)
    target_type: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    target_id: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    details: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(db.String(45), nullable=True)
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<GlobalAuditEntry id={self.id} action={self.action!r}>"
