"""In-process event bus between modules.

A module subscribes in its manifest::

    events={"invoice.overdue": "hubra_keys.hooks:on_invoice_overdue"}

``emit("invoice.overdue", member_id=..., invoice_id=...)`` then calls every
subscriber whose module is enabled for the tenant, with ``tenant_id`` and
the payload as keyword arguments.  A failing handler is logged and does
not stop the others or the caller.

Hubra's own modules' handlers run synchronously in the caller's
transaction. A plugin's handlers run after that transaction commits, in
the worker (``hubra.core.tasks.plugin_event_tasks``), so a slow or failing
plugin can't hold up or roll back the caller's work, and nothing reaches
a plugin for a change that was rolled back. An official plugin can ask for
in-transaction delivery of named events (``Module.events_in_transaction``).
Payloads are ids and plain values, so they can travel to the worker.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from .registry import registry
from .state import CURRENT, _resolve_tenant_id, is_enabled

_log = logging.getLogger(__name__)

# Event names in use, so emitters and subscribers agree on spelling.
INVOICE_OVERDUE = "invoice.overdue"
INVOICE_PAID = "invoice.paid"
EVENT_PUBLISHED = "event.published"
POST_PUBLISHED = "post.published"
POLL_PUBLISHED = "poll.published"
# An event was changed or deleted (event_id; deleted=True when it is gone).
# A series change sends one per date.
EVENT_CHANGED = "event.changed"
# Sent once when the reminder before an event / before a poll closes is due.
EVENT_REMINDER = "event.reminder"
POLL_CLOSING = "poll.closing"
GROUP_MEMBERSHIP_CHANGED = "group.membership_changed"
# A person linked or unlinked an outside account (provider, external_id),
# emitted in each club they are a member of (member_id).
ACCOUNT_LINKED = "account.linked"
ACCOUNT_UNLINKED = "account.unlinked"


def _resolve(target: str):
    module_path, _, attr = target.partition(":")
    return getattr(importlib.import_module(module_path), attr)


_PENDING = "hubra.plugin_events"
_COMMITTED = "hubra.plugin_events_committed"


def _session():
    from hubra.core.extensions import db

    return db.session()


def _queue(item: tuple) -> None:
    from hubra.core.tasks.plugin_event_tasks import deliver_event

    event, code, target, tid, payload = item
    args = (event, code, target, tid, payload)
    if deliver_event.app.conf.task_always_eager:
        # Tests (and installs without a broker): run it here, in this app
        # context and session, as the worker would run it after the commit.
        _run_here(deliver_event, tid, args)
        return
    headers = {"tenant_id": tid} if tid is not None else {}
    deliver_event.apply_async(args=args, headers=headers)


def _run_here(task, tid, args) -> None:
    from hubra.core.tenant.context import current_tenant, in_club

    try:
        here = current_tenant()
    except RuntimeError:
        here = None
    if tid is None or (here is not None and here.id == tid):
        task.run(*args)
        return
    from hubra.core.extensions import db
    from hubra.core.models.tenant import Tenant

    tenant = db.session.get(Tenant, tid)
    if tenant is None:
        return
    with in_club(tenant):
        task.run(*args)


def _after_commit(session) -> None:
    if session.info.get(_PENDING):
        session.info[_COMMITTED] = True


def _after_rollback(session) -> None:
    session.info.pop(_PENDING, None)
    session.info.pop(_COMMITTED, None)


def _after_transaction_end(session, transaction) -> None:
    # The outer transaction only; SQL works again here, so a task Celery
    # runs eagerly (tests) can use the session.
    if transaction.parent is not None or not session.info.pop(_COMMITTED, False):
        return
    pending = session.info.pop(_PENDING, [])
    for item in pending:
        try:
            _queue(item)
        except Exception:
            _log.exception("Couldn't queue %s for %s", item[2], item[0])


def install_after_commit_delivery() -> None:
    """Register the session hooks once per process (from the app factory)."""
    from sqlalchemy import event as sa_event

    from hubra.core.extensions import db

    for name, fn in (
        ("after_commit", _after_commit),
        ("after_rollback", _after_rollback),
        ("after_transaction_end", _after_transaction_end),
    ):
        if not sa_event.contains(db.session, name, fn):
            sa_event.listen(db.session, name, fn)


def _defer(module, event: str) -> bool:
    return bool(module.plugin) and event not in module.events_in_transaction


def emit(event: str, tenant_id=CURRENT, **payload: Any) -> list[str]:
    """Deliver *event* to enabled subscribers.  Returns the module codes called
    (or, for a plugin's handler, queued for after the commit)."""
    registry.load()
    tid = _resolve_tenant_id(tenant_id)
    called: list[str] = []
    for module, target in registry.subscribers(event):
        if not is_enabled(module.code, tenant_id=tid):
            continue
        if _defer(module, event):
            item = (event, module.code, target, tid, dict(payload))
            try:
                session = _session()
                if session.in_transaction():
                    session.info.setdefault(_PENDING, []).append(item)
                else:
                    _queue(item)
                called.append(module.code)
            except Exception:
                _log.exception("Couldn't queue %s for %s", target, event)
            continue
        try:
            _resolve(target)(tenant_id=tid, **payload)
            called.append(module.code)
        except Exception:
            _log.exception("Handler %s for %s failed", target, event)
    return called
