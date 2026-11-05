"""Module registry: discovers manifests and registers their blueprints.

Every package under ``hubra.modules`` exposes a ``module`` manifest, and so
does every installed plugin (``hubra.core.plugins``).
The registry imports them once, checks dependencies, and is the single
place that knows which blueprint belongs to which module.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil

from flask import Flask

from .base import AppProvider, Module

_log = logging.getLogger(__name__)


class ModuleRegistryError(RuntimeError):
    pass


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, Module] = {}
        self._bp_to_module: dict[str, str] = {}
        self._loaded = False

    # ── Discovery ───────────────────────────────────────────────────────────

    def load(self, package: str = "hubra.modules") -> None:
        """Import every manifest in *package*.  Safe to call more than once."""
        if self._loaded:
            return
        pkg = importlib.import_module(package)
        for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
            mod = importlib.import_module(f"{package}.{info.name}")
            manifest = getattr(mod, "module", None)
            if not isinstance(manifest, Module):
                continue
            self.add(manifest)
        # Installed plugins add their modules next (needs an app context to
        # read what is installed; without one only Hubra's own modules load).
        from hubra.core.plugins import loader

        loader.load(self)
        self.validate()
        self._loaded = True

    def add(self, manifest: Module) -> None:
        if manifest.code in self._modules:
            raise ModuleRegistryError(f"Duplicate module code {manifest.code!r}")
        # Check everything before adding anything: a module that fails here
        # (a blueprint that doesn't import, a name already taken) must not
        # stay half registered, or register_blueprints trips over it later
        # and the backend doesn't start.
        names = []
        for bp in manifest.blueprints:
            # request.blueprint reports the Blueprint's own name, which is
            # not always the attribute name (health_bp is "health").
            name = self._blueprint(bp).name
            if name in self._bp_to_module or name in names:
                raise ModuleRegistryError(f"Blueprint {name!r} registered twice")
            names.append(name)
        self._modules[manifest.code] = manifest
        for name in names:
            self._bp_to_module[name] = manifest.code

    def validate(self) -> None:
        for m in self._modules.values():
            for dep in m.depends_on:
                if dep not in self._modules:
                    raise ModuleRegistryError(
                        f"Module {m.code!r} depends on unknown module {dep!r}"
                    )
            if m.required:
                for dep in m.depends_on:
                    if not self._modules[dep].required:
                        raise ModuleRegistryError(
                            f"Required module {m.code!r} cannot depend on "
                            f"optional module {dep!r}"
                        )
        # Cycle check (depth-first).
        state: dict[str, int] = {}

        def visit(code: str, path: list[str]) -> None:
            if state.get(code) == 1:
                raise ModuleRegistryError(
                    "Module dependency cycle: " + " -> ".join([*path, code])
                )
            if state.get(code) == 2:
                return
            state[code] = 1
            for dep in self._modules[code].depends_on:
                visit(dep, [*path, code])
            state[code] = 2

        for code in self._modules:
            visit(code, [])

    # ── Lookup ──────────────────────────────────────────────────────────────

    def get(self, code: str) -> Module | None:
        return self._modules.get(code)

    def all(self) -> list[Module]:
        """All modules, dependencies before dependents."""
        ordered: list[Module] = []
        seen: set[str] = set()

        def add(code: str) -> None:
            if code in seen:
                return
            seen.add(code)
            for dep in self._modules[code].depends_on:
                add(dep)
            ordered.append(self._modules[code])

        for code in sorted(self._modules):
            add(code)
        return ordered

    def codes(self) -> list[str]:
        return [m.code for m in self.all()]

    def dependents(self, code: str) -> list[Module]:
        """Modules that list *code* in depends_on (direct only)."""
        return [m for m in self.all() if code in m.depends_on]

    def module_for_blueprint(self, blueprint_name: str | None) -> Module | None:
        if not blueprint_name:
            return None
        # Nested blueprints are named "parent.child"; the parent owns them.
        code = self._bp_to_module.get(blueprint_name.split(".")[0])
        return self._modules.get(code) if code else None

    def subscribers(self, event: str) -> list[tuple[Module, str]]:
        return [(m, m.events[event]) for m in self.all() if event in m.events]

    def app_providers(self) -> list[tuple[Module, AppProvider]]:
        return [(m, a) for m in self.all() for a in m.apps]

    def app_provider(self, code: str) -> tuple[Module, AppProvider] | None:
        return next(((m, a) for m, a in self.app_providers() if a.code == code), None)

    def processes(self) -> dict[str, str]:
        """Long-lived processes of all modules: ``{name: "module.path:fn"}``."""
        out: dict[str, str] = {}
        for module in self.all():
            out.update(module.processes)
        return out

    def task_modules(self) -> list[str]:
        return [t for m in self.all() for t in m.tasks]

    def schedules(self) -> list:
        return [s for m in self.all() for s in m.schedule]

    def tenant_tables(self) -> list[str]:
        tables: list[str] = []
        for m in self.all():
            tables.extend(t for t in m.tables if t not in tables)
        return tables

    # ── Flask wiring ────────────────────────────────────────────────────────

    @staticmethod
    def _blueprint(bp):
        return getattr(importlib.import_module(bp.import_path), bp.attr)

    def register_blueprints(self, app: Flask) -> None:
        from hubra.core.api_areas import canonical_path
        from hubra.core.permissions import register_perm_prefix

        for m in self.all():
            try:
                for bp in m.blueprints:
                    blueprint = self._blueprint(bp)
                    if bp.perm_prefix:
                        register_perm_prefix(blueprint.name, bp.perm_prefix)
                    # A plugin built before the API areas (hubra.core.api_areas)
                    # may still name an old prefix: mount it at the new one.
                    app.register_blueprint(
                        blueprint, url_prefix=canonical_path(bp.url_prefix)
                    )
                    _log.debug("Module %s: registered %s", m.code, bp.attr)
            except Exception as exc:
                # Hubra's own routes must register; a plugin's that can't
                # (say a blueprint name another plugin already took) only
                # loses its routes instead of stopping the backend.
                if not m.plugin:
                    raise
                _log.exception(
                    "Plugin %s: routes of %s not registered", m.plugin, m.code
                )
                from hubra.core.plugins import loader

                spec = loader.current().get(m.plugin)
                if spec is not None:
                    spec.error = spec.error or f"routes: {type(exc).__name__}: {exc}"


registry = ModuleRegistry()
