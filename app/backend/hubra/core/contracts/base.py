"""Contract types and the errors a call can end in (docs/contracts.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EVENT = "event"
ACTION = "action"
QUERY = "query"
KINDS = (EVENT, ACTION, QUERY)


@dataclass(frozen=True)
class Contract:
    """Something a module offers other modules, by name.

    - ``event``: a fact others may hear about (``emit``), no reply.
    - ``action``: a command with one owner and a reply (``call``, or
      ``send`` to run it after the commit, with retries).
    - ``query``: a read with a reply (``query``); its writes are always
      rolled back.

    ``version`` is the contract's major version: a change that can break a
    consumer (a field removed or renamed, a meaning changed) raises it;
    adding an optional field does not. ``input`` and ``output`` are
    pydantic models, or dotted ``module.path:Model`` strings, that the
    payload, the arguments and the result are checked against; ``None``
    takes any mapping of plain values. ``handler`` is the dotted
    ``module.path:function`` that runs an action or a query. ``perm`` is the
    permission key the acting member needs (actions and queries).
    """

    name: str
    kind: str = EVENT
    version: int = 1
    input: Any = None
    output: Any = None
    handler: str | None = None
    perm: str | None = None
    description: str = ""

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"Contract {self.name}: unknown kind {self.kind!r}")
        if self.kind == EVENT and (self.handler or self.output is not None):
            raise ValueError(f"Contract {self.name}: an event has no handler or output")
        if self.kind != EVENT and not self.handler:
            raise ValueError(f"Contract {self.name}: an {self.kind} needs a handler")
        if not isinstance(self.version, int) or self.version < 1:
            raise ValueError(f"Contract {self.name}: version is a whole number from 1")


def event_contract(
    name: str, input: Any = None, *, version: int = 1, description: str = ""
) -> Contract:
    return Contract(name, EVENT, version, input=input, description=description)


def action_contract(
    name: str,
    handler: str,
    *,
    input: Any = None,
    output: Any = None,
    perm: str | None = None,
    version: int = 1,
    description: str = "",
) -> Contract:
    return Contract(name, ACTION, version, input, output, handler, perm, description)


def query_contract(
    name: str,
    handler: str,
    *,
    input: Any = None,
    output: Any = None,
    perm: str | None = None,
    version: int = 1,
    description: str = "",
) -> Contract:
    return Contract(name, QUERY, version, input, output, handler, perm, description)


@dataclass
class CallContext:
    """What an action or query handler is told about the call.

    ``actor`` is the acting Member, or ``None`` when ``system`` is true (a
    job, or a plugin acting on its own behalf). ``message_id`` is set for a
    queued action and stays the same on every retry: use it to do the work
    only once.
    """

    tenant_id: int | None
    name: str
    caller: str
    actor: Any = None
    system: bool = False
    message_id: str | None = None
    extra: dict = field(default_factory=dict)


class _System:
    def __repr__(self) -> str:
        return "SYSTEM"


# Pass as ``actor=SYSTEM`` to act without a member (no permission check).
SYSTEM = _System()


class ContractError(ValueError):
    """The call itself is wrong: unknown or undeclared name, bad input,
    a result that doesn't match the contract. A bug, not a condition."""

    code = "CONTRACT_INVALID"


class ActionUnavailable(RuntimeError):
    """Nobody offers this (in a version the caller accepts) for this club:
    the plugin isn't installed, didn't load, or its module is off."""

    code = "CONTRACT_UNAVAILABLE"


class ActionForbidden(PermissionError):
    """The acting member lacks the contract's permission."""

    code = "CONTRACT_FORBIDDEN"


class Refused(Exception):
    """Raised by a handler to say no for a reason the caller can show
    ("this key is already handed out"). Never retried."""

    code = "CONTRACT_REFUSED"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code


class ActionFailed(RuntimeError):
    """The handler broke. Its work was rolled back; the caller's was not."""

    code = "CONTRACT_FAILED"
