"""For plugin authors and marketplace publishers: release, sign, pack, index.

Ported from labdex; the archive, SIGNATURE.json and index.json formats are
the same, with ``hubra`` as the version-range key.  Nothing here runs in a
request: these back the ``flask plugins`` publishing commands.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path

from .installer import (
    InstallError,
    _vkey,
    changes_for,
    http_get,
    safe_extract,
    versions_of,
)
from .spec import read_manifest, validate
from .trust import key_entry, key_id, load_public, sign, sign_index, verify

RELEASEIGNORE = ".releaseignore"
ALWAYS_LEFT_OUT = (
    ".git",
    ".github",
    ".gitattributes",
    ".gitignore",
    RELEASEIGNORE,
    "__pycache__",
    "*.pyc",
    "*.zip",
    "node_modules",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def release_ignored(root: Path) -> list[Path]:
    """What a plugin's .releaseignore (and the usual repository files) keeps out of its release.

    One pattern per line, like .gitignore: ``tests/`` (a folder), ``*.log`` (any
    file named so, anywhere), ``docs/draft.md`` (a path from the plugin's root);
    ``#`` starts a comment.
    """
    pats = list(ALWAYS_LEFT_OUT)
    f = root / RELEASEIGNORE
    if f.is_file():
        pats += [
            ln.strip()
            for ln in f.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if any(
            rel == q or rel.startswith(q + "/")
            for q in (x.relative_to(root).as_posix() for x in out)
        ):
            continue  # inside something already left out
        for pat in pats:
            folder = pat.endswith("/")
            pat = pat.strip("/")
            if folder and not p.is_dir():
                continue
            if fnmatch(rel, pat) if "/" in pat else fnmatch(p.name, pat):
                out.append(p)
                break
    return out


def prune_release(root: Path) -> list[str]:
    """Delete what release_ignored() names (on a copy made for the release), before signing."""
    gone = []
    for p in release_ignored(root):
        gone.append(p.relative_to(root).as_posix())
        shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
    return gone


def pack(root: Path) -> bytes:
    """Zip a plugin folder as ``<id>/...`` (what installs and indexes expect)."""
    m = read_manifest(root)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(root.rglob("*")):
            rel = f.relative_to(root)
            if f.is_file() and not any(
                part == "__pycache__" or part.endswith(".pyc") for part in rel.parts
            ):
                zf.write(f, f"{m['id']}/{rel.as_posix()}")
    return buf.getvalue()


def release(src: Path, private_pem: bytes, signer: str) -> tuple[dict, bytes]:
    """Copy *src*, prune it, check it, sign it and zip it.  *src* is left as it is."""
    m = read_manifest(src)
    problem = validate(m, src)
    if problem:
        raise InstallError(f"{src.name}: {problem}")
    fe = m.get("frontend")
    if fe and not (src / str(fe)).is_file():
        raise InstallError(
            f"{src.name}: {fe} is missing; build the frontend first "
            "(npm run build:plugin in app/frontend)"
        )
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / str(m["id"])
        shutil.copytree(
            src, work, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
        prune_release(work)
        sign(work, private_pem, signer)
        return m, pack(work)


def _public_of(private_pem: bytes):
    from cryptography.hazmat.primitives import serialization

    return serialization.load_pem_private_key(private_pem, password=None).public_key()


def plugin_key_entries(public_keys: list[str], index_pem: bytes) -> list[dict] | None:
    """``plugin_keys`` for an index from public key texts (None = none given).
    The index key can't be one of them."""
    if not public_keys:
        return None
    index_id = key_id(_public_of(index_pem))
    out = []
    for text in public_keys:
        pub = load_public(text)
        if key_id(pub) == index_id:
            raise InstallError(
                f"key {index_id} can't sign both the index and the plugins; "
                "use a separate index key"
            )
        out.append(key_entry(key_id(pub), pub))
    return out


def build_repository(
    src: Path,
    out: Path,
    private_pem: bytes,
    name: str,
    description: str = "",
    only: list[str] | None = None,
    plugin_pem: bytes | None = None,
) -> dict:
    """Sign every plugin folder in *src*, zip it into *out*, write a signed index.json.

    *private_pem* signs the index; *plugin_pem*, when given, signs the
    plugins and is listed in the index as its plugin key (else
    *private_pem* signs both, the old format).  Older versions whose
    archives are still in *out* stay offered, so people can go back to
    them.  *src* is not modified.
    """
    plugin_keys = None
    if plugin_pem is not None:
        pub = _public_of(plugin_pem)
        if key_id(pub) == key_id(_public_of(private_pem)):
            raise InstallError("the index key and the plugin key are the same key")
        plugin_keys = [key_entry(name, pub)]
    out.mkdir(parents=True, exist_ok=True)
    plugins = []
    old: dict = {}
    if (out / "index.json").is_file():
        try:
            old = {
                str(p["id"]): p
                for p in json.loads((out / "index.json").read_text()).get("plugins")
                or []
                if isinstance(p, dict) and p.get("id")
            }
        except (ValueError, KeyError):
            old = {}
    folders = sorted(
        p
        for p in src.iterdir()
        if (p / "plugin.yaml").is_file() and not p.name.startswith(("_", "."))
    )
    for d in folders:
        m = read_manifest(d)
        if only and str(m.get("id")) not in only:
            continue
        m, blob = release(d, plugin_pem or private_pem, name)
        ver = str(m.get("version", ""))
        zname = f"{m['id']}-{ver}.zip"
        (out / zname).write_bytes(blob)
        log = (d / "CHANGELOG.md").read_text() if (d / "CHANGELOG.md").is_file() else ""
        prev = old.get(str(m["id"])) or {}
        history = (
            [
                v
                for v in versions_of(prev)
                if v["version"] != ver and v["url"] and (out / v["url"]).is_file()
            ]
            if prev
            else []
        )
        for (
            v
        ) in history:  # a version's notes may have been written after it was published
            v["changes"] = v["changes"] or changes_for(log, v["version"])
        date = (
            next(
                (
                    v["date"]
                    for v in versions_of(prev)
                    if v["version"] == ver and v["date"]
                ),
                "",
            )
            if prev
            else ""
        )
        current = {
            "version": ver,
            "url": zname,
            "sha256": hashlib.sha256(blob).hexdigest(),
            **({"hubra": str(m["hubra"])} if m.get("hubra") else {}),
            "changes": changes_for(log, ver) or str(m.get("changes") or ""),
            "date": date or datetime.now(timezone.utc).date().isoformat(),
        }
        plugins.append(
            {
                **_listing(m),
                **current,
                "versions": [
                    current,
                    *[
                        {
                            k: v
                            for k, v in h.items()
                            if v or k in ("version", "url", "sha256")
                        }
                        for h in history
                    ],
                ],
            }
        )
    for (
        pid,
        prev,
    ) in old.items():  # a plugin whose folder is gone stays offered as it was
        if not any(p["id"] == pid for p in plugins):
            plugins.append(prev)
    _add_parents(plugins)
    doc = sign_index(
        {
            "name": name,
            "description": description,
            "generated": _now(),
            "plugins": sorted(plugins, key=lambda p: p["id"]),
        },
        private_pem,
        plugin_keys,
    )
    (out / "index.json").write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def _add_parents(plugins: list[dict]) -> None:
    """Name each plugin's parent (the plugin it is an add-on of), so a
    catalogue can show add-ons under it."""
    from .spec import parents

    found = parents(plugins)
    for p in plugins:
        p["parent"] = found.get(str(p.get("id")), "")


def _listing(m: dict) -> dict:
    """What an index says about a plugin, from its manifest."""
    return {
        "id": m["id"],
        "name": m.get("name", m["id"]),
        "description": m.get("description", ""),
        "author": m.get("author", ""),
        "homepage": m.get("homepage", ""),
        "license": m.get("license", ""),
        "tags": m.get("tags") or [],
        "modules": m.get("modules") or [],
        "requires": m.get("requires") or [],
        "depends": m.get("depends") or {},
        "replaces": m.get("replaces") or [],
        "uses": m.get("uses"),
    }


def build_index_from_sources(
    sources: dict,
    out: Path,
    private_pem: bytes,
    name: str = "",
    description: str = "",
    token: str = "",
    api: str = "https://api.github.com",
    get=None,
    plugin_keys: list[str] | None = None,
) -> dict:
    """A Marketplace whose plugins live in their own git repositories (sources.yaml)::

        name: Hubra official
        description: ...
        plugins:
          - repo: owner/hubra-plugin-keys       # GitHub: its releases are the versions
            withdrawn: {"1.2": "loses the handover log"}
        discover:
          - {owner: hubra-app, prefix: hubra-plugin-}

    Every release asset named ``<id>-<version>.zip`` is downloaded and checked
    (checksum, SIGNATURE.json signed with one of the plugin keys, manifest id
    and version matching the name).  The index points at the assets where
    they are.  Repositories without a release are left out (``skipped``).

    *plugin_keys* (public key texts, or ``plugin_keys`` in *sources*) are
    the keys the plugins are signed with; they are listed in the index, and
    *private_pem* then signs only the index.  Without them *private_pem*
    must have signed the plugins too (the old format).
    """
    from cryptography.hazmat.primitives import serialization

    def fetch_json(url):
        req_headers = {
            "Accept": "application/vnd.github+json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        }
        if get is not None:
            return get(url, req_headers)
        import urllib.request

        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return json.loads(resp.read())

    def fetch_blob(url):
        return get(url, None) if get is not None else http_get(url, timeout=60)

    key = serialization.load_pem_private_key(private_pem, password=None)
    entries = plugin_key_entries(
        list(plugin_keys or sources.get("plugin_keys") or []), private_pem
    )
    if entries:
        mine = {e["key_id"]: (e["name"], load_public(e["public_key"])) for e in entries}
    else:
        mine = {key_id(key.public_key()): ("this repository", key.public_key())}
    plugins, problems, skipped = [], [], []
    listed = list(sources.get("plugins") or [])
    for d in sources.get("discover") or []:
        owner, prefix = (
            str(d.get("owner") or ""),
            str(d.get("prefix") or "hubra-plugin-"),
        )
        try:
            found = []
            for page in range(1, 11):
                batch = fetch_json(
                    f"{api}/users/{owner}/repos?per_page=100&page={page}"
                )
                found += [
                    x["full_name"]
                    for x in batch
                    if str(x.get("name", "")).startswith(prefix)
                    and not x.get("archived")
                    and not x.get("private")
                ]
                if len(batch) < 100:
                    break
        except Exception as exc:
            problems.append(f"discovering {owner}/{prefix}*: {exc}")
            continue
        have = {str(x.get("repo") or "").lower() for x in listed}
        listed += [{"repo": f} for f in sorted(found) if f.lower() not in have]
    for src in listed:
        repo = str(src.get("repo") or "")
        withdrawn = {str(k): str(v) for k, v in (src.get("withdrawn") or {}).items()}
        try:
            releases = [
                r
                for r in fetch_json(f"{api}/repos/{repo}/releases?per_page=100")
                if not r.get("draft") and not r.get("prerelease")
            ]
        except Exception as exc:
            problems.append(f"{repo}: {exc}")
            continue
        versions, top = [], None
        for r in releases:
            for a in r.get("assets") or []:
                if not str(a.get("name", "")).endswith(".zip"):
                    continue
                try:
                    blob = fetch_blob(a["browser_download_url"])
                    with tempfile.TemporaryDirectory() as tmp:
                        pdir = safe_extract(blob, Path(tmp) / "x")
                        m = read_manifest(pdir)
                        if a["name"] != f"{m.get('id')}-{m.get('version')}.zip":
                            raise InstallError(
                                f"{a['name']} holds {m.get('id')} {m.get('version')}"
                            )
                        t = verify(pdir, m, mine)
                        if (
                            t["status"] not in ("official", "community")
                            or t.get("key_id") not in mine
                        ):
                            raise InstallError(
                                f"not signed with this repository's plugin key ({t['detail']})"
                            )
                        problem = validate(m, pdir)
                        if problem:
                            raise InstallError(problem)
                except Exception as exc:
                    problems.append(f"{repo} {a.get('name')}: {exc}")
                    continue
                ver = str(m["version"])
                v = {
                    "version": ver,
                    "url": a["browser_download_url"],
                    "sha256": hashlib.sha256(blob).hexdigest(),
                    **({"hubra": str(m["hubra"])} if m.get("hubra") else {}),
                    "changes": str(r.get("body") or "").strip()[:4000],
                    "date": str(r.get("published_at") or "")[:10],
                    **({"yanked": withdrawn[ver]} if ver in withdrawn else {}),
                }
                versions.append(v)
                if top is None or _vkey(ver) > _vkey(top[0]["version"]):
                    top = (v, m)
        if top is None:
            # Not released yet: left out, not an error.  A release whose
            # archive fails a check is a problem, reported above.
            skipped.append(repo)
            continue
        v, m = top
        versions.sort(key=lambda x: _vkey(x["version"]), reverse=True)
        plugins.append(
            {
                **_listing(m),
                "source": f"https://github.com/{repo}",
                **v,
                "versions": versions,
            }
        )
    out.mkdir(parents=True, exist_ok=True)
    _add_parents(plugins)
    doc = sign_index(
        {
            "name": name or sources.get("name") or "plugins",
            "description": description or sources.get("description") or "",
            "generated": _now(),
            "plugins": sorted(plugins, key=lambda p: p["id"]),
        },
        private_pem,
        entries,
    )
    (out / "index.json").write_text(json.dumps(doc, indent=2) + "\n")
    return {**doc, "problems": problems, "skipped": skipped}


def yank(out: Path, private_pem: bytes, pid: str, version: str, reason: str) -> dict:
    """Mark one version as withdrawn (or, with reason '', not any more) and re-sign the index."""
    doc = json.loads((out / "index.json").read_text())
    entry = next((p for p in doc.get("plugins") or [] if str(p.get("id")) == pid), None)
    if entry is None:
        raise InstallError(f"no plugin '{pid}' in this index")
    hit = False
    for v in [entry, *(entry.get("versions") or [])]:
        if str(v.get("version")) == version:
            hit = True
            if reason:
                v["yanked"] = reason[:300]
            else:
                v.pop("yanked", None)
    if not hit:
        raise InstallError(f"the index has no {pid} {version}")
    for k in ("signature", "key_id", "public_key"):
        doc.pop(k, None)
    doc["generated"] = _now()
    doc = sign_index(doc, private_pem)
    (out / "index.json").write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def check_repository(url: str, expect_key: str = "") -> tuple[dict, list[str]]:
    """Download a published repository the way a Hubra does and check it.

    The index must verify against its own key (and be *expect_key*, default
    the official index key), and every archive it offers must match its
    checksum, unpack safely, and carry a SIGNATURE.json from one of its
    plugin keys (the official ones for the official index; the index key in
    the old format) for that id and version.  Returns the index and the
    problems found ([] = all good).
    """
    from urllib.parse import urljoin

    from .installer import preview_repository
    from .trust import official_keys, plugin_keys_of

    info = preview_repository(url)
    kid = info["keyId"]
    wanted = expect_key or next(iter(official_keys("index")), "")
    problems = []
    if wanted and kid != wanted:
        problems.append(f"the index is signed with key {kid}, not {wanted}")
    doc = json.loads(http_get(url, timeout=15, limit=10 * 1024 * 1024))
    if info["official"]:
        signer = official_keys("plugins")
    else:
        signer = plugin_keys_of(doc) or {
            kid: (info["name"], load_public(info["publicKey"]))
        }
    for p in doc["plugins"]:
        for v in versions_of(p):
            what = f"{p.get('id')} {v['version']}"
            if not v["url"] or not v["sha256"]:
                problems.append(f"{what}: no archive or checksum in the index")
                continue
            try:
                blob = http_get(urljoin(url, v["url"]), timeout=60)
            except InstallError as exc:
                problems.append(f"{what}: {exc}")
                continue
            if hashlib.sha256(blob).hexdigest() != v["sha256"]:
                problems.append(f"{what}: the archive doesn't match its checksum")
                continue
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    pdir = safe_extract(blob, Path(tmp))
                    m = read_manifest(pdir)
                except (InstallError, ValueError) as exc:
                    problems.append(f"{what}: {exc}")
                    continue
                if (str(m.get("id")), str(m.get("version"))) != (
                    str(p.get("id")),
                    v["version"],
                ):
                    problems.append(
                        f"{what}: the archive holds {m.get('id')} {m.get('version')}"
                    )
                t = verify(pdir, m, signer)
                if t["status"] not in ("official", "community") or t[
                    "key_id"
                ] not in signer:
                    problems.append(f"{what}: {t['detail']}")
    return doc, problems
