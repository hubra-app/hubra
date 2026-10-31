"""Connected apps: a club's links to outside services, and members' linked
accounts.

``ConnectedApp`` is one club's link to one outside thing, such as a Discord
server. Requests from that service (a button click in Discord) carry only
the outside id, so Hubra has to find the club from it: the table lives in
the public schema (in no module manifest, never cloned into a club schema),
and an outside id can be linked to one club at a time.

``ExternalAccount`` is a person's own link to an outside account (their
Discord user), made on the SSO account page. It belongs to the account,
not to a club, in line with clubs never managing accounts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db

_JSON = JSONB().with_variant(db.JSON, "sqlite")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConnectedApp(db.Model):
    __tablename__ = "connected_apps"
    __table_args__ = (
        # One club per outside id; revoked and pending rows don't count.
        Index(
            "uq_connected_apps_active_external",
            "provider",
            "external_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The AppProvider code, e.g. "discord".
    provider: Mapped[str] = mapped_column(db.String(50), nullable=False)
    # The outside id, e.g. the Discord server (guild) id.
    external_id: Mapped[str] = mapped_column(db.String(100), nullable=False)
    label: Mapped[str] = mapped_column(db.String(200), nullable=False, default="")
    # pending (waits for an admin to confirm) | active | revoked
    status: Mapped[str] = mapped_column(
        db.String(20), nullable=False, default="pending"
    )
    # The scope keys the admin granted, from the provider's list.
    scopes: Mapped[list | None] = mapped_column(_JSON, nullable=True)
    # Settings the provider keeps (channel, role mapping); never secrets.
    config: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    # Fernet token of a secret the provider needs; read with apps.secret().
    secret_encrypted: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    # Club member ids (club schema) and names as they were, for the page.
    created_by_member_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    created_by_name: Mapped[str] = mapped_column(
        db.String(255), nullable=False, default=""
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by_name: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class ConnectedAppEvent(db.Model):
    """What a connection did: deliveries, syncs, changes. The page shows the
    latest ones; older rows are trimmed."""

    __tablename__ = "connected_app_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("connected_apps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(db.String(50), nullable=False)
    ok: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    detail: Mapped[str] = mapped_column(db.String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class ExternalAccount(db.Model):
    __tablename__ = "external_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_external_account"),
        UniqueConstraint("user_id", "provider", name="uq_external_account_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(db.String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(db.String(100), nullable=False)
    username: Mapped[str] = mapped_column(db.String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
