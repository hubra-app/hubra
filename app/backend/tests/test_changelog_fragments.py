"""Changelog entries in app/backend/changes/ (hubra.core.changelog_fragments)."""

import pytest

from hubra.core import changelog_fragments as cf

LOG = """# Changelog

Intro.

## [Unreleased]

### Fixed

- Old fix.

## [1.0.0] - 2026-11-01

### Added

- First.
"""

FRAGMENT = """### Added

- **New**: thing. <!-- for: events -->

### Fixed

- Another fix,
  wrapped.

<!-- de -->

### Added

- **Neu**: Sache. <!-- for: events -->

### Fixed

- Noch ein Fix,
  umbrochen.
"""


def test_shipped_fragments_are_valid():
    # Every file in app/backend/changes/ has English and German in the same shape.
    for path in cf.files():
        cf.read(path)


def test_shipped_fragments_use_swiss_spelling():
    for path in cf.files():
        assert "ß" not in path.read_text(encoding="utf-8"), path.name


def test_read_checks_the_shape(tmp_path):
    good = tmp_path / "good.md"
    good.write_text(FRAGMENT)
    parts = cf.read(good)
    assert parts["en"]["Fixed"] == ["- Another fix,\n  wrapped."]
    assert parts["de"]["Added"] == ["- **Neu**: Sache. <!-- for: events -->"]

    no_german = tmp_path / "a.md"
    no_german.write_text("### Added\n\n- x\n")
    with pytest.raises(cf.FragmentError, match="<!-- de -->"):
        cf.read(no_german)

    uneven = tmp_path / "b.md"
    uneven.write_text("### Added\n\n- x\n- y\n\n<!-- de -->\n\n### Added\n\n- x\n")
    with pytest.raises(cf.FragmentError, match="same sections"):
        cf.read(uneven)


def test_fold_into_appends_and_orders_sections():
    out = cf.fold_into(LOG, {"Fixed": ["- New fix."], "Added": ["- New."]})
    unreleased = out.split("## [Unreleased]")[1].split("## [1.0.0]")[0]
    assert unreleased == "\n\n### Added\n\n- New.\n\n### Fixed\n\n- Old fix.\n- New fix.\n\n"
    # The rest of the file is untouched.
    assert out.startswith("# Changelog\n\nIntro.\n\n## [Unreleased]\n")
    assert out.endswith("## [1.0.0] - 2026-11-01\n\n### Added\n\n- First.\n")


def test_fold_into_adds_unreleased_when_missing():
    log = "# Changelog\n\n## [1.0.0] - 2026-11-01\n\n### Added\n\n- First.\n"
    out = cf.fold_into(log, {"Changed": ["- X."]})
    assert out == (
        "# Changelog\n\n## [Unreleased]\n\n### Changed\n\n- X.\n\n"
        "## [1.0.0] - 2026-11-01\n\n### Added\n\n- First.\n"
    )
    assert cf.fold_into(log, {}) == log


def test_fold_moves_fragments_and_deletes_them(tmp_path):
    changes = tmp_path / "changes"
    changes.mkdir()
    (changes / "README.md").write_text("not a fragment")
    (changes / "b-second.md").write_text(FRAGMENT.replace("New", "Second").replace("Neu", "Zweit"))
    (changes / "a-first.md").write_text(FRAGMENT)
    en, de = tmp_path / "CHANGELOG.md", tmp_path / "CHANGELOG.de.md"
    en.write_text(LOG)
    de.write_text(LOG.replace("Old fix.", "Alter Fix."))

    done = cf.fold(changes, {"en": en, "de": de})

    assert [p.name for p in done] == ["a-first.md", "b-second.md"]
    assert [p.name for p in changes.iterdir()] == ["README.md"]
    text = en.read_text()
    assert text.index("**New**") < text.index("**Second**") < text.index("## [1.0.0]")
    assert "- Old fix.\n- Another fix,\n  wrapped.\n- Another fix," in text
    assert "**Zweit**" in de.read_text() and "**Second**" not in de.read_text()


def test_whats_new_shows_fragments_under_unreleased(tmp_path, monkeypatch):
    from hubra.core.services.version import VersionService

    changes = tmp_path / "changes"
    changes.mkdir()
    (changes / "x.md").write_text(FRAGMENT)
    en, de = tmp_path / "CHANGELOG.md", tmp_path / "CHANGELOG.de.md"
    en.write_text(LOG)
    de.write_text(LOG.replace("Old fix.", "Alter Fix.").replace("First.", "Erstes."))
    monkeypatch.setattr("hubra.core.services.version._CHANGELOG_PATH", en)
    monkeypatch.setattr("hubra.core.services.version._CHANGELOG_DE_PATH", de)
    monkeypatch.setattr("hubra.core.services.version._CHANGES_DIR", changes)
    monkeypatch.setattr("hubra.core.services.version._changelog_cache", {})

    english = VersionService.get_changelog("en")[0]
    assert english["version"] == "Unreleased"
    assert english["sections"] == {
        "Added": ["**New**: thing."],
        "Fixed": ["Old fix.", "Another fix, wrapped."],
    }
    assert english["tags"]["Added"] == [["events"]]

    german = VersionService.get_changelog("de-CH")[0]
    assert german["lang"] == "de"
    assert german["sections"]["Added"] == ["**Neu**: Sache."]

    # A new fragment shows without a restart.
    (changes / "y.md").write_text("### Removed\n\n- Gone.\n\n<!-- de -->\n\n### Removed\n\n- Weg.\n")
    assert VersionService.get_changelog("en")[0]["sections"]["Removed"] == ["Gone."]
