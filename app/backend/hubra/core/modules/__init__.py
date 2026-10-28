"""Module system: manifests, registry, per-tenant state, gate and events.

See ``hubra/modules/README.md`` for how to add a module.
"""

from .base import Blueprint, Module, NavItem, Schedule, SettingField
from .events import emit
from .gate import module_gate, module_required
from .registry import ModuleRegistryError, registry
from .state import (
    CURRENT,
    enabled_codes,
    get_config,
    is_enabled,
    per_tenant_job,
    run_for_tenants,
    set_allowed,
    set_config,
    set_enabled,
    states,
    sync_catalog,
)

__all__ = [
    "CURRENT",
    "Blueprint",
    "Module",
    "ModuleRegistryError",
    "NavItem",
    "Schedule",
    "SettingField",
    "emit",
    "enabled_codes",
    "get_config",
    "is_enabled",
    "module_gate",
    "module_required",
    "per_tenant_job",
    "registry",
    "run_for_tenants",
    "set_allowed",
    "set_config",
    "set_enabled",
    "states",
    "sync_catalog",
]
