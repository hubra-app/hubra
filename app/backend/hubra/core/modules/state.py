"""Per-tenant module state: which modules are on, and their settings.

Resolution for one module and one tenant:

1. ``required`` modules are always on.
2. A ``TenantFeature`` row decides ``enabled`` and ``allowed`` (the
   platform manager can block a module for a tenant; the club admin then
   cannot switch it on).
3. Without a row, the catalog default (``Feature.default_enabled``, which
   starts as the manifest default) applies.
4. A module is only effectively on when all its dependencies are on.

Without a tenant (single-club installs and the public schema) the catalog
row itself is the switch.

The resolved state is cached for the rest of the request and cleared by
every write.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from flask import g, has_request_context, request
from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db

from .base import Module
from .registry import registry

_log = logging.getLogger(__name__)


class _Current:
    def __repr__(self) -> str:
        return "<current tenant>"


CURRENT = _Current()


@dataclass
class ModuleState:
    module: Module
    enabled: bool  # the switch itself
    allowed: bool  # not blocked by the platform manager
    effective: bool  # enabled, allowed and all dependencies effective
    config: dict[str, Any]
    missing_dependencies: list[str]

    def to_dict(self) -> dict:
        data = self.module.to_dict()
        if self.module.plugin:
            from hubra.core.plugins import current

            spec = current().get(self.module.plugin)
            if spec is not None:
                data["plugin"] = {
                    "id": spec.id,
                    "name": spec.name,
                    "version": spec.version,
                    "author": str(spec.manifest.get("author", "")),
                    "trust": spec.trust.get("status", ""),
                    # The app loads <api>/v1/plugins/<id>/frontend.js?v=<this>.
                    "frontend": spec.frontend_tag,
                }
        secrets = {s.key for s in self.module.settings if s.type == "secret"}
        data.update(
            {
                "enabled": self.effective,
                "switchedOn": self.enabled,
                "allowed": self.allowed,
                "missingDependencies": self.missing_dependencies,
                "config": {
                    k: ("" if k in secrets else v) for k, v in self.config.items()
                },
                "configured": all(
                    self.config.get(s.key) not in (None, "")
                    for s in self.module.settings
                    if s.required
                ),
            }
        )
        return data


def _resolve_tenant_id(tenant_id) -> int | None:
    if tenant_id is CURRENT:
        from hubra.core.tenant.context import current_tenant

        try:
            tenant = current_tenant()
        except RuntimeError:  # outside a request
            tenant = None
        return tenant.id if tenant is not None else None
    return tenant_id


def _cache() -> dict | None:
    # Kept in the WSGI environ rather than on g: g lives as long as the app
    # context, which tests and some CLI paths keep open across requests.
    if not has_request_context():
        return None
    return request.environ.setdefault("hubra.module_state", {})


def invalidate() -> None:
    cache = _cache()
    if cache is not None:
        cache.clear()


def states(tenant_id=CURRENT) -> dict[str, ModuleState]:
    """Resolve the state of every registered module for *tenant_id*."""
    from hubra.core.models.feature import Feature, TenantFeature

    registry.load()
    tid = _resolve_tenant_id(tenant_id)
    cache = _cache()
    if cache is not None and tid in cache:
        return cache[tid]

    catalog = {f.code: f for f in db.session.scalars(select(Feature)).all()}
    grants = {}
    if tid is not None:
        grants = {
            gr.feature_code: gr
            for gr in db.session.scalars(
                select(TenantFeature).where(TenantFeature.tenant_id == tid)
            ).all()
        }

    removed = _uninstalled_plugins()
    result: dict[str, ModuleState] = {}
    for m in registry.all():  # dependencies first
        if m.plugin is not None and m.plugin in removed:
            # Uninstalled since this process started; gone after its reload.
            continue
        grant = grants.get(m.code)
        feature = catalog.get(m.code)
        if m.required:
            enabled, allowed = True, True
        elif grant is not None:
            enabled, allowed = bool(grant.enabled), bool(grant.allowed)
        elif feature is not None:
            enabled, allowed = bool(feature.default_enabled), True
        else:
            enabled, allowed = m.default_enabled, True
        missing = [
            d for d in m.depends_on if d not in result or not result[d].effective
        ]
        raw_config = (grant.config if grant is not None else None) or {}
        config = {s.key: raw_config.get(s.key, s.default) for s in m.settings}
        result[m.code] = ModuleState(
            module=m,
            enabled=enabled,
            allowed=allowed,
            effective=enabled and allowed and not missing,
            config=config,
            missing_dependencies=missing,
        )

    if cache is not None:
        cache[tid] = result
    return result


def _uninstalled_plugins() -> set[str]:
    """Plugins this process loaded that are no longer installed."""
    from hubra.core.models.plugin import InstalledPlugin
    from hubra.core.plugins import current

    plugins = current()
    loaded = {s.id for s in plugins.loaded()} - plugins.autoinstalled
    if not loaded:
        return set()
    installed = set(db.session.scalars(select(InstalledPlugin.id)).all())
    return loaded - installed


def is_enabled(code: str, tenant_id=CURRENT) -> bool:
    state = states(tenant_id).get(code)
    return bool(state and state.effective)


def get_config(code: str, tenant_id=CURRENT) -> dict[str, Any]:
    state = states(tenant_id).get(code)
    return dict(state.config) if state else {}


def enabled_codes(tenant_id=CURRENT) -> list[str]:
    return [c for c, s in states(tenant_id).items() if s.effective]


# ── Writes ───────────────────────────────────────────────────────────────────


def sync_catalog() -> int:
    """Upsert one ``Feature`` row per manifest.  Returns rows created.

    ``default_enabled`` is only written when the row is created, so a
    single-club install that switched a module keeps its choice.
    """
    from hubra.core.models.feature import Feature

    registry.load()
    created = 0
    for m in registry.all():
        row = db.session.get(Feature, m.code)
        if row is None:
            db.session.add(
                Feature(
                    code=m.code,
                    name=m.name,
                    description=m.description,
                    default_enabled=m.default_enabled or m.required,
                )
            )
            created += 1
        else:
            row.name = m.name
            row.description = m.description
    db.session.flush()
    return created


def _module_or_404(code: str) -> Module:
    registry.load()
    m = registry.get(code)
    if m is None or (m.plugin is not None and m.plugin in _uninstalled_plugins()):
        raise_error(404, "NOT_FOUND", f"Module '{code}' does not exist")
    return m


def _grant(tenant_id: int, code: str, create: bool = True):
    from hubra.core.models.feature import Feature, TenantFeature

    grant = db.session.scalar(
        select(TenantFeature)
        .where(TenantFeature.tenant_id == tenant_id)
        .where(TenantFeature.feature_code == code)
    )
    if grant is None and create:
        if db.session.get(Feature, code) is None:
            sync_catalog()
        feature = db.session.get(Feature, code)
        grant = TenantFeature(
            tenant_id=tenant_id,
            feature_code=code,
            enabled=bool(feature.default_enabled) if feature else False,
            allowed=True,
            config={},
        )
        db.session.add(grant)
    return grant


def set_enabled(code: str, enabled: bool, tenant_id=CURRENT) -> ModuleState:
    """Switch a module on or off for a tenant.

    Switching on fails when a dependency is off or the manager blocked the
    module.  Switching off fails while an enabled module depends on it.
    Data is never deleted; an off module is only hidden and unreachable.
    """
    from hubra.core.models.feature import Feature

    m = _module_or_404(code)
    tid = _resolve_tenant_id(tenant_id)
    current = states(tid)

    if m.required and not enabled:
        raise_error(409, "MODULE_REQUIRED", f"{m.name} cannot be switched off")
    if enabled:
        if not current[code].allowed:
            raise_error(
                403, "MODULE_NOT_ALLOWED", f"{m.name} is not available for this club"
            )
        off = [d for d in m.depends_on if d not in current or not current[d].effective]
        if off:
            names = ", ".join(registry.get(d).name for d in off)
            raise_error(
                409,
                "MODULE_DEPENDENCY_OFF",
                f"Switch on {names} first; {m.name} needs it",
            )
    else:
        on = [
            d.name
            for d in registry.dependents(code)
            if d.code in current and current[d.code].effective
        ]
        if on:
            raise_error(
                409,
                "MODULE_HAS_DEPENDENTS",
                f"Switch off {', '.join(on)} first; it needs {m.name}",
            )

    if tid is None:
        row = db.session.get(Feature, code)
        if row is None:
            sync_catalog()
            row = db.session.get(Feature, code)
        row.default_enabled = enabled
    else:
        _grant(tid, code).enabled = enabled
    db.session.flush()
    invalidate()
    return states(tid)[code]


def set_allowed(code: str, allowed: bool, tenant_id: int) -> ModuleState:
    """Manager-level switch.  Blocking a module also switches it off."""
    m = _module_or_404(code)
    if m.required and not allowed:
        raise_error(409, "MODULE_REQUIRED", f"{m.name} cannot be blocked")
    grant = _grant(tenant_id, code)
    grant.allowed = allowed
    if not allowed:
        grant.enabled = False
    db.session.flush()
    invalidate()
    return states(tenant_id)[code]


def set_config(code: str, config: dict, tenant_id=CURRENT) -> ModuleState:
    """Validate and store a module's settings for a tenant.

    Secret fields sent empty keep their stored value.
    """
    m = _module_or_404(code)
    tid = _resolve_tenant_id(tenant_id)
    if tid is None:
        raise_error(
            400, "NO_TENANT", "Module settings are stored per club; pick a club first"
        )
    grant = _grant(tid, code)
    previous = dict(grant.config or {})
    incoming = dict(config or {})
    for s in m.settings:
        if s.type == "secret" and incoming.get(s.key) in (None, ""):
            if previous.get(s.key):
                incoming[s.key] = previous[s.key]
    try:
        grant.config = m.validate_config(incoming)
    except ValueError as exc:
        raise_error(400, "VALIDATION_ERROR", str(exc))
    db.session.flush()
    invalidate()
    return states(tid)[code]


# ── Background jobs ──────────────────────────────────────────────────────────


def run_for_tenants(code: str, fn: Callable[[int | None], Any]) -> dict:
    """Run *fn* once per active tenant that has *code* enabled.

    Sets the tenant's search_path and ``g.tenant`` around each call and returns
    ``{tenant_id: result}``.  Installs without tenants run *fn(None)* once
    against the public schema if the module is on there.  One tenant's
    failure is logged and does not stop the others.
    """
    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.context import reset_search_path, set_search_path

    tenants = db.session.scalars(select(Tenant).where(Tenant.status == "active")).all()
    results: dict = {}
    if not tenants:
        if is_enabled(code, tenant_id=None):
            results[None] = fn(None)
        return results

    for tenant in tenants:
        if not is_enabled(code, tenant_id=tenant.id):
            continue
        try:
            g.tenant = tenant
            set_search_path(tenant.id)
            results[tenant.id] = fn(tenant.id)
            db.session.commit()
        except Exception:
            db.session.rollback()
            _log.exception("%s job failed for tenant %s", code, tenant.slug)
            results[tenant.id] = {"error": True}
        finally:
            reset_search_path()
            g.tenant = None
    return results


def per_tenant_job(code: str):
    """Decorator for a periodic task body that works on one club's data.

    Inside a club (a task queued from a request) it runs once if *code* is
    on.  From the scheduler it runs once per club that has *code* on.  An
    install without tenants gets the body's own result back unchanged.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from hubra.core.tenant.context import current_tenant

            skipped = {"skipped": f"{code} disabled"}
            if current_tenant() is not None:
                return fn(*args, **kwargs) if is_enabled(code) else skipped
            results = run_for_tenants(code, lambda _tid: fn(*args, **kwargs))
            if not results:
                return skipped
            if list(results) == [None]:
                return results[None]
            return {"tenants": results}

        return wrapper

    return decorator
