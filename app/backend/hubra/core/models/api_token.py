"""API tokens: long-lived bearer secrets for scripts, integrations and the
Claude connector (docs/api-tokens.md).

A token always acts as a real person and never has more rights than they
have right now:

* ``member``  — a personal token: one member in one club.
* ``club``    — a club integration token, made by a club admin; it acts as
  that admin's membership, so it is capped by the admin's live rights.
* ``platform`` — a platform admin's read-only token for the platform API.

The secret is shown once and only its peppered hash is kept. The table lives
in the public schema (in no module manifest): a request's token is found
before its club is known.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db

_JSON = JSONB().with_variant(db.JSON, "sqlite")

KINDS = ("member", "club", "platform")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApiToken(db.Model):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Public part of the token, e.g. "hbr_pat_<public_id>_<secret>".
    public_id: Mapped[str] = mapped_column(
        db.String(16), unique=True, nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(db.String(20), nullable=False)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    # The account the token belongs to (personal and platform tokens) or the
    # admin who made it (club tokens).
    user_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    # The club, for member and club tokens; empty for platform tokens.
    tenant_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True,
        index=True,
    )
    # The membership the token acts as (club schema id).
    member_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    created_by_name: Mapped[str] = mapped_column(
        db.String(255), nullable=False, default=""
    )
    # HMAC-SHA256 of the secret under a pepper derived from FERNET_KEY.
    secret_hash: Mapped[str] = mapped_column(db.String(64), nullable=False)
    last4: Mapped[str] = mapped_column(db.String(4), nullable=False)
    # Permission keys (club) or global permission keys (platform).
    scopes: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    allowed_ips: Mapped[list | None] = mapped_column(_JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by_name: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    # Why the token stopped working before it was revoked or expired,
    # e.g. "failed_attempts" or "unused".
    revoked_reason: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_ip: Mapped[str | None] = mapped_column(db.String(45), nullable=True)
    use_count: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    failed_attempts: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=0
    )
    failed_window_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
