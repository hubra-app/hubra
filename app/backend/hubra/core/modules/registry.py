"""Module registry: discovers manifests and registers their blueprints.

Every package under ``hubra.modules`` exposes a ``module`` manifest.
The registry imports them once, checks dependencies, and is the single
place that knows which blueprint belongs to which module.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil

from flask import Flask

from .base import Module

_log = logging.getLogger(__name__)


class ModuleRegistryError(RuntimeError):
    pass


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, Module] = {}
        self._bp_to_module: dict[str, str] = {}
        self._bp_canonical: dict[str, str] = {}
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
        self.validate()
        self._loaded = True

    def add(self, manifest: Module) -> None:
        if manifest.code in self._modules:
            raise ModuleRegistryError(f"Duplicate module code {manifest.code!r}")
        self._modules[manifest.code] = manifest
        for bp in manifest.blueprints:
            # request.blueprint reports the Blueprint's own name, which is
            # not always the attribute name (health_bp is "health").
            name = self._blueprint(bp).name
            for registered in (name, *(n for _, n in bp.v2)):
                if registered in self._bp_to_module:
                    raise ModuleRegistryError(
                        f"Blueprint {registered!r} registered twice"
                    )
                self._bp_to_module[registered] = manifest.code
                self._bp_canonical[registered] = name

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

    def canonical_blueprint(self, blueprint_name: str | None) -> str | None:
        """Map a v2 registration name back to the v1 blueprint name."""
        if not blueprint_name:
            return blueprint_name
        return self._bp_canonical.get(blueprint_name, blueprint_name)

    def subscribers(self, event: str) -> list[tuple[Module, str]]:
        return [(m, m.events[event]) for m in self.all() if event in m.events]

    def task_modules(self) -> list[str]:
        return [t for m in self.all() for t in m.tasks]

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
        for m in self.all():
            for bp in m.blueprints:
                blueprint = self._blueprint(bp)
                app.register_blueprint(blueprint, url_prefix=bp.url_prefix)
                for prefix, name in bp.v2:
                    app.register_blueprint(blueprint, url_prefix=prefix, name=name)
                _log.debug("Module %s: registered %s", m.code, bp.attr)


registry = ModuleRegistry()
