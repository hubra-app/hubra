"""Contract types and the errors a call can end in (docs/contracts.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

EVENT = "event"
ACTION = "action"
QUERY = "query"
WIDGET = "widget"
KINDS = (EVENT, ACTION, QUERY, WIDGET)

# How a widget is drawn: by core from its data (stat: one number; list:
# rows), or by the plugin's own frontend component (custom).
WIDGET_VIEWS = ("stat", "list", "custom")
WIDGET_SIZES = ("s", "m", "l")
FIELD_KINDS = ("text", "number", "switch")


@dataclass(frozen=True)
class WidgetField:
    """A setting the member fills in when adding a widget."""

    key: str
    label: str
    kind: str = "text"
    default: Any = None

    def __post_init__(self):
        if self.kind not in FIELD_KINDS:
            raise ValueError(f"WidgetField {self.key}: kind is one of {FIELD_KINDS}")

    def coerce(self, value: Any) -> Any:
        if value is None or value == "":
            return self.default
        if self.kind == "number":
            try:
                return float(value) if "." in str(value) else int(value)
            except (TypeError, ValueError):
                return self.default
        if self.kind == "switch":
            return value is True or str(value).lower() in ("1", "true", "yes", "on")
        return str(value)[:500]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "default": self.default,
        }


@dataclass(frozen=True)
class Contract:
    """Something a module offers other modules, by name.

    - ``event``: a fact others may hear about (``emit``), no reply.
    - ``action``: a command with one owner and a reply (``call``, or
      ``send`` to run it after the commit, with retries).
    - ``query``: a read with a reply (``query``); its writes are always
      rolled back.
    - ``widget``: a dashboard widget. Its handler reads the data the widget
      shows, as the viewing member, like a query; ``label``, ``size``,
      ``view`` and ``fields`` say how it is offered and drawn.

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
    # Widgets only.
    label: str = ""
    size: str = "m"
    view: str = "custom"
    fields: tuple = ()

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"Contract {self.name}: unknown kind {self.kind!r}")
        if self.kind == EVENT and (self.handler or self.output is not None):
            raise ValueError(f"Contract {self.name}: an event has no handler or output")
        if self.kind != EVENT and not self.handler:
            raise ValueError(f"Contract {self.name}: an {self.kind} needs a handler")
        if not isinstance(self.version, int) or self.version < 1:
            raise ValueError(f"Contract {self.name}: version is a whole number from 1")
        if self.kind == WIDGET:
            if self.size not in WIDGET_SIZES:
                raise ValueError(f"Widget {self.name}: size is one of {WIDGET_SIZES}")
            if self.view not in WIDGET_VIEWS:
                raise ValueError(f"Widget {self.name}: view is one of {WIDGET_VIEWS}")
            if not all(isinstance(f, WidgetField) for f in self.fields):
                raise ValueError(f"Widget {self.name}: fields are WidgetField")

    def config(self, raw: Any) -> dict:
        """A widget's settings from what was saved: known keys, coerced."""
        raw = raw if isinstance(raw, dict) else {}
        return {f.key: f.coerce(raw.get(f.key)) for f in self.fields}


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


def widget_contract(
    name: str,
    handler: str,
    *,
    label: str,
    description: str = "",
    size: str = "m",
    view: str = "custom",
    fields: tuple = (),
    output: Any = None,
    perm: str | None = None,
    version: int = 1,
) -> Contract:
    """A dashboard widget. ``handler(ctx, config)`` returns what it shows:
    for ``view="stat"`` a :class:`StatData`, for ``"list"`` a
    :class:`ListData`, for ``"custom"`` whatever ``output`` describes (the
    plugin's frontend draws it). ``label`` and ``description`` are
    translation keys or plain text."""
    return Contract(
        name,
        WIDGET,
        version,
        None,
        output,
        handler,
        perm,
        description,
        label=label,
        size=size,
        view=view,
        fields=tuple(fields),
    )


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


# ── What core-drawn widgets show ────────────────────────────────────────────


class StatData(BaseModel):
    """One number (or short text), with a line under it."""

    value: int | float | str
    sub: str | None = None
    path: str | None = None  # club-app path the tile opens


class ListRow(BaseModel):
    label: str
    sub: str | None = None
    path: str | None = None


class ListData(BaseModel):
    """Rows, most important first; ``total`` when there are more."""

    items: list[ListRow]
    total: int | None = None
