"""Session & device management — list, revoke, revoke-all, admin revoke, devices."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from hubra.core.extensions import db
from hubra.core.models.account_session import AccountSession
from hubra.core.models.device_session import Device, Session
from hubra.core.redis_client import get_redis_client as _get_redis_client
from hubra.core.redis_client import mark_redis_down as _mark_redis_down

_log = logging.getLogger(__name__)

_SESSION_CACHE_TTL = 60  # seconds


def _cache_key(session_id: int) -> str:
    """Sessions live in each club's schema, so the key names the club too."""
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    return f"session:{tenant.id if tenant else 0}:{session_id}"


def _invalidate_session_cache(session_id: int) -> None:
    """Delete the cached session-valid flag for a session ID."""
    client = _get_redis_client()
    if client is not None:
        try:
            client.delete(_cache_key(session_id))
        except Exception:
            _log.debug("Redis cache invalidation failed for session %s", session_id)
            _mark_redis_down()


def is_session_revoked(session_id: int) -> bool:
    """Check if a session is revoked, using Redis cache (60s TTL) if available."""

    def load() -> bool:
        session = db.session.get(Session, session_id)
        return session is not None and session.revoked_at is not None

    return _cached_revoked(_cache_key(session_id), load)


def _cached_revoked(cache_key: str, load) -> bool:
    """*load()* answers whether a session is revoked; Redis keeps it 60s."""
    client = _get_redis_client()
    redis_read_ok = True
    if client is not None:
        try:
            cached = client.get(cache_key)
            if cached is not None:
                return cached == b"revoked" or cached == "revoked"
        except Exception:
            _log.debug("Redis cache read failed for %s", cache_key)
            redis_read_ok = False
            _mark_redis_down()

    revoked = load()

    # Only attempt the cache write if the read succeeded — avoids a second
    # timeout when Redis is already failing.
    if client is not None and redis_read_ok:
        try:
            client.setex(
                cache_key, _SESSION_CACHE_TTL, "revoked" if revoked else "active"
            )
        except Exception:
            _log.debug("Redis cache write failed for %s", cache_key)
            _mark_redis_down()

    return revoked


def update_last_active(session_id: int) -> None:
    """Update last_active_at on Session and last_seen_at on Device (token refresh)."""
    session = db.session.get(Session, session_id)
    if session is not None:
        now = datetime.now(timezone.utc)
        session.last_active_at = now
        device = db.session.get(Device, session.device_id)
        if device is not None:
            device.last_seen_at = now


# ── Session queries ─────────────────────────────────────────────────────────


def list_sessions(member_id: int, include_revoked: bool = False) -> list[Session]:
    """Return sessions for a member (via Device join), newest first."""
    stmt = (
        select(Session)
        .join(Device, Session.device_id == Device.id)
        .where(Device.member_id == member_id)
        .order_by(Session.last_active_at.desc())
    )
    if not include_revoked:
        stmt = stmt.where(Session.revoked_at.is_(None))
    return list(db.session.scalars(stmt).all())


def get_session(session_id: int, member_id: int) -> Session | None:
    """Return a single session if it belongs to *member_id* (via Device)."""
    session = db.session.get(Session, session_id)
    if session is None:
        return None
    device = db.session.get(Device, session.device_id)
    if device is None or device.member_id != member_id:
        return None
    return session


def revoke_session(
    session_id: int, member_id: int, reason: str = "user_revoke"
) -> Session | None:
    """Revoke a single session. Returns the session or None if not found."""
    session = get_session(session_id, member_id)
    if session is None or session.revoked_at is not None:
        return None
    session.revoked_at = datetime.now(timezone.utc)
    session.revoked_reason = reason
    _invalidate_session_cache(session.id)
    return session


def revoke_all_other_sessions(
    member_id: int, keep_session_id: int, reason: str = "revoke_all"
) -> int:
    """Revoke all sessions for *member_id* except the one with *keep_session_id*.

    Returns the number of sessions revoked.
    """
    sessions = list(
        db.session.scalars(
            select(Session)
            .join(Device, Session.device_id == Device.id)
            .where(Device.member_id == member_id)
            .where(Session.revoked_at.is_(None))
            .where(Session.id != keep_session_id)
        ).all()
    )
    now = datetime.now(timezone.utc)
    for s in sessions:
        s.revoked_at = now
        s.revoked_reason = reason
        _invalidate_session_cache(s.id)
    return len(sessions)


