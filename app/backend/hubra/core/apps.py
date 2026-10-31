"""Connected apps: how a club links an outside service, and what it may do.

A module declares the services it can connect as ``AppProvider`` entries in
its manifest (``apps=``). Core owns everything that has to be the same for
every service: who may connect (``apps.manage``), the signed and
browser-bound sign-in round trip, the admin's confirmation, encrypted
secrets, disconnecting, the audit log and the activity list on the page.

The provider's ``handler`` object supplies only what is specific to the
service. Every hook is optional unless marked:

``unavailable() -> str | None``
    Why the service can't be connected on this platform right now (missing
    credentials), or None.
``authorize_url(state, redirect_uri, scopes) -> str``  (required to connect)
    The outside page the admin is sent to. It must hand ``state`` back.
``complete(args, redirect_uri) -> ConnectionDraft``  (required to connect)
    Called with the callback's query string inside the club; turns it into
    the connection to confirm. Raises ``AppError`` with a message to show.
``confirmed(connection)``
    After the admin confirmed (register commands, post a hello).
``options(connection) -> dict``
    What the settings form can choose from (channels, roles on the service,
    the club's groups); served at ``/connections/<id>/options``.
``update_config(connection, config) -> dict``
    Validates the provider's own settings (channel, role mapping); returns
    what to store. Raises ``AppError``.
``test(connection) -> str``
    Tries the connection; returns a message or raises ``AppError``.
``revoke(connection)``
    Undoes the link on the outside service (bot leaves the server). Best
    effort: the connection is removed in Hubra either way.
"""

from __future__ import annotations

import logging
import secrets as _secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import delete, select

from hubra.core.extensions import db
from hubra.core.models.connected_app import ConnectedApp, ConnectedAppEvent
from hubra.core.modules import AppProvider, Module, is_enabled, registry

_log = logging.getLogger(__name__)

# How long the outside sign-in round trip and the confirm step may take.
STATE_MAX_AGE = 600
PENDING_MAX_AGE = timedelta(hours=1)
# Activity rows kept per connection.
KEEP_EVENTS = 200
NONCE_COOKIE = "hubra_app_connect"


class AppError(Exception):
    """A provider hook failed in a way the admin should read."""


@dataclass
class ConnectionDraft:
    external_id: str
    label: str
    config: dict[str, Any] = field(default_factory=dict)
    secret: str | None = None


# ── Providers ────────────────────────────────────────────────────────────────


def provider(code: str) -> tuple[Module, AppProvider] | None:
    registry.load()
    return registry.app_provider(code)


def providers(tenant_id) -> list[tuple[Module, AppProvider]]:
    """Providers whose module is on for the club."""
    registry.load()
    return [
        (m, a)
        for m, a in registry.app_providers()
        if is_enabled(m.code, tenant_id=tenant_id)
    ]


def handler(app: AppProvider):
    import importlib

    module_path, _, attr = app.handler.partition(":")
    obj = importlib.import_module(module_path)
    return getattr(obj, attr) if attr else obj


def hook(app: AppProvider, name: str):
    try:
        return getattr(handler(app), name, None)
    except Exception:
        _log.exception("connected apps: could not load handler %s", app.handler)
        return None


def unavailable(app: AppProvider) -> str | None:
    fn = hook(app, "unavailable")
    if fn is None and hook(app, "authorize_url") is None:
        return "This service can't be connected"
    return fn() if fn else None


# ── The sign-in round trip ───────────────────────────────────────────────────


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="connected-apps"
    )


def make_state(code: str, tenant_id: int, member_id: int, scopes: list[str]):
    """Signed state for the outside page, and the nonce for the browser cookie.

    The cookie binds the round trip to the browser that started it, so a
    callback link someone else started can't be completed in your session.
    """
    nonce = _secrets.token_urlsafe(24)
    state = _serializer().dumps(
        {"p": code, "t": tenant_id, "m": member_id, "s": scopes, "n": nonce}
    )
    return state, nonce


