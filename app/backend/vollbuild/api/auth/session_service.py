"""Session & device management — list, revoke, revoke-all, admin revoke, devices."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from vollbuild.core.extensions import db
from vollbuild.core.models.device_session import Device, Session
from vollbuild.core.redis_client import get_redis_client as _get_redis_client
from vollbuild.core.redis_client import mark_redis_down as _mark_redis_down

_log = logging.getLogger(__name__)

_SESSION_CACHE_TTL = 60  # seconds


def _invalidate_session_cache(session_id: int) -> None:
    """Delete the cached session-valid flag for a session ID."""
    client = _get_redis_client()
    if client is not None:
        try:
            client.delete(f"session:{session_id}")
        except Exception:
            _log.debug("Redis cache invalidation failed for session %s", session_id)
            _mark_redis_down()


def is_session_revoked(session_id: int) -> bool:
    """Check if a session is revoked, using Redis cache (60s TTL) if available."""
    cache_key = f"session:{session_id}"
    client = _get_redis_client()
    redis_read_ok = True
    if client is not None:
        try:
            cached = client.get(cache_key)
            if cached is not None:
                return cached == b"revoked" or cached == "revoked"
        except Exception:
            _log.debug("Redis cache read failed for session %s", session_id)
            redis_read_ok = False
            _mark_redis_down()

    session = db.session.get(Session, session_id)
    revoked = session is not None and session.revoked_at is not None

    # Only attempt the cache write if the read succeeded — avoids a second
    # timeout when Redis is already failing.
    if client is not None and redis_read_ok:
        try:
            client.setex(
                cache_key, _SESSION_CACHE_TTL, "revoked" if revoked else "active"
            )
        except Exception:
            _log.debug("Redis cache write failed for session %s", session_id)
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