def revoke_all_including_current(
    member_id: int, reason: str = "revoke_all_full"
) -> int:
    """Revoke ALL sessions for *member_id* including current. Returns count."""
    sessions = list(
        db.session.scalars(
            select(Session)
            .join(Device, Session.device_id == Device.id)
            .where(Device.member_id == member_id)
            .where(Session.revoked_at.is_(None))
        ).all()
    )
    now = datetime.now(timezone.utc)
    for s in sessions:
        s.revoked_at = now
        s.revoked_reason = reason
        _invalidate_session_cache(s.id)
    return len(sessions)


def admin_revoke_all_sessions(member_id: int, reason: str = "admin_revoke") -> int:
    """Admin endpoint: revoke all sessions for a member. Returns count."""
    return revoke_all_including_current(member_id, reason)


def update_session_activity(session_id: int) -> None:
    """Alias for update_last_active — called on token refresh."""
    update_last_active(session_id)


# ── Device queries ──────────────────────────────────────────────────────────


def list_devices(member_id: int) -> list[dict]:
    """Return all devices for a member with active session count and last active."""
    devices = list(
        db.session.scalars(
            select(Device)
            .where(Device.member_id == member_id)
            .order_by(Device.last_seen_at.desc())
        ).all()
    )
    result = []
    for device in devices:
        active_count = (
            db.session.scalar(
                select(func.count(Session.id)).where(
                    Session.device_id == device.id,
                    Session.revoked_at.is_(None),
                )
            )
            or 0
        )
        last_active = db.session.scalar(
            select(func.max(Session.last_active_at)).where(
                Session.device_id == device.id
            )
        )
        result.append(
            {
                **serialize_device(device),
                "activeSessionCount": active_count,
                "lastActiveAt": last_active.isoformat() if last_active else None,
            }
        )
    return result


def rename_device(device_id: int, member_id: int, name: str | None) -> Device | None:
    """Rename a device. Returns the device or None if not found."""
    device = db.session.get(Device, device_id)
    if device is None or device.member_id != member_id:
        return None
    device.name = name
    db.session.flush()
    return device


def revoke_device_sessions(
    device_id: int, member_id: int, reason: str = "device_revoke"
) -> int:
    """Revoke all active sessions for a device. Returns count revoked."""
    device = db.session.get(Device, device_id)
    if device is None or device.member_id != member_id:
        return 0
    sessions = list(
        db.session.scalars(
            select(Session)
            .where(Session.device_id == device_id)
            .where(Session.revoked_at.is_(None))
        ).all()
    )
    now = datetime.now(timezone.utc)
    for s in sessions:
        s.revoked_at = now
        s.revoked_reason = reason
        _invalidate_session_cache(s.id)
    return len(sessions)


def serialize_device(device: Device) -> dict:
    """Serialize a Device for API responses."""
    return {
        "id": device.id,
        "name": device.name,
        "browserFamily": device.browser_family or "",
        "platform": device.platform or "",
        "userAgent": device.user_agent or "",
        "fingerprint": device.fingerprint,
        "createdAt": device.created_at.isoformat() if device.created_at else None,
        "lastSeenAt": device.last_seen_at.isoformat() if device.last_seen_at else None,
    }


def serialize_session(session: Session) -> dict:
    """Serialize a Session (with Device info) for API responses."""
    device = db.session.get(Device, session.device_id)
    return {
        "id": session.id,
        "deviceId": session.device_id,
        "deviceName": device.name if device else None,
        "browserFamily": device.browser_family if device else "",
        "platform": device.platform if device else "",
        "userAgent": device.user_agent if device else "",
        "ipAddress": session.ip_address or "",
        "createReason": session.create_reason,
        "createdAt": session.created_at.isoformat() if session.created_at else None,
        "lastActiveAt": session.last_active_at.isoformat()
        if session.last_active_at
        else None,
        "revokedAt": session.revoked_at.isoformat() if session.revoked_at else None,
        "revokedReason": session.revoked_reason,
    }


# ── Account sign-ins (SSO portal, no club) ──────────────────────────────────

# A refresh token lives at most this long, so an older sign-in is over.
_ACCOUNT_SESSION_MAX_IDLE = timedelta(days=30)


def _account_cache_key(account_sid: int) -> str:
    return f"account-session:{account_sid}"


