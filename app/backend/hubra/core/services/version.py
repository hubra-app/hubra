"""Version service: the app version (pyproject.toml), the release notes
(CHANGELOG.md, German in CHANGELOG.de.md) and the roadmap (ROADMAP.yaml)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

from hubra.core import changelog_fragments

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT_PATH = _BACKEND_ROOT / "pyproject.toml"
_CHANGELOG_PATH = _BACKEND_ROOT / "CHANGELOG.md"
_CHANGELOG_DE_PATH = _BACKEND_ROOT / "CHANGELOG.de.md"
# Entries of pull requests merged since the last release, one file each
# (hubra.core.changelog_fragments); shown under [Unreleased].
_CHANGES_DIR = _BACKEND_ROOT / "changes"
_ROADMAP_PATH = _BACKEND_ROOT / "ROADMAP.yaml"

# Roadmap columns, in the order the apps show them.
ROADMAP_STATUSES = ("now", "next", "later", "done")

_VERSION_HEADING_RE = re.compile(
    r"^##\s*\[(?P<version>[^\]]+)\](?:\s*-\s*(?P<date>\d{4}-\d{2}-\d{2}))?\s*$"
)
_SECTION_HEADING_RE = re.compile(r"^###\s*(?P<name>.+?)\s*$")
# Who a changelog item is for, at the end of its bullet:
# "- **Event templates**: ... <!-- for: events -->". The words are module
# codes, "admins" (club admins only) or "staff" (Hubra's own team, never
# shown in the club app). Invisible on GitHub; the apps get the text without.
_FOR_RE = re.compile(r"\s*<!--\s*for:\s*(?P<tags>[^>]*?)\s*-->\s*", re.IGNORECASE)
AUDIENCES = ("admins", "staff")

_version_cache: str | None = None
# Parsed changelog files by path, each with what it was read from (the
# file's and the fragments' mtimes).
_changelog_cache: dict[Path, tuple[tuple, list[dict]]] = {}
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
    def get_changelog(lang: str | None = None) -> list[dict]:
        """The release notes, newest first, in ``lang`` where translated.

        English (CHANGELOG.md) is the source. For German, a version comes from
        CHANGELOG.de.md only when it has the same sections with as many items
        as the English one; otherwise that version stays English, so a
        translation that lags behind never hides a change. Each entry says
        which language it is in (``lang``).
        """
        english = _parse_changelog(_CHANGELOG_PATH)
        if not lang or not lang.lower().startswith("de"):
            return [{**e, "lang": "en"} for e in english]
        german = {e["version"]: e for e in _parse_changelog(_CHANGELOG_DE_PATH)}
        out = []
        for entry in english:
            de = german.get(entry["version"])
            if de and _same_shape(entry, de):
                out.append({**entry, "sections": de["sections"], "lang": "de"})
            else:
                out.append({**entry, "lang": "en"})
        return out

    @staticmethod
    def for_reader(
        entries: list[dict], modules: set[str] | None, *, admin: bool
    ) -> list[dict]:
        """Only the items a reader in a club cares about: untagged items,
        items for a module in *modules* (on in the club, and the reader may
        use it), "admins" items only for an admin, never "staff" items. The
        marks come from the English file (a German version has the same
        shape). A version left without items keeps its heading."""
        out = []
        for entry in entries:
            tags = entry.get("tags") or {}
            sections = {}
            for name, items in entry["sections"].items():
                marks = tags.get(name) or []
                sections[name] = [
                    item
                    for i, item in enumerate(items)
                    if _shown(marks[i] if i < len(marks) else None, modules, admin)
                ]
            out.append({**entry, "sections": sections})
        return out

    @staticmethod
    def get_roadmap() -> list[dict]:
        """Parse ROADMAP.yaml into roadmap items, cached until the file changes.

        Each item is ``{id, status, area, title, summary, version, link}``;
        ``area``, ``title`` and ``summary`` are ``{lang: text}`` maps (a plain string in
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
                    "area": _texts(raw.get("area")),
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


def _same_shape(english: dict, translated: dict) -> bool:
    """True when both have the same sections with as many items each."""
    a = {k: len(v) for k, v in english["sections"].items() if v}
    b = {k: len(v) for k, v in translated["sections"].items() if v}
    return a == b


def _fragment_text(path: Path) -> str:
    """The changelog at *path* with the waiting fragments under [Unreleased]."""
    text = path.read_text(encoding="utf-8")
    lang = "de" if path == _CHANGELOG_DE_PATH else "en"
    try:
        extra = changelog_fragments.collected(_CHANGES_DIR)[lang]
    except changelog_fragments.FragmentError:
        # tests/test_changelog_fragments.py fails on it; What's new still works.
        return text
    return changelog_fragments.fold_into(text, extra)


def _parse_changelog(path: Path) -> list[dict]:
    """Parse a Keep-a-Changelog file into entries, cached until it or a
    fragment changes."""
    if not path.exists():
        return []

    stamp = (
        path.stat().st_mtime,
        tuple((f.name, f.stat().st_mtime) for f in changelog_fragments.files(_CHANGES_DIR)),
    )
    cached = _changelog_cache.get(path)
    if cached is not None and cached[0] == stamp:
        return cached[1]

    entries: list[dict] = []
    current: dict | None = None
    current_section: str | None = None
    # True while the lines below belong to the last bullet (a wrapped item).
    in_item = False

    for line in _fragment_text(path).splitlines():
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

    for entry in entries:
        entry["tags"] = {}
        for name, items in entry["sections"].items():
            marks: list[list[str] | None] = []
            for i, item in enumerate(items):
                items[i], found = _split_for(item)
                marks.append(found)
            entry["tags"][name] = marks

    _changelog_cache[path] = (stamp, entries)
    return entries


def _split_for(item: str) -> tuple[str, list[str] | None]:
    """An item's text without its "<!-- for: ... -->" mark, and the mark's
    words in lower case (None without a mark)."""
    match = _FOR_RE.search(item)
    if match is None:
        return item, None
    words = [w.lower() for w in re.split(r"[,\s]+", match.group("tags")) if w]
    return _FOR_RE.sub(" ", item).strip(), words or None


def _shown(tags: list[str] | None, modules: set[str] | None, admin: bool) -> bool:
    if not tags:
        return True
    if "staff" in tags:
        return False
    if "admins" in tags and not admin:
        return False
    wanted = [t for t in tags if t not in AUDIENCES]
    if not wanted or modules is None:
        return True
    return any(code in modules for code in wanted)