def read_state(state: str, code: str, nonce: str | None) -> dict | None:
    try:
        data = _serializer().loads(state, max_age=STATE_MAX_AGE)
    except BadSignature:  # includes SignatureExpired
        return None
    if (
        data.get("p") != code
        or not nonce
        or not _secrets.compare_digest(str(data.get("n")), nonce)
    ):
        return None
    return data


# ── Connections ──────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    # SQLite hands back naive datetimes; they are UTC.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get(connection_id: int, tenant_id: int) -> ConnectedApp | None:
    """One of the club's connections; never another club's."""
    conn = db.session.get(ConnectedApp, connection_id)
    if conn is None or conn.tenant_id != tenant_id:
        return None
    return conn


def active(code: str, external_id: str) -> ConnectedApp | None:
    """The live connection for an outside id, whatever club it belongs to.

    For requests from the service itself (a button click carries only the
    Discord server id)."""
    return db.session.scalar(
        select(ConnectedApp).where(
            ConnectedApp.provider == code,
            ConnectedApp.external_id == str(external_id),
            ConnectedApp.status == "active",
        )
    )


def for_tenant(tenant_id: int, code: str | None = None) -> list[ConnectedApp]:
    """The club's live connections (optionally of one provider)."""
    query = select(ConnectedApp).where(
        ConnectedApp.tenant_id == tenant_id, ConnectedApp.status == "active"
    )
    if code:
        query = query.where(ConnectedApp.provider == code)
    return list(db.session.scalars(query.order_by(ConnectedApp.id)).all())


def pending_is_open(conn: ConnectedApp) -> bool:
    return (
        conn.status == "pending" and _now() - _aware(conn.created_at) < PENDING_MAX_AGE
    )


def listed(tenant_id: int) -> list[ConnectedApp]:
    """What the club's page shows: live connections and open confirmations."""
    rows = db.session.scalars(
        select(ConnectedApp)
        .where(
            ConnectedApp.tenant_id == tenant_id,
            ConnectedApp.status.in_(("active", "pending")),
        )
        .order_by(ConnectedApp.id)
    ).all()
    return [c for c in rows if c.status == "active" or pending_is_open(c)]


def has_scope(conn: ConnectedApp, scope: str) -> bool:
    return scope in (conn.scopes or [])


def secret(conn: ConnectedApp) -> str | None:
    if not conn.secret_encrypted:
        return None
    from cryptography.fernet import InvalidToken

    from hubra.core.crypto import decrypt_code

    try:
        return decrypt_code(conn.secret_encrypted)
    except InvalidToken:
        _log.error(
            "connected app %s: secret can't be decrypted (key changed?)", conn.id
        )
        return None


def set_secret(conn: ConnectedApp, value: str | None) -> None:
    from hubra.core.crypto import encrypt_code

    conn.secret_encrypted = encrypt_code(value) if value else None


def create_pending(
    tenant_id: int,
    code: str,
    draft: ConnectionDraft,
    scopes: list[str],
    member_id: int | None,
    member_name: str,
) -> ConnectedApp:
    # Confirmations nobody finished don't need to stay around.
    db.session.execute(
        delete(ConnectedApp).where(
            ConnectedApp.status == "pending",
            ConnectedApp.created_at < _now() - timedelta(days=1),
        )
    )
    conn = ConnectedApp(
        tenant_id=tenant_id,
        provider=code,
        external_id=str(draft.external_id),
        label=(draft.label or "")[:200],
        status="pending",
        scopes=list(scopes),
        config=dict(draft.config or {}),
        created_by_member_id=member_id,
        created_by_name=member_name[:255],
    )
    set_secret(conn, draft.secret)
    db.session.add(conn)
    db.session.flush()
    record(conn, "connect_started", True, "Waiting for confirmation")
    return conn


def taken_elsewhere(conn: ConnectedApp) -> bool:
    other = active(conn.provider, conn.external_id)
    return other is not None and other.tenant_id != conn.tenant_id


