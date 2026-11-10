"""
Tests for VersionService and GET /api/v1/version, /api/v1/version/changelog
"""

import re
import tomllib
from pathlib import Path

import pytest

from hubra.core.services.version import VersionService

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_get_version_reads_pyproject_toml():
    # Compared with the file, not a fixed number, so a version bump needs no
    # test change (CI skips the tests on version-only pull requests).
    with _PYPROJECT.open("rb") as f:
        expected = tomllib.load(f)["project"]["version"]
    version = VersionService.get_version()
    assert version == expected
    assert re.fullmatch(r"\d+\.\d+\.\d+([-.+].+)?", version)


def test_changelog_parses_sample_file(tmp_path, monkeypatch):
    sample = tmp_path / "CHANGELOG.md"
    sample.write_text(
        "# Changelog\n"
        "\n"
        "## [Unreleased]\n"
        "\n"
        "## [0.2.0] - 2026-07-03\n"
        "### Added\n"
        "- New thing\n"
        "\n"
        "## [0.1.0] - 2026-07-02\n"
        "### Added\n"
        "- Initial versioned release baseline.\n"
        "### Fixed\n"
        "- Something fixed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("hubra.core.services.version._CHANGELOG_PATH", sample)
    monkeypatch.setattr("hubra.core.services.version._changelog_cache", {})

    # "tags" (who each item is for) stays inside; the endpoint drops it.
    entries = [
        {k: v for k, v in e.items() if k != "tags"}
        for e in VersionService.get_changelog()
    ]

    assert entries == [
        {"version": "Unreleased", "date": None, "sections": {}, "lang": "en"},
        {
            "version": "0.2.0",
            "date": "2026-07-03",
            "sections": {"Added": ["New thing"]},
            "lang": "en",
        },
        {
            "version": "0.1.0",
            "date": "2026-07-02",
            "sections": {
                "Added": ["Initial versioned release baseline."],
                "Fixed": ["Something fixed"],
            },
            "lang": "en",
        },
    ]


def test_changelog_reads_real_file_when_uncached(monkeypatch):
    monkeypatch.setattr("hubra.core.services.version._changelog_cache", {})
    entries = VersionService.get_changelog()
    assert any(e["version"] == "0.1.0" for e in entries)


def test_version_endpoint_returns_version_string(client):
    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["version"] == VersionService.get_version()
    assert "commit" in data


def test_version_endpoint_no_auth_required(client):
    resp = client.get("/api/v1/version")
    assert resp.status_code not in (401, 403)


def test_changelog_endpoint_structure(client):
    resp = client.get("/api/v1/version/changelog")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["version"] == VersionService.get_version()
    assert isinstance(data["entries"], list)
    assert data["entries"], "expected at least one changelog entry"
    first = data["entries"][0]
    assert set(first.keys()) == {"version", "date", "sections", "lang"}


def test_changelog_endpoint_no_auth_required(client):
    resp = client.get("/api/v1/version/changelog")
    assert resp.status_code not in (401, 403)


def test_changelog_joins_wrapped_item_lines(tmp_path, monkeypatch):
    sample = tmp_path / "CHANGELOG.md"
    sample.write_text(
        "## [0.3.0] - 2026-08-01\n"
        "### Added\n"
        "- **Long item** that goes on\n"
        "  onto the next line.\n"
        "- Second item\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("hubra.core.services.version._CHANGELOG_PATH", sample)
    monkeypatch.setattr("hubra.core.services.version._changelog_cache", {})

    entries = VersionService.get_changelog()

    assert entries[0]["sections"]["Added"] == [
        "**Long item** that goes on onto the next line.",
        "Second item",
    ]


def test_roadmap_parses_items_and_skips_bad_ones(tmp_path, monkeypatch):
    sample = tmp_path / "ROADMAP.yaml"
    sample.write_text(
        "items:\n"
        "  - id: a\n"
        "    status: next\n"
        "    area: Finance\n"
        "    title: {de: Titel, en: Title}\n"
        "    summary: Plain English summary\n"
        "    link: javascript:alert(1)\n"
        "  - id: b\n"
        "    status: Done\n"
        "    title: Shipped\n"
        "    version: 0.6.0\n"
        "    link: https://example.org/b\n"
        "  - id: c\n"
        "    status: someday\n"
        "    title: Unknown status\n"
        "  - status: now\n"
        "    title: No id\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("hubra.core.services.version._ROADMAP_PATH", sample)
    monkeypatch.setattr("hubra.core.services.version._roadmap_cache", None)

    items = VersionService.get_roadmap()

    assert items == [
        {
            "id": "a",
            "status": "next",
            "area": {"en": "Finance"},
            "title": {"de": "Titel", "en": "Title"},
            "summary": {"en": "Plain English summary"},
            "version": None,
            "link": None,
        },
        {
            "id": "b",
            "status": "done",
            "area": {},
            "title": {"en": "Shipped"},
            "summary": {},
            "version": "0.6.0",
            "link": "https://example.org/b",
        },
    ]


def test_roadmap_shipped_file_is_valid(monkeypatch):
    import yaml

    from hubra.core.services import version as services

    monkeypatch.setattr("hubra.core.services.version._roadmap_cache", None)
    raw = yaml.safe_load(services._ROADMAP_PATH.read_text(encoding="utf-8"))["items"]
    items = VersionService.get_roadmap()
    # Every item in the shipped file is shown, ids are unique, both languages.
    assert len(items) == len(raw)
    assert len({i["id"] for i in items}) == len(items)
    for item in items:
        assert item["title"].get("de") and item["title"].get("en"), item["id"]


def test_roadmap_endpoint(client):
    resp = client.get("/api/v1/version/roadmap")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["statuses"] == ["now", "next", "later", "done", "idea"]
    assert isinstance(body["items"], list)
    assert all(i["source"] in ("plan", "idea") for i in body["items"])


def test_changelog_in_german_falls_back_per_version(tmp_path, monkeypatch):
    en = tmp_path / "CHANGELOG.md"
    en.write_text(
        "## [Unreleased]\n### Added\n- One\n- Two\n"
        "## [0.2.0] - 2026-07-03\n### Fixed\n- Bug\n"
        "## [0.1.0] - 2026-07-02\n### Added\n- Start\n",
        encoding="utf-8",
    )
    de = tmp_path / "CHANGELOG.de.md"
    # Unreleased lags behind (one item), 0.2.0 matches, 0.1.0 is missing.
    de.write_text(
        "## [Unreleased]\n### Added\n- Eins\n## [0.2.0] - 2026-07-03\n### Fixed\n- Fehler\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("hubra.core.services.version._CHANGELOG_PATH", en)
    monkeypatch.setattr("hubra.core.services.version._CHANGELOG_DE_PATH", de)
    monkeypatch.setattr("hubra.core.services.version._changelog_cache", {})

    entries = VersionService.get_changelog("de-CH")

    assert [(e["version"], e["lang"]) for e in entries] == [
        ("Unreleased", "en"),
        ("0.2.0", "de"),
        ("0.1.0", "en"),
    ]
    assert entries[0]["sections"] == {"Added": ["One", "Two"]}
    assert entries[1]["sections"] == {"Fixed": ["Fehler"]}
    assert [e["lang"] for e in VersionService.get_changelog("en")] == ["en"] * 3


def test_shipped_german_changelog_only_has_known_versions(monkeypatch):
    from hubra.core.services import version as services

    monkeypatch.setattr("hubra.core.services.version._changelog_cache", {})
    english = {
        e["version"] for e in services._parse_changelog(services._CHANGELOG_PATH)
    }
    german = services._parse_changelog(services._CHANGELOG_DE_PATH)
    assert german, "CHANGELOG.de.md is missing or empty"
    assert {e["version"] for e in german} <= english
    # Released versions are translated in full; only Unreleased may lag.
    shown = VersionService.get_changelog("de")
    lagging = [
        e["version"]
        for e in shown
        if e["lang"] == "en" and e["version"] != "Unreleased"
    ]
    assert lagging == []


def test_changelog_endpoint_takes_a_language(client):
    resp = client.get("/api/v1/version/changelog?lang=de")
    assert resp.status_code == 200
    assert any(e["lang"] == "de" for e in resp.get_json()["entries"])


def test_instance_lists_the_legal_pages(client, db):
    from hubra.core.services import platform_settings

    body = client.get("/api/v1/instance").get_json()
    assert body["legal"] == {
        "privacyUrl": "https://hubra.club/datenschutz/",
        "termsUrl": "https://hubra.club/nutzungsbedingungen/",
        "imprintUrl": "https://hubra.club/impressum/",
    }
    platform_settings.set_many(
        {"legal.terms_url": "https://example.test/agb", "legal.imprint_url": ""}
    )
    db.session.commit()
    body = client.get("/api/v1/instance").get_json()
    assert body["legal"]["termsUrl"] == "https://example.test/agb"
    assert body["legal"]["imprintUrl"] is None


# ── Who an item is for (<!-- for: ... -->) ─────────────────────────────────

MARKED = """# Changelog

## [Unreleased]

### Added

- For everyone.
- Event templates. <!-- for: events -->
- Posters for the club.
  <!-- for: members, admins -->
- Deploy steps. <!-- for: staff -->
- Support access. <!-- FOR: Admins -->
"""

MARKED_DE = """# Changelog

## [Unreleased]

### Added

- Für alle.
- Anlass-Vorlagen.
- Plakate.
- Deploy.
- Support-Zugriff.
"""


@pytest.fixture
def marked(tmp_path, monkeypatch):
    en, de = tmp_path / "CHANGELOG.md", tmp_path / "CHANGELOG.de.md"
    en.write_text(MARKED)
    de.write_text(MARKED_DE)
    monkeypatch.setattr("hubra.core.services.version._CHANGELOG_PATH", en)
    monkeypatch.setattr("hubra.core.services.version._CHANGELOG_DE_PATH", de)
    monkeypatch.setattr("hubra.core.services.version._changelog_cache", {})


def _added(entries):
    return entries[0]["sections"]["Added"]


def test_marks_are_stripped_from_the_text(marked):
    items = _added(VersionService.get_changelog("en"))
    assert items == [
        "For everyone.",
        "Event templates.",
        "Posters for the club.",
        "Deploy steps.",
        "Support access.",
    ]


def test_a_member_sees_their_modules_only(marked):
    entries = VersionService.for_reader(
        VersionService.get_changelog("en"), {"posts"}, admin=False
    )
    assert _added(entries) == ["For everyone."]
    entries = VersionService.for_reader(
        VersionService.get_changelog("en"), {"events"}, admin=False
    )
    assert _added(entries) == ["For everyone.", "Event templates."]


def test_an_admin_sees_admin_items_but_never_staff_ones(marked):
    entries = VersionService.for_reader(
        VersionService.get_changelog("en"), {"events", "members"}, admin=True
    )
    assert _added(entries) == [
        "For everyone.",
        "Event templates.",
        "Posters for the club.",
        "Support access.",
    ]


def test_german_follows_the_english_marks(marked):
    entries = VersionService.for_reader(
        VersionService.get_changelog("de"), {"events"}, admin=False
    )
    assert entries[0]["lang"] == "de"
    assert _added(entries) == ["Für alle.", "Anlass-Vorlagen."]


def test_the_endpoint_filters_for_one_reader(client, marked):
    resp = client.get("/api/v1/global/version/changelog?modules=events&admin=0")
    assert resp.status_code == 200
    entry = resp.get_json()["entries"][0]
    assert "tags" not in entry
    assert entry["sections"]["Added"] == ["For everyone.", "Event templates."]
    # Without a reader (support site, manage): everything, marks stripped.
    unfiltered = client.get("/api/v1/global/version/changelog").get_json()
    assert len(unfiltered["entries"][0]["sections"]["Added"]) == 5


def test_the_shipped_changelog_marks_name_known_modules(monkeypatch):
    from hubra.core.modules import registry
    from hubra.core.services.version import AUDIENCES

    monkeypatch.setattr("hubra.core.services.version._changelog_cache", {})
    known = set(registry._modules) | set(AUDIENCES)
    for entry in VersionService.get_changelog("en"):
        for marks in (entry.get("tags") or {}).values():
            for words in marks:
                assert not set(words or []) - known, words
