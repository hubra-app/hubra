"""pg_dump/pg_restore must not be older than the database server.

pg_dump aborts with "server version mismatch" when the server's major version
is newer than its own (PostgreSQL 18 server, pg_dump 16 in the image).  These
tests cover picking the client, and that the backend image installs a client
for every Postgres image the deployments in this repository run.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from hubra.core.services import pg_tools

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def lib(tmp_path):
    """A fake /usr/lib/postgresql with clients 16, 17 and 18."""

    def make(*majors):
        for m in majors:
            bin_dir = tmp_path / str(m) / "bin"
            bin_dir.mkdir(parents=True)
            for name in ("pg_dump", "pg_restore"):
                exe = bin_dir / name
                exe.write_text("#!/bin/sh\n")
                exe.chmod(0o755)
        return str(tmp_path)

    return make


def test_installed_majors_sorted_and_ignores_non_clients(lib, tmp_path):
    lib_dir = lib(18, 16, 17)
    (tmp_path / "15").mkdir()  # no bin/pg_dump: not a client
    (tmp_path / "common").mkdir()
    assert pg_tools.installed_majors(lib_dir) == [16, 17, 18]


def test_installed_majors_missing_dir():
    assert pg_tools.installed_majors("/nonexistent/pg") == []


@pytest.mark.parametrize(
    ("server", "expected"),
    [(16, 16), (17, 17), (18, 18), (15, 16), (13, 16)],
)
def test_picks_matching_or_closest_newer_client(lib, server, expected):
    lib_dir = lib(16, 17, 18)
    assert pg_tools.tool("pg_dump", server, lib_dir) == os.path.join(
        lib_dir, str(expected), "bin", "pg_dump"
    )


def test_server_newer_than_every_client_is_a_clear_error(lib):
    """The reported bug: server 18, only client 16 in the image."""
    lib_dir = lib(16)
    with pytest.raises(pg_tools.ClientTooOld, match="PostgreSQL 18.*newest pg_dump.*16"):
        pg_tools.tool("pg_dump", 18, lib_dir)


def test_falls_back_to_path_without_versioned_clients():
    assert pg_tools.tool("pg_dump", 18, "/nonexistent/pg") == "pg_dump"


def test_unknown_server_uses_path(lib):
    assert pg_tools.tool("pg_dump", None, lib(16, 18)) == "pg_dump"


def test_newest_restore_reads_any_archive(lib):
    lib_dir = lib(16, 17, 18)
    assert pg_tools.newest("pg_restore", lib_dir).endswith("/18/bin/pg_restore")


def test_create_backup_fails_clearly_when_client_too_old(app, db, monkeypatch, lib):
    """A backup against a newer server fails before running pg_dump, with
    the reason on the record."""
    from unittest.mock import patch

    from hubra.core.services.backup import BackupService

    monkeypatch.setattr(pg_tools, "PG_LIB_DIR", lib(16))
    monkeypatch.setattr(pg_tools, "server_major", lambda: 18)
    app.config["BACKUP_ENCRYPTION_KEY"] = "test-encryption-key"
    with (
        patch("hubra.core.services.backup._get_s3_client", return_value=object()),
        patch("hubra.core.services.backup._get_s3_config", return_value={}),
        patch("hubra.core.services.backup.subprocess.run") as run,
    ):
        record = BackupService.create_backup("manual", triggered_by="test")
    assert record.status == "failed"
    assert "PostgreSQL 18" in record.error_message
    run.assert_not_called()


def test_status_reports_mismatch(monkeypatch, lib):
    monkeypatch.setattr(pg_tools, "PG_LIB_DIR", lib(16))
    monkeypatch.setattr(pg_tools, "server_major", lambda: 18)
    st = pg_tools.status()
    assert not st.ok
    assert st.client_majors == [16]
    assert "PostgreSQL 18" in st.error


# ── The image covers every Postgres the deployments run ────────────────────


def _image_client_majors() -> set[int]:
    dockerfile = (REPO / "app/backend/Dockerfile").read_text()
    return {int(m) for m in re.findall(r"postgresql-client-(\d+)", dockerfile)}


def _deployed_server_majors() -> dict[str, int]:
    """Postgres major per file, from Compose and the k3s manifests."""
    found: dict[str, int] = {}
    files = [REPO / "docker-compose.yml", *sorted((REPO / "deploy").rglob("*.yaml"))]
    pattern = re.compile(
        r"(?:image:\s*[\"']?(?:docker\.io/)?(?:library/)?postgres:"
        r"|imageName:\s*[\"']?ghcr\.io/cloudnative-pg/postgresql:)(\d+)"
    )
    for path in files:
        for major in pattern.findall(path.read_text()):
            found[f"{path.relative_to(REPO)}:{major}"] = int(major)
    return found


def test_backend_image_has_a_client_for_every_deployed_postgres():
    clients = _image_client_majors()
    servers = _deployed_server_majors()
    assert clients, "app/backend/Dockerfile installs no postgresql-client-<major>"
    assert servers, "no Postgres image found in docker-compose.yml or deploy/"
    newest = max(clients)
    too_new = {where: m for where, m in servers.items() if m > newest}
    assert not too_new, (
        f"pg_dump {newest} in the backend image cannot back up {too_new}: "
        "add postgresql-client-<major> to app/backend/Dockerfile"
    )


def test_backend_image_supports_postgres_18():
    """Installs run their own PostgreSQL 18 (CloudNativePG, managed Postgres)."""
    assert max(_image_client_majors()) >= 18


# ── A real backup against the test database (Postgres test mode) ───────────


def test_real_backup_uses_a_client_matching_the_server(app, db, tmp_path):
    """Runs the real pg_dump: only on Postgres (TEST_DATABASE_URL) with the
    PostgreSQL clients installed.  S3 and encryption are stubbed out."""
    import shutil
    import subprocess
    from unittest.mock import MagicMock, patch

    from hubra.core.services.backup import BackupService

    server = pg_tools.server_major()
    if server is None or not shutil.which(pg_tools.tool("pg_dump", server)):
        pytest.skip("needs a Postgres test database and pg_dump")

    uploaded = tmp_path / "uploaded.dump"

    def fake_encrypt(src, dst_base, _keys, **_kw):
        shutil.copy(src, dst_base + ".plain")
        return dst_base + ".plain"

    s3 = MagicMock()
    s3.upload_file.side_effect = lambda path, *_: shutil.copy(path, uploaded)
    app.config["BACKUP_ENCRYPTION_KEY"] = "test-encryption-key"
    with (
        patch("hubra.core.services.backup._get_s3_client", return_value=s3),
        patch("hubra.core.services.backup.backup_crypto.encrypt", fake_encrypt),
    ):
        record = BackupService.create_backup("manual", triggered_by="test")

    assert record.status == "completed", record.error_message
    listing = subprocess.run(
        [pg_tools.newest("pg_restore"), "--list", str(uploaded)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    dumped_from = re.search(r"Dumped from database version: (\d+)", listing)
    dumped_by = re.search(r"Dumped by pg_dump version: (\d+)", listing)
    assert int(dumped_from.group(1)) == server
    assert int(dumped_by.group(1)) >= server
    assert "TABLE DATA public" in listing
