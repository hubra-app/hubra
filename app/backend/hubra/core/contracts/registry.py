"""Who offers which contract, and who may use it.

Built from the module registry: Hubra's own events (``core_events``) plus
every module's ``provides``. A plugin that uses another plugin's contract
names it under ``consumes`` with a version range; the index answers
whether that range is met here and now.
"""

from __future__ import annotations

import importlib
import json
import logging
import sys
from dataclasses import dataclass
from typing import Any

from .base import Contract, ContractError

_log = logging.getLogger(__name__)

# Frames of these modules are skipped when finding who called.
_OWN = ("hubra.core.contracts", "hubra.core.modules.events")


@dataclass(frozen=True)
class Offer:
    contract: Contract
    module_code: str  # "core" for Hubra's own events
    plugin: str | None = None

    def to_dict(self) -> dict:
        c = self.contract
        return {
            "name": c.name,
            "kind": c.kind,
            "version": c.version,
            "module": self.module_code,
            "plugin": self.plugin,
            "perm": c.perm,
            "description": c.description,
            "input": json_schema(c.input),
            "output": json_schema(c.output),
            **(self.widget_dict() if c.kind == "widget" else {}),
        }

    def widget_dict(self) -> dict:
        c = self.contract
        return {
            "label": c.label,
            "size": c.size,
            "view": c.view,
            "fields": [f.to_dict() for f in c.fields],
        }


_cache: dict = {"key": None, "offers": {}}


def _registry():
    from hubra.core.modules import registry

    registry.load()
    return registry


def offers() -> dict[str, Offer]:
    """Every contract on offer here, by name."""
    reg = _registry()
    # The modules themselves, not their ids: a module dropped and another
    # made in its place can get the same id (tests swap modules).
    key = tuple(reg.all())
    cached = _cache["key"]
    if (
        cached is not None
        and len(cached) == len(key)
        and all(a is b for a, b in zip(cached, key, strict=True))
    ):
        return _cache["offers"]
    from .core_events import CORE_EVENTS

    out: dict[str, Offer] = {c.name: Offer(c, "core") for c in CORE_EVENTS}
    for module in reg.all():
        for c in module.provides:
            if c.name in out:
                _log.error(
                    "Contract %s offered by %s and %s; keeping the first",
                    c.name,
                    out[c.name].module_code,
                    module.code,
                )
                continue
            out[c.name] = Offer(c, module.code, module.plugin)
    _cache.update(key=key, offers=out)
    return out


def get(name: str) -> Offer | None:
    return offers().get(name)


def accepts(rng: str | None, version: int) -> bool:
    """Whether contract *version* is in the range a consumer named."""
    if not rng:
        return True
    from packaging.specifiers import InvalidSpecifier, SpecifierSet
    from packaging.version import Version

    try:
        return SpecifierSet(str(rng)).contains(Version(str(version)))
    except InvalidSpecifier:
        return False


# ── Schemas ─────────────────────────────────────────────────────────────────


def model(spec: Any):
    """The pydantic model a contract names (class or ``module.path:Model``)."""
    if spec is None or not isinstance(spec, str):
        return spec
    path, _, attr = spec.partition(":")
    return getattr(importlib.import_module(path), attr)


def json_schema(spec: Any) -> dict | None:
    m = model(spec)
    if m is None:
        return None
    try:
        return m.model_json_schema()
    except Exception:
        return None


def check_input(contract: Contract, data: dict, *, portable: bool):
    """*data* checked against the contract's input: the model instance, or the
    dict itself when the contract names none. *portable* data must survive
    JSON (it is stored and sent to a worker)."""
    from pydantic import ValidationError

    m = model(contract.input)
    if m is None:
        if not isinstance(data, dict):
            raise ContractError(f"{contract.name}: input must be a mapping")
        if portable:
            try:
                json.dumps(data)
            except (TypeError, ValueError) as exc:
                raise ContractError(
                    f"{contract.name}: input must be plain values (ids, text, numbers): {exc}"
                ) from None
        return data
    try:
        return m.model_validate(data)
    except ValidationError as exc:
        raise ContractError(f"{contract.name}: {_short(exc)}") from None


def portable(value) -> Any:
    """A model instance, or anything else, as plain JSON values."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def check_output(contract: Contract, value):
    from pydantic import TypeAdapter, ValidationError

    m = model(contract.output)
    if m is None:
        return portable(value)
    try:
        if isinstance(value, m):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return TypeAdapter(list[m]).dump_python(
                TypeAdapter(list[m]).validate_python(value), mode="json"
            )
        return m.model_validate(value).model_dump(mode="json")
    except ValidationError as exc:
        raise ContractError(f"{contract.name}: the result {_short(exc)}") from None


def _short(exc) -> str:
    parts = []
    for err in exc.errors()[:3]:
        loc = ".".join(str(p) for p in err.get("loc", ())) or "value"
        parts.append(f"{loc}: {err.get('msg')}")
    return "; ".join(parts)


# ── Callers ─────────────────────────────────────────────────────────────────


def caller_module() -> str:
    """The Python module that called into the contracts (past our own frames)."""
    frame = sys._getframe(1)
    while frame is not None:
        name = frame.f_globals.get("__name__", "")
        if not name.startswith(_OWN):
            return name
        frame = frame.f_back
    return ""


def plugin_of(module_name: str) -> str | None:
    """The plugin id whose package *module_name* lives in, else None."""
    top = module_name.split(".")[0]
    if not top.startswith("hubra_"):
        return None
    from hubra.core.plugins import loader

    for spec in loader.current().loaded():
        if spec.package == top:
            return spec.id
    # A plugin package that isn't loaded (tests build modules by hand):
    # match the modules' plugin ids against the package name.
    for module in _registry().all():
        if module.plugin and "hubra_" + module.plugin.replace("-", "_") == top:
            return module.plugin
    return top


def consumer_range(plugin: str, name: str) -> tuple[bool, str | None]:
    """(declared, range) for *plugin* using contract *name*: its modules'
    ``consumes``, or its own contracts (always allowed)."""
    rng = None
    declared = False
    for module in _registry().all():
        if module.plugin != plugin:
            continue
        if any(c.name == name for c in module.provides):
            return True, None
        if name in module.consumes:
            declared = True
            rng = module.consumes[name] or rng
    return declared, rng
