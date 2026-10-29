"""Session-related Celery tasks — cleanup, last_seen, session activity."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from hubra.core.extensions import db
from hubra.core.models.device_session import Device, Session
from hubra.core.tasks import celery_app

_log = logging.getLogger(__name__)

_RETENTION_DAYS = 90


@celery_app.task(name="hubra.core.tasks.session_tasks.cleanup_revoked_sessions")
def cleanup_revoked_sessions() -> int:
    """Delete Session rows that were revoked more than _RETENTION_DAYS ago,
    in the public schema and in every club's (club sign-ins are recorded
    in the club schema).

    Device rows are kept — they persist so the device history is retained.
    Returns the number of rows deleted.
    """
    from sqlalchemy import select

    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.context import reset_search_path, set_search_path

    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)

    def _clean() -> int:
        result = db.session.execute(
            delete(Session).where(
                Session.revoked_at.is_not(None),
                Session.revoked_at < cutoff,
            )
        )
        db.session.commit()
        return result.rowcount  # type: ignore[attr-defined]

    count = _clean()
    for tenant_id in db.session.scalars(select(Tenant.id)).all():
        try:
            set_search_path(tenant_id)
            count += _clean()
        except Exception:
            db.session.rollback()
            _log.exception("session cleanup failed for tenant %s", tenant_id)
        finally:
            reset_search_path()
    _log.info(
        "cleaned up %s revoked sessions older than %s days", count, _RETENTION_DAYS
    )
    return count


@celery_app.task(name="hubra.core.tasks.session_tasks.update_last_seen")
def update_last_seen(user_id: int) -> None:
    """Update User.last_seen timestamp (fire-and-forget).

    Swallows exceptions so a DB error never propagates back to the caller.
    """
    try:
        from hubra.core.models.user import User

        User.query.filter(User.id == user_id).update(
            {"last_seen": datetime.now(timezone.utc)}
        )
        db.session.commit()
    except Exception:
        _log.debug("update_last_seen failed for user %s", user_id, exc_info=True)
        db.session.rollback()


@celery_app.task(name="hubra.core.tasks.session_tasks.update_session_activity")
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
