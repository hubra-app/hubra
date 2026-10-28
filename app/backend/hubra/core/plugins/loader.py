"""Finding and loading plugins at startup.

Every process (gunicorn worker, Celery worker, beat, ``flask`` command)
does the same on start:

1. Read which plugins are installed (``installed_plugins``).
2. Unpack each downloaded or uploaded plugin from its archive in the
   database into the local plugin folder, unless the right version is
   already there, and check its signature.
3. Import the package of every installed plugin, and of bundled plugins
   listed in ``PLUGINS_AUTOINSTALL``, and add their module manifests to
   the module registry.

A plugin that fails any step is skipped and logged; the rest of Hubra and
the other plugins start as usual.
"""

from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import importlib
import importlib.util
import logging
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, has_app_context

from .spec import Spec, compatibility, scan

_log = logging.getLogger(__name__)


def stamp_file(root: Path, pid: str) -> Path:
    """Which archive ``root/<pid>`` was unpacked from.  Kept outside the
    plugin's folder, which its signature covers."""
    return root / f".{pid}.archive-sha256"


@dataclasses.dataclass
class PluginSet:
    """What this process found and loaded."""

    specs: dict[str, Spec] = dataclasses.field(default_factory=dict)
    generation: int = 0
    autoinstalled: set[str] = dataclasses.field(default_factory=set)
    # Installed (or auto-installed): the plugins this process tries to load.
    wanted: set[str] = dataclasses.field(default_factory=set)

    def loaded(self) -> list[Spec]:
        return [s for s in self.specs.values() if s.loaded]

    def get(self, pid: str) -> Spec | None:
        return self.specs.get(pid)

    def for_module(self, code: str) -> Spec | None:
        for s in self.specs.values():
            if s.loaded and code in s.module_codes:
                return s
        return None


# One per process, like the module registry it feeds.
_current = PluginSet()


def current() -> PluginSet:
    return _current


# ── Folders ──────────────────────────────────────────────────────────────────


def bundled_dirs(app=None) -> list[Path]:
    """Folders of plugins shipped with this copy: BUNDLED_PLUGIN_DIR (several
    separated by os.pathsep), else the plugins/ folder of the checkout or image."""
    app = app or current_app
    configured = app.config.get("BUNDLED_PLUGIN_DIR") or ""
    if configured:
        return [Path(p) for p in configured.split(os.pathsep) if p]
    here = Path(__file__).resolve()
    # A checkout: <repo>/app/backend/hubra/core/plugins -> <repo>/plugins.
    # The image: /app/hubra/core/plugins -> /app/plugins.
    for up in (5, 3):
        if len(here.parents) > up and (here.parents[up] / "plugins").is_dir():
            return [here.parents[up] / "plugins"]
    return []