def record_account_login(
    user_id: int,
    ip: str,
    ua: str,
    fingerprint: str,
    browser_family: str = "",
    platform: str = "",
) -> int:
    """Record a sign-in without a club and return its id.  Does NOT commit.

    Like club sign-ins, a browser that is still signed in keeps its row.
    """
    now = datetime.now(timezone.utc)
    session = db.session.scalar(
        select(AccountSession)
        .where(AccountSession.user_id == user_id)
        .where(AccountSession.fingerprint == fingerprint)
        .where(AccountSession.revoked_at.is_(None))
        .where(AccountSession.last_active_at >= now - _ACCOUNT_SESSION_MAX_IDLE)
        .order_by(AccountSession.last_active_at.desc())
        .limit(1)
    )
    if session is None:
        session = AccountSession(
            user_id=user_id,
            fingerprint=fingerprint,
            browser_family=browser_family or None,
            platform=platform or None,
            created_at=now,
        )
        db.session.add(session)
    session.user_agent = ua[:512] or session.user_agent
    session.ip_address = ip[:45] if ip else None
    session.last_active_at = now
    db.session.flush()
    return session.id


def is_account_session_revoked(account_sid: int) -> bool:
    def load() -> bool:
        session = db.session.get(AccountSession, account_sid)
        return session is None or session.revoked_at is not None

    return _cached_revoked(_account_cache_key(account_sid), load)


def touch_account_session(account_sid: int) -> None:
    """Mark the sign-in as active now (token refresh).  Does NOT commit."""
    session = db.session.get(AccountSession, account_sid)
    if session is not None and session.revoked_at is None:
        session.last_active_at = datetime.now(timezone.utc)


def list_account_sessions(user, keep_id: int | None = None) -> list[AccountSession]:
    """The user's sign-ins that can still be in use, newest first.

    Hidden: revoked ones, ones idle longer than a refresh token lives, and
    ones from before the account ended all its sessions (password change),
    except *keep_id*, the sign-in asking.
    """
    cutoff = datetime.now(timezone.utc) - _ACCOUNT_SESSION_MAX_IDLE
    ended = user.tokens_valid_after
    if ended is not None:
        if ended.tzinfo is None:
            ended = ended.replace(tzinfo=timezone.utc)
        cutoff = max(cutoff, ended)
    stmt = (
        select(AccountSession)
        .where(AccountSession.user_id == user.id)
        .where(AccountSession.revoked_at.is_(None))
        .where(
            (AccountSession.last_active_at >= cutoff)
            | (AccountSession.id == (keep_id if keep_id is not None else -1))
        )
        .order_by(AccountSession.last_active_at.desc())
    )
    return list(db.session.scalars(stmt).all())


def revoke_account_session(
    account_sid: int, user_id: int, reason: str = "user_revoke"
) -> AccountSession | None:
    """End one sign-in of *user_id*.  Does NOT commit."""
    session = db.session.get(AccountSession, account_sid)
    if session is None or session.user_id != user_id or session.revoked_at:
        return None
    session.revoked_at = datetime.now(timezone.utc)
    session.revoked_reason = reason
    _invalidate_account_session_cache(session.id)
    return session


def revoke_other_account_sessions(
    user_id: int, keep_id: int | None, reason: str = "revoke_all"
) -> int:
    """End every sign-in of *user_id* except *keep_id*.  Does NOT commit."""
    stmt = (
        select(AccountSession)
        .where(AccountSession.user_id == user_id)
        .where(AccountSession.revoked_at.is_(None))
    )
    if keep_id is not None:
        stmt = stmt.where(AccountSession.id != keep_id)
    sessions = list(db.session.scalars(stmt).all())
    now = datetime.now(timezone.utc)
    for s in sessions:
        s.revoked_at = now
        s.revoked_reason = reason
        _invalidate_account_session_cache(s.id)
    return len(sessions)


def _invalidate_account_session_cache(account_sid: int) -> None:
    client = _get_redis_client()
    if client is not None:
        try:
            client.delete(_account_cache_key(account_sid))
        except Exception:
            _log.debug("Redis cache invalidation failed for %s", account_sid)
            _mark_redis_down()


def serialize_account_session(session: AccountSession) -> dict:
    """The same shape as a club session, without device or club."""
    return {
        "id": session.id,
        "deviceId": None,
        "deviceName": None,
        "browserFamily": session.browser_family or "",
        "platform": session.platform or "",
        "userAgent": session.user_agent or "",
        "ipAddress": session.ip_address or "",
        "createReason": None,
        "createdAt": session.created_at.isoformat() if session.created_at else None,
        "lastActiveAt": session.last_active_at.isoformat()
        if session.last_active_at
        else None,
        "revokedAt": session.revoked_at.isoformat() if session.revoked_at else None,
        "revokedReason": session.revoked_reason,
    }
