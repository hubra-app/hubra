"""Version service: the app version (pyproject.toml), the release notes
(CHANGELOG.md) and the roadmap (ROADMAP.yaml)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT_PATH = _BACKEND_ROOT / "pyproject.toml"
_CHANGELOG_PATH = _BACKEND_ROOT / "CHANGELOG.md"
_ROADMAP_PATH = _BACKEND_ROOT / "ROADMAP.yaml"

# Roadmap columns, in the order the apps show them.
ROADMAP_STATUSES = ("now", "next", "later", "done")

_VERSION_HEADING_RE = re.compile(
    r"^##\s*\[(?P<version>[^\]]+)\](?:\s*-\s*(?P<date>\d{4}-\d{2}-\d{2}))?\s*$"
)
_SECTION_HEADING_RE = re.compile(r"^###\s*(?P<name>.+?)\s*$")

_version_cache: str | None = None
_changelog_cache: tuple[float, list[dict]] | None = None
_roadmap_cache: tuple[float, list[dict]] | None = None


class VersionService:
    """Reads version metadata and changelog entries for the running backend."""

    @staticmethod
    def get_version() -> str:
        """Return the app version from pyproject.toml, cached for the process lifetime."""
        global _version_cache
        if _version_cache is None:
            with _PYPROJECT_PATH.open("rb") as f:
                data = tomllib.load(f)
            _version_cache = data["project"]["version"]
        return _version_cache

    @staticmethod
    def get_changelog() -> list[dict]:
        """Parse CHANGELOG.md into structured entries, cached until the file changes."""
        global _changelog_cache

        if not _CHANGELOG_PATH.exists():
            return []

        mtime = _CHANGELOG_PATH.stat().st_mtime
        if _changelog_cache is not None and _changelog_cache[0] == mtime:
            return _changelog_cache[1]

        entries: list[dict] = []
        current: dict | None = None
        current_section: str | None = None
        # True while the lines below belong to the last bullet (a wrapped item).
        in_item = False

        for line in _CHANGELOG_PATH.read_text(encoding="utf-8").splitlines():
            version_match = _VERSION_HEADING_RE.match(line)
            if version_match:
                current = {
                    "version": version_match.group("version"),
                    "date": version_match.group("date"),
                    "sections": {},
                }
                entries.append(current)
                current_section = None
                in_item = False
                continue

            if current is None:
                continue

            section_match = _SECTION_HEADING_RE.match(line)
            if section_match:
                current_section = section_match.group("name")
                current["sections"].setdefault(current_section, [])
                in_item = False
                continue

            stripped = line.strip()
            if stripped.startswith("- ") and current_section is not None:
                current["sections"][current_section].append(stripped[2:].strip())
                in_item = True
            elif stripped and in_item and line[:1].isspace():
                # A long item wrapped onto an indented next line.
                items = current["sections"][current_section]
                items[-1] = f"{items[-1]} {stripped}"
            elif not stripped:
                in_item = False

        _changelog_cache = (mtime, entries)
        return entries

    @staticmethod
    def get_roadmap() -> list[dict]:
        """Parse ROADMAP.yaml into roadmap items, cached until the file changes.

        Each item is ``{id, status, area, title, summary, version, link}``;
        ``title`` and ``summary`` are ``{lang: text}`` maps (a plain string in
        the file counts as English). Items with an unknown status are skipped.
        """
        global _roadmap_cache

        if not _ROADMAP_PATH.exists():
            return []

        mtime = _ROADMAP_PATH.stat().st_mtime
        if _roadmap_cache is not None and _roadmap_cache[0] == mtime:
            return _roadmap_cache[1]

        data = yaml.safe_load(_ROADMAP_PATH.read_text(encoding="utf-8")) or {}
        items: list[dict] = []
        for raw in data.get("items") or []:
            if not isinstance(raw, dict):
                continue
            status = str(raw.get("status") or "").strip().lower()
            title = _texts(raw.get("title"))
            if status not in ROADMAP_STATUSES or not title or not raw.get("id"):
                continue
            link = raw.get("link")
            items.append(
                {
                    "id": str(raw["id"]),
                    "status": status,
                    "area": str(raw["area"]) if raw.get("area") else None,
                    "title": title,
                    "summary": _texts(raw.get("summary")),
                    # The release it shipped in, for "done" items.
                    "version": str(raw["version"]) if raw.get("version") else None,
                    # Only web links: the apps render this as an <a href>.
                    "link": link
                    if isinstance(link, str) and link.startswith("https://")
                    else None,
                }
            )

        _roadmap_cache = (mtime, items)
        return items


def _texts(value: Any) -> dict[str, str]:
    """A text in one or more languages as ``{lang: text}``; a string is English."""
    if isinstance(value, str):
        return {"en": value.strip()} if value.strip() else {}
    if isinstance(value, dict):
        return {
            str(k): str(v).strip() for k, v in value.items() if v and str(v).strip()
        }
    return {}
