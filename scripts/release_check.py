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
        app/backend/CHANGELOG.md. Writes version, prerelease and minor to
        $GITHUB_OUTPUT (or prints them).

    release_check.py notes v1.3.0 --images out/images.yaml --out out
        Writes out/CHANGELOG.md (this version's section) and notes.md (the
        release description: a draft's $BODY, the changelog, the images).

Both take --root, the repository checkout (default: the current directory).
Python 3.11+, standard library only.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import tomllib

CHANGELOG = "app/backend/CHANGELOG.md"
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


def check(tag: str, root: Path) -> dict[str, str]:
    info = parse_tag(tag)
    version = str(info["version"])
    with open(root / PYPROJECT, "rb") as f:
        declared = tomllib.load(f)["project"]["version"]
    if declared != version:
        raise ReleaseError(f"tag {tag}, but {PYPROJECT} says version {declared}")
    if not info["prerelease"]:
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check a tag against pyproject.toml and the changelog")
    c.add_argument("tag")
    c.add_argument("--root", type=Path, default=Path("."))
    n = sub.add_parser("notes", help="write the release's CHANGELOG.md and notes.md")
    n.add_argument("tag")
    n.add_argument("--root", type=Path, default=Path("."))
    n.add_argument("--images", type=Path, required=True, help="the images.yaml block")
    n.add_argument("--out", type=Path, required=True, help="directory for CHANGELOG.md")
    n.add_argument("--notes", type=Path, default=Path("notes.md"))
    a = p.parse_args(argv)
    try:
        if a.cmd == "check":
            result = check(a.tag, a.root)
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
