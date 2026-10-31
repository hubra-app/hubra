"""User model — global identity shared across tenants.

All personal identity attributes live here: name, email, password, contact
info, verification, lockout, preferences. Member is a thin link table that
connects a User to a tenant with tenant-specific data (tier, roles, groups).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import Date, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.avatar import random_avatar_color
from hubra.core.extensions import db

_ph = PasswordHasher()


class User(db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)

    first_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_color: Mapped[str] = mapped_column(
        db.String(7), default=random_avatar_color, nullable=False
    )

    is_superadmin: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )
    is_disabled: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    # Tokens issued before this moment are refused (password reset, password
    # set by an admin, account disabled): every session everywhere ends.
    tokens_valid_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    must_change_password: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )

    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    private_email_verified: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )
    language: Mapped[str] = mapped_column(
        db.String(10), default="de-CH", nullable=False
    )
    # light, dark or auto (follow the browser); see core/services/account.py.
    theme: Mapped[str] = mapped_column(
        db.String(10), default="auto", server_default="auto", nullable=False
    )

    # Two-factor sign-in (hubra/api/auth/mfa.py).  Secrets are Fernet
    # encrypted; recovery codes are kept as SHA-256 hashes, used ones removed.
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_pending_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The last 30-second step a code was accepted for: a code works once.
    totp_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recovery_codes: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )

    phone: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    mobile: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)

    address_street: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    address_house_no: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    address_postal_code: Mapped[str | None] = mapped_column(
        db.String(20), nullable=True
    )
    address_city: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    address_country: Mapped[str] = mapped_column(
        db.String(2), default="CH", nullable=False
    )

    emergency_contact: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True, default=dict
    )
    profile_note: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    @property
    def name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    @name.setter
    def name(self, value: str) -> None:
        parts = value.strip().split(None, 1)
        self.first_name = parts[0] if parts else ""
        self.last_name = parts[1] if len(parts) > 1 else ""

    def end_sessions(self) -> None:
        """Refuse every token issued so far, in every club and portal."""
        self.tokens_valid_after = datetime.now(timezone.utc)

    def set_password(self, plain: str) -> None:
        self.password_hash = _ph.hash(plain)

    def check_password(self, plain: str) -> bool:
        if self.password_hash.startswith("$argon2"):
            try:
                return _ph.verify(self.password_hash, plain)
            except VerifyMismatchError:
                return False
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, plain)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
