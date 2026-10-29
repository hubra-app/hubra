"""Queue a Celery task once the current transaction is committed.

A task queued inside the transaction can run before the commit (and see
nothing), or after a rollback (and send a mail for a change that never
happened). ``delay_after_commit`` holds it until the session commits and
drops it when the session rolls back.
"""

from __future__ import annotations

import logging

from sqlalchemy import event

from hubra.core.extensions import db

_log = logging.getLogger(__name__)
_KEY = "hubra_after_commit"


def delay_after_commit(task, *args, **kwargs) -> None:
    session = db.session()
    if not session.info.get(f"{_KEY}_listening"):
        event.listen(session, "after_commit", _send)
        event.listen(session, "after_soft_rollback", _drop)
        session.info[f"{_KEY}_listening"] = True
    session.info.setdefault(_KEY, []).append((task, args, kwargs))


def _send(session) -> None:
    for task, args, kwargs in session.info.pop(_KEY, None) or []:
        try:
            task.delay(*args, **kwargs)
        except Exception:
            # The commit is done; a broker outage must not look like it failed.
            _log.exception("could not queue %s after commit", task.name)


def _drop(session, previous_transaction) -> None:
    if not previous_transaction.nested:  # a savepoint leaves the rest alive
        session.info.pop(_KEY, None)
