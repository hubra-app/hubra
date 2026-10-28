"""Tier service — business logic for membership tiers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from vollbuild.api.utils import escape_like, log_audit
from vollbuild.errors import raise_error
from vollbuild.extensions import db
from vollbuild.core.models.member import Member, MembershipTier


class TierService:
    """Operations on a single tier."""

    @staticmethod
    def get(tier_id: int) -> MembershipTier:
        """Return a tier or raise 404."""
        tier = db.session.get(MembershipTier, tier_id)
        if tier is None:
            raise_error(404, "NOT_FOUND", f"Tier {tier_id} not found")
        return tier  # type: ignore[return-value]

    @staticmethod
    def update(tier: MembershipTier, data: dict) -> MembershipTier:
        """Update allowed fields on a tier. Returns the tier."""
        ALLOWED = {
            "name",
            "price_chf",
            "color",
            "billing_cycle",
            "price_type",
            "percentage_value",
            "coefficient",
            "round_to",
            "deduct_tier_ids",
        }
        unknown = set(data.keys()) - ALLOWED
        if unknown:
            raise_error(422, "VALIDATION_ERROR", f"Unknown fields: {unknown}")

        if "name" in data:
            name = data["name"]
            if not isinstance(name, str) or not name.strip():
                raise_error(400, "VALIDATION_ERROR", "name must be a non-empty string")
            if name.strip() != tier.name:
                conflict = db.session.scalar(
                    select(MembershipTier.id)
                    .where(MembershipTier.name == name.strip())
                    .where(MembershipTier.id != tier.id)
                )
                if conflict is not None:
                    raise_error(409, "CONFLICT", f"Tier name '{name}' already in use")
            tier.name = name.strip()

        if "price_chf" in data:
            val = data["price_chf"]
            if val is not None:
                try:
                    price = Decimal(str(val))
                    if price < 0:
                        raise_error(
                            400,
                            "VALIDATION_ERROR",
                            "price_chf must be a non-negative number",
                        )
                    tier.price_chf = price
                except (TypeError, InvalidOperation):
                    raise_error(
                        400,
                        "VALIDATION_ERROR",
                        "price_chf must be a non-negative number",
                    )
            else:
                tier.price_chf = None

        if "color" in data:
            if not isinstance(data["color"], str):
                raise_error(400, "VALIDATION_ERROR", "color must be a string")
            tier.color = data["color"]

        if "billing_cycle" in data:
            val = data["billing_cycle"]
            if val is not None and val not in ("monthly", "yearly"):
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    "billing_cycle must be monthly, yearly, or null",
                )
            tier.billing_cycle = val

        if "price_type" in data:
            val = data["price_type"]
            if val not in ("fixed", "percentage", "formula"):
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    "price_type must be fixed, percentage, or formula",
                )
            tier.price_type = val

        DECIMAL_FIELDS = ("percentage_value", "coefficient")
        for field in DECIMAL_FIELDS:
            if field in data:
                val = data[field]
                setattr(tier, field, Decimal(str(val)) if val is not None else None)

        if "round_to" in data:
            val = data["round_to"]
            tier.round_to = int(val) if val is not None else None

        if "deduct_tier_ids" in data:
            val = data["deduct_tier_ids"]
            if val is not None and not isinstance(val, list):
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    "deduct_tier_ids must be a list of integers or null",
                )
            tier.deduct_tier_ids = [int(i) for i in val] if val else []

        return tier

    @staticmethod
    def delete(tier_id: int, actor_id: int) -> None:
        """Delete a tier if no members reference it."""
        tier = TierService.get(tier_id)

        member_count = (
            db.session.scalar(
                select(func.count())
                .select_from(Member)
                .where(Member.tier_id == tier.id)
            )
            or 0
        )
        if member_count > 0:
            raise_error(
                409,
                "CONFLICT",
                f"Cannot delete tier: {member_count} member(s) still reference it",
            )

        tier_name = tier.name
        db.session.delete(tier)

        log_audit(
            actor_id=actor_id,
            action="delete",
            target_type="tier",
            target_id=tier.id,
            target_label=tier_name,
        )

    @staticmethod
    def list_members(tier_id: int, search: str = "") -> list[Member]:
        """Return members belonging to a tier, with optional search."""
        from vollbuild.core.models.user import User

        query = (
            select(Member)
            .join(User, Member.user_id == User.id, isouter=True)
            .where(Member.tier_id == tier_id)
            .where(Member.archived_at.is_(None))
            .order_by(User.last_name, User.first_name)
            .options(
                selectinload(Member.tier),
                selectinload(Member.roles),
                selectinload(Member.groups),
            )
        )

        if search:
            pattern = f"%{escape_like(search)}%"
            query = query.where(
                User.first_name.ilike(pattern, escape="\\")
                | User.last_name.ilike(pattern, escape="\\")
                | User.email.ilike(pattern, escape="\\")
            )

        return db.session.scalars(query).all()  # type: ignore[return-value]


class TiersService:
    """Operations on the tier collection."""

    @staticmethod
    def list() -> list[MembershipTier]:
        """Return all tiers ordered by name."""
        return db.session.scalars(  # type: ignore[return-value]
            select(MembershipTier).order_by(MembershipTier.name)
        ).all()

    @staticmethod
    def create(data: dict, actor_id: int | None = None) -> MembershipTier:
        """Create a new tier. Raises 409 on name conflict."""
        existing = db.session.scalar(
            select(MembershipTier.id).where(MembershipTier.name == data["name"])
        )
        if existing is not None:
            raise_error(409, "CONFLICT", f"Tier '{data['name']}' already exists")

        tier = MembershipTier(
            name=data["name"],
            price_chf=data.get("price_chf"),
            color=data.get("color"),
            billing_cycle=data.get("billing_cycle"),
            price_type=data.get("price_type"),
            percentage_value=data.get("percentage_value"),
            coefficient=data.get("coefficient"),
            round_to=data.get("round_to"),
            deduct_tier_ids=data.get("deduct_tier_ids"),
        )
        db.session.add(tier)

        log_audit(
            actor_id=actor_id,
            action="create",
            target_type="tier",
            target_id=tier.id,
            target_label=tier.name,
        )
        return tier  # type: ignore[return-value]
