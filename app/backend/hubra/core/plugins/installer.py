"""Installing, updating and removing plugins: from a signed repository or an upload.

Ported from labdex (same archive, signature and index formats), changed for
a platform that runs as several processes and pods:

- An install goes through a staging step.  The archive is unpacked
  safely, the manifest validated and the signature checked **without
  running any plugin code**; the manager sees the result and confirms.
  Unsigned plugins need an explicit "accept unsigned"; plugins with an
  invalid signature are refused.
- Staged and installed archives are kept in the database
  (``plugin_archives``), not on a shared disk, so every pod can unpack
  them on start and a confirm may reach another pod than the upload.
- Confirming runs the plugin's migrations (public schema and every club),
  records it in ``installed_plugins`` and bumps the plugin generation;
  every process then reloads (``reload.py``).
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import logging
import os
import shutil
import socket
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from hubra.core.extensions import db

from .spec import MANIFEST, Spec, compatibility, read_manifest, validate
from .trust import SKIP_DIRS, load_public, verify

_log = logging.getLogger(__name__)

MAX_ZIP = 20 * 1024 * 1024
MAX_FILES = 2000
MAX_UNPACKED = 80 * 1024 * 1024
STAGE_TTL = timedelta(hours=1)


class InstallError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def community_keys() -> dict:
    """Keys trusted besides the official ones: added by hand, and those of the repositories."""
    from hubra.core.models.plugin import PluginRepository, TrustedKey

    out = {}
    try:
        keys = list(db.session.scalars(select(TrustedKey)))
        repos = list(
            db.session.scalars(
                select(PluginRepository).where(PluginRepository.enabled.is_(True))
            )
        )
    except Exception:
        db.session.rollback()
        return out
    for k in keys:
        try:
            out[k.key_id] = (k.name, load_public(k.public_key))
        except (ValueError, TypeError):
            continue
    for r in repos:
        try:
            out.setdefault(r.key_id, (r.name, load_public(r.public_key)))
        except (ValueError, TypeError):
            continue
    return out


# ── Archives ─────────────────────────────────────────────────────────────────


def _unhashed(name: str) -> bool:
    """Paths the signature leaves out: bytecode, caches, VCS and node_modules."""
    parts = [p for p in name.replace("\\", "/").split("/") if p]
    return any(
        p in SKIP_DIRS or p.endswith((".pyc", ".pyo")) for p in parts
    )


def safe_extract(blob: bytes, dest: Path) -> Path:
    """Unpack a plugin zip into *dest*; return the folder holding plugin.yaml."""
    if len(blob) > MAX_ZIP:
        raise InstallError(f"archive is larger than {MAX_ZIP // 1024 // 1024} MB")
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as exc:
        raise InstallError("not a zip file") from exc
    infos = zf.infolist()
    if len(infos) > MAX_FILES:
        raise InstallError("too many files in the archive")
    if sum(i.file_size for i in infos) > MAX_UNPACKED:
        raise InstallError("archive unpacks to too much data")
    dest.mkdir(parents=True, exist_ok=True)
    written = 0
    for i in infos:
        name = i.filename
        if name.startswith(("/", "\\")) or ".." in Path(name).parts or ":" in name:
            raise InstallError(f"unsafe path in archive: {name}")
        if (i.external_attr >> 16) & 0o170000 == 0o120000:
            raise InstallError(f"symlinks aren't allowed: {name}")
        if _unhashed(name):
            # The signature doesn't cover these (trust.file_hashes skips them),
            # and Python would run a .pyc instead of the signed .py next to it.
            raise InstallError(f"compiled or tooling files aren't allowed: {name}")
        target = (dest / name).resolve()
        if not target.is_relative_to(dest.resolve()):
            raise InstallError(f"unsafe path in archive: {name}")
        if i.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(i) as src, open(target, "wb") as out:
            while chunk := src.read(65536):
                written += len(chunk)
                if written > MAX_UNPACKED:  # sizes in the zip's directory can lie
                    raise InstallError("archive unpacks to too much data")
                out.write(chunk)
    # plugin.yaml at the top, or inside a single top-level folder
    if (dest / MANIFEST).is_file():
        return dest
    subs = [
        p for p in dest.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))
    ]
    if len(subs) == 1 and (subs[0] / MANIFEST).is_file():
        return subs[0]
    raise InstallError("no plugin.yaml in the archive")


def _inspect(blob: bytes, tmp: Path) -> tuple[Path, dict, dict]:
    """Unpack, validate and check the signature.  Runs no plugin code."""
    pdir = safe_extract(blob, tmp / "x")
    try:
        manifest = read_manifest(pdir)
    except ValueError as exc:
        raise InstallError(str(exc)) from exc
    problem = validate(manifest, pdir)
    if problem:
        raise InstallError(problem)
    ok, why = compatibility(manifest)
    if not ok:
        raise InstallError(f"{manifest['id']} {manifest.get('version', '')}: {why}")
    trust = verify(pdir, manifest, community_keys())
    return pdir, manifest, trust


def _store_archive(pid: str, version: str, blob: bytes) -> str:
    from hubra.core.models.plugin import PluginArchive

    sha = hashlib.sha256(blob).hexdigest()
    if (
        db.session.scalar(select(PluginArchive).where(PluginArchive.sha256 == sha))
        is None
    ):
        db.session.add(
            PluginArchive(plugin_id=pid, version=version, sha256=sha, data=blob)
        )
        db.session.flush()
    return sha


def _archive(sha: str):
    from hubra.core.models.plugin import PluginArchive

    return db.session.scalar(select(PluginArchive).where(PluginArchive.sha256 == sha))


def cleanup_archives() -> int:
    """Delete staged archives nobody confirmed within an hour."""
    from hubra.core.models.plugin import InstalledPlugin, PluginArchive

    keep = set()
    for row in db.session.scalars(select(InstalledPlugin)):
        keep.update(s for s in (row.archive_sha256, row.previous_sha256) if s)
    old = db.session.scalars(
        select(PluginArchive).where(PluginArchive.created_at < _now() - STAGE_TTL)
    ).all()
    gone = 0
    for a in old:
        if a.sha256 not in keep:
            db.session.delete(a)
            gone += 1
    return gone


# ── Staging ──────────────────────────────────────────────────────────────────


def _loaded():
    from . import loader

    return loader.current()


def stage(
    blob: bytes, source: str = "upload", repository_id: int | None = None
) -> dict:
    """Check an archive and keep it for confirmation.  Returns what the
    manager is about to install; ``token`` confirms it."""
    with tempfile.TemporaryDirectory() as tmp:
        pdir, manifest, trust = _inspect(blob, Path(tmp))
        files = sorted(
            p.relative_to(pdir).as_posix() for p in pdir.rglob("*") if p.is_file()
        )
        has_frontend = (
            bool(manifest.get("frontend"))
            and (pdir / str(manifest["frontend"])).is_file()
        )
        has_migrations = bool(manifest.get("migrations"))
    pid = str(manifest["id"])
    cur = _installed_row(pid)
    sha = _store_archive(pid, str(manifest.get("version", "")), blob)
    db.session.commit()
    return {
        "token": sha,
        "id": pid,
        "name": manifest.get("name", pid),
        "version": str(manifest.get("version", "")),
        "description": manifest.get("description", ""),
        "author": manifest.get("author", ""),
        "homepage": manifest.get("homepage", ""),
        "license": manifest.get("license", ""),
        "tags": manifest.get("tags") or [],
        "modules": manifest.get("modules") or [],
        "requires": manifest.get("requires") or [],
        "trust": trust,
        "source": source,
        "repositoryId": repository_id,
        "installedVersion": cur.version if cur else None,
        "migrations": has_migrations,
        "frontend": has_frontend,
        "files": files[:200],
        "installable": trust["status"] != "invalid",
        "needsConfirmation": trust["status"] == "unsigned",
    }


def discard_stage(token: str) -> None:
    from hubra.core.models.plugin import InstalledPlugin

    a = _archive(token)
    if a is None:
        return
    used = db.session.scalar(
        select(InstalledPlugin).where(
            (InstalledPlugin.archive_sha256 == token)
            | (InstalledPlugin.previous_sha256 == token)
        )
    )
    if used is None:
        db.session.delete(a)
        db.session.commit()


# ── Installed state ──────────────────────────────────────────────────────────


def _installed_row(pid: str):
    from hubra.core.models.plugin import InstalledPlugin

    return db.session.get(InstalledPlugin, pid)


def installed_rows() -> list:
    from hubra.core.models.plugin import InstalledPlugin

    return list(
        db.session.scalars(select(InstalledPlugin).order_by(InstalledPlugin.id))
    )


def bump_generation() -> int:
    from hubra.core.models.plugin import PluginState

    row = db.session.get(PluginState, "generation")
    if row is None:
        row = PluginState(key="generation", value="0")
        db.session.add(row)
    try:
        value = int(row.value or 0) + 1
    except ValueError:
        value = 1
    row.value = str(value)
    db.session.flush()
    return value


def _audit(action: str, pid: str, details: dict) -> None:
    from flask import g

    from hubra.core.models.tenant import GlobalAuditEntry

    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=getattr(getattr(g, "system_user", None), "id", None),
            action=action,
            target_type="plugin",
            target_id=pid,
            details=details,
        )
    )


def _available_modules(excluding: str | None = None) -> set[str]:
    """Module codes Hubra has, plus those of other installed plugins."""
    from hubra.core.modules import registry

    registry.load()
    codes = {m.code for m in registry.all() if m.plugin is None}
    plugins = _loaded()
    for row in installed_rows():
        if row.id == excluding:
            continue
        spec = plugins.get(row.id)
        if spec is not None:
            codes.update(spec.module_codes)
    for pid in plugins.autoinstalled:
        if pid != excluding and plugins.get(pid):
            codes.update(plugins.get(pid).module_codes)
    return codes


def _check_requires(manifest: dict) -> None:
    have = _available_modules(excluding=str(manifest.get("id")))
    missing = [c for c in manifest.get("requires") or [] if c not in have]
    if missing:
        raise InstallError(
            f"{manifest.get('name', manifest.get('id'))} needs {', '.join(missing)}: "
            "install the plugin that provides it first"
        )


def _actor() -> str:
    from flask import g

    user = getattr(g, "system_user", None)
    return str(getattr(user, "email", "") or getattr(user, "id", "") or "cli")


def confirm(
    token: str, accept_unsigned: bool, repository_id: int | None = None
) -> dict:
    """Install the staged archive *token* for the whole platform."""
    from hubra.core.models.plugin import InstalledPlugin

    from . import loader, migrate

    archive = _archive(token)
    if archive is None:
        raise InstallError("this upload expired; upload it again")
    root = loader.plugin_dir()
    with tempfile.TemporaryDirectory(dir=root) as tmp:
        pdir, manifest, trust = _inspect(archive.data, Path(tmp))
        if trust["status"] == "invalid":
            raise InstallError(f"refused: {trust['detail']}")
        if trust["status"] == "unsigned" and not accept_unsigned:
            raise InstallError(
                "the plugin isn't signed; confirm that you trust its author"
            )
        pid = str(manifest["id"])
        if pid in _loaded().autoinstalled:
            raise InstallError(f"'{pid}' is loaded from a development checkout here")
        _check_requires(manifest)
        spec = Spec(id=pid, path=pdir, manifest=manifest, trust=trust)
        # Migrations first: if they fail nothing is recorded as installed.
        try:
            migrate.upgrade_everywhere(spec)
        except Exception as exc:
            db.session.rollback()
            raise InstallError(f"its migrations failed: {exc}") from exc
        # Keep the unpacked copy so this process needs no second unpack.
        dest = root / pid
        with loader._folder_lock(root):
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(pdir), dest)
            loader.stamp_file(root, pid).write_text(token)

    row = db.session.get(InstalledPlugin, pid)
    before = row.version if row else None
    if row is None:
        row = InstalledPlugin(id=pid, installed_at=_now())
        db.session.add(row)
    elif row.archive_sha256 and row.archive_sha256 != token:
        row.previous_sha256 = row.archive_sha256
    row.name = str(manifest.get("name", pid))
    row.version = str(manifest.get("version", ""))
    row.source = "archive"
    row.origin = "upload" if repository_id is None else ""
    if repository_id is not None:
        from hubra.core.models.plugin import PluginRepository

        repo = db.session.get(PluginRepository, repository_id)
        row.origin = repo.name if repo else ""
    row.repository_id = repository_id
    row.trust = trust["status"]
    row.signer = trust.get("signer", "")
    row.key_id = trust.get("key_id", "")
    row.archive_sha256 = token
    row.installed_by = _actor()
    row.error = ""
    generation = bump_generation()
    _audit(
        "update_plugin" if before else "install_plugin",
        pid,
        {"version": row.version, "from": before, "trust": row.trust},
    )
    db.session.commit()
    return {
        "id": pid,
        "version": row.version,
        "previous": before,
        "generation": generation,
    }


def install_bundled(pid: str) -> dict:
    """Install a plugin that ships with this Hubra (nothing to download)."""
    from hubra.core.models.plugin import InstalledPlugin

    from . import migrate

    spec = _loaded().get(pid)
    if spec is None or not spec.bundled:
        raise InstallError(f"'{pid}' doesn't ship with this Hubra")
    if spec.error and not spec.manifest:
        raise InstallError(spec.error)
    problem = validate(spec.manifest, spec.path)
    if problem:
        raise InstallError(problem)
    ok, why = compatibility(spec.manifest)
    if not ok:
        raise InstallError(why)
    row = db.session.get(InstalledPlugin, pid)
    if row is not None and row.source == "bundled":
        raise InstallError(f"{spec.name} is installed already")
    _check_requires(spec.manifest)
    try:
        migrate.upgrade_everywhere(spec)
    except Exception as exc:
        db.session.rollback()
        raise InstallError(f"its migrations failed: {exc}") from exc
    if row is None:
        row = InstalledPlugin(id=pid, installed_at=_now())
        db.session.add(row)
    elif row.archive_sha256:
        # Going back from a downloaded update to the shipped copy.
        row.previous_sha256 = row.archive_sha256
    row.name, row.version = spec.name, spec.version
    row.source, row.origin, row.repository_id = "bundled", "shipped with Hubra", None
    row.trust, row.signer, row.key_id = "bundled", "Hubra", ""
    row.archive_sha256 = None
    row.installed_by = _actor()
    row.error = ""
    generation = bump_generation()
    _audit("install_plugin", pid, {"version": row.version, "trust": "bundled"})
    db.session.commit()
    return {"id": pid, "version": row.version, "generation": generation}


def rollback(pid: str) -> dict:
    """Go back to the version an update replaced (and forward again the same way).

    Migrations are not undone: plugin migrations must keep the previous
    version working (add columns and tables; drop them a release later).
    """
    row = _installed_row(pid)
    if row is None:
        raise InstallError(f"'{pid}' isn't installed")
    if not row.previous_sha256 or _archive(row.previous_sha256) is None:
        raise InstallError(f"no earlier version of '{pid}' is kept")
    prev = _archive(row.previous_sha256)
    with tempfile.TemporaryDirectory() as tmp:
        _pdir, manifest, trust = _inspect(prev.data, Path(tmp))
    if trust["status"] == "invalid":
        raise InstallError(f"the earlier version is refused: {trust['detail']}")
    before = row.version
    row.archive_sha256, row.previous_sha256 = row.previous_sha256, row.archive_sha256
    row.version = str(manifest.get("version", ""))
    row.trust, row.signer, row.key_id = (
        trust["status"],
        trust.get("signer", ""),
        trust.get("key_id", ""),
    )
    row.source = "archive"
    row.error = ""
    generation = bump_generation()
    _audit("rollback_plugin", pid, {"from": before, "to": row.version})
    db.session.commit()
    return {
        "id": pid,
        "version": row.version,
        "previous": before,
        "generation": generation,
    }


def dependents(pid: str) -> list[str]:
    """Installed plugins that need a module of *pid*."""
    plugins = _loaded()
    spec = plugins.get(pid)
    codes = set(spec.module_codes) if spec else set()
    out = []
    for row in installed_rows():
        other = plugins.get(row.id)
        if row.id != pid and other is not None and codes & set(other.requires):
            out.append(other.name)
    return out


def uninstall(pid: str, delete_data: bool = False) -> dict:
    """Remove a plugin from the platform.

    Its modules disappear for every club.  Its tables and the clubs'
    module settings stay unless *delete_data*: then its migrations are run
    down to nothing in every club and the public schema.
    """
    from hubra.core.models.feature import Feature, TenantFeature
    from hubra.core.models.plugin import PluginArchive

    from . import migrate

    row = _installed_row(pid)
    plugins = _loaded()
    if row is None:
        if pid in plugins.autoinstalled:
            raise InstallError(f"'{pid}' is loaded from a development checkout here")
        raise InstallError(f"'{pid}' isn't installed")
    needed_by = dependents(pid)
    if needed_by:
        raise InstallError(f"{', '.join(needed_by)} need(s) it; remove those first")
    spec = plugins.get(pid)
    if delete_data:
        if (
            spec is None
            or spec.migrations_dir is None
            and spec.manifest.get("migrations")
        ):
            raise InstallError(
                "its files aren't available in this process; reload and try again"
            )
        if spec is not None:
            migrate.downgrade_everywhere(spec)
            for code in spec.module_codes:
                db.session.execute(
                    TenantFeature.__table__.delete().where(
                        TenantFeature.feature_code == code
                    )
                )
                db.session.execute(
                    Feature.__table__.delete().where(Feature.code == code)
                )
    version = row.version
    db.session.delete(row)
    db.session.execute(
        PluginArchive.__table__.delete().where(PluginArchive.plugin_id == pid)
    )
    generation = bump_generation()
    _audit("uninstall_plugin", pid, {"version": version, "deleteData": delete_data})
    db.session.commit()
    return {
        "id": pid,
        "version": version,
        "dataDeleted": delete_data,
        "generation": generation,
    }


def hold(pid: str, version: str | None) -> None:
    row = _installed_row(pid)
    if row is None:
        raise InstallError(f"'{pid}' isn't installed")
    row.held_version = version or None
    db.session.commit()


# ── Repositories ─────────────────────────────────────────────────────────────

_index_cache: dict = {}


def _check_url(url: str) -> None:
    """Plugin downloads go to public https hosts only, so a manager can't
    point the server at its own network (HUBRA_PLUGINS_ALLOW_PRIVATE=1 lifts
    the address check for a repository on the local network)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise InstallError(f"{url}: only https:// addresses")
    if os.environ.get("HUBRA_PLUGINS_ALLOW_PRIVATE") == "1":
        return
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except OSError as exc:
        raise InstallError(f"{url}: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise InstallError(f"{url}: {parsed.hostname} is not a public address")


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_get(url: str, timeout: int = 30, limit: int = MAX_ZIP) -> bytes:
    _check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "Hubra plugin installer"})
    opener = urllib.request.build_opener(_CheckedRedirects)
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read(limit + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise InstallError(f"{url}: {exc}") from exc
    if len(data) > limit:
        raise InstallError(f"{url}: larger than {limit // 1024 // 1024} MB")
    return data


def _get_index(url: str) -> dict:
    try:
        data = json.loads(http_get(url, timeout=15, limit=10 * 1024 * 1024))
    except ValueError as exc:
        raise InstallError(f"{url}: not JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
        raise InstallError(f"{url}: not a Hubra plugin index")
    return data


def preview_repository(url: str) -> dict:
    """What adding this repository would trust: its name and key (from the index, checked against itself)."""
    from .trust import key_id, official_keys, verify_index

    if not url.startswith("https://"):
        raise InstallError("the index URL starts with https://")
    doc = _get_index(url)
    try:
        pub = load_public(str(doc.get("public_key", "")))
        verify_index(doc, pub)
    except (ValueError, TypeError) as exc:
        raise InstallError(f"{url}: {exc}") from exc
    kid = key_id(pub)
    return {
        "url": url,
        "name": str(doc.get("name") or url)[:64],
        "description": str(doc.get("description") or ""),
        "keyId": kid,
        "publicKey": doc["public_key"],
        "official": kid in official_keys(),
        "plugins": len(doc["plugins"]),
        "generated": doc.get("generated"),
    }


def add_repository(url: str, key_id: str) -> object:
    """Add a repository after the manager compared its key id."""
    from hubra.core.models.plugin import PluginRepository

    info = preview_repository(url)
    if info["keyId"] != key_id:
        raise InstallError(
            f"the repository is now signed with key {info['keyId']}, not {key_id}"
        )
    if db.session.scalar(select(PluginRepository).where(PluginRepository.url == url)):
        raise InstallError("this repository is added already")
    name = info["name"]
    if db.session.scalar(select(PluginRepository).where(PluginRepository.name == name)):
        name = f"{name[:50]} ({info['keyId'][:6]})"
    repo = PluginRepository(
        name=name,
        url=url,
        key_id=info["keyId"],
        public_key=info["publicKey"],
        official=info["official"],
        added_by=_actor(),
    )
    db.session.add(repo)
    _audit("add_plugin_repository", name, {"url": url, "keyId": info["keyId"]})
    db.session.commit()
    _index_cache.pop(url, None)
    return repo


def fetch_repository(repo, force: bool = False) -> dict:
    """The repository's index, verified with the key pinned when it was added."""
    from .trust import verify_index

    hit = _index_cache.get(repo.url)
    if hit and not force and time.time() - hit[0] < 600 and hit[2] == repo.key_id:
        return hit[1]
    try:
        doc = _get_index(repo.url)
        verify_index(doc, load_public(repo.public_key))
    except (InstallError, ValueError, TypeError) as exc:
        repo.error, repo.fetched_at = str(exc)[:500], _now()
        db.session.commit()
        raise InstallError(f"{repo.name}: {exc}") from exc
    repo.error, repo.fetched_at = "", _now()
    db.session.commit()
    _index_cache[repo.url] = (time.time(), doc, repo.key_id)
    return doc


OFFICIAL_SEEDED = "official_repo_seeded"
OFFICIAL_NAME = "Hubra official"


def ensure_official_repository() -> None:
    """The official repository is there out of the box, once: remove it and it stays removed.
    Nothing is fetched here; the key is the one that ships with Hubra."""
    from hubra.core.models.plugin import PluginRepository, PluginState

    from .trust import official_index_url, official_keys, public_b64

    url = official_index_url()
    keys = official_keys()
    if not url or not keys:
        return
    kid, (_, pub) = next(iter(keys.items()))
    # The official repository follows the address and key this Hubra ships with.
    for r in db.session.scalars(
        select(PluginRepository).where(PluginRepository.official.is_(True))
    ):
        if (r.url, r.key_id) != (url, kid):
            r.url, r.key_id, r.public_key, r.error, r.fetched_at = (
                url,
                kid,
                public_b64(pub),
                "",
                None,
            )
            _index_cache.clear()
    if db.session.get(PluginState, OFFICIAL_SEEDED) is None:
        row = db.session.scalar(
            select(PluginRepository).where(PluginRepository.url == url)
        )
        if row is None:
            db.session.add(
                PluginRepository(
                    name=OFFICIAL_NAME,
                    url=url,
                    key_id=kid,
                    public_key=public_b64(pub),
                    official=True,
                    added_by="Hubra",
                )
            )
        else:
            row.official = True
        db.session.add(PluginState(key=OFFICIAL_SEEDED, value="true"))
    db.session.commit()


def _vkey(v: str):
    from packaging.version import InvalidVersion, Version

    try:
        return (1, Version(v))
    except InvalidVersion:
        return (0, Version("0"))


def newer(a: str, b: str) -> bool:
    from packaging.version import InvalidVersion, Version

    try:
        return Version(a) > Version(b)
    except InvalidVersion:
        return a != b


def versions_of(entry: dict) -> list[dict]:
    """Every version a repository offers for one plugin, newest first."""
    out, seen = [], set()
    for v in [entry, *(entry.get("versions") or [])]:
        if not isinstance(v, dict) or not v.get("version") or str(v["version"]) in seen:
            continue
        seen.add(str(v["version"]))
        out.append(
            {
                "version": str(v["version"]),
                "url": v.get("url", ""),
                "sha256": v.get("sha256", ""),
                "hubra": str(v.get("hubra") or ""),
                "changes": str(v.get("changes") or "")[:4000],
                "yanked": str(v.get("yanked") or "")[:300],
                "date": str(v.get("date") or ""),
            }
        )
    return sorted(out, key=lambda v: _vkey(v["version"]), reverse=True)


def _compatible(v: dict) -> tuple[bool, str]:
    return compatibility({"hubra": v["hubra"]} if v.get("hubra") else {})


def best_version(entry: dict) -> dict | None:
    """The newest version that isn't withdrawn and works with this Hubra."""
    for v in versions_of(entry):
        if not v["yanked"] and _compatible(v)[0]:
            return v
    return None


def install_from_repository(repo, pid: str, version: str | None = None) -> dict:
    """Download, check and stage *pid* from *repo* (confirm installs it)."""
    from urllib.parse import urljoin

    idx = fetch_repository(repo)
    top = next(
        (p for p in idx["plugins"] if isinstance(p, dict) and str(p.get("id")) == pid),
        None,
    )
    if top is None:
        raise InstallError(f"'{pid}' isn't in {repo.name}")
    if version:
        entry = next(
            (v for v in versions_of(top) if v["version"] == str(version)), None
        )
        if entry is None:
            raise InstallError(f"{repo.name} doesn't offer {pid} {version}")
    else:
        entry = best_version(top) or versions_of(top)[0]
    zurl = urljoin(repo.url, str(entry.get("url", "")))
    if not entry.get("sha256"):
        raise InstallError("the index has no checksum for this plugin")
    blob = http_get(zurl, timeout=60)
    if hashlib.sha256(blob).hexdigest() != entry["sha256"]:
        raise InstallError("download doesn't match the checksum in the index")
    info = stage(blob, source=f"{repo.name}: {zurl}", repository_id=repo.id)
    if info["trust"].get("key_id") != repo.key_id or info["trust"]["status"] not in (
        "official",
        "community",
    ):
        discard_stage(info["token"])
        raise InstallError(f"'{pid}' isn't signed with {repo.name}'s key")
    return info


def changes_for(changelog: str, version: str) -> str:
    """The notes for one version from a plugin's CHANGELOG.md (a ``## <version>`` heading)."""
    import re

    m = re.search(
        rf"^##+\s*\[?v?{re.escape(version)}\]?\b[^\n]*\n(.*?)(?=^##+\s|\Z)",
        changelog,
        re.M | re.S,
    )
    return m.group(1).strip()[:4000] if m else ""


# ── The Marketplace ──────────────────────────────────────────────────────────


def _local_entry(spec: Spec, row) -> dict:
    m = spec.manifest
    installed = row is not None or spec.id in _loaded().autoinstalled
    return {
        **spec.as_dict(),
        "requiresHubra": str(m.get("hubra") or ""),
        "compatible": compatibility(m)[0],
        "incompatibleReason": compatibility(m)[1],
        "official": spec.bundled or spec.trust.get("status") == "official",
        "source": "shipped with Hubra"
        if spec.bundled
        else spec.trust.get("detail") or "uploaded",
        "repository": "",
        "repositoryId": None,
        "installed": installed,
        "installedVersion": (row.version if row else spec.version)
        if installed
        else None,
        "update": False,
        "changes": changes_for(spec.changelog(), spec.version),
    }


def marketplace(fetch: bool = True) -> dict:
    """Everything that can be installed, one entry per plugin: what ships
    with Hubra, what is installed, and what the enabled repositories offer."""
    from hubra.core.models.plugin import PluginRepository

    plugins = _loaded()
    rows = {r.id: r for r in installed_rows()}
    out: dict[str, dict] = {}
    for spec in plugins.specs.values():
        if not spec.manifest:
            continue
        out[spec.id] = _local_entry(spec, rows.get(spec.id))
    for pid, row in rows.items():
        if pid not in out:  # installed, but this process couldn't read it
            spec = plugins.get(pid)
            out[pid] = {
                "id": pid,
                "name": row.name,
                "version": row.version,
                "description": "",
                "author": "",
                "tags": [],
                "modules": [],
                "requires": [],
                "bundled": row.source == "bundled",
                "trust": {
                    "status": row.trust,
                    "signer": row.signer,
                    "key_id": row.key_id,
                    "detail": "",
                },
                "loaded": False,
                "error": (spec.error if spec else "") or row.error or "not loaded here",
                "installed": True,
                "installedVersion": row.version,
                "compatible": True,
                "incompatibleReason": "",
                "official": row.trust in ("official", "bundled"),
                "source": row.origin,
                "repository": "",
                "repositoryId": None,
                "update": False,
                "changes": "",
            }
    errors: list[str] = []
    repos = (
        db.session.scalars(
            select(PluginRepository)
            .where(PluginRepository.enabled.is_(True))
            .order_by(PluginRepository.official.desc(), PluginRepository.name)
        ).all()
        if fetch
        else []
    )
    for repo in repos:
        try:
            idx = fetch_repository(repo)
        except InstallError as exc:
            errors.append(str(exc))
            continue
        for p in idx["plugins"]:
            if not isinstance(p, dict) or not p.get("id"):
                continue
            pid = str(p["id"])
            entry = out.get(pid) or {
                "id": pid,
                "name": p.get("name", pid),
                "description": p.get("description", ""),
                "author": p.get("author", ""),
                "homepage": p.get("homepage", ""),
                "license": p.get("license", ""),
                "tags": p.get("tags") or [],
                "modules": p.get("modules") or [],
                "requires": p.get("requires") or [],
                "bundled": False,
                "trust": {"status": "", "signer": "", "key_id": "", "detail": ""},
                "loaded": False,
                "error": "",
                "installed": False,
                "installedVersion": None,
                "source": repo.name,
            }
            if entry.get("repositoryId"):  # the first repository offering it wins
                continue
            vers = versions_of(p)
            best = best_version(p)
            latest = vers[0] if vers else None
            if latest is None:
                continue
            ok, why = _compatible(latest)
            row = rows.get(pid)
            have = entry.get("installedVersion") or ""
            target = best["version"] if best else ""
            installed = bool(entry.get("installed"))
            mine = (
                next((v for v in vers if v["version"] == have), None)
                if installed
                else None
            )
            held = bool(row and row.held_version)
            entry.update(
                {
                    "repository": repo.name,
                    "repositoryId": repo.id,
                    "official": bool(entry.get("official")) or repo.official,
                    "officialSigned": bool(repo.official),
                    "repoVersion": target or latest["version"],
                    "latestVersion": latest["version"],
                    "requiresHubra": (best or latest).get("hubra")
                    or entry.get("requiresHubra", ""),
                    "compatible": bool(best) or ok,
                    "incompatibleReason": ""
                    if best
                    else why
                    or (
                        "every version is withdrawn"
                        if all(v["yanked"] for v in vers)
                        else ""
                    ),
                    "sourceUrl": str(p.get("source") or "")
                    if str(p.get("source") or "").startswith("https://")
                    else "",
                    "versions": [
                        {
                            k: v[k]
                            for k in ("version", "hubra", "changes", "yanked", "date")
                        }
                        | {"compatible": _compatible(v)[0]}
                        for v in vers
                    ],
                    "withdrawn": (mine or {}).get("yanked", "") if installed else "",
                    "update": bool(
                        installed
                        and have
                        and target
                        and newer(target, have)
                        and not held
                    ),
                    "changes": "\n\n".join(
                        f"{v['version']}: {v['changes']}"
                        for v in vers
                        if v["changes"] and (not have or newer(v["version"], have))
                    )[:4000]
                    if installed
                    else latest.get("changes") or "",
                }
            )
            if not entry.get("version"):
                entry["version"] = target or latest["version"]
            out[pid] = entry
    for e in out.values():
        row = rows.get(e["id"])
        e["held"] = row.held_version if row and row.held_version else ""
        e["previous"] = (
            _archive(row.previous_sha256).version
            if row and row.previous_sha256 and _archive(row.previous_sha256)
            else None
        )
        e["source"] = row.origin if row and row.origin else e.get("source", "")
        e.setdefault("versions", [])
        e.setdefault("withdrawn", "")
        e.setdefault("officialSigned", False)
        e["autoinstalled"] = e["id"] in plugins.autoinstalled
    return {
        "plugins": sorted(out.values(), key=lambda e: str(e["name"]).lower()),
        "errors": errors,
        "generation": plugins.generation,
    }
