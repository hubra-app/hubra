"""delay_after_commit stores held tasks in the outbox when a broker runs them."""

from __future__ import annotations

from hubra.core.contracts import outbox
from hubra.core.contracts import transport as transport_mod
from hubra.core.extensions import db
from hubra.core.models.contract_outbox import ContractMessage
from hubra.core.tasks import after_commit, celery_app
from hubra.core.tasks.smoke import add


class _Lost:
    name = "lost"

    def __init__(self):
        self.sent = []

    def publish(self, uid, tenant_id):
        self.sent.append(uid)


def _jobs() -> int:
    return db.session.query(ContractMessage).filter_by(kind="job").count()


def _broker(monkeypatch):
    monkeypatch.setitem(celery_app.conf, "task_always_eager", False)
    lost = _Lost()
    transport_mod.set_transport(lost)
    return lost


def test_a_held_task_is_stored_with_the_commit_and_queued_on_delivery(app, monkeypatch):
    lost = _broker(monkeypatch)
    queued = []
    monkeypatch.setattr(add, "delay", lambda *a, **kw: queued.append((a, kw)))
    try:
        with app.app_context():
            after_commit.delay_after_commit(add, 1, y=2)
            db.session.commit()
            row = (
                db.session.query(ContractMessage)
                .filter_by(kind="job")
                .order_by(ContractMessage.id.desc())
                .first()
            )
            assert row.target == add.name and lost.sent == [row.uid]
            assert queued == []  # not queued straight away any more
            assert outbox.deliver(row.uid) == "done"
            assert queued == [((1,), {"y": 2})]
    finally:
        transport_mod.set_transport(None)


def test_a_rollback_stores_nothing(app, monkeypatch):
    _broker(monkeypatch)
    try:
        with app.app_context():
            before = _jobs()
            after_commit.delay_after_commit(add, 1, 2)
            db.session.rollback()
            db.session.commit()
            assert _jobs() == before
    finally:
        transport_mod.set_transport(None)


def test_arguments_that_are_not_json_go_straight_to_the_broker(app, monkeypatch):
    _broker(monkeypatch)
    queued = []
    monkeypatch.setattr(add, "delay", lambda *a, **kw: queued.append(a))
    marker = object()
    try:
        with app.app_context():
            before = _jobs()
            after_commit.delay_after_commit(add, marker, 2)
            db.session.commit()
            assert _jobs() == before
            assert queued == [(marker, 2)]
    finally:
        transport_mod.set_transport(None)
