"""Using another module's actions and queries (docs/contracts.md)."""

from __future__ import annotations

import importlib
import logging
from typing import Any

from hubra.core.extensions import db

from . import registry as reg
from .base import (
    ACTION,
    QUERY,
    SYSTEM,
    ActionFailed,
    ActionForbidden,
    ActionUnavailable,
    CallContext,
    ContractError,
    Refused,
)

_log = logging.getLogger(__name__)


class _Current:
    def __repr__(self) -> str:
        return "CURRENT"


# The member of the current request (the default actor).
CURRENT = _Current()


def _resolve(target: str):
    path, _, attr = target.partition(":")
    return getattr(importlib.import_module(path), attr)


def _tenant_id():
    from hubra.core.tenant.context import current_tenant

    try:
        tenant = current_tenant()
    except RuntimeError:
        tenant = None
    return tenant.id if tenant is not None else None


def _offer(name: str, kind: str, caller: str) -> reg.Offer:
    """The offer *caller* may use, or the reason it can't."""
    offer = reg.get(name)
    if offer is not None and offer.contract.kind != kind:
        raise ContractError(f"{name} is an {offer.contract.kind}, not an {kind}")
    plugin = reg.plugin_of(caller)
    rng = None
    if plugin is not None:
        declared, rng = reg.consumer_range(plugin, name)
        if not declared:
            raise ContractError(
                f"{plugin} uses {name} without listing it under consumes"
            )
    if offer is None:
        raise ActionUnavailable(f"nothing offers {name} here")
    if not reg.accepts(rng, offer.contract.version):
        raise ActionUnavailable(
            f"{name} is version {offer.contract.version} here; {plugin} needs {rng}"
        )
    return offer


def _check_on(offer: reg.Offer, tenant_id) -> None:
    from hubra.core.modules.state import is_enabled

    if offer.module_code != "core" and not is_enabled(
        offer.module_code, tenant_id=tenant_id
    ):
        raise ActionUnavailable(f"{offer.module_code} is off for this club")


def _actor(actor):
    """(member, system) for an ``actor`` argument."""
    if actor is SYSTEM:
        return None, True
    if actor is CURRENT:
        from hubra.core.permissions import _current_member

        try:
            return _current_member(), False
        except RuntimeError:  # no request
            return None, False
    if isinstance(actor, int):
        from hubra.core.models.member import Member

        return db.session.get(Member, actor), False
    return actor, False


def _check_perm(offer: reg.Offer, member, system: bool) -> None:
    perm = offer.contract.perm
    if system or not perm:
        return
    from hubra.core.permissions import member_has_permission

    if not member_has_permission(member, perm):
        raise ActionForbidden(f"{offer.contract.name} needs the right {perm}")


def _run(offer: reg.Offer, data: dict, ctx: CallContext, *, read_only: bool):
    contract = offer.contract
    value = reg.check_input(contract, data, portable=False)
    fn = _resolve(contract.handler)
    session = db.session()
    savepoint = session.begin_nested()
    try:
        result = fn(ctx, value)
        out = reg.check_output(contract, result)
    except Refused:
        savepoint.rollback()
        raise
    except (ContractError, ActionForbidden, ActionUnavailable):
        savepoint.rollback()
        raise
    except Exception as exc:
        if savepoint.is_active:
            savepoint.rollback()
        _log.exception("%s %s failed", contract.kind, contract.name)
        raise ActionFailed(f"{contract.name} failed: {type(exc).__name__}") from exc
    if read_only:
        # A query never writes, whatever its handler did.
        if savepoint.is_active:
            savepoint.rollback()
    elif savepoint.is_active:
        savepoint.commit()
    return out


def call(name: str, data: dict | None = None, /, *, actor: Any = CURRENT, **fields):
    """Run action *name* now, inside the caller's transaction, and return its
    result (plain values). The action's own work rolls back alone when it
    fails; the caller decides what to do with the error.

    Raises ActionUnavailable (not offered, off, wrong version),
    ActionForbidden, Refused (the handler said no, with a reason),
    ActionFailed (the handler broke) or ContractError (a bug: bad input,
    undeclared use).
    """
    return _sync(name, ACTION, data, fields, actor, read_only=False)


def query(name: str, data: dict | None = None, /, *, actor: Any = CURRENT, **fields):
    """Run query *name* and return its result; any writes are rolled back."""
    return _sync(name, QUERY, data, fields, actor, read_only=True)


