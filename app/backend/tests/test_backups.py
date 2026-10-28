"""Tests for the backup system — BackupService, API routes, and config status.

Mocks pg_dump (subprocess), GPG (subprocess), and boto3 (S3) so tests
run without a real Postgres or S3 endpoint.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def backup_config(app):
    """Set backup env vars so BackupService sees them as configured."""
    app.config["BACKUP_ENCRYPTION_KEY"] = "test-encryption-key"
    app.config["BACKUP_S3_ENDPOINT"] = "https://s3.test.example.com"
    app.config["BACKUP_S3_BUCKET"] = "test-bucket"
    app.config["BACKUP_S3_ACCESS_KEY"] = "test-access-key"
    app.config["BACKUP_S3_SECRET_KEY"] = "test-secret-key"
    app.config["BACKUP_S3_REGION"] = "default"
    yield


@pytest.fixture
def mock_s3_client():
    """Mock the boto3 S3 client."""
    client = MagicMock()
    client.head_bucket = MagicMock(return_value={})
    client.upload_file = MagicMock()
    client.download_file = MagicMock()
    client.delete_object = MagicMock()
    return client


class TestBackupRecordModel:
    """BackupRecord model CRUD and status transitions."""

    def test_create_record(self, db):
        from vollbuild.core.models.backup import BackupRecord

        record = BackupRecord(type="manual", status="pending", triggered_by="test")
        db.session.add(record)
        db.session.commit()

        assert record.id is not None
        assert record.type == "manual"
        assert record.status == "pending"
        assert record.triggered_by == "test"
        assert record.created_at is not None
        assert record.size_bytes is None
        assert record.verified_ok is None

    def test_record_repr(self, db):
        from vollbuild.core.models.backup import BackupRecord

        record = BackupRecord(type="manual", status="pending")
        assert "BackupRecord" in repr(record)
        assert "manual" in repr(record)


class TestBackupService:
    """BackupService with mocked subprocess and boto3."""

    def test_get_config_status_unconfigured(self, app, db):
        from vollbuild.core.services.backup import BackupService

        app.config["BACKUP_S3_ENDPOINT"] = ""
        app.config["BACKUP_S3_BUCKET"] = ""
        app.config["BACKUP_S3_ACCESS_KEY"] = ""
        app.config["BACKUP_S3_SECRET_KEY"] = ""
        app.config["BACKUP_ENCRYPTION_KEY"] = ""

        status = BackupService.get_config_status()
        assert status["s3_configured"] is False
        assert status["encryption_configured"] is False
        assert status["s3_reachable"] is False

    def test_get_config_status_configured(self, app, db, mock_s3_client):
        from vollbuild.core.services.backup import BackupService

        app.config["BACKUP_S3_ENDPOINT"] = "https://s3.test.example.com"
        app.config["BACKUP_S3_BUCKET"] = "test-bucket"
        app.config["BACKUP_S3_ACCESS_KEY"] = "test-key"
        app.config["BACKUP_S3_SECRET_KEY"] = "test-secret"
        app.config["BACKUP_ENCRYPTION_KEY"] = "test-enc-key"

        with patch(
            "vollbuild.core.services.backup._get_s3_client", return_value=mock_s3_client
        ):
            status = BackupService.get_config_status()
        assert status["s3_configured"] is True
        assert status["encryption_configured"] is True
        assert status["s3_reachable"] is True

    def test_create_backup_success(self, app, db, backup_config, mock_s3_client):
        from vollbuild.core.services.backup import BackupService

        def fake_run(cmd, env=None, capture_output=True, timeout=None, input=None):
            if cmd[0] == "pg_dump":
                return MagicMock(returncode=0, stdout=b"FAKE_DUMP_DATA", stderr=b"")
            elif cmd[0] == "gpg":
                output_idx = cmd.index("--output") + 1 if "--output" in cmd else None
                output_file = cmd[output_idx] if output_idx else None
                input_file = cmd[-1]
                if output_file and os.path.exists(input_file):
                    with open(output_file, "wb") as f:
                        with open(input_file, "rb") as inf:
                            f.write(b"ENCRYPTED_" + inf.read())
                return MagicMock(returncode=0, stdout=b"", stderr=b"")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        with (
            patch(
                "vollbuild.core.services.backup.subprocess.run", side_effect=fake_run
            ),
            patch(
                "vollbuild.core.services.backup._get_s3_client",
                return_value=mock_s3_client,
            ),
        ):
            record = BackupService.create_backup(
                backup_type="manual", triggered_by="test-admin"
            )

        assert record.status == "completed"
        assert record.s3_key is not None
        assert record.s3_key.startswith("backups/")
        assert record.s3_key.endswith(".dump.gpg")
        assert record.size_bytes is not None
        assert record.size_bytes > 0
        assert record.checksum is not None
        assert len(record.checksum) == 64
        assert record.error_message is None

        mock_s3_client.upload_file.assert_called_once()

    def test_create_backup_no_encryption_key(self, app, db):
        from vollbuild.core.services.backup import BackupService

        app.config["BACKUP_ENCRYPTION_KEY"] = ""
        app.config["BACKUP_S3_ENDPOINT"] = "https://s3.test.example.com"
        app.config["BACKUP_S3_BUCKET"] = "test-bucket"
        app.config["BACKUP_S3_ACCESS_KEY"] = "test-key"
        app.config["BACKUP_S3_SECRET_KEY"] = "test-secret"

        record = BackupService.create_backup(backup_type="manual", triggered_by="test")
        assert record.status == "failed"
        assert "BACKUP_ENCRYPTION_KEY" in (record.error_message or "")

    def test_create_backup_no_s3_config(self, app, db):
        from vollbuild.core.services.backup import BackupService

        app.config["BACKUP_ENCRYPTION_KEY"] = "test-key"
        app.config["BACKUP_S3_ENDPOINT"] = ""
        app.config["BACKUP_S3_BUCKET"] = ""
        app.config["BACKUP_S3_ACCESS_KEY"] = ""

        record = BackupService.create_backup(backup_type="manual")
        assert record.status == "failed"
        assert "S3" in (record.error_message or "")

    def test_create_backup_pg_dump_fails(self, app, db, backup_config, mock_s3_client):
        from vollbuild.core.services.backup import BackupService

        def fake_run(cmd, env=None, capture_output=True, timeout=None, input=None):
            if cmd[0] == "pg_dump":
                return MagicMock(returncode=1, stdout=b"", stderr=b"connection refused")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        with (
            patch(
                "vollbuild.core.services.backup.subprocess.run", side_effect=fake_run
            ),
            patch(
                "vollbuild.core.services.backup._get_s3_client",
                return_value=mock_s3_client,
            ),
        ):
            record = BackupService.create_backup(backup_type="manual")

        assert record.status == "failed"
        assert "pg_dump" in (record.error_message or "")

    def test_verify_backup_success(self, app, db, backup_config, mock_s3_client):
        from vollbuild.core.services.backup import BackupService
        from vollbuild.core.models.backup import BackupRecord

        record = BackupRecord(
            type="manual",
            status="completed",
            s3_key="backups/test.dump.gpg",
            size_bytes=1024,
            checksum="abc123",
        )
        db.session.add(record)
        db.session.commit()

        def fake_run(cmd, env=None, capture_output=True, timeout=None, input=None):
            if cmd[0] == "gpg" and "--decrypt" in cmd:
                output_file = cmd[cmd.index("--output") + 1]
                with open(output_file, "wb") as f:
                    f.write(b"FAKE_DUMP_DATA")
                return MagicMock(returncode=0, stdout=b"", stderr=b"")
            elif cmd[0] == "pg_restore":
                listing = "; Table Data: public.members\n; Table Data: public.roles\n; Table Data: public.setting\n"
                return MagicMock(returncode=0, stdout=listing.encode(), stderr=b"")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        def fake_download(bucket, key, path):
            with open(path, "wb") as f:
                f.write(b"ENCRYPTED_DATA")

        mock_s3_client.download_file = MagicMock(side_effect=fake_download)

        with (
            patch(
                "vollbuild.core.services.backup.subprocess.run", side_effect=fake_run
            ),
            patch(
                "vollbuild.core.services.backup._get_s3_client",
                return_value=mock_s3_client,
            ),
        ):
            result = BackupService.verify_backup(record.id)

        assert result.verified_ok is True
        assert result.verified_at is not None
        assert result.table_count == 3
        assert result.verify_error is None

    def test_verify_backup_not_found(self, app, db):
        from vollbuild.core.services.backup import BackupService

        with pytest.raises(ValueError, match="not found"):
            BackupService.verify_backup(9999)

    def test_verify_backup_not_completed(self, app, db):
        from vollbuild.core.services.backup import BackupService
        from vollbuild.core.models.backup import BackupRecord

        record = BackupRecord(type="manual", status="pending")
        db.session.add(record)
        db.session.commit()

        with pytest.raises(ValueError, match="not in a verifiable state"):
            BackupService.verify_backup(record.id)

    def test_list_backups(self, app, db):
        from vollbuild.core.services.backup import BackupService
        from vollbuild.core.models.backup import BackupRecord

        r1 = BackupRecord(type="manual", status="completed")
        r2 = BackupRecord(type="scheduled_daily", status="completed")
        db.session.add_all([r1, r2])
        db.session.commit()

        records = BackupService.list_backups()
        assert len(records) == 2

    def test_delete_backup(self, app, db, backup_config, mock_s3_client):
        from vollbuild.core.services.backup import BackupService
        from vollbuild.core.models.backup import BackupRecord

        record = BackupRecord(
            type="manual",
            status="completed",
            s3_key="backups/test.dump.gpg",
        )
        db.session.add(record)
        db.session.commit()
        record_id = record.id

        with patch(
            "vollbuild.core.services.backup._get_s3_client", return_value=mock_s3_client
        ):
            BackupService.delete_backup(record_id)

        assert db.session.get(BackupRecord, record_id) is None
        mock_s3_client.delete_object.assert_called_once()

    def test_delete_backup_not_found(self, app, db):
        from vollbuild.core.services.backup import BackupService

        with pytest.raises(ValueError, match="not found"):
            BackupService.delete_backup(9999)

    def test_retention_cleanup(self, app, db, backup_config, mock_s3_client):
        from vollbuild.core.services.backup import BackupService
        from vollbuild.core.models.backup import BackupRecord

        for i in range(10):
            db.session.add(
                BackupRecord(
                    type="scheduled_daily",
                    status="completed",
                    s3_key=f"backups/daily_{i}.dump.gpg",
                )
            )
        db.session.add(
            BackupRecord(
                type="manual", status="completed", s3_key="backups/manual.dump.gpg"
            )
        )
        db.session.commit()

        with patch(
            "vollbuild.core.services.backup._get_s3_client", return_value=mock_s3_client
        ):
            deleted = BackupService.run_retention_cleanup()

        assert deleted.get("scheduled_daily") == 3
        remaining = BackupService.list_backups()
        daily = [r for r in remaining if r.type == "scheduled_daily"]
        assert len(daily) == 7
        manual = [r for r in remaining if r.type == "manual"]
        assert len(manual) == 1


class TestBackupAPI:
    """Backup API routes — admin-only access."""

    def test_list_backups_admin(self, client, seeded_db, auth_headers):
        resp = client.get("/api/v1/backups/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_list_backups_unauthenticated(self, client, seeded_db):
        resp = client.get("/api/v1/backups/")
        assert resp.status_code == 401

    def test_get_config_admin(self, client, seeded_db, auth_headers):
        resp = client.get("/api/v1/backups/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "s3_configured" in data
        assert "encryption_configured" in data

    def test_get_config_unauthenticated(self, client, seeded_db):
        resp = client.get("/api/v1/backups/config")
        assert resp.status_code == 401

    def test_create_backup_testing_mode(
        self, client, seeded_db, auth_headers, app, backup_config, mock_s3_client
    ):
        """In testing mode, POST /backups/ calls BackupService directly (no Celery)."""

        def fake_run(cmd, env=None, capture_output=True, timeout=None, input=None):
            if cmd[0] == "pg_dump":
                return MagicMock(returncode=0, stdout=b"FAKE_DUMP", stderr=b"")
            elif cmd[0] == "gpg":
                output_idx = cmd.index("--output") + 1 if "--output" in cmd else None
                output_file = cmd[output_idx] if output_idx else None
                input_file = cmd[-1]
                if output_file and os.path.exists(input_file):
                    with open(output_file, "wb") as f:
                        with open(input_file, "rb") as inf:
                            f.write(b"ENC_" + inf.read())
                return MagicMock(returncode=0, stdout=b"", stderr=b"")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        with (
            patch(
                "vollbuild.core.services.backup.subprocess.run", side_effect=fake_run
            ),
            patch(
                "vollbuild.core.services.backup._get_s3_client",
                return_value=mock_s3_client,
            ),
        ):
            resp = client.post("/api/v1/backups/", headers=auth_headers)

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["s3_key"] is not None

    def test_get_single_backup(self, client, seeded_db, auth_headers, db):
        from vollbuild.core.models.backup import BackupRecord

        record = BackupRecord(
            type="manual", status="completed", s3_key="backups/test.dump.gpg"
        )
        db.session.add(record)
        db.session.commit()

        resp = client.get(f"/api/v1/backups/{record.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == record.id
        assert data["status"] == "completed"

    def test_get_single_backup_not_found(self, client, seeded_db, auth_headers):
        resp = client.get("/api/v1/backups/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_backup_api(
        self, client, seeded_db, auth_headers, db, app, backup_config, mock_s3_client
    ):
        from vollbuild.core.models.backup import BackupRecord

        record = BackupRecord(
            type="manual", status="completed", s3_key="backups/test.dump.gpg"
        )
        db.session.add(record)
        db.session.commit()
        record_id = record.id

        with patch(
            "vollbuild.core.services.backup._get_s3_client", return_value=mock_s3_client
        ):
            resp = client.delete(f"/api/v1/backups/{record_id}", headers=auth_headers)

        assert resp.status_code == 204

    def test_delete_backup_not_found(self, client, seeded_db, auth_headers):
        resp = client.delete("/api/v1/backups/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_verify_backup_api_testing_mode(
        self, client, seeded_db, auth_headers, db, app, backup_config, mock_s3_client
    ):
        from vollbuild.core.models.backup import BackupRecord

        record = BackupRecord(
            type="manual",
            status="completed",
            s3_key="backups/test.dump.gpg",
        )
        db.session.add(record)
        db.session.commit()

        def fake_run(cmd, env=None, capture_output=True, timeout=None, input=None):
            if cmd[0] == "gpg" and "--decrypt" in cmd:
                output_file = cmd[cmd.index("--output") + 1]
                with open(output_file, "wb") as f:
                    f.write(b"FAKE_DUMP_DATA")
                return MagicMock(returncode=0, stdout=b"", stderr=b"")
            elif cmd[0] == "pg_restore":
                return MagicMock(
                    returncode=0,
                    stdout=b"; Table Data: public.members\n; Table Data: public.roles\n",
                    stderr=b"",
                )
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        def fake_download(bucket, key, path):
            with open(path, "wb") as f:
                f.write(b"ENCRYPTED_DATA")

        mock_s3_client.download_file = MagicMock(side_effect=fake_download)

        with (
            patch(
                "vollbuild.core.services.backup.subprocess.run", side_effect=fake_run
            ),
            patch(
                "vollbuild.core.services.backup._get_s3_client",
                return_value=mock_s3_client,
            ),
        ):
            resp = client.post(
                f"/api/v1/backups/{record.id}/verify", headers=auth_headers
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["verified_ok"] is True
        assert data["table_count"] == 2

    def test_verify_backup_not_completed(self, client, seeded_db, auth_headers, db):
        from vollbuild.core.models.backup import BackupRecord

        record = BackupRecord(type="manual", status="pending")
        db.session.add(record)
        db.session.commit()

        resp = client.post(f"/api/v1/backups/{record.id}/verify", headers=auth_headers)
        assert resp.status_code == 409
