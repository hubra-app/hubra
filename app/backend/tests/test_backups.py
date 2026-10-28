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
        from hubra.core.models.backup import BackupRecord

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
        from hubra.core.models.backup import BackupRecord

        record = BackupRecord(type="manual", status="pending")
        assert "BackupRecord" in repr(record)
        assert "manual" in repr(record)


class TestBackupService:
    """BackupService with mocked subprocess and boto3."""

    def test_get_config_status_unconfigured(self, app, db):
        from hubra.core.services.backup import BackupService

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
        from hubra.core.services.backup import BackupService

        app.config["BACKUP_S3_ENDPOINT"] = "https://s3.test.example.com"
        app.config["BACKUP_S3_BUCKET"] = "test-bucket"
        app.config["BACKUP_S3_ACCESS_KEY"] = "test-key"
        app.config["BACKUP_S3_SECRET_KEY"] = "test-secret"
        app.config["BACKUP_ENCRYPTION_KEY"] = "test-enc-key"

        with patch(
            "hubra.core.services.backup._get_s3_client", return_value=mock_s3_client
        ):
            status = BackupService.get_config_status()
        assert status["s3_configured"] is True
        assert status["encryption_configured"] is True
        assert status["s3_reachable"] is True

    def test_create_backup_success(self, app, db, backup_config, mock_s3_client):
        from hubra.core.services.backup import BackupService

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
            patch("hubra.core.services.backup.subprocess.run", side_effect=fake_run),
            patch(
                "hubra.core.services.backup._get_s3_client",
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
        from hubra.core.services.backup import BackupService

        app.config["BACKUP_ENCRYPTION_KEY"] = ""
        app.config["BACKUP_S3_ENDPOINT"] = "https://s3.test.example.com"
        app.config["BACKUP_S3_BUCKET"] = "test-bucket"
        app.config["BACKUP_S3_ACCESS_KEY"] = "test-key"
        app.config["BACKUP_S3_SECRET_KEY"] = "test-secret"

        record = BackupService.create_backup(backup_type="manual", triggered_by="test")
        assert record.status == "failed"
        assert "BACKUP_ENCRYPTION_KEY" in (record.error_message or "")

    def test_create_backup_no_s3_config(self, app, db):
        from hubra.core.services.backup import BackupService

        app.config["BACKUP_ENCRYPTION_KEY"] = "test-key"
        app.config["BACKUP_S3_ENDPOINT"] = ""
        app.config["BACKUP_S3_BUCKET"] = ""
        app.config["BACKUP_S3_ACCESS_KEY"] = ""

        record = BackupService.create_backup(backup_type="manual")
        assert record.status == "failed"
        assert "S3" in (record.error_message or "")

    def test_create_backup_pg_dump_fails(self, app, db, backup_config, mock_s3_client):
        from hubra.core.services.backup import BackupService

        def fake_run(cmd, env=None, capture_output=True, timeout=None, input=None):
            if cmd[0] == "pg_dump":
                return MagicMock(returncode=1, stdout=b"", stderr=b"connection refused")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        with (
            patch("hubra.core.services.backup.subprocess.run", side_effect=fake_run),
            patch(
                "hubra.core.services.backup._get_s3_client",
                return_value=mock_s3_client,
            ),
        ):
            record = BackupService.create_backup(backup_type="manual")

        assert record.status == "failed"
        assert "pg_dump" in (record.error_message or "")

    def test_verify_backup_success(self, app, db, backup_config, mock_s3_client):
        from hubra.core.services.backup import BackupService
        from hubra.core.models.backup import BackupRecord

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
            patch("hubra.core.services.backup.subprocess.run", side_effect=fake_run),
            patch(
                "hubra.core.services.backup._get_s3_client",
                return_value=mock_s3_client,
            ),
        ):
            result = BackupService.verify_backup(record.id)

        assert result.verified_ok is True
        assert result.verified_at is not None
        assert result.table_count == 3
        assert result.verify_error is None

    def test_verify_backup_not_found(self, app, db):
        from hubra.core.services.backup import BackupService

        with pytest.raises(ValueError, match="not found"):
            BackupService.verify_backup(9999)

    def test_verify_backup_not_completed(self, app, db):
        from hubra.core.services.backup import BackupService
        from hubra.core.models.backup import BackupRecord

        record = BackupRecord(type="manual", status="pending")
        db.session.add(record)
        db.session.commit()

        with pytest.raises(ValueError, match="not in a verifiable state"):
            BackupService.verify_backup(record.id)

    def test_list_backups(self, app, db):
        from hubra.core.services.backup import BackupService
        from hubra.core.models.backup import BackupRecord

        r1 = BackupRecord(type="manual", status="completed")
        r2 = BackupRecord(type="scheduled_daily", status="completed")
        db.session.add_all([r1, r2])
        db.session.commit()

        records = BackupService.list_backups()
        assert len(records) == 2

    def test_delete_backup(self, app, db, backup_config, mock_s3_client):
        from hubra.core.services.backup import BackupService
        from hubra.core.models.backup import BackupRecord

        record = BackupRecord(
            type="manual",
            status="completed",
            s3_key="backups/test.dump.gpg",
        )
        db.session.add(record)
        db.session.commit()
        record_id = record.id

        with patch(
            "hubra.core.services.backup._get_s3_client", return_value=mock_s3_client
        ):
            BackupService.delete_backup(record_id)

        assert db.session.get(BackupRecord, record_id) is None
        mock_s3_client.delete_object.assert_called_once()

    def test_delete_backup_not_found(self, app, db):
        from hubra.core.services.backup import BackupService

        with pytest.raises(ValueError, match="not found"):
            BackupService.delete_backup(9999)

    def test_retention_cleanup(self, app, db, backup_config, mock_s3_client):
        from hubra.core.services.backup import BackupService
        from hubra.core.models.backup import BackupRecord

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
            "hubra.core.services.backup._get_s3_client", return_value=mock_s3_client
        ):
            deleted = BackupService.run_retention_cleanup()

        assert deleted.get("scheduled_daily") == 3
        remaining = BackupService.list_backups()
        daily = [r for r in remaining if r.type == "scheduled_daily"]
        assert len(daily) == 7
        manual = [r for r in remaining if r.type == "manual"]
        assert len(manual) == 1


