"""Envelopes and the transport that carries them from the outbox to a worker.

Every queued event or action is stored as an envelope shaped like a
CloudEvents 1.0 event (``specversion``, ``id``, ``source``, ``type``,
``time``, ``data``), with the club in ``tenantid`` and the contract's major
version in ``dataversion``. A broker (NATS, Kafka, RabbitMQ) carries that
shape unchanged, so swapping the transport needs no change to emitters,
handlers or stored rows.

Today the only transport is Celery over Redis: after the commit it queues
``contract_tasks.deliver`` per outbox row. A broker transport would
implement :class:`Transport` the same way (publish after the commit; the
outbox sweep keeps retrying what didn't go out) and be picked in
:func:`transport`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol

SPEC_VERSION = "1.0"


def envelope(
    *,
    kind: str,
    name: str,
    version: int,
    data: dict,
    tenant_id: int | None,
    source: str,
    actor: dict | None = None,
    message_id: str | None = None,
) -> dict:
    """A CloudEvents-shaped envelope; plain JSON values only."""
    env = {
        "specversion": SPEC_VERSION,
        "id": message_id or str(uuid.uuid4()),
        "source": f"hubra/{source}",
        "type": name,
        "time": datetime.now(timezone.utc).isoformat(),
        "datacontenttype": "application/json",
        "dataversion": version,
        "hubrakind": kind,
        "tenantid": tenant_id,
        "data": data,
    }
    if actor is not None:
        env["hubraactor"] = actor
    from hubra.core import request_id

    rid = request_id.current()
    if rid:
        # The request (or task) that stored it, for following one change
        # through the logs of every worker that handles it.
        env["hubrarequestid"] = rid
    return env


class Transport(Protocol):
    """Hands committed outbox rows to whoever delivers them."""

    name: str

    def publish(self, uid: str, tenant_id: int | None) -> None:
        """Send outbox row *uid* on its way. May raise; the sweep retries."""


class CeleryTransport:
    name = "celery"

    def publish(self, uid: str, tenant_id: int | None) -> None:
        from hubra.core.tasks.contract_tasks import deliver

        if deliver.app.conf.task_always_eager:
            # Tests (and installs without a broker): run it here, in this
            # app context, as the worker would after the commit.
            _run_here(deliver, tenant_id, (uid,))
            return
        headers = {"tenant_id": tenant_id} if tenant_id is not None else {}
        deliver.apply_async(args=(uid,), headers=headers)


def _run_here(task, tid, args) -> None:
    from hubra.core.extensions import db
    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.context import current_tenant, in_club

    try:
        here = current_tenant()
    except RuntimeError:
        here = None
    if tid is None or (here is not None and here.id == tid):
        task.run(*args)
        return
    tenant = db.session.get(Tenant, tid)
    if tenant is None:
        return
    with in_club(tenant):
        task.run(*args)


_TRANSPORT: Transport | None = None


def transport() -> Transport:
    """The transport in use. One place to plug in a broker later."""
    global _TRANSPORT
    if _TRANSPORT is None:
        _TRANSPORT = CeleryTransport()
    return _TRANSPORT


def set_transport(value: Transport | None) -> None:
    """Swap the transport (tests; a broker transport at start-up)."""
    global _TRANSPORT
    _TRANSPORT = value
