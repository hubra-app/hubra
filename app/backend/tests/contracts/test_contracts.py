"""Contracts between modules: typed events, actions, queries, the outbox
(docs/contracts.md)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from hubra.core import contracts
from hubra.core.contracts import outbox
from hubra.core.contracts import registry as creg
from hubra.core.contracts import transport as transport_mod
from hubra.core.contracts.base import (
    SYSTEM,
    ActionFailed,
    ActionForbidden,
    ActionUnavailable,
    ContractError,
    Refused,
    action_contract,
    event_contract,
    query_contract,
)
from hubra.core.models.contract_outbox import ContractMessage
from hubra.core.models.plugin import PluginState
from hubra.core.modules import Module, registry
from hubra.core.modules import events as events_mod
from hubra.core.plugins.limits import LimitError, check
from hubra.core.plugins.spec import Spec

HERE = __name__
CALLS: list = []
FAIL = {"n": 0}


class ThingHappened(BaseModel):
    thing_id: int


class ItemsIn(BaseModel):
    ids: list[int]


class Item(BaseModel):
    id: int
    name: str


def on_thing(tenant_id, thing_id, event_id=None):
    if FAIL["n"] > 0:
        FAIL["n"] -= 1
        raise RuntimeError("down")
    CALLS.append(("thing", thing_id, event_id))


def on_thing_refused(tenant_id, thing_id):
    raise Refused("no")


def get_items(ctx, data: ItemsIn):
    # A query's writes never stay.
    from hubra.core.extensions import db

    db.session.merge(PluginState(key="query-wrote", value="1"))
    return [Item(id=i, name=f"item {i}") for i in data.ids]


def hand_out(ctx, data):
    from hubra.core.extensions import db

    CALLS.append(("hand_out", data["key_id"], ctx.system, ctx.message_id))
    db.session.merge(PluginState(key=f"key-{data['key_id']}", value="out"))
    if FAIL["n"] > 0:
        FAIL["n"] -= 1
        raise RuntimeError("lock offline")
    if data["key_id"] == 0:
        raise Refused("key 0 is lost", code="KEY_LOST")
    return {"ok": True}


PROVIDER = Module(
    code="demo",
    name="Demo",
    plugin="demo",
    provides=(
        event_contract("demo.thing.happened", ThingHappened),
        query_contract(
            "demo.items.get",
            f"{HERE}:get_items",
            input=ItemsIn,
            output=Item,
            perm="demo.items.read",
        ),
        action_contract(
            "demo.key.hand_out", f"{HERE}:hand_out", perm="demo.keys.update"
        ),
    ),
)
CONSUMER = Module(
    code="other",
    name="Other",
    plugin="other",
    events={"demo.thing.happened": f"{HERE}:on_thing"},
    consumes={"demo.items.get": ">=1,<2", "demo.thing.happened": ">=1"},
)


@pytest.fixture
def wired(app, db, monkeypatch):
    monkeypatch.setitem(registry._modules, "demo", PROVIDER)
    monkeypatch.setitem(registry._modules, "other", CONSUMER)
    monkeypatch.setattr(
        "hubra.core.modules.state.is_enabled", lambda code, tenant_id=None: True
    )
    monkeypatch.setattr(events_mod, "is_enabled", lambda code, tenant_id=None: True)
    CALLS.clear()
    FAIL["n"] = 0
    yield
    CALLS.clear()
    FAIL["n"] = 0


def _rows():
    from hubra.core.extensions import db

    return db.session.scalars(
        select(ContractMessage).order_by(ContractMessage.id)
    ).all()


def _due_now(db):
    for row in _rows():
        row.next_attempt_at = outbox._now() - timedelta(seconds=1)
    db.session.commit()


def as_plugin(package: str, source: str, **names):
    """Run *source* as code of plugin package *package* (the caller check
    looks at the calling module's name)."""
    scope = {"__name__": f"{package}.logic", "contracts": contracts, **names}
    exec(compile(source, f"<{package}>", "exec"), scope)
    return scope


# ── Events ──────────────────────────────────────────────────────────────────


def test_core_event_payloads_are_checked(wired):
    with pytest.raises(ContractError, match="invoice_id"):
        events_mod.emit("invoice.paid", tenant_id=None, invoice_id="not a number")


def test_a_plugin_cant_emit_an_event_nobody_declared(wired):
    with pytest.raises(ContractError, match="no module lists under provides"):
        as_plugin(
            "hubra_other",
            "contracts_emit('other.secret', tenant_id=None)",
            contracts_emit=events_mod.emit,
        )


def test_plugin_events_go_through_the_outbox(wired, db):
    db.session.merge(PluginState(key="x", value="1"))
    assert events_mod.emit("demo.thing.happened", tenant_id=None, thing_id=3) == [
        "other"
    ]
    assert CALLS == []  # waits for the commit
    db.session.commit()
    (row,) = _rows()
    assert row.status == "done" and row.attempts == 1
    assert row.envelope["type"] == "demo.thing.happened"
    assert row.envelope["specversion"] == "1.0"
    assert CALLS == [("thing", 3, row.message_id)]


def test_a_rollback_stores_nothing(wired, db):
    db.session.merge(PluginState(key="x", value="2"))
    events_mod.emit("demo.thing.happened", tenant_id=None, thing_id=4)
    db.session.rollback()
    assert _rows() == [] and CALLS == []


def test_a_failing_handler_is_retried_then_succeeds(wired, db):
    FAIL["n"] = 1
    events_mod.emit("demo.thing.happened", tenant_id=None, thing_id=5)
    (row,) = _rows()
    assert row.status == "pending" and row.attempts == 1
    assert "down" in row.last_error
    assert row.next_attempt_at.replace(tzinfo=None) > outbox._now().replace(tzinfo=None)
    assert outbox.sweep()["sent"] == 0  # not due yet
    _due_now(db)
    outbox.sweep()
    db.session.refresh(row)
    assert row.status == "done" and row.attempts == 2
    assert [c[1] for c in CALLS] == [5]


def test_a_handler_that_keeps_failing_ends_dead(wired, db, monkeypatch):
    from hubra.core.services import alerts

    sent = []
    monkeypatch.setattr(alerts, "alert_warning", lambda **kw: sent.append(kw))
    FAIL["n"] = 100
    events_mod.emit("demo.thing.happened", tenant_id=None, thing_id=6)
    for _ in range(outbox.MAX_ATTEMPTS):
        _due_now(db)
        outbox.sweep()
    (row,) = _rows()
    assert row.status == "dead" and row.attempts == outbox.MAX_ATTEMPTS
    assert len(sent) == 1 and "demo.thing.happened" in sent[0]["description"]
    assert outbox.replay(row.uid)
    FAIL["n"] = 0
    outbox.sweep()
    db.session.refresh(row)
    assert row.status == "done"


def test_a_refusal_is_not_retried(wired, db, monkeypatch):
    mod = Module(
        code="other",
        name="O",
        plugin="other",
        events={"demo.thing.happened": f"{HERE}:on_thing_refused"},
    )
    monkeypatch.setitem(registry._modules, "other", mod)
    events_mod.emit("demo.thing.happened", tenant_id=None, thing_id=7)
    (row,) = _rows()
    assert row.status == "dead" and row.attempts == 1


def test_lost_by_the_transport_the_sweep_sends_it(wired, db):
    class Down:
        name = "down"

        def publish(self, uid, tenant_id):
            raise ConnectionError("redis down")

    transport_mod.set_transport(Down())
    try:
        events_mod.emit("demo.thing.happened", tenant_id=None, thing_id=8)
    finally:
        transport_mod.set_transport(None)
    (row,) = _rows()
    assert row.status == "pending" and row.attempts == 0 and CALLS == []
    # Within the grace period the sweep leaves it alone: its own delivery
    # may still be waiting in the queue.
    outbox.sweep()
    db.session.refresh(row)
    assert row.status == "pending" and CALLS == []
    _due_now(db)
    outbox.sweep()
    db.session.refresh(row)
    assert row.status == "done" and CALLS[0][1] == 8


def test_a_new_row_is_delivered_at_once_but_swept_only_after_the_grace(wired, db):
    class Lost:
        name = "lost"
        sent: list = []

        def publish(self, uid, tenant_id):
            self.sent.append(uid)

    transport_mod.set_transport(Lost())
    try:
        events_mod.emit("demo.thing.happened", tenant_id=None, thing_id=11)
        (row,) = _rows()
        assert row.next_attempt_at.replace(tzinfo=None) > outbox._now().replace(
            tzinfo=None
        )
        assert outbox.sweep()["sent"] == 0  # not a second copy
        assert outbox.deliver(row.uid) == "done"  # the first one still runs
    finally:
        transport_mod.set_transport(None)
    assert CALLS[-1][1] == 11


def test_deliver_stops_inside_the_lease():
    from hubra.core.tasks import contract_tasks

    lease = outbox.LEASE.total_seconds()
    assert contract_tasks.deliver.soft_time_limit < contract_tasks.deliver.time_limit
    assert contract_tasks.deliver.time_limit < lease


def test_a_consumer_wanting_another_version_isnt_called(wired, db, monkeypatch):
    mod = Module(
        code="other",
        name="O",
        plugin="other",
        events={"demo.thing.happened": f"{HERE}:on_thing"},
        consumes={"demo.thing.happened": ">=2"},
    )
    monkeypatch.setitem(registry._modules, "other", mod)
    assert events_mod.emit("demo.thing.happened", tenant_id=None, thing_id=9) == []
    assert _rows() == []


def test_a_claimed_row_runs_once(wired, db):
    db.session.merge(PluginState(key="x", value="3"))
    events_mod.emit("demo.thing.happened", tenant_id=None, thing_id=10)
    db.session.commit()
    (row,) = _rows()
    assert outbox.deliver(row.uid) == "skipped"  # done already
    assert len(CALLS) == 1


# ── Queries and actions ─────────────────────────────────────────────────────


def test_query_returns_checked_plain_values_and_never_writes(wired, db):
    out = contracts.query("demo.items.get", ids=[3, 7], actor=SYSTEM)
    assert out == [{"id": 3, "name": "item 3"}, {"id": 7, "name": "item 7"}]
    assert db.session.get(PluginState, "query-wrote") is None


def test_query_input_is_checked(wired):
    with pytest.raises(ContractError, match="ids"):
        contracts.query("demo.items.get", ids="three", actor=SYSTEM)


def test_permission_is_checked_for_the_acting_member(wired):
    with pytest.raises(ActionForbidden, match="demo.items.read"):
        contracts.query("demo.items.get", ids=[1], actor=None)


def test_unknown_or_off_is_unavailable(wired, monkeypatch):
    with pytest.raises(ActionUnavailable):
        contracts.call("nobody.does.this", actor=SYSTEM)
    monkeypatch.setattr(
        "hubra.core.modules.state.is_enabled", lambda code, tenant_id=None: False
    )
    with pytest.raises(ActionUnavailable, match="off"):
        contracts.query("demo.items.get", ids=[1], actor=SYSTEM)
    assert contracts.available("demo.items.get") is False


def test_a_failing_action_rolls_back_only_its_own_work(wired, db):
    db.session.merge(PluginState(key="caller", value="mine"))
    FAIL["n"] = 1
    with pytest.raises(ActionFailed):
        contracts.call("demo.key.hand_out", key_id=4, actor=SYSTEM)
    db.session.commit()
    assert db.session.get(PluginState, "caller").value == "mine"
    assert db.session.get(PluginState, "key-4") is None


def test_a_refusal_reaches_the_caller_with_its_code(wired):
    with pytest.raises(Refused) as exc:
        contracts.call("demo.key.hand_out", key_id=0, actor=SYSTEM)
    assert exc.value.code == "KEY_LOST"


def test_plugins_may_only_use_what_they_declare(wired, monkeypatch):
    src = "result = contracts.query('demo.items.get', ids=[1], actor=contracts.SYSTEM)"
    # "other" lists demo.items.get under consumes.
    assert as_plugin("hubra_other", src)["result"] == [{"id": 1, "name": "item 1"}]
    # "third" doesn't.
    third = Module(code="third", name="T", plugin="third")
    monkeypatch.setitem(registry._modules, "third", third)
    with pytest.raises(ContractError, match="without listing it under consumes"):
        as_plugin("hubra_third", src)
    # A range the offer doesn't meet.
    monkeypatch.setitem(
        registry._modules,
        "third",
        Module(
            code="third", name="T", plugin="third", consumes={"demo.items.get": ">=2"}
        ),
    )
    with pytest.raises(ActionUnavailable, match="needs >=2"):
        as_plugin("hubra_third", src)
    assert (
        as_plugin("hubra_third", "ok = contracts.available('demo.items.get')")["ok"]
        is False
    )


def test_send_runs_the_action_after_the_commit_with_retries(wired, db):
    db.session.merge(PluginState(key="x", value="4"))
    FAIL["n"] = 1
    message_id = contracts.send("demo.key.hand_out", key_id=5, actor=SYSTEM)
    assert CALLS == []
    db.session.commit()
    (row,) = _rows()
    assert row.kind == "action" and row.status == "pending" and row.attempts == 1
    _due_now(db)
    outbox.sweep()
    db.session.refresh(row)
    assert row.status == "done"
    # The same message id on each try, so a handler can do the work once.
    assert [c[3] for c in CALLS] == [message_id, message_id]
    assert db.session.get(PluginState, "key-5").value == "out"


def test_send_needs_plain_values(wired):
    with pytest.raises(ContractError, match="plain values"):
        contracts.send("demo.key.hand_out", key_id=object(), actor=SYSTEM)


def test_contract_list_shows_schemas(wired):
    offer = creg.get("demo.items.get")
    d = offer.to_dict()
    assert d["kind"] == "query" and d["plugin"] == "demo"
    assert d["input"]["properties"]["ids"]["type"] == "array"


# ── Loader limits ───────────────────────────────────────────────────────────


def _spec(tmp_path: Path, **manifest) -> Spec:
    m = {"id": "demo", "name": "Demo", "version": "1.0.0", "package": "hubra_demo"}
    m.update(manifest)
    return Spec(
        id="demo",
        path=tmp_path,
        manifest=m,
        trust={"status": "community", "signer": "", "key_id": "", "detail": ""},
    )


def test_limits_contract_names_and_code(tmp_path):
    ok = Module(
        code="demo",
        name="D",
        provides=(query_contract("demo.items.get", "hubra_demo.queries:get"),),
        consumes={"inventory.items.get": ">=1,<2"},
    )
    assert check(ok, _spec(tmp_path), {}, set()) is not None
    for bad, msg in (
        (query_contract("inventory.items.get", "hubra_demo.q:get"), "named"),
        (query_contract("demo.items.get", "hubra_inventory.q:get"), "outside"),
        (event_contract("demo.x", "hubra_inventory.schemas:X"), "outside"),
        (event_contract("demo.x", Item), "outside"),
    ):
        with pytest.raises(LimitError, match=msg):
            check(
                Module(code="demo", name="D", provides=(bad,)),
                _spec(tmp_path),
                {},
                set(),
            )
    with pytest.raises(LimitError, match="range"):
        check(
            Module(code="demo", name="D", consumes={"a.b": "lots"}),
            _spec(tmp_path),
            {},
            set(),
        )


def test_limits_contracts_need_the_area(tmp_path):
    mod = Module(code="demo", name="D", consumes={"inventory.items.get": ">=1"})
    with pytest.raises(LimitError, match="contracts"):
        check(mod, _spec(tmp_path, uses=["routes"]), {}, set())
    assert check(mod, _spec(tmp_path, uses=["contracts"]), {}, set())


# ── In a club's schema (Postgres) ───────────────────────────────────────────


def test_club_events_land_in_the_public_outbox_and_run_in_the_club(
    wired, db, seeded_db
):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("club schemas need Postgres")
    from sqlalchemy import text

    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.context import in_club
    from hubra.core.tenant.schema_manager import (
        create_tenant_schema,
        drop_tenant_schema,
    )

    db.session.execute(
        text(
            "CREATE TABLE IF NOT EXISTS public.alembic_version"
            " (version_num varchar(32) PRIMARY KEY)"
        )
    )
    club = Tenant(name="Outbox", slug="outbox-club", status="active")
    db.session.add(club)
    db.session.commit()
    create_tenant_schema(club.id)
    db.session.commit()
    seen = []

    def record(tenant_id, thing_id, event_id=None):
        path = db.session.execute(text("SHOW search_path")).scalar()
        seen.append((tenant_id, thing_id, path))

    import sys

    sys.modules[HERE].record_in_club = record
    mod = Module(
        code="other",
        name="O",
        plugin="other",
        events={"demo.thing.happened": f"{HERE}:record_in_club"},
    )
    registry._modules["other"] = mod
    try:
        with in_club(club):
            db.session.execute(text("SELECT 1"))
            events_mod.emit("demo.thing.happened", thing_id=11)
            db.session.commit()
        (row,) = _rows()
        assert row.tenant_id == club.id and row.status == "done"
        assert seen[0][:2] == (club.id, 11)
        assert f"tenant_{club.id}" in seen[0][2]
        # Nothing landed in the club's schema.
        assert (
            db.session.execute(
                text("SELECT to_regclass(:t)"),
                {"t": f"tenant_{club.id}.contract_outbox"},
            ).scalar()
            is None
        )
    finally:
        db.session.rollback()
        drop_tenant_schema(club.id)
        db.session.commit()