class TestBackupAPI:
    """Backup API routes in the manager portal: platform staff only."""

    @pytest.fixture(autouse=True)
    def _platform_staff(self, seeded_db, db):
        """A backup holds every club: only platform staff may use the API."""
        seeded_db["user"].is_superadmin = True
        db.session.commit()
        yield
        seeded_db["user"].is_superadmin = False
        db.session.commit()

    def test_club_admins_are_refused(self, client, seeded_db, auth_headers, db):
        seeded_db["user"].is_superadmin = False
        db.session.commit()
        url = "/api/v1/manager/platform/backups/"
        assert client.get(url, headers=auth_headers).status_code == 403
        assert client.post(url, headers=auth_headers).status_code == 403
        # The old club route is gone.
        assert client.get("/api/v1/backups/", headers=auth_headers).status_code == 404

    def test_list_backups_admin(self, client, seeded_db, auth_headers):
        resp = client.get("/api/v1/manager/platform/backups/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_list_backups_unauthenticated(self, client, seeded_db):
        resp = client.get("/api/v1/manager/platform/backups/")
        assert resp.status_code == 401

    def test_get_config_admin(self, client, seeded_db, auth_headers):
        resp = client.get("/api/v1/manager/platform/backups/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "s3_configured" in data
        assert "encryption_configured" in data

    def test_get_config_unauthenticated(self, client, seeded_db):
        resp = client.get("/api/v1/manager/platform/backups/config")
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
            patch("hubra.core.services.backup.subprocess.run", side_effect=fake_run),
            patch(
                "hubra.core.services.backup._get_s3_client",
                return_value=mock_s3_client,
            ),
        ):
            resp = client.post("/api/v1/manager/platform/backups/", headers=auth_headers)

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["s3_key"] is not None

    def test_get_single_backup(self, client, seeded_db, auth_headers, db):
        from hubra.core.models.backup import BackupRecord

        record = BackupRecord(
            type="manual", status="completed", s3_key="backups/test.dump.gpg"
        )
        db.session.add(record)
        db.session.commit()

        resp = client.get(f"/api/v1/manager/platform/backups/{record.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == record.id
        assert data["status"] == "completed"

    def test_get_single_backup_not_found(self, client, seeded_db, auth_headers):
        resp = client.get("/api/v1/manager/platform/backups/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_backup_api(
        self, client, seeded_db, auth_headers, db, app, backup_config, mock_s3_client
    ):
        from hubra.core.models.backup import BackupRecord

        record = BackupRecord(
            type="manual", status="completed", s3_key="backups/test.dump.gpg"
        )
        db.session.add(record)
        db.session.commit()
        record_id = record.id

        with patch(
            "hubra.core.services.backup._get_s3_client", return_value=mock_s3_client
        ):
            resp = client.delete(f"/api/v1/manager/platform/backups/{record_id}", headers=auth_headers)

        assert resp.status_code == 204

    def test_delete_backup_not_found(self, client, seeded_db, auth_headers):
        resp = client.delete("/api/v1/manager/platform/backups/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_verify_backup_api_testing_mode(
        self, client, seeded_db, auth_headers, db, app, backup_config, mock_s3_client
    ):
        from hubra.core.models.backup import BackupRecord

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
            patch("hubra.core.services.backup.subprocess.run", side_effect=fake_run),
            patch(
                "hubra.core.services.backup._get_s3_client",
                return_value=mock_s3_client,
            ),
        ):
            resp = client.post(
                f"/api/v1/manager/platform/backups/{record.id}/verify", headers=auth_headers
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["verified_ok"] is True
        assert data["table_count"] == 2

    def test_verify_backup_not_completed(self, client, seeded_db, auth_headers, db):
        from hubra.core.models.backup import BackupRecord

        record = BackupRecord(type="manual", status="pending")
        db.session.add(record)
        db.session.commit()

        resp = client.post(f"/api/v1/manager/platform/backups/{record.id}/verify", headers=auth_headers)
        assert resp.status_code == 409


# ── Global and per-club backups, club restore ────────────────────────────────


def _fake_tools(calls, *, restore_rc=0):
    """subprocess.run stand-in for pg_dump, gpg and pg_restore; records each cmd."""

    def fake_run(cmd, env=None, capture_output=True, timeout=None, input=None):
        calls.append(cmd)
        if cmd[0] == "pg_dump":
            return MagicMock(returncode=0, stdout=b"FAKE_DUMP", stderr=b"")
        if cmd[0] == "gpg":
            output_file = cmd[cmd.index("--output") + 1]
            with open(output_file, "wb") as f:
                f.write(b"GPG_OUT")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")
        if cmd[0] == "pg_restore":
            return MagicMock(returncode=restore_rc, stdout=b"", stderr=b"boom")
        return MagicMock(returncode=0, stdout=b"", stderr=b"")

    return fake_run


def _download(bucket, key, path):
    with open(path, "wb") as f:
        f.write(b"ENCRYPTED")


def _club(db, status="active"):
    import uuid

    from hubra.core.models.tenant import Tenant

    slug = f"club-{uuid.uuid4().hex[:8]}"
    tenant = Tenant(name=slug, slug=slug, plan="starter", status=status)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def _club_record(db, tenant, **kw):
    from hubra.core.models.backup import BackupRecord

    record = BackupRecord(
        type="manual",
        status="completed",
        scope="club",
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        s3_key=f"backups/clubs/{tenant.id}-{tenant.slug}/x.dump.gpg",
        **kw,
    )
    db.session.add(record)
    db.session.commit()
    return record


def _pg_dump_schema(calls):
    dump = next(c for c in calls if c[0] == "pg_dump")
    return dump[dump.index("--schema") + 1]


class TestScopedBackups:
    def test_global_backup_holds_only_public(
        self, app, db, backup_config, mock_s3_client
    ):
        from hubra.core.services.backup import BackupService

        calls: list = []
        with (
            patch("hubra.core.services.backup.subprocess.run", side_effect=_fake_tools(calls)),
            patch("hubra.core.services.backup._get_s3_client", return_value=mock_s3_client),
        ):
            record = BackupService.create_backup("manual", "t")

        assert record.status == "completed"
        assert record.scope == "global"
        assert record.tenant_id is None
        assert _pg_dump_schema(calls) == "public"
        assert record.s3_key.startswith("backups/global/")

    def test_club_backup_holds_only_its_schema(
        self, app, db, backup_config, mock_s3_client
    ):
        from hubra.core.services.backup import BackupService

        club = _club(db)
        calls: list = []
        with (
            patch("hubra.core.services.backup.subprocess.run", side_effect=_fake_tools(calls)),
            patch("hubra.core.services.backup._get_s3_client", return_value=mock_s3_client),
        ):
            record = BackupService.create_backup("manual", "t", club.id)

        assert record.status == "completed"
        assert (record.scope, record.tenant_id, record.tenant_slug) == (
            "club",
            club.id,
            club.slug,
        )
        assert _pg_dump_schema(calls) == f"tenant_{club.id}"
        assert record.s3_key.startswith(f"backups/clubs/{club.id}-{club.slug}/")

    def test_unknown_club_is_refused(self, app, db):
        from hubra.core.services.backup import BackupService

        with pytest.raises(ValueError, match="not found"):
            BackupService.create_backup("manual", "t", 987654)

    def test_scheduled_run_backs_up_global_and_each_active_club(
        self, app, db, backup_config, mock_s3_client
    ):
        from hubra.core.services.backup import BackupService

        active, other = _club(db), _club(db)
        disabled = _club(db, status="disabled")
        calls: list = []
        with (
            patch("hubra.core.services.backup.subprocess.run", side_effect=_fake_tools(calls)),
            patch("hubra.core.services.backup._get_s3_client", return_value=mock_s3_client),
        ):
            records = BackupService.create_scheduled_backups("scheduled_monthly")

        assert [r.scope for r in records].count("global") == 1
        clubs = {r.tenant_id for r in records if r.scope == "club"}
        assert {active.id, other.id} <= clubs
        assert disabled.id not in clubs
        assert all(r.status == "completed" for r in records)
        dumped = {c[c.index("--schema") + 1] for c in calls if c[0] == "pg_dump"}
        assert dumped >= {
            "public",
            f"tenant_{active.id}",
            f"tenant_{other.id}",
        }

    def test_retention_counts_each_club_on_its_own(
        self, app, db, backup_config, mock_s3_client
    ):
        from hubra.core.models.backup import BackupRecord
        from hubra.core.services.backup import BackupService

        a, b = _club(db), _club(db)
        for club in (a, b):
            for i in range(9):
                _club_record(db, club)
        for r in BackupRecord.query.filter(
            BackupRecord.tenant_id.in_([a.id, b.id])
        ).all():
            r.type = "scheduled_daily"
        db.session.commit()

        with patch("hubra.core.services.backup._get_s3_client", return_value=mock_s3_client):
            BackupService.run_retention_cleanup()

        for club in (a, b):
            assert len(BackupService.list_backups(club.id)) == 7


class TestClubRestore:
    def _run(self, record_id, *, restore_rc=0, schema_exists=True):
        from hubra.core.services.backup import BackupService

        calls: list = []
        s3 = MagicMock()
        s3.download_file = MagicMock(side_effect=_download)
        rename, drop, migrate = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("hubra.core.services.backup.subprocess.run", side_effect=_fake_tools(calls, restore_rc=restore_rc)),
            patch("hubra.core.services.backup._get_s3_client", return_value=s3),
            patch("hubra.core.services.backup._schema_exists", return_value=schema_exists),
            patch("hubra.core.services.backup._rename_schema", rename),
            patch("hubra.core.services.backup._drop_schema", drop),
            patch("hubra.core.tenant.migration.apply_migrations_to_tenant", migrate),
        ):
            try:
                result = BackupService.restore_club(record_id)
            except Exception as exc:
                result = exc
        return result, calls, rename, drop, migrate

    def test_restore_keeps_a_safety_copy(self, app, db, backup_config):
        club = _club(db)
        record = _club_record(db, club)

        result, calls, rename, drop, migrate = self._run(record.id)

        schema = f"tenant_{club.id}"
        rename.assert_called_once()
        old, new = rename.call_args.args
        assert old == schema and new.startswith(f"{schema}_before_restore_")
        drop.assert_not_called()
        migrate.assert_called_once_with(club.id)
        restore = next(c for c in calls if c[0] == "pg_restore")
        assert "--single-transaction" in restore and "--exit-on-error" in restore
        assert result.restored_at is not None
        assert result.safety_schema == new
        assert result.restore_error is None

    def test_failed_restore_puts_the_club_back(self, app, db, backup_config):
        from hubra.core.services.backup import RestoreError

        club = _club(db)
        record = _club_record(db, club)

        result, _calls, rename, drop, migrate = self._run(record.id, restore_rc=1)

        schema = f"tenant_{club.id}"
        assert isinstance(result, RestoreError)
        drop.assert_called_once_with(schema)
        assert rename.call_count == 2
        safety = rename.call_args_list[0].args[1]
        assert rename.call_args_list[1].args == (safety, schema)
        migrate.assert_not_called()
        db.session.refresh(record)
        assert "pg_restore failed" in record.restore_error
        assert record.restored_at is None

    def test_global_backup_cannot_be_restored_here(self, app, db, backup_config):
        from hubra.core.models.backup import BackupRecord

        record = BackupRecord(type="manual", status="completed", s3_key="backups/global/x")
        db.session.add(record)
        db.session.commit()

        result, calls, rename, _drop, _migrate = self._run(record.id)

        assert isinstance(result, ValueError)
        assert calls == []
        rename.assert_not_called()


class TestScopedBackupAPI:
    @pytest.fixture(autouse=True)
    def _platform_staff(self, seeded_db, db):
        seeded_db["user"].is_superadmin = True
        db.session.commit()
        yield
        seeded_db["user"].is_superadmin = False
        db.session.commit()

    URL = "/api/v1/manager/platform/backups/"

    def test_back_up_one_club(
        self, client, auth_headers, db, backup_config, mock_s3_client
    ):
        club = _club(db)
        calls: list = []
        with (
            patch("hubra.core.services.backup.subprocess.run", side_effect=_fake_tools(calls)),
            patch("hubra.core.services.backup._get_s3_client", return_value=mock_s3_client),
        ):
            resp = client.post(self.URL, json={"tenant_id": club.id}, headers=auth_headers)

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["scope"] == "club"
        assert data["tenant_slug"] == club.slug

        listed = client.get(f"{self.URL}?tenant_id={club.id}", headers=auth_headers)
        assert [r["id"] for r in listed.get_json()] == [data["id"]]

    def test_back_up_unknown_club(self, client, auth_headers):
        resp = client.post(self.URL, json={"tenant_id": 987654}, headers=auth_headers)
        assert resp.status_code == 404

    def test_restore_needs_the_club_address(self, client, auth_headers, db):
        club = _club(db)
        record = _club_record(db, club)
        resp = client.post(
            f"{self.URL}{record.id}/restore", json={"confirm": "nope"}, headers=auth_headers
        )
        assert resp.status_code == 400

    def test_restore_refuses_global_backups(self, client, auth_headers, db):
        from hubra.core.models.backup import BackupRecord

        record = BackupRecord(type="manual", status="completed", s3_key="backups/global/y")
        db.session.add(record)
        db.session.commit()
        resp = client.post(
            f"{self.URL}{record.id}/restore", json={"confirm": "x"}, headers=auth_headers
        )
        assert resp.status_code == 409

    def test_restore_club(self, client, auth_headers, db, backup_config):
        from hubra.core.services.backup import BackupService

        club = _club(db)
        record = _club_record(db, club)

        def fake_restore(record_id):
            r = BackupService.get_backup(record_id)
            r.safety_schema = f"tenant_{club.id}_before_restore_1"
            return r

        with patch.object(BackupService, "restore_club", side_effect=fake_restore) as m:
            resp = client.post(
                f"{self.URL}{record.id}/restore",
                json={"confirm": club.slug},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        m.assert_called_once_with(record.id)
        assert resp.get_json()["safety_schema"].startswith(f"tenant_{club.id}_")

    def test_club_admins_cannot_restore(self, client, seeded_db, auth_headers, db):
        seeded_db["user"].is_superadmin = False
        db.session.commit()
        club = _club(db)
        record = _club_record(db, club)
        resp = client.post(
            f"{self.URL}{record.id}/restore", json={"confirm": club.slug}, headers=auth_headers
        )
        assert resp.status_code == 403
