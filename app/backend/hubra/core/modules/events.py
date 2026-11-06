"""In-process event bus between modules.

A module subscribes in its manifest::

    events={"invoice.overdue": "hubra_keys.hooks:on_invoice_overdue"}

``emit("invoice.overdue", member_id=..., invoice_id=...)`` then calls every
subscriber whose module is enabled for the tenant, with ``tenant_id`` and
the payload as keyword arguments.  A failing handler is logged and does
not stop the others or the caller.

Hubra's own modules' handlers run synchronously in the caller's
transaction. A plugin's handlers get the event from the contract outbox
(``hubra.core.contracts.outbox``): one row per handler, written in the
caller's transaction and delivered by the worker after it commits, retried
when the handler fails. So a slow or failing plugin can't hold up or roll
back the caller's work, nothing reaches a plugin for a change that was
rolled back, and an event isn't lost when Redis is down at the commit. An
official plugin can ask for in-transaction delivery of named events
(``Module.events_in_transaction``).

Every event is a contract (``hubra.core.contracts``): Hubra's own are in
``contracts.core_events``, a plugin's in its ``Module.provides``. The
payload is checked against the contract's schema before anyone hears of
it. Payloads are ids and plain values, so they can travel to the worker
(and, later, through a message broker).
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
# An invoice was created (invoice_id, category_id = the transaction category
# the form picked, or None), changed (invoice_id, was_paid, changed = the
# fields set) or deleted (invoice_id, transaction_id = its linked booking).
INVOICE_CREATED = "invoice.created"
INVOICE_UPDATED = "invoice.updated"
INVOICE_DELETED = "invoice.deleted"
EVENT_PUBLISHED = "event.published"
POST_PUBLISHED = "post.published"
POLL_PUBLISHED = "poll.published"
# An event was changed or deleted (event_id; deleted=True when it is gone).
# A series change sends one per date.
EVENT_CHANGED = "event.changed"
# Someone signed up for an event, cancelled, or was approved or declined
# (event_id).  Places taken changed; nothing else about the event did.
EVENT_SIGNUPS_CHANGED = "event.signups_changed"
# Sent once when the reminder before an event / before a poll closes is due.
EVENT_REMINDER = "event.reminder"
POLL_CLOSING = "poll.closing"
# An organiser closed a poll early (poll_id).  A poll that closes on its
# own at closes_at sends nothing: whoever cares checks closes_at.
POLL_CLOSED = "poll.closed"
GROUP_MEMBERSHIP_CHANGED = "group.membership_changed"
# A person linked or unlinked an outside account (provider, external_id),
# emitted in each club they are a member of (member_id).
ACCOUNT_LINKED = "account.linked"
ACCOUNT_UNLINKED = "account.unlinked"
# A member joined (accepted an invite or an application) or left (left,
# archived or deleted).
MEMBER_JOINED = "member.joined"
MEMBER_LEFT = "member.left"
# A new Hubra version / a new version of a plugin runs, with its changelog
# section (services.changelogs). Once per version; a plugin's only in the
# clubs that have that plugin on.
HUBRA_RELEASED = "hubra.released"
PLUGIN_RELEASED = "plugin.released"


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

    from hubra.core.contracts import outbox
    from hubra.core.extensions import db

    outbox.install()

    for name, fn in (
        ("after_commit", _after_commit),
        ("after_rollback", _after_rollback),
        ("after_transaction_end", _after_transaction_end),
    ):
        if not sa_event.contains(db.session, name, fn):
            sa_event.listen(db.session, name, fn)


def _defer(module, event: str) -> bool:
    return bool(module.plugin) and event not in module.events_in_transaction


def _check_contract(event: str, payload: dict):
    """The event's contract, after checking *payload* against it (None for a
    name no contract declares: allowed for Hubra's own code, refused for a
    plugin's)."""
    from hubra.core.contracts import registry as contracts
    from hubra.core.contracts.base import EVENT, ContractError

    offer = contracts.get(event)
    if offer is None:
        plugin = contracts.plugin_of(contracts.caller_module())
        if plugin is not None:
            raise ContractError(
                f"{plugin} emits {event}, which no module lists under provides"
            )
        _log.debug("Event %s has no contract", event)
        return None
    if offer.contract.kind != EVENT:
        raise ContractError(f"{event} is an {offer.contract.kind}, not an event")
    contracts.check_input(offer.contract, payload, portable=True)
    return offer


