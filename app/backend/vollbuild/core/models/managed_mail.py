"""ManagedMailAddress model — single source of truth for all club mail addresses."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vollbuild.core.extensions import db


class ManagedMailAddress(db.Model):
    """A mail address managed by the club, provisioned in WildDuck.

    Links to a Group, Function, or Member (mutually exclusive), or neither
    for fixed infrastructure addresses (postmaster, noreply).

    This model is the universal registry for all four mail categories:
    ``kind`` distinguishes the category instead of three separate FK columns.

    Old columns (is_system, wildduck_user_id, provisioning_status) are
    **deprecated** — kept for backward compatibility with the first-generation
    provisioning code. New code should use ``kind``, ``owner_type``/``owner_id``,
    ``wildduck_id``, and ``sync_state``.

    address_type (deprecated):
      "mailbox" — WildDuck user with local storage (members, noreply)
      "alias"   — WildDuck forwarded alias, pure forward (groups, functions, postmaster)

    is_enabled controls whether forwarding is active in WildDuck.  When
    disabled, the current forward targets are cached in
    cached_forward_targets and the WildDuck alias targets are set to [].
    Re-enabling restores the cached targets.

    fixed_forward_targets is a JSON-encoded list of addresses that override
    the dynamic resolution (used by system mailboxes like abuse@).

    is_system (deprecated) marks infrastructure addresses (noreply, postmaster, info,
    abuse) that appear in the System tab rather than group/function tabs.

    mail_prefix stores the local part of the address so admins can edit it
    without parsing the full address string.

    display_name is a human-readable label shown in the UI for system
    addresses.
    """

    __tablename__ = "managed_mail_addresses"
    __table_args__ = (
        UniqueConstraint("local_part", "domain", name="uq_local_part_domain"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    address_type: Mapped[str] = mapped_column(db.String(20), nullable=False)
    is_protected: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    forwarding_enabled: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    mail_prefix: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    display_name: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
    cached_forward_targets: Mapped[str | None] = mapped_column(Text, nullable=True)
    fixed_forward_targets: Mapped[str | None] = mapped_column(Text, nullable=True)
    provisioning_status: Mapped[str] = mapped_column(
        db.String(20), default="pending", nullable=False
    )
    wildduck_user_id: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    wildduck_filter_id: Mapped[str | None] = mapped_column(
        db.String(255), nullable=True
    )
    # ── New universal-registry columns ────────────────────────────────────
    kind: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    local_part: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    domain: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    owner_type: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    forward_enabled: Mapped[bool | None] = mapped_column(db.Boolean, nullable=True)
    enabled: Mapped[bool | None] = mapped_column(db.Boolean, nullable=True)
    quota_bytes: Mapped[int | None] = mapped_column(db.BigInteger, nullable=True)
    quota_used: Mapped[int | None] = mapped_column(db.BigInteger, nullable=True)
    retention: Mapped[int | None] = mapped_column(db.BigInteger, nullable=True)
    from_whitelist: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_quota_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    wildduck_id: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    wildduck_type: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_state: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    mailbox_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

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
        return f"<ManagedMailAddress id={self.id} address={self.address!r}>"