def plugin_dir(app=None) -> Path:
    app = app or current_app
    d = Path(
        app.config.get("PLUGIN_DIR")
        or Path(tempfile.gettempdir()) / f"hubra-plugins-{os.getuid()}"
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def _folder_lock(root: Path):
    """Several workers of one pod share the plugin folder: unpack one at a time."""
    with open(root / ".lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def autoinstall(app=None) -> set[str] | str:
    raw = str((app or current_app).config.get("PLUGINS_AUTOINSTALL") or "").strip()
    if raw == "all":
        return "all"
    return {p.strip() for p in raw.split(",") if p.strip()}


# ── Unpacking ────────────────────────────────────────────────────────────────


def materialize(row, root: Path) -> Path:
    """Make ``root/<id>`` hold the archive *row* names; return that folder."""
    from hubra.core.extensions import db
    from hubra.core.models.plugin import PluginArchive

    from .installer import InstallError, safe_extract

    dest = root / row.id
    stamp = stamp_file(root, row.id)
    if (
        dest.is_dir()
        and stamp.is_file()
        and stamp.read_text().strip() == row.archive_sha256
    ):
        return dest
    archive = db.session.scalar(
        db.select(PluginArchive).where(PluginArchive.sha256 == row.archive_sha256)
    )
    if archive is None:
        raise InstallError(f"the archive of {row.id} {row.version} is missing")
    if hashlib.sha256(archive.data).hexdigest() != row.archive_sha256:
        raise InstallError(f"the archive of {row.id} {row.version} is damaged")
    tmp = Path(tempfile.mkdtemp(prefix=f".{row.id}-", dir=root))
    try:
        pdir = safe_extract(archive.data, tmp / "x")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(pdir), dest)
        stamp.write_text(row.archive_sha256)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dest


def _installed_rows():
    from hubra.core.extensions import db
    from hubra.core.models.plugin import InstalledPlugin

    try:
        return list(db.session.scalars(db.select(InstalledPlugin)))
    except Exception:  # no database yet, or before the migration
        db.session.rollback()
        _log.info("Plugins: no installed_plugins table yet; loading none")
        return []


def read_generation() -> int:
    from hubra.core.extensions import db
    from hubra.core.models.plugin import PluginState

    try:
        row = db.session.get(PluginState, "generation")
    except Exception:
        db.session.rollback()
        return 0
    try:
        return int(row.value) if row is not None else 0
    except ValueError:
        return 0


def discover(app=None) -> PluginSet:
    """Find every plugin this process could load, and decide which to load.

    Unpacks installed archives on the way.  Imports nothing.
    """
    from .trust import verify
    from .installer import community_keys

    app = app or current_app
    found = PluginSet()
    for spec in [s for root in bundled_dirs(app) for s in scan(root, bundled=True)]:
        spec.trust = {
            "status": "bundled",
            "signer": "Hubra",
            "key_id": "",
            "detail": "shipped with Hubra",
        }
        found.specs[spec.id] = spec

    rows = _installed_rows()
    want = found.wanted
    auto = autoinstall(app)
    for spec in found.specs.values():
        if auto == "all" or spec.id in auto:
            want.add(spec.id)
            found.autoinstalled.add(spec.id)

    root = plugin_dir(app)
    keys = community_keys() if rows else {}
    for row in rows:
        want.add(row.id)
        if row.source != "archive":
            if row.id not in found.specs:
                _log.warning("Plugin %s is installed but not shipped here", row.id)
            continue
        try:
            with _folder_lock(root):
                pdir = materialize(row, root)
        except Exception as exc:
            _log.error("Plugin %s: unpacking failed: %s", row.id, exc)
            found.specs[row.id] = Spec(
                id=row.id, path=root / row.id, manifest={}, error=f"unpacking: {exc}"
            )
            continue
        specs = scan(root, bundled=False)
        spec = next((s for s in specs if s.path == pdir), None)
        if spec is None:
            continue
        if not spec.error:
            spec.trust = verify(pdir, spec.manifest, keys)
            status = spec.trust["status"]
            if spec.id != row.id:
                spec.error = f"the archive holds {spec.id}, not {row.id}"
            elif status == "invalid":
                spec.error = f"signature: {spec.trust['detail']}"
            elif status == "unsigned" and row.trust != "unsigned":
                spec.error = "not signed, and nobody accepted it unsigned"
        # An installed copy replaces the bundled one (an update of it).
        found.specs[row.id] = spec

    for spec in found.specs.values():
        if spec.id not in want or spec.error:
            continue
        ok, why = compatibility(spec.manifest)
        if not ok:
            spec.error = why
    found.generation = read_generation() if rows else 0
    found.specs = dict(sorted(found.specs.items()))
    return found


# ── Importing ────────────────────────────────────────────────────────────────


def _import(spec: Spec) -> list:
    """Import the plugin's package and return its Module manifests."""
    from hubra.core.modules.base import Module

    pkg = spec.package
    if not pkg:
        return []
    path = str(spec.path)
    if not spec.bundled:
        # Only the signed sources may run: drop any bytecode next to them.
        for cache in spec.path.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
    # Appended, never first: a plugin can't shadow Hubra or a library by
    # shipping a module with its name, and its own package must come from
    # its own directory.
    if path not in sys.path:
        sys.path.append(path)
    found = importlib.util.find_spec(pkg)
    places = list(found.submodule_search_locations or []) if found else []
    if found is not None and found.origin and not places:
        places = [found.origin]
    if not places or not all(
        os.path.realpath(p).startswith(os.path.realpath(path) + os.sep)
        for p in places
    ):
        raise ValueError(f"package {pkg!r} is not the plugin's own (name taken)")
    mod = importlib.import_module(pkg)
    modules = []
    for attr in ("module", "modules"):
        val = getattr(mod, attr, None)
        if isinstance(val, Module):
            modules.append(val)
        elif isinstance(val, (list, tuple)):
            modules.extend(m for m in val if isinstance(m, Module))
    codes = sorted(m.code for m in modules)
    if codes != sorted(spec.module_codes):
        raise ValueError(
            f"plugin.yaml lists modules {sorted(spec.module_codes)}, "
            f"the package declares {codes}"
        )
    try:
        importlib.import_module(f"{pkg}.models")
    except ModuleNotFoundError as exc:
        if exc.name != f"{pkg}.models":
            raise
    return [dataclasses.replace(m, plugin=spec.id) for m in modules]


def load(registry, app=None) -> PluginSet:
    """Discover plugins and add the installed ones to *registry*."""
    global _current
    app = app or (current_app if has_app_context() else None)
    if app is None:
        return _current
    found = discover(app)
    want = found.wanted
    known = set(registry.codes()) if hasattr(registry, "codes") else set()
    # Load in dependency order: a plugin whose required modules come from
    # another plugin waits for it.
    pending = [found.specs[p] for p in sorted(want) if p in found.specs]
    progress = True
    while pending and progress:
        progress = False
        for spec in list(pending):
            if spec.error:
                pending.remove(spec)
                continue
            if any(code not in known for code in spec.requires):
                continue
            pending.remove(spec)
            progress = True
            try:
                modules = _import(spec)
                for m in modules:
                    registry.add(m)
            except Exception as exc:
                _log.exception("Plugin %s failed to load", spec.id)
                spec.error = f"{type(exc).__name__}: {exc}"
                continue
            spec.modules = modules
            spec.loaded = True
            known.update(m.code for m in modules)
    for spec in pending:
        missing = [c for c in spec.requires if c not in known]
        spec.error = spec.error or f"needs the module(s) {', '.join(missing)}"
    for spec in found.specs.values():
        if spec.error and spec.id in want:
            _log.error("Plugin %s not loaded: %s", spec.id, spec.error)
        elif spec.loaded:
            _log.info("Plugin %s %s loaded", spec.id, spec.version)
    _current = found
    return found
