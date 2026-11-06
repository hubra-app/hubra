"""Queue a Celery task once the current transaction is committed.

A task queued inside the transaction can run before the commit (and see
nothing), or after a rollback (and send a mail for a change that never
happened). ``delay_after_commit`` holds it until the session commits and
drops it when the session rolls back.

It is also durable: just before the commit, each held task is written to the
contract outbox (``kind="job"``) in the same transaction. After the commit
the outbox hands it to a worker, which queues the real task. If Redis is
down at that moment the row stays and the outbox sweep queues it later, so
a mail or push for a committed change is never lost. A task whose arguments
aren't plain JSON, or one held while the final flush already runs, is
queued straight after the commit as before.
"""

from __future__ import annotations

import json
import logging

from flask import current_app
from sqlalchemy import event

from hubra.core.extensions import db

_log = logging.getLogger(__name__)
_KEY = "hubra_after_commit"


def delay_after_commit(task, *args, **kwargs) -> None:
    session = db.session()
    if not session.info.get(f"{_KEY}_listening"):
        event.listen(session, "before_commit", _persist)
        event.listen(session, "after_commit", _send)
        event.listen(session, "after_soft_rollback", _drop)
        session.info[f"{_KEY}_listening"] = True
    session.info.setdefault(_KEY, []).append((task, args, kwargs))


def _plain(args, kwargs) -> bool:
    try:
        json.dumps([list(args), kwargs])
    except (TypeError, ValueError):
        return False
    return True


def _persist(session) -> None:
    """Move the held tasks into the outbox, inside the committing transaction."""
    held = session.info.get(_KEY) or []
    if not held:
        return
    if held[0][0].app.conf.task_always_eager:
        # Tests (and installs without a broker) run tasks inline after the
        # commit; there is no broker to lose them.
        return
    from hubra.core.contracts import outbox

    left = []
    for task, args, kwargs in held:
        if not _plain(args, kwargs):
            left.append((task, args, kwargs))
            continue
        try:
            outbox.add_job(task.name, list(args), dict(kwargs))
        except Exception:
            if current_app.testing:
                raise
            _log.exception("could not store %s in the outbox", task.name)
            left.append((task, args, kwargs))
    session.info[_KEY] = left


def _send(session) -> None:
    for task, args, kwargs in session.info.pop(_KEY, None) or []:
        try:
            task.delay(*args, **kwargs)
        except Exception:
            # Tests run tasks eagerly; a broken task must fail them.
            if current_app.testing:
                raise
            # The commit is done; a broker outage must not look like it failed.
            _log.exception("could not queue %s after commit", task.name)


def _drop(session, previous_transaction) -> None:
    if not previous_transaction.nested:  # a savepoint leaves the rest alive
        session.info.pop(_KEY, None)
