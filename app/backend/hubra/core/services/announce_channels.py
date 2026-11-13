"""Where something new is announced: one picker for posts and events.

The channels are ``app`` (the bell and push in Hubra) and every module on in
the club that announces the thing, that is, listens to its event
(``post.published``, ``event.published``): Discord, Messengers, ... The
author picks some of them; ``None`` stands for all of them, also ones the
club adds later. Core then only calls the modules picked
(``emit(..., to_modules=...)``); the club's webhooks always hear it.
"""

from __future__ import annotations

from hubra.core.errors import raise_error

APP_CHANNEL = "app"


def channels(event: str, own: str) -> list[dict]:
    """The app, then each module on here that listens to *event* (except
    *own*, the module that sends it), as ``{key, name}``."""
    from hubra.core.modules.registry import registry
    from hubra.core.modules.state import is_enabled

    registry.load()
    out = [{"key": APP_CHANNEL, "name": "Hubra"}]
    for module, _target in registry.subscribers(event):
        if module.code != own and is_enabled(module.code):
            out.append({"key": module.code, "name": module.name})
    return out


def check_channels(value: list[str] | None, event: str, own: str) -> list[str] | None:
    """400 unless every channel in *value* is one this club has. A list
    naming all of them is stored as None (every channel, also ones added
    later)."""
    if value is None:
        return None
    known = [c["key"] for c in channels(event, own)]
    unknown = sorted(set(value) - set(known))
    if unknown:
        raise_error(
            400, "VALIDATION_ERROR", f"channels: unknown channel {', '.join(unknown)}"
        )
    if set(known) <= set(value):
        return None
    return [k for k in known if k in value]


def to_app(picked: list[str] | None) -> bool:
    """Whether the bell and push are among *picked*."""
    return picked is None or APP_CHANNEL in picked


def to_modules(picked: list[str] | None) -> list[str] | None:
    """The modules *picked* names, for ``emit(to_modules=...)``."""
    return None if picked is None else [c for c in picked if c != APP_CHANNEL]
