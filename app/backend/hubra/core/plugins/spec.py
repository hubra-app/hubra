"""Plugin folders: ``plugin.yaml``, validation and the Hubra version range.

A plugin is a folder::

    keys/
        plugin.yaml          # id, name, version, hubra range, package, ...
        hubra_keys/          # the Python package (``package:``)
            __init__.py      # module manifests: ``module = Module(...)``
            models.py        # optional; imported before the app starts
        migrations/          # optional; Alembic revisions of this plugin only
        frontend/dist/plugin.js   # optional; built UI, loaded by the SPA
        CHANGELOG.md         # optional; ``## <version>`` sections
        SIGNATURE.json       # added by ``flask plugins sign``

Everything here reads files only.  No plugin code runs until the signature
has been checked (``trust.verify``) and the loader imports the package.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
PACKAGE_RE = re.compile(r"^hubra_[a-z0-9_]{1,40}$")
MODULE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
MANIFEST = "plugin.yaml"


def hubra_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("hubra")
    except PackageNotFoundError:
        pass
    # Not installed as a distribution (the image copies the source): read
    # pyproject.toml next to the package.
    import tomllib

    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    try:
        return str(tomllib.loads(pyproject.read_text())["project"]["version"])
    except (OSError, KeyError, ValueError):
        return "0"


def compatibility(m: dict) -> tuple[bool, str]:
    """A plugin names the Hubra versions it works with: ``hubra: ">=0.1,<1"``
    (a PEP 440 range).  No range: assumed to work."""
    from packaging.specifiers import InvalidSpecifier, SpecifierSet
    from packaging.version import InvalidVersion, Version

    req = m.get("hubra") if isinstance(m, dict) else None
    if req in (None, ""):
        return True, ""
    try:
        rng = SpecifierSet(str(req))
    except InvalidSpecifier:
        return False, f"hubra: '{req}' isn't a version range like '>=0.1'"
    current = hubra_version()
    try:
        ok = rng.contains(Version(current), prereleases=True)
    except InvalidVersion:
        ok = False
    if ok:
        return True, ""
    return False, f"needs Hubra {req}, this is {current}"


def validate(m: dict, path: Path | None = None) -> str:
    """'' if *m* is a valid plugin.yaml, else what is wrong with it."""
    if not isinstance(m, dict):
        return "plugin.yaml must be a mapping"
    if not ID_RE.match(str(m.get("id", ""))):
        return "id: lowercase letters, digits and dashes"
    if not str(m.get("version", "")).strip():
        return "version is required"
    if not str(m.get("name", "")).strip():
        return "name is required"
    if m.get("hubra") not in (None, ""):
        from packaging.specifiers import InvalidSpecifier, SpecifierSet

        try:
            SpecifierSet(str(m["hubra"]))
        except InvalidSpecifier:
            return f"hubra: '{m['hubra']}' isn't a version range like '>=0.1'"
    pkg = m.get("package")
    if pkg is not None and not PACKAGE_RE.match(str(pkg)):
        return "package: a Python package name starting with hubra_"
    for key in ("modules", "requires"):
        val = m.get(key) or []
        if not isinstance(val, list) or not all(
            isinstance(c, str) and MODULE_RE.match(c) for c in val
        ):
            return f"{key}: a list of module codes like inventory.keys"
    if m.get("modules") and not pkg:
        return "modules need a package that declares them"
    tags = m.get("tags") or []
    if not isinstance(tags, list):
        return "tags: a list"
    if path is not None:
        if pkg and not (path / str(pkg) / "__init__.py").is_file():
            return f"package {pkg}: {pkg}/__init__.py not found"
        mig = m.get("migrations")
        if mig and not (path / str(mig)).is_dir():
            return f"migrations: folder {mig} not found"
        fe = m.get("frontend")
        if fe and (".." in Path(str(fe)).parts or not str(fe).startswith("frontend/")):
            return "frontend: a file under frontend/, e.g. frontend/dist/plugin.js"
    return ""


def read_manifest(path: Path) -> dict:
    try:
        data = yaml.safe_load((path / MANIFEST).read_text()) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{MANIFEST}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{MANIFEST} must be a mapping")
    return data


@dataclass
class Spec:
    """One plugin folder found on disk (loaded or not)."""

    id: str
    path: Path
    manifest: dict
    bundled: bool = False  # shipped in the image / a development checkout
    trust: dict = field(
        default_factory=lambda: {
            "status": "unsigned",
            "signer": "",
            "key_id": "",
            "detail": "",
        }
    )
    error: str = ""
    loaded: bool = False
    modules: list = field(default_factory=list)  # Module manifests once loaded

    @property
    def name(self) -> str:
        return str(self.manifest.get("name", self.id))

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", ""))

    @property
    def package(self) -> str | None:
        pkg = self.manifest.get("package")
        return str(pkg) if pkg else None

    @property
    def module_codes(self) -> list[str]:
        return [str(c) for c in self.manifest.get("modules") or []]

    @property
    def requires(self) -> list[str]:
        return [str(c) for c in self.manifest.get("requires") or []]

    @property
    def migrations_dir(self) -> Path | None:
        mig = self.manifest.get("migrations")
        if not mig:
            return None
        d = self.path / str(mig)
        return d if d.is_dir() else None

    @property
    def frontend_file(self) -> Path | None:
        fe = self.manifest.get("frontend")
        if not fe:
            return None
        f = self.path / str(fe)
        return f if f.is_file() else None

    @property
    def frontend_tag(self) -> str | None:
        """Changes whenever the built frontend does; the app adds it to the URL."""
        f = self.frontend_file
        if f is None:
            return None
        st = f.stat()
        return f"{self.version}-{st.st_size:x}{int(st.st_mtime):x}"

    @property
    def version_table(self) -> str:
        return "alembic_version_" + self.id.replace("-", "_")

    def changelog(self) -> str:
        f = self.path / "CHANGELOG.md"
        return f.read_text() if f.is_file() else ""

    def as_dict(self) -> dict:
        m = self.manifest
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": str(m.get("description", "")),
            "author": str(m.get("author", "")),
            "homepage": str(m.get("homepage", "")),
            "license": str(m.get("license", "")),
            "tags": list(m.get("tags") or []),
            "hubra": str(m.get("hubra") or ""),
            "modules": self.module_codes,
            "requires": self.requires,
            "bundled": self.bundled,
            "trust": dict(self.trust),
            "loaded": self.loaded,
            "error": self.error,
            "hasFrontend": self.frontend_file is not None,
        }


def scan(root: Path, bundled: bool) -> list[Spec]:
    """Every plugin folder directly under *root* (hidden folders skipped)."""
    out: list[Spec] = []
    if not root or not root.is_dir():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if d.name.startswith((".", "_")) or not (d / MANIFEST).is_file():
            continue
        try:
            m = read_manifest(d)
        except ValueError as exc:
            out.append(
                Spec(id=d.name, path=d, manifest={}, bundled=bundled, error=str(exc))
            )
            continue
        problem = validate(m, d)
        spec = Spec(
            id=str(m.get("id") or d.name),
            path=d,
            manifest=m,
            bundled=bundled,
            error=problem,
        )
        out.append(spec)
    return out
