"""In-process event bus between modules.

A module subscribes in its manifest::

    events={"invoice.overdue": "vollbuild.modules.inventory_keys.hooks:on_overdue"}

``emit("invoice.overdue", member_id=..., invoice_id=...)`` then calls every
subscriber whose module is enabled for the tenant, with ``tenant_id`` and
the payload as keyword arguments.  Handlers run synchronously in the
caller's transaction; a failing handler is logged and does not stop the
others or the caller.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from .registry import registry
from .state import CURRENT, _resolve_tenant_id, is_enabled

_log = logging.getLogger(__name__)

# Event names in use, so emitters and subscribers agree on spelling.
INVOICE_OVERDUE = "invoice.overdue"
INVOICE_PAID = "invoice.paid"
EVENT_PUBLISHED = "event.published"
POST_PUBLISHED = "post.published"
GROUP_MEMBERSHIP_CHANGED = "group.membership_changed"


def _resolve(target: str):
    module_path, _, attr = target.partition(":")
    return getattr(importlib.import_module(module_path), attr)


def emit(event: str, tenant_id=CURRENT, **payload: Any) -> list[str]:
    """Deliver *event* to enabled subscribers.  Returns the module codes called."""
    registry.load()
    tid = _resolve_tenant_id(tenant_id)
    called: list[str] = []
    for module, target in registry.subscribers(event):
        if not is_enabled(module.code, tenant_id=tid):
            continue
        try:
            _resolve(target)(tenant_id=tid, **payload)
            called.append(module.code)
        except Exception:
            _log.exception("Handler %s for %s failed", target, event)
    return called
