"""Import rules that keep the shared code separable from the API areas.

``hubra.core`` is the library every backend shares (app, global and
platform): models, migrations, sign-in and tokens, permissions, settings,
notifications. ``hubra.api`` holds the routes of the API areas
(hubra.core.api_areas). Code goes one way only: the API may import core,
core never imports the API. That is what lets each area become an image of
its own, built only when its code or core changes.

The check reads every import, also the ones inside functions, so a lazy
import does not slip past it.

``CORE_TO_API_LEFT`` lists the core modules that still import club code from
the API. It may only shrink: a new entry fails, and so does an entry that
no longer imports the API (delete it then).
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
HUBRA = BACKEND / "hubra"

# Old names of modules that moved to core, kept only so that plugins built
# against older Hubra versions still import them. Hubra's own code uses the
# new names.
PLUGIN_ALIASES = {
    "hubra.api.permissions": "hubra.core.permissions",
    "hubra.api.utils": "hubra.core.utils",
    "hubra.api.auth.helpers": "hubra.core.auth.helpers",
    "hubra.api.notifications.services": "hubra.core.notifications.services",
}

# Core modules that still use club (app area) code from the API: club
# schemas, the starter data of a new club, club tasks. They move to the app
# area with the split into one image per area.
CORE_TO_API_LEFT = {
    "hubra.core.pricing": {"hubra.api.finance.fee_basis"},
    "hubra.core.schemas.event": {"hubra.api.events.services"},
    "hubra.core.schemas.member": {"hubra.api.tiers.plans"},
    "hubra.core.schemas.poll": {"hubra.api.polls.services"},
    "hubra.core.seeds": {
        "hubra.api.finance.services",
        "hubra.api.functions.services",
        "hubra.api.groups.services",
    },
    "hubra.core.services.data_requests": {"hubra.api.members.services"},
    "hubra.core.tasks.finance_tasks": {
        "hubra.api.finance.recurring",
        "hubra.api.finance.services",
        "hubra.api.finance.statement",
    },
    "hubra.core.tasks.mail_sync": {"hubra.api.mail.services"},
    "hubra.core.tasks.reminder_tasks": {
        "hubra.api.events.services",
        "hubra.api.polls.services",
    },
}


def _module_name(path: Path) -> str:
    parts = path.relative_to(BACKEND).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports(path: Path) -> set[str]:
    """Every module *path* imports, at any depth, as absolute names."""
    name = _module_name(path)
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found: set[str] = set()
    with warnings.catch_warnings():  # not ours to report (escapes in tests)
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - node.level + 1]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            found.add(module)
            # "from hubra.api.x import y" may import the module hubra.api.x.y
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def _modules(root: Path) -> dict[str, set[str]]:
    return {_module_name(p): _imports(p) for p in sorted(root.rglob("*.py"))}


def _api_modules(imports: set[str]) -> set[str]:
    """The hubra.api modules among *imports* (names imported from a module
    collapse into that module)."""
    modules = {_module_name(p) for p in (HUBRA / "api").rglob("*.py")}
    out = set()
    for name in imports:
        if not name.startswith("hubra.api."):
            continue
        while name and name not in modules:
            name = name.rpartition(".")[0]
        if name and name != "hubra.api":
            out.add(name)
    return out


@pytest.fixture(scope="module")
def core_imports() -> dict[str, set[str]]:
    return _modules(HUBRA / "core")


def test_core_does_not_import_the_api(core_imports):
    found = {
        module: api
        for module, imports in core_imports.items()
        if (api := _api_modules(imports))
    }
    new = {
        module: sorted(api - CORE_TO_API_LEFT.get(module, set()))
        for module, api in found.items()
        if api - CORE_TO_API_LEFT.get(module, set())
    }
    assert not new, (
        "hubra.core must not import hubra.api (shared code must not depend on "
        "an API area). Move what core needs into core, or the caller into the "
        f"API: {new}"
    )


def test_the_list_of_core_to_api_imports_only_shrinks(core_imports):
    stale = {
        module: sorted(api - _api_modules(core_imports.get(module, set())))
        for module, api in CORE_TO_API_LEFT.items()
        if api - _api_modules(core_imports.get(module, set()))
    }
    assert not stale, (
        "These no longer import the API: remove them from CORE_TO_API_LEFT "
        f"in {Path(__file__).name}: {stale}"
    )


def test_hubra_uses_the_new_names_of_moved_modules():
    alias_files = {HUBRA / (name.replace(".", "/") + ".py") for name in PLUGIN_ALIASES}
    offenders = {}
    for root in (HUBRA, BACKEND / "tests"):
        for path in sorted(root.rglob("*.py")):
            if path in alias_files:
                continue
            old = {
                name
                for name in _imports(path)
                for alias in PLUGIN_ALIASES
                if name == alias or name.startswith(alias + ".")
            }
            if old:
                offenders[str(path.relative_to(BACKEND))] = sorted(old)
    assert not offenders, (
        "Use the new module names (the old ones are only for plugins): "
        f"{PLUGIN_ALIASES} - found in {offenders}"
    )


@pytest.mark.parametrize(("old", "new"), sorted(PLUGIN_ALIASES.items()))
def test_plugin_aliases_are_the_moved_modules(old, new):
    import importlib

    assert importlib.import_module(old) is importlib.import_module(new)
