"""The transactional outbox: store in the caller's transaction, deliver after.

``add`` writes a row next to the caller's own changes, so a rollback drops
the event with them and a commit keeps both. Once the transaction commits,
the transport sends each new row on its way. ``deliver`` runs one row in
the worker: it claims the row for a while (a lease), runs the handler and
marks it done, or schedules a retry. ``sweep`` (every minute) sends again
whatever is due: retries, rows whose worker died, rows the transport lost
because Redis was down at the commit.

Delivery is at least once. A handler whose work is only database writes
gets it once in effect (its writes and the done mark commit together
unless the handler commits itself); one that talks to an outside service
should use the ``event_id`` / ``ctx.message_id`` it gets to skip a repeat.
"""

from __future__ import annotations

import inspect
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update

from hubra.core.extensions import db
from hubra.core.models.contract_outbox import ContractMessage

from . import transport as transport_mod
from .base import ActionForbidden, ActionUnavailable, ContractError, Refused

_log = logging.getLogger(__name__)

# Seconds before attempt n+1 (after attempt n failed); then the row is dead.
RETRY_DELAYS = (30, 120, 600, 3600, 6 * 3600)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1
# A claimed row is left alone this long; a worker that died gives it back.
# contract_tasks.deliver is stopped before it runs out (its time limit).
LEASE = timedelta(minutes=5)
# A new row is published right after the commit; the sweep leaves it alone
# this long, so it only picks up rows the transport lost instead of sending
# a second copy of every row still waiting in the queue.
PUBLISH_GRACE = timedelta(minutes=2)
SWEEP_BATCH = 500
KEEP_DONE = timedelta(days=7)
KEEP_DEAD = timedelta(days=30)

_PENDING = "hubra.contract_outbox"
_COMMITTED = "hubra.contract_outbox_committed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def add(
    *, kind: str, name: str, module_code: str, target: str, tenant_id, env: dict
) -> str:
    """Store one delivery in the caller's transaction; returns its uid."""
    uid = str(uuid.uuid4())
    session = db.session()
    started = session.in_transaction()
    session.add(
        ContractMessage(
            uid=uid,
            message_id=env["id"],
            kind=kind,
            name=name,
            module_code=module_code,
            target=target,
            tenant_id=tenant_id,
            envelope=env,
            next_attempt_at=_now() + PUBLISH_GRACE,
        )
    )
    session.info.setdefault(_PENDING, []).append((uid, tenant_id))
    if not started:
        # Nobody else's work to wait for.
        session.commit()
    return uid


def add_job(task_name: str, args: list, kwargs: dict) -> str:
    """Store "queue Celery task *task_name*" in the caller's transaction
    (``tasks.after_commit.delay_after_commit``). Delivering the row queues
    the task, in the club the caller was in."""
    from hubra.core.tenant.context import current_tenant

    try:
        tenant = current_tenant()
    except RuntimeError:
        tenant = None
    tid = getattr(tenant, "id", None)
    env = transport_mod.envelope(
        kind="job",
        name=task_name,
        version=1,
        data={"args": args, "kwargs": kwargs},
        tenant_id=tid,
        source="core",
    )
    return add(
        kind="job",
        name=task_name[:120],
        module_code="core",
        target=task_name,
        tenant_id=tid,
        env=env,
    )


# ── After the commit ────────────────────────────────────────────────────────


def _after_commit(session) -> None:
    if session.info.get(_PENDING):
        session.info[_COMMITTED] = True


def _after_rollback(session) -> None:
    session.info.pop(_PENDING, None)
    session.info.pop(_COMMITTED, None)


def _after_transaction_end(session, transaction) -> None:
    if transaction.parent is not None or not session.info.pop(_COMMITTED, False):
        return
    pending = session.info.pop(_PENDING, [])
    send = transport_mod.transport()
    for uid, tid in pending:
        try:
            send.publish(uid, tid)
        except Exception:
            # Stored and committed: the sweep sends it.
            _log.exception("Couldn't hand outbox row %s to %s", uid, send.name)


def install() -> None:
    """Register the session hooks once per process (from the app factory)."""
    from sqlalchemy import event as sa_event

    for name, fn in (
        ("after_commit", _after_commit),
        ("after_rollback", _after_rollback),
        ("after_transaction_end", _after_transaction_end),
    ):
        if not sa_event.contains(db.session, name, fn):
            sa_event.listen(db.session, name, fn)


# ── Delivery ────────────────────────────────────────────────────────────────


class _Skip(Exception):
    """Nothing to do for this row (module off): done, not failed."""


_FINAL = (Refused, ActionForbidden, ContractError, ActionUnavailable)


def _claim(uid: str) -> bool:
    now = _now()
    result = db.session.execute(
        update(ContractMessage)
        .where(
            ContractMessage.uid == uid,
            ContractMessage.status == "pending",
            # Due, or never tried: a new row waits out PUBLISH_GRACE only
            # for the sweep, not for its own first delivery.
            (ContractMessage.next_attempt_at <= now) | (ContractMessage.attempts == 0),
        )
        .values(
            attempts=ContractMessage.attempts + 1,
            next_attempt_at=now + LEASE,
        )
        .execution_options(synchronize_session=False)
    )
    db.session.commit()
    return result.rowcount == 1


def _row(uid: str) -> ContractMessage | None:
    return db.session.scalar(select(ContractMessage).where(ContractMessage.uid == uid))