def _sync(name, kind, data, fields, actor, *, read_only):
    caller = reg.caller_module()
    offer = _offer(name, kind, caller)
    tid = _tenant_id()
    _check_on(offer, tid)
    member, system = _actor(actor)
    _check_perm(offer, member, system)
    ctx = CallContext(tid, name, caller, actor=member, system=system)
    return _run(offer, {**(data or {}), **fields}, ctx, read_only=read_only)


def available(name: str) -> bool:
    """Whether *name* can be used here, for this club, by the caller (its
    declared range met, its module on). Permissions are not checked."""
    caller = reg.caller_module()
    try:
        offer = reg.get(name)
        if offer is None:
            return False
        _offer(name, offer.contract.kind, caller)
        _check_on(offer, _tenant_id())
    except (ActionUnavailable, ContractError):
        return False
    return True


def send(
    name: str, data: dict | None = None, /, *, actor: Any = CURRENT, **fields
) -> str:
    """Queue action *name* to run after the caller's transaction commits, in
    the worker, retried on failure. Returns the message id. Nothing is sent
    if the caller's transaction rolls back."""
    from . import outbox
    from .transport import envelope

    caller = reg.caller_module()
    offer = _offer(name, ACTION, caller)
    tid = _tenant_id()
    _check_on(offer, tid)
    member, system = _actor(actor)
    _check_perm(offer, member, system)
    payload = {**(data or {}), **fields}
    reg.check_input(offer.contract, payload, portable=True)
    payload = reg.portable(payload)
    who = {"system": True} if system else {"member_id": getattr(member, "id", None)}
    env = envelope(
        kind=ACTION,
        name=name,
        version=offer.contract.version,
        data=payload,
        tenant_id=tid,
        source=reg.plugin_of(caller) or caller.split(".")[0],
        actor={**who, "caller": caller},
    )
    outbox.add(
        kind=ACTION,
        name=name,
        module_code=offer.module_code,
        target=offer.contract.handler or "",
        tenant_id=tid,
        env=env,
    )
    return env["id"]


def run_queued(name: str, env: dict) -> Any:
    """Run a queued action from its envelope (``outbox.deliver``)."""
    offer = reg.get(name)
    if offer is None or offer.contract.kind != ACTION:
        raise ActionUnavailable(f"nothing offers {name} here")
    if offer.contract.version != env.get("dataversion"):
        raise ActionUnavailable(
            f"{name} is version {offer.contract.version} here; queued for {env.get('dataversion')}"
        )
    tid = env.get("tenantid")
    _check_on(offer, tid)
    who = env.get("hubraactor") or {}
    if who.get("system"):
        member, system = None, True
    else:
        member, system = (
            _actor(who.get("member_id")) if who.get("member_id") else (None, False)
        )
    _check_perm(offer, member, system)
    ctx = CallContext(
        tid,
        name,
        who.get("caller", ""),
        actor=member,
        system=system,
        message_id=env.get("id"),
    )
    return _run(offer, dict(env.get("data") or {}), ctx, read_only=False)


# ── Widgets ─────────────────────────────────────────────────────────────────


def _widget_output(contract):
    import dataclasses

    from .base import ListData, StatData

    model = {"stat": StatData, "list": ListData}.get(contract.view)
    return dataclasses.replace(contract, output=model) if model else contract


def widgets(actor: Any = CURRENT) -> list[reg.Offer]:
    """The widgets *actor* may put on a dashboard here: module on, right held."""
    from .base import WIDGET

    tid = _tenant_id()
    member, system = _actor(actor)
    out = []
    for offer in reg.offers().values():
        if offer.contract.kind != WIDGET:
            continue
        try:
            _check_on(offer, tid)
            _check_perm(offer, member, system)
        except (ActionUnavailable, ActionForbidden):
            continue
        out.append(offer)
    return sorted(out, key=lambda o: o.contract.name)


def widget_data(name: str, config: Any = None, *, actor: Any = CURRENT):
    """What widget *name* shows for *actor* with its saved *config*: checked
    like a query (module on, right held, result against the view's shape),
    and its writes rolled back."""
    from .base import WIDGET

    offer = reg.get(name)
    if offer is None or offer.contract.kind != WIDGET:
        raise ActionUnavailable(f"no widget {name} here")
    tid = _tenant_id()
    _check_on(offer, tid)
    member, system = _actor(actor)
    _check_perm(offer, member, system)
    contract = _widget_output(offer.contract)
    ctx = CallContext(tid, name, "dashboards", actor=member, system=system)
    return _run(
        reg.Offer(contract, offer.module_code, offer.plugin),
        offer.contract.config(config),
        ctx,
        read_only=True,
    )
