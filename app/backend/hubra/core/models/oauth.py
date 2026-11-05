"""OAuth apps (docs/oauth.md): outside apps that act for a person with
their consent, such as the Claude connector.

* ``OAuthClient`` — an app: registered by a platform admin (``registered``),
  by a club admin for the club's own website or forum (``club``, sign-in
  only, docs/oidc.md) or by itself through dynamic client registration
  (``dynamic``, only for the Claude connector).
* ``OAuthCode``   — a one-time authorization code, valid five minutes.

A sign-in an app holds is an ``api_tokens`` row with ``oauth_client_id``
set (``hubra/core/auth/oauth.py``): the same checks, scopes, rate limits and
revocation as an API token. All tables live in the public schema.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db

_JSON = JSONB().with_variant(db.JSON, "sqlite")

CLIENT_KINDS = ("registered", "club", "dynamic")
# What an app may ask for: the Hubra API itself, or the Claude connector.
RESOURCES = ("api", "mcp")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OAuthClient(db.Model):
    __tablename__ = "oauth_clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(
        db.String(64), unique=True, nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(db.String(20), nullable=False)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    description: Mapped[str] = mapped_column(db.String(500), nullable=False, default="")
    client_uri: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    redirect_uris: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    # Empty for a public client (PKCE only).
    secret_hash: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    secret_last4: Mapped[str | None] = mapped_column(db.String(4), nullable=True)
    # Subset of RESOURCES; empty for an app that only signs people in.
    resources: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    # "read", "write" (API access) and "openid" (Sign in with Hubra).
    scopes: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    # A club's own app: only its members sign in, and it may ask for the
    # "club" claims (membership, groups).
    tenant_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by_name: Mapped[str] = mapped_column(
        db.String(255), nullable=False, default=""
    )
    created_ip: Mapped[str | None] = mapped_column(db.String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OAuthCode(db.Model):
    __tablename__ = "oauth_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code_hash: Mapped[str] = mapped_column(
        db.String(64), unique=True, nullable=False, index=True
    )
    client_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("oauth_clients.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # "member" (a club), "platform" or "identity" (sign-in only).
    kind: Mapped[str] = mapped_column(db.String(20), nullable=False)
    tenant_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )
    member_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    scopes: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    oauth_scope: Mapped[str] = mapped_column(db.String(100), nullable=False)
    resource: Mapped[str] = mapped_column(db.String(500), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(db.String(1000), nullable=False)
    # Empty only for a confidential app's OpenID request with a nonce.
    code_challenge: Mapped[str] = mapped_column(db.String(128), nullable=False)
    # OpenID Connect: echoed in the ID token; when the person signed in.
    nonce: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    auth_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    days: Mapped[int] = mapped_column(db.Integer, nullable=False)
    created_by_name: Mapped[str] = mapped_column(
        db.String(255), nullable=False, default=""
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The sign-in the code turned into, so a second use can end it.
    token_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
