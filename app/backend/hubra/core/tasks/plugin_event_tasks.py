"""Delivering domain events to plugin handlers after the commit.

``hubra.core.modules.events.emit`` queues one :func:`deliver_event` per
plugin handler once the transaction that emitted the event has committed.
The task runs in the club of the event (the ``tenant_id`` header), on the
default queue, so it is club work, never platform work.
"""

from __future__ import annotations

import logging

from hubra.core.extensions import db
from hubra.core.tasks import celery_app

_log = logging.getLogger(__name__)


@celery_app.task(
    name="hubra.core.tasks.plugin_event_tasks.deliver_event",
    ignore_result=True,
)
def deliver_event(event: str, module_code: str, target: str, tenant_id, payload: dict):
    from hubra.core.modules.events import _resolve
    from hubra.core.modules.state import is_enabled

    if not is_enabled(module_code, tenant_id=tenant_id):
        return False
    try:
        _resolve(target)(tenant_id=tenant_id, **payload)
        db.session.commit()
    except Exception:
        db.session.rollback()
        _log.exception("Handler %s for %s failed", target, event)
        return False
    return True
