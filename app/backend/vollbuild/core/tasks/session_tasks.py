"""Session-related Celery tasks — cleanup, last_seen, session activity."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from vollbuild.extensions import db
from vollbuild.core.models.device_session import Device, Session
from vollbuild.core.tasks import celery_app

_log = logging.getLogger(__name__)

_RETENTION_DAYS = 90


@celery_app.task(name="vollbuild.core.tasks.session_tasks.cleanup_revoked_sessions")
def cleanup_revoked_sessions() -> int:
    """Delete Session rows that were revoked more than _RETENTION_DAYS ago.

    Device rows are kept — they persist so the device history is retained.
    Returns the number of rows deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    result = db.session.execute(
        delete(Session).where(
            Session.revoked_at.is_not(None),
            Session.revoked_at < cutoff,
        )
    )
    db.session.commit()
    count = result.rowcount  # type: ignore[attr-defined]
    _log.info(
        "cleaned up %s revoked sessions older than %s days", count, _RETENTION_DAYS
    )
    return count


@celery_app.task(name="vollbuild.core.tasks.session_tasks.update_last_seen")
def update_last_seen(user_id: int) -> None:
    """Update User.last_seen timestamp (fire-and-forget).

    Swallows exceptions so a DB error never propagates back to the caller.
    """
    try:
        from vollbuild.core.models.user import User

        User.query.filter(User.id == user_id).update(
            {"last_seen": datetime.now(timezone.utc)}
        )
        db.session.commit()
    except Exception:
        _log.debug("update_last_seen failed for user %s", user_id, exc_info=True)
        db.session.rollback()


@celery_app.task(name="vollbuild.core.tasks.session_tasks.update_session_activity")
def update_session_activity(session_id: int) -> None:
    """Update Session.last_active_at and Device.last_seen_at (fire-and-forget).

    Swallows exceptions so a DB error never propagates back to the caller.
    """
    try:
        session = db.session.get(Session, session_id)
        if session is not None:
            now = datetime.now(timezone.utc)
            session.last_active_at = now
            device = db.session.get(Device, session.device_id)
            if device is not None:
                device.last_seen_at = now
            db.session.commit()
    except Exception:
        _log.debug(
            "update_session_activity failed for session %s", session_id, exc_info=True
        )
        db.session.rollback()
