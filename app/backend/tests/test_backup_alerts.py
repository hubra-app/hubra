"""Backup alerts: failed backups, checks and restores a person started, and
backups deleted by hand, raise platform alerts; retention is only logged."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hubra.core.models.platform_event import PlatformEvent
from tests import test_backups
from tests.test_backups import _club, _club_record, _download, _fake_tools

# The fixtures of the backup tests, shared.
backup_config = test_backups.backup_config
mock_s3_client = test_backups.mock_s3_client


@pytest.fixture
def alerts():
    sent: list[tuple] = []

    def fake_alert(alert_type, subject, lines, **kw):
        sent.append((alert_type, subject, lines, kw))
        return True

    with patch("hubra.core.services.platform_monitor.alert", side_effect=fake_alert):
        yield sent


def _events(db, kind):
    return db.session.query(PlatformEvent).filter_by(kind=kind).all()


def _failing_dump(cmd, env=None, capture_output=True, timeout=None, input=None):
    if cmd[0] == "pg_dump":
        return MagicMock(returncode=1, stdout=b"", stderr=b"connection refused")
    return MagicMock(returncode=0, stdout=b"", stderr=b"")


def test_failed_manual_backup_alerts(app, db, backup_config, mock_s3_client, alerts):
    from hubra.core.services.backup import BackupService

    with (
        patch("hubra.core.services.backup.subprocess.run", side_effect=_failing_dump),
        patch("hubra.core.services.backup._get_s3_client", return_value=mock_s3_client),
    ):
        record = BackupService.create_backup(backup_type="manual")

    assert record.status == "failed"
    assert [a[0] for a in alerts] == ["backup_failed"]
    alert_type, subject, lines, kw = alerts[0]
    assert subject == "Backup failed: global"
    assert any("connection refused" in line for line in lines)
    assert kw["throttle"] is False
    (event,) = _events(db, "backup.manual_failed")
    assert event.level == "error"
    assert event.details["id"] == record.id


def test_scheduled_run_alerts_once_for_all(
    app, db, backup_config, mock_s3_client, alerts
):
    from hubra.core.tasks.backup_tasks import create_scheduled_backups_task

    _club(db), _club(db)
    with (
        patch("hubra.core.services.backup.subprocess.run", side_effect=_failing_dump),
        patch("hubra.core.services.backup._get_s3_client", return_value=mock_s3_client),
    ):
        create_scheduled_backups_task.run("scheduled_daily")

    assert [a[0] for a in alerts] == ["backup_failed"]
    assert "scheduled backups failed" in alerts[0][1]
    assert _events(db, "backup.manual_failed") == []


def test_failed_verify_alerts(app, db, backup_config, alerts):
    from hubra.core.services.backup import BackupService

    club = _club(db)
    record = _club_record(db, club)
    s3 = MagicMock()
    s3.download_file = MagicMock(side_effect=RuntimeError("NoSuchKey"))
    with patch("hubra.core.services.backup._get_s3_client", return_value=s3):
        result = BackupService.verify_backup(record.id)

    assert result.verified_ok is False
    assert [a[0] for a in alerts] == ["backup_failed"]
    assert alerts[0][1] == f"Backup check failed: {club.slug}"
    (event,) = _events(db, "backup.verify_failed")
    assert event.tenant_id == club.id


def test_failed_restore_alerts(app, db, backup_config, alerts):
    from hubra.core.services.backup import BackupService, RestoreError

    club = _club(db)
    record = _club_record(db, club)
    s3 = MagicMock()
    s3.download_file = MagicMock(side_effect=_download)
    with (
        patch(
            "hubra.core.services.backup.subprocess.run",
            side_effect=_fake_tools([], restore_rc=1),
        ),
        patch("hubra.core.services.backup._get_s3_client", return_value=s3),
        patch("hubra.core.services.backup._schema_exists", return_value=True),
        patch("hubra.core.services.backup._rename_schema"),
        patch("hubra.core.services.backup._drop_schema"),
        pytest.raises(RestoreError),
    ):
        BackupService.restore_club(record.id)

    assert [a[0] for a in alerts] == ["backup_failed"]
    assert alerts[0][1] == f"Club restore failed: {club.slug}"
    assert len(_events(db, "backup.restore_failed")) == 1


def test_delete_alerts_with_who(app, db, backup_config, mock_s3_client, alerts):
    from hubra.core.services.backup import BackupService

    club = _club(db)
    record = _club_record(db, club, size_bytes=1234)
    with patch(
        "hubra.core.services.backup._get_s3_client", return_value=mock_s3_client
    ):
        BackupService.delete_backup(record.id, "ops@example.com")

    assert [a[0] for a in alerts] == ["backup_deleted"]
    _type, subject, lines, kw = alerts[0]
    assert subject == f"Backup deleted: {club.slug}"
    assert "ops@example.com" in lines[0]
    assert kw["level"] == "warning" and kw["throttle"] is False
    (event,) = _events(db, "backup.deleted")
    assert event.details["by"] == "ops@example.com"
    assert event.details["size_bytes"] == 1234
    assert event.tenant_id == club.id


def test_delete_says_when_the_file_stayed(
    app, db, backup_config, mock_s3_client, alerts
):
    from hubra.core.services.backup import BackupService

    record = _club_record(db, _club(db))
    mock_s3_client.delete_object.side_effect = RuntimeError("AccessDenied")
    with patch(
        "hubra.core.services.backup._get_s3_client", return_value=mock_s3_client
    ):
        BackupService.delete_backup(record.id, "ops@example.com")

    lines = alerts[0][2]
    assert any("still there" in line and "AccessDenied" in line for line in lines)


def test_retention_is_logged_not_alerted(
    app, db, backup_config, mock_s3_client, alerts
):
    from hubra.core.models.backup import BackupRecord
    from hubra.core.services.backup import BackupService

    for i in range(9):
        db.session.add(
            BackupRecord(
                type="scheduled_daily",
                status="completed",
                s3_key=f"backups/global/d{i}",
            )
        )
    db.session.commit()
    with patch(
        "hubra.core.services.backup._get_s3_client", return_value=mock_s3_client
    ):
        BackupService.run_retention_cleanup()

    assert alerts == []
    (event,) = _events(db, "backup.pruned")
    assert event.details["deleted"] == {"scheduled_daily": 2}


class TestDeleteAPI:
    @pytest.fixture(autouse=True)
    def _platform_staff(self, seeded_db, db):
        seeded_db["user"].is_superadmin = True
        db.session.commit()
        yield
        seeded_db["user"].is_superadmin = False
        db.session.commit()

    def test_delete_names_the_person(
        self, client, seeded_db, auth_headers, db, backup_config, mock_s3_client, alerts
    ):
        record = _club_record(db, _club(db))
        with patch(
            "hubra.core.services.backup._get_s3_client", return_value=mock_s3_client
        ):
            resp = client.delete(
                f"/api/v1/manager/platform/backups/{record.id}", headers=auth_headers
            )

        assert resp.status_code == 204
        assert [a[0] for a in alerts] == ["backup_deleted"]
        assert seeded_db["user"].email in alerts[0][2][0]


def test_backup_deleted_is_an_alert_type():
    from hubra.core.services import platform_monitor

    assert "backup_deleted" in platform_monitor.ALERT_TYPES
    assert platform_monitor.default_prefs()["backup_deleted"] is True
