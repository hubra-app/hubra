"""Member model, MembershipTier, and M:N association tables.

Member is a thin link table connecting a global User to a tenant with
tenant-specific data (tier, roles, groups, status, club mail address).
All personal identity attributes (name, email, password, contact info,
verification, lockout, preferences) live on the User model.

Association tables that reference members are defined here to avoid circular
imports.  FK targets for the other side (groups) use string-based
references that SQLAlchemy resolves lazily.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, JSON, Numeric, Table, Text, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db

# ── Association tables ────────────────────────────────────────────────────────

# Many-to-many: Member ↔ Group
member_groups = Table(
    "member_groups",
    db.metadata,
    Column(
        "member_id",
        db.Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "group_id",
        db.Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
        # The primary key leads with member_id; lists by group need this.
        index=True,
    ),
)

# Many-to-many: Member ↔ Role (a member may belong to multiple roles;
# effective permissions are the union of all role permission sets).
member_roles = Table(
    "member_roles",
    db.metadata,
    Column(
        "member_id",
        db.Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        db.Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        # The primary key leads with member_id; lists by role need this.
        index=True,
    ),
)

# ── MembershipTier ────────────────────────────────────────────────────────────


class MembershipTier(db.Model):
    __tablename__ = "membership_tiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    price_chf: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    color: Mapped[str | None] = mapped_column(db.String(7), nullable=True)
    # 'monthly' | 'yearly' | None — None means no auto-invoicing
    billing_cycle: Mapped[str | None] = mapped_column(db.String(10), nullable=True)
    # 'fixed' | 'percentage' | 'formula' | None
    price_type: Mapped[str | None] = mapped_column(db.String(20), nullable=True)

    # Percentage-type fields
    percentage_value: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    # Formula-type fields
    coefficient: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    round_to: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    deduct_tier_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    members: Mapped[list["Member"]] = relationship("Member", back_populates="tier")
    applications: Mapped[list["Application"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Application", back_populates="wants_tier"
    )
    payment_plans: Mapped[list["PaymentPlan"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "PaymentPlan",
        back_populates="tier",
        cascade="all, delete-orphan",
        order_by="PaymentPlan.id",
    )

    def __repr__(self) -> str:
        return f"<MembershipTier id={self.id} name={self.name!r}>"


# ── Member ────────────────────────────────────────────────────────────────────


class Member(db.Model):
    """Tenant-scoped link to a global User.

    Holds only tenant-specific data: tier, roles, groups, status, club mail
    address, membership metadata. All identity attributes are on User.
    """

    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Tenant-specific club mail address (local part is club_username)
    public_email: Mapped[str | None] = mapped_column(
        db.String(255), unique=True, nullable=True
    )
    club_username: Mapped[str | None] = mapped_column(
        db.String(64), unique=True, nullable=True
    )

    tier_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("membership_tiers.id"), nullable=True, index=True
    )
    # How the tier is paid; None means the tier's own billing cycle.
    payment_plan_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("payment_plans.id", ondelete="SET NULL"), nullable=True
    )

    joined: Mapped[date | None] = mapped_column(Date, nullable=True)

    # active | trial | inactive | suspended
    status: Mapped[str] = mapped_column(db.String(50), default="trial", nullable=False)
    tool_hours: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # regular | honorary | passive | trial
    membership_type: Mapped[str] = mapped_column(
        db.String(50), default="regular", nullable=False
    )
    membership_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    custom_fields: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True, default=dict
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Mail provisioning fields (per-tenant)
    retention_days: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    inbound_count: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set while a club admin has switched this member off. Only this club:
    # the person's account (and their other clubs) is not touched.
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set while the member's request to leave waits for a club admin.
    leave_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Contact data this member shows other members in the club's directory
    # ("email", "phone", "address", "birthday"). Nothing until they choose;
    # those who manage members always see everything.
    directory_shared: Mapped[list[str] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
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

    # ── Relationships ─────────────────────────────────────────────────────────

    user: Mapped["User | None"] = relationship("User")  # type: ignore[name-defined]  # noqa: F821
    tier: Mapped[MembershipTier | None] = relationship(
        "MembershipTier", back_populates="members"
    )
    payment_plan: Mapped["PaymentPlan | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "PaymentPlan"
    )
    roles: Mapped[list["Role"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Role",
        secondary=member_roles,
        back_populates="members",
    )
    groups: Mapped[list["Group"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Group",
        secondary=member_groups,
        back_populates="members",
    )
    led_groups: Mapped[list["Group"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Group", foreign_keys="Group.lead_id", back_populates="lead"
    )
    events: Mapped[list["ClubEvent"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ClubEvent", secondary="event_attendees", back_populates="attendees"
    )
    instructed_items: Mapped[list] = relationship(
        "InventoryItem",
        secondary="item_instructions",
        back_populates="instructed_members",
    )
    mailbox_folders: Mapped[list["MailboxFolder"]] = relationship(  # noqa: F821 # type: ignore
        "MailboxFolder",
        back_populates="member",
    )

    # ── Identity passthrough (getters + setters) ──────────────────────────────

    @property
    def name(self) -> str:
        return self.user.name if self.user else ""

    @name.setter
    def name(self, value: str) -> None:
        if self.user:
            self.user.name = value

    @property
    def email(self) -> str:
        return self.user.email if self.user else ""

    @email.setter
    def email(self, value: str) -> None:
        if self.user:
            self.user.email = value

    @property
    def first_name(self) -> str:
        return self.user.first_name if self.user else ""

    @first_name.setter
    def first_name(self, value: str) -> None:
        if self.user:
            self.user.first_name = value

    @property
    def last_name(self) -> str:
        return self.user.last_name if self.user else ""

    @last_name.setter
    def last_name(self, value: str) -> None:
        if self.user:
            self.user.last_name = value

    @property
    def password_hash(self) -> str:
        return self.user.password_hash if self.user else ""

    @property
    def avatar_color(self) -> str:
        return self.user.avatar_color if self.user else "#6366f1"

    @avatar_color.setter
    def avatar_color(self, value: str) -> None:
        if self.user:
            self.user.avatar_color = value

    @property
    def avatar(self) -> str | None:
        return self.user.avatar if self.user else None

    @avatar.setter
    def avatar(self, value: str | None) -> None:
        if self.user:
            self.user.avatar = value

    @property
    def must_change_password(self) -> bool:
        return self.user.must_change_password if self.user else False

    @must_change_password.setter
    def must_change_password(self, value: bool) -> None:
        if self.user:
            self.user.must_change_password = value

    @property
    def is_disabled(self) -> bool:
        """Switched off in this club, or the whole account is disabled."""
        if self.disabled_at is not None:
            return True
        return self.user.is_disabled if self.user else False

    @is_disabled.setter
    def is_disabled(self, value: bool) -> None:
        self.disabled_at = datetime.now(timezone.utc) if value else None

    @property
    def is_blocked(self) -> bool:
        """May not open the club: switched off (``is_disabled``) or marked
        "suspended". Unlike a disabled one, a suspended member's status is
        set back to active by an admin, not their switch."""
        return self.is_disabled or self.status == "suspended"

    @property
    def private_email_verified(self) -> bool:
        return self.user.private_email_verified if self.user else False

    @private_email_verified.setter
    def private_email_verified(self, value: bool) -> None:
        if self.user:
            self.user.private_email_verified = value

    @property
    def language(self) -> str:
        return self.user.language if self.user else "de-CH"

    @language.setter
    def language(self, value: str) -> None:
        if self.user:
            self.user.language = value

    @property
    def phone(self) -> str | None:
        return self.user.phone if self.user else None

    @phone.setter
    def phone(self, value: str | None) -> None:
        if self.user:
            self.user.phone = value

    @property
    def mobile(self) -> str | None:
        return self.user.mobile if self.user else None

    @mobile.setter
    def mobile(self, value: str | None) -> None:
        if self.user:
            self.user.mobile = value

    @property
    def birthday(self) -> date | None:
        return self.user.birthday if self.user else None

    @birthday.setter
    def birthday(self, value: date | None) -> None:
        if self.user:
            self.user.birthday = value

    @property
    def profile_note(self) -> str | None:
        return self.user.profile_note if self.user else None

    @profile_note.setter
    def profile_note(self, value: str | None) -> None:
        if self.user:
            self.user.profile_note = value

    @property
    def last_seen(self) -> datetime | None:
        return self.user.last_seen if self.user else None

    @last_seen.setter
    def last_seen(self, value: datetime | None) -> None:
        if self.user:
            self.user.last_seen = value

    @property
    def address_street(self) -> str | None:
        return self.user.address_street if self.user else None

    @address_street.setter
    def address_street(self, value: str | None) -> None:
        if self.user:
            self.user.address_street = value

    @property
    def address_house_no(self) -> str | None:
        return self.user.address_house_no if self.user else None

    @address_house_no.setter
    def address_house_no(self, value: str | None) -> None:
        if self.user:
            self.user.address_house_no = value

    @property
    def address_postal_code(self) -> str | None:
        return self.user.address_postal_code if self.user else None

    @address_postal_code.setter
    def address_postal_code(self, value: str | None) -> None:
        if self.user:
            self.user.address_postal_code = value

    @property
    def address_city(self) -> str | None:
        return self.user.address_city if self.user else None

    @address_city.setter
    def address_city(self, value: str | None) -> None:
        if self.user:
            self.user.address_city = value

    @property
    def address_country(self) -> str:
        return self.user.address_country if self.user else "CH"

    @address_country.setter
    def address_country(self, value: str) -> None:
        if self.user:
            self.user.address_country = value

    @property
    def emergency_contact(self) -> dict | None:
        return self.user.emergency_contact if self.user else None

    @emergency_contact.setter
    def emergency_contact(self, value: dict | None) -> None:
        if self.user:
            self.user.emergency_contact = value

    # ── Lockout / login passthrough ───────────────────────────────────────────

    @property
    def locked_until(self) -> datetime | None:
        return self.user.locked_until if self.user else None

    @locked_until.setter
    def locked_until(self, value: datetime | None) -> None:
        if self.user:
            self.user.locked_until = value

    @property
    def failed_login_count(self) -> int:
        return self.user.failed_login_count if self.user else 0

    @failed_login_count.setter
    def failed_login_count(self, value: int) -> None:
        if self.user:
            self.user.failed_login_count = value

    # ── Method passthroughs ───────────────────────────────────────────────────

    def set_password(self, plain: str) -> None:
        if self.user:
            self.user.set_password(plain)

    def check_password(self, plain: str) -> bool:
        if self.user:
            return self.user.check_password(plain)
        return False

    def __repr__(self) -> str:
        return f"<Member id={self.id} user_id={self.user_id}>"
