"""PlatformPlan and PlatformAddon: the plans clubs are on and the paid
add-ons, with their list prices, as the platform sets them in manage.

Public schema only.  ``public`` decides what the public pricing API
(``GET /api/v1/public/pricing``) and so the website show; a plan that is
not public is still assignable, for individual deals.  A club's own price,
discount, sponsor and add-on prices live on the club
(``services.club_billing``).  Nothing here charges anyone yet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PlatformPlan(db.Model):
    __tablename__ = "platform_plans"

    # The value in tenants.plan.
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    name_de: Mapped[str] = mapped_column(String(80), nullable=False)
    name_en: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    description_de: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Per month and per year in CHF; null: on request.
    price_month_chf: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    price_year_chf: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    # [{"de": "...", "en": "..."}]
    features: Mapped[list | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True
    )
    # Null: no limit (see services.quotas).
    limit_members: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_mail_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_storage_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    highlighted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Hidden: no new club gets it, clubs on it keep it.
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class PlatformAddon(db.Model):
    __tablename__ = "platform_addons"

    # A module code (built in or from a plugin).
    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    price_month_chf: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Shown instead of the module's own name and description, if set.
    label_de: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    label_en: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    note_de: Mapped[str] = mapped_column(Text, nullable=False, default="")
    note_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
