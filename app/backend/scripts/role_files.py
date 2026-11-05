"""Which backend files each backend role needs: one image per role.

    python scripts/role_files.py <role>            list the files (relative to
                                                   app/backend), one per line
    python scripts/role_files.py <role> --prune    delete the hubra modules the
                                                   role doesn't import (Dockerfile)

Roles: ``app``, ``global``, ``platform`` (their own images) and ``all`` (the
one Compose image, every file). Run from app/backend, or pass ``--root``.

A role's Python code is everything its entry points import, followed through
every ``import`` in the source (also inside functions), so nothing a code
path could import is left out:

- all of ``hubra.core`` (sign-in, models, services, tasks, CLI: every role
  runs them) and the module manifests (``hubra.modules``);
- the blueprint modules of the role's API area, read from the manifests the
  same way ``hubra.core.roles.registers`` picks them at start-up, plus the
  shared ones (probes, version, OAuth metadata).

Everything that isn't a ``hubra`` module (migrations, templates, seed data,
requirements, changelogs) goes into every image. tests/test_role_files.py
starts each role and checks that it imported nothing outside its list.

Only the standard library: images.yml runs this before any install.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROLES = ("app", "global", "platform", "all")

V1 = "/api/v1"
# hubra.core.api_areas / hubra.core.roles: an area is the prefix after /api/v1.
_AREAS = {"platform": f"{V1}/platform", "global": f"{V1}/global"}

# Not part of any image (the Dockerfile copies app/backend/ as it is otherwise).
_SKIP_DIRS = {"tests", "scripts", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache"}


def _load_api_areas(root: Path):
    """hubra.core.api_areas (plain Python, no imports) for the old prefixes."""
    namespace: dict = {"__name__": "hubra_api_areas"}
    path = root / "hubra" / "core" / "api_areas.py"
    exec(compile(path.read_text(), str(path), "exec"), namespace)  # noqa: S102
    return namespace


def area_of(prefix: str, root: Path) -> str:
    """``platform``, ``global`` or ``app`` for a blueprint's URL prefix, as
    ``hubra.core.roles.area_of`` decides it."""
    path = _load_api_areas(root)["canonical_path"](prefix or "/")
    for area, start in _AREAS.items():
        if path == start or path.startswith(start + "/"):
            return area
    return "app"


def _serves(area: str, role: str) -> bool:
    return role == "all" or area == role


# ── Module graph ─────────────────────────────────────────────────────────────


def _modules(root: Path) -> dict[str, Path]:
    """Every module of the hubra package: dotted name -> file."""
    out: dict[str, Path] = {}
    for path in sorted((root / "hubra").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        parts = path.relative_to(root).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out[".".join(parts)] = path
    return out


def _known(name: str, modules: dict[str, Path]) -> str | None:
    """The longest prefix of *name* that is a module (``a.b.func`` -> ``a.b``)."""
    while name:
        if name in modules:
            return name
        name = name.rpartition(".")[0]
    return None


def _imports(name: str, path: Path, modules: dict[str, Path]) -> set[str]:
    """The hubra modules *path* imports, anywhere in the file."""
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join(parts + ([base] if base else []))
            # from x import y: y may be a module of package x.
            names = [base] + [f"{base}.{alias.name}" for alias in node.names]
        else:
            continue
        for imported in names:
            if imported == "hubra" or imported.startswith("hubra."):
                module = _known(imported, modules)
                if module:
                    found.add(module)
    return found


def _closure(starts: set[str], modules: dict[str, Path]) -> set[str]:
    """*starts* and everything they import, with every parent package (an
    import runs the package's ``__init__`` first)."""
    seen: set[str] = set()
    todo = list(starts)
    while todo:
        name = todo.pop()
        if name in seen or name not in modules:
            continue
        seen.add(name)
        parts = name.split(".")
        todo.extend(".".join(parts[:i]) for i in range(1, len(parts)))
        todo.extend(_imports(name, modules[name], modules))
    return seen


# ── Entry points ─────────────────────────────────────────────────────────────


def manifest_blueprints(root: Path) -> list[tuple[str, str, str, bool]]:
    """``(import_path, attr, url_prefix, shared)`` of every ``Blueprint(...)``
    in Hubra's own module manifests (``hubra/modules``)."""
    out = []
    for path in sorted((root / "hubra" / "modules").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", getattr(node.func, "attr", None)) == "Blueprint"
            ):
                continue
            values = [a.value for a in node.args if isinstance(a, ast.Constant)]
            keywords = {
                k.arg: k.value.value for k in node.keywords if isinstance(k.value, ast.Constant)
            }
            fields = dict(zip(("import_path", "attr", "url_prefix"), values))
            fields.update({k: v for k, v in keywords.items() if k in fields})
            if len(fields) < 3 or not str(fields["import_path"]).startswith("hubra."):
                continue
            out.append(
                (
                    fields["import_path"],
                    fields["attr"],
                    fields["url_prefix"],
                    bool(keywords.get("shared", False)),
                )
            )
    return out


def role_blueprints(role: str, root: Path) -> list[tuple[str, str, str, bool]]:
    return [
        bp
        for bp in manifest_blueprints(root)
        if bp[3] or _serves(area_of(bp[2], root), role)
    ]


def role_modules(role: str, root: Path) -> set[str]:
    """The hubra modules a backend in *role* may import."""
    modules = _modules(root)
    if role == "all":
        return set(modules)
    starts = {"hubra"}
    starts.update(n for n in modules if n == "hubra.core" or n.startswith("hubra.core."))
    starts.update(n for n in modules if n == "hubra.modules" or n.startswith("hubra.modules."))
    starts.update(bp[0] for bp in role_blueprints(role, root))
    return _closure(starts, modules)


def role_files(role: str, root: Path) -> list[str]:
    """Every file under *root* that goes into *role*'s image, relative and
    sorted: the role's hubra modules and all other files."""
    modules = _modules(root)
    keep = {modules[name] for name in role_modules(role, root)}
    out = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or _SKIP_DIRS & set(rel.parts[:-1]) or rel.parts[0] in _SKIP_DIRS:
            continue
        if path.suffix == ".py" and rel.parts[0] == "hubra" and path not in keep:
            continue
        out.append(rel.as_posix())
    return out


def prune(role: str, root: Path) -> list[str]:
    """Delete the hubra modules *role* doesn't import; returns them."""
    modules = _modules(root)
    keep = role_modules(role, root)
    gone = []
    for name, path in modules.items():
        if name not in keep:
            path.unlink()
            gone.append(path.relative_to(root).as_posix())
    return sorted(gone)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("role", choices=ROLES)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--prune", action="store_true", help="delete the other modules")
    parser.add_argument("--prefix", default="", help="put this before every listed path")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.prune:
        gone = prune(args.role, root)
        print(f"{args.role}: removed {len(gone)} modules another role needs", file=sys.stderr)
        return 0
    for rel in role_files(args.role, root):
        print(args.prefix + rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