def _wants(module, offer) -> bool:
    """Whether a plugin's handler takes this version of the event."""
    from hubra.core.contracts import registry as contracts

    if offer is None or not module.plugin:
        return True
    rng = module.consumes.get(offer.contract.name)
    if contracts.accepts(rng, offer.contract.version):
        return True
    _log.warning(
        "%s wants %s %s; this is version %s: not delivered",
        module.code,
        offer.contract.name,
        rng,
        offer.contract.version,
    )
    return False


def _to_outbox(event, module, target, tid, env) -> bool:
    from hubra.core.contracts import outbox

    try:
        outbox.add(
            kind="event",
            name=event,
            module_code=module.code,
            target=target,
            tenant_id=tid,
            env=env,
        )
        return True
    except Exception:
        _log.exception("Couldn't store %s for %s", event, target)
        return False


def emit(event: str, tenant_id=CURRENT, **payload: Any) -> list[str]:
    """Deliver *event* to enabled subscribers.  Returns the module codes called
    (or, for a plugin's handler, stored for after the commit)."""
    from hubra.core.contracts import registry as contracts
    from hubra.core.contracts.transport import envelope

    registry.load()
    offer = _check_contract(event, payload)
    tid = _resolve_tenant_id(tenant_id)
    called: list[str] = []
    env = None
    for module, target in registry.subscribers(event):
        if not is_enabled(module.code, tenant_id=tid):
            continue
        if _defer(module, event):
            if not _wants(module, offer):
                continue
            if env is None:
                # One envelope (one id) for every handler of this event.
                env = envelope(
                    kind="event",
                    name=event,
                    version=offer.contract.version if offer else 1,
                    data=dict(payload),
                    tenant_id=tid,
                    source=contracts.plugin_of(contracts.caller_module())
                    or (offer.module_code if offer else "hubra"),
                )
            if _to_outbox(event, module, target, tid, env):
                called.append(module.code)
            continue
        try:
            _resolve(target)(tenant_id=tid, **payload)
            called.append(module.code)
        except Exception:
            _log.exception("Handler %s for %s failed", target, event)
    if _webhooks_listening(event, tid):
        item = (
            event,
            "webhooks",
            _WEBHOOK_TARGET,
            tid,
            {"event": event, "data": dict(payload)},
        )
        if _after_commit_or_now(item):
            called.append("webhooks")
    return called


def _after_commit_or_now(item: tuple) -> bool:
    """Queue *item* for after the caller's commit (or now, outside one)."""
    try:
        session = _session()
        if session.in_transaction():
            session.info.setdefault(_PENDING, []).append(item)
        else:
            _queue(item)
        return True
    except Exception:
        _log.exception("Couldn't queue %s for %s", item[2], item[0])
        return False


# The club's outgoing webhooks (hubra.core.webhooks) hear the events they
# list, after the commit, in the worker, like a plugin's handler.
_WEBHOOK_TARGET = "hubra.core.webhooks:dispatch"


def _webhooks_listening(event: str, tid) -> bool:
    from hubra.core.webhooks import EVENTS

    if event not in EVENTS:
        return False
    try:
        if not is_enabled("webhooks", tenant_id=tid):
            return False
        from sqlalchemy import select

        from hubra.core.models.webhook import Webhook

        session = _session()
        # A savepoint: a failing look-up must not abort the caller's work.
        with session.begin_nested():
            found = session.scalar(
                select(Webhook.id).where(Webhook.active.is_(True)).limit(1)
            )
        return found is not None
    except Exception:
        _log.exception("Couldn't check the webhooks for %s", event)
        return False