def deliver(uid: str) -> str:
    """Run outbox row *uid* once; returns its status afterwards."""
    if not _claim(uid):
        return "skipped"
    row = _row(uid)
    if row is None:
        return "skipped"
    kind, env = row.kind, dict(row.envelope)
    if env.get("hubrarequestid"):
        from flask import g

        # Log lines of the handler carry the id of the request that stored it.
        g.request_id = env["hubrarequestid"]
    module_code, target, name = row.module_code, row.target, row.name
    try:
        if kind == "event":
            _run_event(module_code, target, env)
        elif kind == "job":
            _run_job(target, env)
        else:
            _run_action(name, env)
    except _Skip as exc:
        db.session.rollback()
        return _finish(uid, "done", f"skipped: {exc}")
    except _FINAL as exc:
        db.session.rollback()
        _log.warning("Outbox %s %s for %s: %s", kind, name, module_code, exc)
        if isinstance(exc, ContractError):  # a bug, not an answer
            _alert_dead(kind, name, module_code, f"{type(exc).__name__}: {exc}")
        return _finish(uid, "dead", f"{type(exc).__name__}: {exc}")
    except Exception as exc:
        db.session.rollback()
        _log.exception("Outbox %s %s for %s failed", kind, name, module_code)
        return _retry(uid, f"{type(exc).__name__}: {exc}")
    return _finish(uid, "done", None)


def _finish(uid: str, status: str, error: str | None) -> str:
    row = _row(uid)
    if row is None:
        return status
    row.status = status
    row.last_error = error
    row.done_at = _now()
    db.session.commit()
    return status


def _retry(uid: str, error: str) -> str:
    row = _row(uid)
    if row is None:
        return "dead"
    row.last_error = error[:2000]
    if row.attempts >= MAX_ATTEMPTS:
        row.status = "dead"
        row.done_at = _now()
    else:
        row.next_attempt_at = _now() + timedelta(
            seconds=RETRY_DELAYS[min(row.attempts, len(RETRY_DELAYS)) - 1]
        )
    db.session.commit()
    if row.status == "dead":
        _alert_dead(row.kind, row.name, row.module_code, row.last_error)
    return row.status


def _alert_dead(kind: str, name: str, module_code: str, error: str | None) -> None:
    """A system alert when a delivery gave up after every retry, at most once
    an hour per contract and module (a broken handler kills many rows)."""
    try:
        from hubra.core.redis_client import get_redis_client

        client = get_redis_client()
        if client is not None and not client.set(
            f"hubra:outbox:dead-alert:{module_code}:{name}", "1", nx=True, ex=3600
        ):
            return
        from hubra.core.services.alerts import alert_warning

        alert_warning(
            title="Plugin delivery gave up",
            description=(
                f"The {kind} {name} for {module_code} failed {MAX_ATTEMPTS} times "
                "and is not retried any more. `flask contracts outbox --dead` "
                "lists the rows, `flask contracts retry <uid>` runs one again."
            ),
            fields=[{"name": "Last error", "value": (error or "")[:300]}],
        )
    except Exception:  # an alert must never break the delivery bookkeeping
        _log.debug("dead outbox row not alerted", exc_info=True)


def _accepts_event_id(fn) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return "event_id" in params


def _run_event(module_code: str, target: str, env: dict) -> None:
    from hubra.core.modules.events import _resolve
    from hubra.core.modules.state import is_enabled

    tid = env.get("tenantid")
    if not is_enabled(module_code, tenant_id=tid):
        raise _Skip(f"{module_code} is off")
    fn = _resolve(target)
    data = dict(env.get("data") or {})
    # The delivery id goes in as ``event_id`` only when the event's own data
    # has no ``event_id`` (club events do: the id of the ClubEvent, which
    # the handler needs).
    extra = (
        {"event_id": env["id"]}
        if "event_id" not in data and _accepts_event_id(fn)
        else {}
    )
    fn(tenant_id=tid, **data, **extra)
    db.session.commit()


def _run_job(task_name: str, env: dict) -> None:
    """Queue the Celery task; the row is done once the broker has it."""
    from hubra.core.tasks import celery_app

    task = celery_app.tasks.get(task_name)
    if task is None:
        raise ContractError(f"no task {task_name} in this process")
    data = env.get("data") or {}
    task.delay(*list(data.get("args") or []), **dict(data.get("kwargs") or {}))


def _run_action(name: str, env: dict) -> None:
    from . import calls

    calls.run_queued(name, env)
    db.session.commit()


# ── Sweep ───────────────────────────────────────────────────────────────────


def sweep() -> dict:
    """Send what is due again and forget what is long done."""
    now = _now()
    rows = db.session.execute(
        select(ContractMessage.uid, ContractMessage.tenant_id)
        .where(
            ContractMessage.status == "pending",
            ContractMessage.next_attempt_at <= now,
        )
        .order_by(ContractMessage.next_attempt_at)
        .limit(SWEEP_BATCH)
    ).all()
    db.session.commit()
    send = transport_mod.transport()
    sent = 0
    for uid, tid in rows:
        try:
            send.publish(uid, tid)
            sent += 1
        except Exception:
            _log.exception("Couldn't hand outbox row %s to %s", uid, send.name)
    pruned = db.session.execute(
        delete(ContractMessage)
        .where(
            (
                (ContractMessage.status == "done")
                & (ContractMessage.done_at < now - KEEP_DONE)
            )
            | (
                (ContractMessage.status == "dead")
                & (ContractMessage.done_at < now - KEEP_DEAD)
            )
        )
        .execution_options(synchronize_session=False)
    ).rowcount
    db.session.commit()
    return {"sent": sent, "pruned": pruned}


def replay(uid: str) -> bool:
    """Give a dead row another round of attempts (``flask contracts retry``)."""
    row = _row(uid)
    if row is None or row.status != "dead":
        return False
    row.status = "pending"
    row.attempts = 0
    row.next_attempt_at = _now()
    row.done_at = None
    db.session.commit()
    return True
