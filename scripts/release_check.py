#!/usr/bin/env python3
"""The release checks and release notes of .github/workflows/release.yml.

They used to be inline scripts in the workflow, which only ran on a tag push:
a bug in them showed up when a release failed, and a pushed v* tag cannot be
moved. As a file, the same code runs on pull requests (ci.yml, job
"release-check"), in the dry run (release-dry-run.yml) and in its tests
(scripts/test_release_check.py).

    release_check.py check v1.3.0
        The tag is vX.Y.Z or vX.Y.Z-<pre>, matches app/backend/pyproject.toml,
        and a release (not a pre-release) has a non-empty [X.Y.Z] section in
        app/backend/CHANGELOG.md. With --no-fragments (always on a tag
        push) app/backend/changes/ must be empty: its entries belong in the
        changelog before the version bump. Writes version, prerelease and
        minor to $GITHUB_OUTPUT (or prints them).

    release_check.py notes v1.3.0 --images out/images.yaml --out out
        Writes out/CHANGELOG.md (this version's section) and notes.md (the
        release description: a draft's $BODY, the changelog, the images).

    release_check.py plugins v1.3.0 [--index URL-or-file] [--strict]
        Upgrade impact: which official plugins (plugins.hubra.club/index.json)
        have no version whose `hubra:` range takes this release, and which
        need an update first. Warnings; with --strict a plugin without any
        working version fails (the dry run passes --strict).

check and notes take --root, the repository checkout (default: the current
directory).
Python 3.11+, standard library only.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import importlib.util
import json
import tomllib
import urllib.request

CHANGELOG = "app/backend/CHANGELOG.md"
CHANGES = "app/backend/changes"
FRAGMENTS = "app/backend/hubra/core/changelog_fragments.py"
PYPROJECT = "app/backend/pyproject.toml"
TAG_RE = re.compile(r"v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<pre>-[0-9A-Za-z.-]+)?")


class ReleaseError(Exception):
    """A check failed; the message says what to fix."""


def parse_tag(tag: str) -> dict[str, str | bool]:
    m = TAG_RE.fullmatch(tag)
    if not m:
        raise ReleaseError(f"{tag} is not vX.Y.Z or vX.Y.Z-rc.N")
    return {
        "version": tag[1:],
        "prerelease": bool(m["pre"]),
        "minor": f"{m['major']}.{m['minor']}",
    }


def section_of(log: str, name: str) -> str | None:
    """The text under '## [name]' up to the next '## ' heading, stripped;
    None when there is no such heading."""
    m = re.search(rf"^##\s*\[{re.escape(name)}\][^\n]*\n(.*?)(?=^##\s|\Z)", log, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def _fragments(root: Path):
    """app/backend/hubra/core/changelog_fragments.py, loaded by path (the
    hubra package needs Flask; this module only the standard library)."""
    spec = importlib.util.spec_from_file_location("changelog_fragments", root / FRAGMENTS)
    if spec is None or spec.loader is None or not (root / FRAGMENTS).exists():
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check(tag: str, root: Path, no_fragments: bool = False) -> dict[str, str]:
    info = parse_tag(tag)
    version = str(info["version"])
    with open(root / PYPROJECT, "rb") as f:
        declared = tomllib.load(f)["project"]["version"]
    if declared != version:
        raise ReleaseError(f"tag {tag}, but {PYPROJECT} says version {declared}")
    if not info["prerelease"]:
        frag = _fragments(root)
        waiting = frag.files(root / CHANGES) if frag else []
        # Fragments are normal between releases; at a version bump (the
        # release pull request) or a tag push they must be in the changelog.
        if waiting and no_fragments:
            names = ", ".join(p.name for p in waiting)
            raise ReleaseError(
                f"{CHANGES} still has entries ({names}); run "
                f"`python3 {FRAGMENTS} fold` before the version bump"
            )
        section = section_of((root / CHANGELOG).read_text(), version)
        if section is None:
            raise ReleaseError(f"{CHANGELOG} has no [{version}] section; move [Unreleased] there first")
        # The section is the release description and its CHANGELOG.md file.
        if not section:
            raise ReleaseError(f"the [{version}] section of {CHANGELOG} is empty; add what changed")
    return {
        "version": version,
        "prerelease": "true" if info["prerelease"] else "false",
        "minor": str(info["minor"]),
    }


def notes(tag: str, root: Path, images: Path, out: Path, body: str = "", repo: str = "") -> str:
    info = parse_tag(tag)
    v = str(info["version"])
    log = (root / CHANGELOG).read_text()
    frag = _fragments(root)
    if frag and info["prerelease"]:
        # A pre-release ships the waiting fragments with [Unreleased].
        log = frag.fold_into(log, frag.collected(root / CHANGES)["en"])
    # A release has its own [X.Y.Z] section (check insists); a pre-release
    # may not yet, then it ships what [Unreleased] says.
    section = section_of(log, v) or (section_of(log, "Unreleased") if info["prerelease"] else "") or ""
    out.mkdir(parents=True, exist_ok=True)
    (out / "CHANGELOG.md").write_text(f"# Hubra {v}\n\n{section or 'No changelog entry for this version.'}\n")
    body = body.strip()
    parts = [body] if body else []
    if section and section not in body:
        parts.append(f"## Changelog\n\n{section}")
    block = images.read_text().rstrip()
    parts.append(
        "## Images\n\n"
        "Pin them by digest (`images.yaml` is attached too):\n\n"
        f"```yaml\n{block}\n```\n\n"
        "Every image is signed (cosign, keyless) by this repository's release workflow "
        f"and carries a build provenance attestation; see [docs/releases.md](https://github.com/{repo}/blob/{tag}/docs/releases.md) to verify."
    )
    return "\n\n".join(parts)


DEFAULT_INDEX = "https://plugins.hubra.club/index.json"
_SPEC_RE = re.compile(r"^\s*(~=|==|!=|<=|>=|<|>)\s*([0-9][0-9A-Za-z.*+-]*)\s*$")


def _vtuple(v: str) -> tuple[int, ...]:
    """1.2.3rc1 -> (1, 2, 3); enough for ranges like '>=0.2,<1'."""
    parts = []
    for piece in v.split("."):
        m = re.match(r"\d+", piece)
        parts.append(int(m.group()) if m else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def in_range(version: str, spec: str) -> bool:
    """Whether *version* satisfies a PEP 440 range such as '>=0.2,<1'.
    Standard library only, so the common operators and numeric versions;
    '==1.2.*' works too. An empty range takes every version."""
    if not spec or not spec.strip():
        return True
    v = _vtuple(version)
    for clause in spec.split(","):
        if not clause.strip():
            continue
        m = _SPEC_RE.match(clause)
        if not m:
            raise ReleaseError(f"hubra range '{spec}' is not like '>=0.2,<1'")
        op, raw = m.groups()
        if raw.endswith(".*"):
            prefix = tuple(int(x) for x in raw[:-2].split("."))
            same = v[: len(prefix)] == prefix
            if (op == "==" and not same) or (op == "!=" and same):
                return False
            continue
        w = _vtuple(raw)
        ok = {
            "==": v == w,
            "!=": v != w,
            ">=": v >= w,
            "<=": v <= w,
            ">": v > w,
            "<": v < w,
            # ~=1.2 means >=1.2,==1.*; ~=1.2.3 means >=1.2.3,==1.2.*
            "~=": v >= w and v[: max(1, raw.count("."))] == w[: max(1, raw.count("."))],
        }[op]
        if not ok:
            return False
    return True


def _versions(entry: dict) -> list[dict]:
    seen, out = set(), []
    for v in [entry, *(entry.get("versions") or [])]:
        if isinstance(v, dict) and v.get("version") and str(v["version"]) not in seen:
            seen.add(str(v["version"]))
            out.append(v)
    return sorted(out, key=lambda v: _vtuple(str(v["version"])), reverse=True)


def plugin_impact(version: str, index: dict) -> dict[str, list[dict]]:
    """``{"blocked": [...], "update": [...], "ok": [...]}`` for every plugin of
    *index*: blocked has no live version that takes *version*; update means
    the newest version does not, but an older one does (rare: a plugin that
    narrowed its range), so clubs on it are fine only after picking it; ok:
    the newest version works."""
    out: dict[str, list[dict]] = {"blocked": [], "update": [], "ok": []}
    for entry in index.get("plugins") or []:
        live = [v for v in _versions(entry) if not v.get("yanked")]
        if not live:
            continue
        newest = live[0]
        fits = [v for v in live if in_range(version, str(v.get("hubra") or ""))]
        row = {
            "id": entry.get("id"),
            "newest": str(newest["version"]),
            "hubra": str(newest.get("hubra") or ""),
            "works": str(fits[0]["version"]) if fits else None,
        }
        if not fits:
            out["blocked"].append(row)
        elif fits[0] is not newest:
            out["update"].append(row)
        else:
            out["ok"].append(row)
    return out


def _load_index(where: str) -> dict:
    if where.startswith(("https://", "http://")):
        req = urllib.request.Request(where, headers={"User-Agent": "hubra-release-check"})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https URL
            return json.load(resp)
    return json.loads(Path(where).read_text())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check a tag against pyproject.toml and the changelog")
    c.add_argument("tag")
    c.add_argument("--root", type=Path, default=Path("."))
    c.add_argument(
        "--no-fragments",
        action="store_true",
        help="fail while app/backend/changes/ has entries (always on for a tag push)",
    )
    n = sub.add_parser("notes", help="write the release's CHANGELOG.md and notes.md")
    n.add_argument("tag")
    n.add_argument("--root", type=Path, default=Path("."))
    n.add_argument("--images", type=Path, required=True, help="the images.yaml block")
    n.add_argument("--out", type=Path, required=True, help="directory for CHANGELOG.md")
    n.add_argument("--notes", type=Path, default=Path("notes.md"))
    pl = sub.add_parser("plugins", help="official plugins whose hubra: range leaves this release out")
    pl.add_argument("tag")
    pl.add_argument("--index", default=DEFAULT_INDEX, help="index.json URL or file")
    pl.add_argument("--strict", action="store_true", help="fail when a plugin has no working version")
    a = p.parse_args(argv)
    try:
        if a.cmd == "plugins":
            version = str(parse_tag(a.tag)["version"])
            try:
                index = _load_index(a.index)
            except (OSError, ValueError) as e:
                print(f"::warning::plugin index {a.index} not readable ({e}); upgrade impact not checked")
                return 0
            impact = plugin_impact(version, index)
            for row in impact["update"]:
                print(
                    f"::warning::plugin {row['id']}: newest {row['newest']} needs Hubra "
                    f"{row['hubra']}; {row['works']} is the newest that takes {version}"
                )
            level = "error" if a.strict else "warning"
            for row in impact["blocked"]:
                print(
                    f"::{level}::plugin {row['id']}: no version takes Hubra {version} "
                    f"(newest {row['newest']} needs {row['hubra']}); release a plugin version "
                    "with a wider hubra: range first"
                )
            print(
                f"plugins: {len(impact['ok'])} fine, {len(impact['update'])} need an older version, "
                f"{len(impact['blocked'])} without a version for {version}"
            )
            return 1 if a.strict and impact["blocked"] else 0
        if a.cmd == "check":
            strict = a.no_fragments or os.environ.get("GITHUB_REF_TYPE") == "tag"
            result = check(a.tag, a.root, no_fragments=strict)
            lines = "".join(f"{k}={v}\n" for k, v in result.items())
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write(lines)
            print(lines, end="")
        else:
            text = notes(a.tag, a.root, a.images, a.out,
                         body=os.environ.get("BODY", ""), repo=os.environ.get("GITHUB_REPOSITORY", ""))
            a.notes.write_text(text)
    except ReleaseError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
