"""
Tests for VersionService and GET /api/v1/version, /api/v1/version/changelog
"""

from hubra.api.version.services import VersionService


def test_get_version_reads_pyproject_toml():
    version = VersionService.get_version()
    assert version == "0.2.0"


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
    monkeypatch.setattr("hubra.api.version.services._CHANGELOG_PATH", sample)
    monkeypatch.setattr("hubra.api.version.services._changelog_cache", None)

    entries = VersionService.get_changelog()

    assert entries == [
        {"version": "Unreleased", "date": None, "sections": {}},
        {
            "version": "0.2.0",
            "date": "2026-07-03",
            "sections": {"Added": ["New thing"]},
        },
        {
            "version": "0.1.0",
            "date": "2026-07-02",
            "sections": {
                "Added": ["Initial versioned release baseline."],
                "Fixed": ["Something fixed"],
            },
        },
    ]


def test_changelog_reads_real_file_when_uncached(monkeypatch):
    monkeypatch.setattr("hubra.api.version.services._changelog_cache", None)
    entries = VersionService.get_changelog()
    assert any(e["version"] == "0.1.0" for e in entries)


def test_version_endpoint_returns_version_string(client):
    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"version": VersionService.get_version()}


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
    assert set(first.keys()) == {"version", "date", "sections"}


def test_changelog_endpoint_no_auth_required(client):
    resp = client.get("/api/v1/version/changelog")
    assert resp.status_code not in (401, 403)