def confirm(conn: ConnectedApp) -> ConnectedApp:
    """Make a pending connection live. The caller checked the permission."""
    if not pending_is_open(conn):
        raise AppError("This confirmation has expired. Connect again.")
    if taken_elsewhere(conn):
        raise AppError("This is already connected to another club.")
    # Connecting the same thing again replaces the old link.
    previous = active(conn.provider, conn.external_id)
    if previous is not None:
        previous.status = "revoked"
        previous.revoked_at = _now()
        previous.revoked_by_name = "Replaced"
        previous.secret_encrypted = None
        db.session.flush()
    conn.status = "active"
    conn.confirmed_at = _now()
    db.session.flush()
    record(conn, "connected", True, "")
    found = provider(conn.provider)
    fn = hook(found[1], "confirmed") if found else None
    if fn is not None:
        try:
            fn(conn)
        except AppError as exc:
            record(conn, "connected", False, str(exc))
        except Exception:
            _log.exception("connected app %s: confirmed hook failed", conn.id)
    return conn


def revoke(conn: ConnectedApp, by_name: str) -> ConnectedApp:
    """Disconnect: undo it on the outside service if possible, forget the
    secret, and keep the row (revoked) for the record."""
    found = provider(conn.provider)
    fn = hook(found[1], "revoke") if found and conn.status == "active" else None
    if fn is not None:
        try:
            fn(conn)
        except Exception as exc:  # the link goes in Hubra either way
            _log.warning(
                "connected app %s: revoke on the service failed: %s", conn.id, exc
            )
            record(
                conn, "disconnected", False, f"Not undone on the service: {exc}"[:500]
            )
    conn.status = "revoked"
    conn.revoked_at = _now()
    conn.revoked_by_name = by_name[:255]
    conn.secret_encrypted = None
    db.session.flush()
    record(conn, "disconnected", True, "")
    return conn


def record(conn: ConnectedApp, action: str, ok: bool = True, detail: str = "") -> None:
    """Note what the connection did, for the activity list and its health."""
    now = _now()
    db.session.add(
        ConnectedAppEvent(
            connection_id=conn.id,
            action=action[:50],
            ok=ok,
            detail=(detail or "")[:500],
        )
    )
    if ok:
        conn.last_used_at = now
    else:
        conn.last_error = (detail or action)[:500]
        conn.last_error_at = now
    db.session.flush()
    stale = db.session.scalars(
        select(ConnectedAppEvent.id)
        .where(ConnectedAppEvent.connection_id == conn.id)
        .order_by(ConnectedAppEvent.id.desc())
        .offset(KEEP_EVENTS)
    ).all()
    if stale:
        db.session.execute(
            delete(ConnectedAppEvent).where(ConnectedAppEvent.id.in_(stale))
        )


def events(conn: ConnectedApp, limit: int = 50) -> list[ConnectedAppEvent]:
    return list(
        db.session.scalars(
            select(ConnectedAppEvent)
            .where(ConnectedAppEvent.connection_id == conn.id)
            .order_by(ConnectedAppEvent.id.desc())
            .limit(limit)
        ).all()
    )


def _iso(value: datetime | None) -> str | None:
    value = _aware(value)
    return value.isoformat() if value else None


def serialize(conn: ConnectedApp, with_events: bool = False) -> dict:
    found = provider(conn.provider)
    data = {
        "id": conn.id,
        "provider": conn.provider,
        "providerName": found[1].name if found else conn.provider,
        "externalId": conn.external_id,
        "label": conn.label,
        "status": conn.status,
        "scopes": list(conn.scopes or []),
        "config": dict(conn.config or {}),
        "hasSecret": bool(conn.secret_encrypted),
        "createdBy": conn.created_by_name,
        "createdAt": _iso(conn.created_at),
        "confirmedAt": _iso(conn.confirmed_at),
        "lastUsedAt": _iso(conn.last_used_at),
        "lastError": conn.last_error,
        "lastErrorAt": _iso(conn.last_error_at),
    }
    if with_events:
        data["events"] = [
            {
                "action": e.action,
                "ok": e.ok,
                "detail": e.detail,
                "at": _iso(e.created_at),
            }
            for e in events(conn)
        ]
    return data
