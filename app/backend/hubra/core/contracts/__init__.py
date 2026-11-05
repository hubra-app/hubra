"""Contracts: how modules and plugins use each other without importing each other.

A module offers events, actions and queries under a name and a version
(``Module.provides``); another names what it uses with a version range
(``Module.consumes``) and goes through core::

    from hubra.core.contracts import call, query, send, available

    items = query("inventory.items.get", ids=[3, 7])
    call("keys.key.hand_out", key_id=12, member_id=5)
    send("payments.link.create", invoice_id=9)   # after the commit, retried

Core finds who offers it, checks the module is on for the club and the
acting member's right, checks input and result against the contract's
schema, and keeps a failing handler's work from touching the caller's.
Events go through ``hubra.core.modules.emit``; a plugin's handlers get them
from the outbox after the commit, with retries. See docs/contracts.md.
"""

from .base import (
    ACTION,
    EVENT,
    QUERY,
    SYSTEM,
    ActionFailed,
    ActionForbidden,
    ActionUnavailable,
    CallContext,
    Contract,
    ContractError,
    ListData,
    ListRow,
    Refused,
    StatData,
    WidgetField,
    action_contract,
    event_contract,
    query_contract,
    widget_contract,
)
from .calls import CURRENT, available, call, query, send, widget_data, widgets

__all__ = [
    "ACTION",
    "CURRENT",
    "EVENT",
    "QUERY",
    "SYSTEM",
    "ActionFailed",
    "ActionForbidden",
    "ActionUnavailable",
    "CallContext",
    "Contract",
    "ContractError",
    "ListData",
    "ListRow",
    "Refused",
    "StatData",
    "WidgetField",
    "action_contract",
    "available",
    "call",
    "event_contract",
    "query",
    "query_contract",
    "send",
    "widget_contract",
    "widget_data",
    "widgets",
]
