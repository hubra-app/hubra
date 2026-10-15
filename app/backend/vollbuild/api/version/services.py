"""Version service — reads app version from pyproject.toml and parses CHANGELOG.md."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT_PATH = _BACKEND_ROOT / "pyproject.toml"
_CHANGELOG_PATH = _BACKEND_ROOT / "CHANGELOG.md"

_VERSION_HEADING_RE = re.compile(
    r"^##\s*\[(?P<version>[^\]]+)\](?:\s*-\s*(?P<date>\d{4}-\d{2}-\d{2}))?\s*$"
)
_SECTION_HEADING_RE = re.compile(r"^###\s*(?P<name>.+?)\s*$")

_version_cache: str | None = None
_changelog_cache: tuple[float, list[dict]] | None = None


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
                continue

            if current is None:
                continue

            section_match = _SECTION_HEADING_RE.match(line)
            if section_match:
                current_section = section_match.group("name")
                current["sections"].setdefault(current_section, [])
                continue

            stripped = line.strip()
            if stripped.startswith("- ") and current_section is not None:
                current["sections"][current_section].append(stripped[2:].strip())

        _changelog_cache = (mtime, entries)
        return entries
