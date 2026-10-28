"""Backup service — encrypted Postgres backups to S3-compatible storage.

Flow:
    1. pg_dump (custom format) → temp file
    2. GPG symmetric encryption → .gpg file
    3. SHA-256 checksum of encrypted file
    4. Upload to S3 (Contabo or any S3-compatible endpoint)
    5. Record metadata in BackupRecord table

Verification:
    1. Download .gpg from S3
    2. GPG decrypt
    3. pg_restore --list to confirm valid archive

S3 connection settings are read from the KV Setting store (backup namespace)
with env-var fallback via Flask config.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import current_app
from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.backup import BackupRecord

logger = logging.getLogger(__name__)

_BACKUP_TYPES = ("manual", "scheduled_daily", "scheduled_weekly", "scheduled_monthly")

_RETENTION: dict[str, int] = {
    "scheduled_daily": 7,
    "scheduled_weekly": 4,
    "scheduled_monthly": 6,
}


def _get_s3_config() -> dict[str, str]:
    """Where backups are stored: a platform setting, defaulting to env."""
    from hubra.core.services import platform_settings

    return {
        "endpoint": platform_settings.get("backup.s3.endpoint"),
        "bucket": platform_settings.get("backup.s3.bucket"),
        "access_key": platform_settings.get("backup.s3.access_key"),
        "secret_key": platform_settings.get("backup.s3.secret_key"),
        "region": platform_settings.get("backup.s3.region") or "default",
    }


def _get_encryption_key() -> str:
    """Return the GPG encryption passphrase from env (never from DB)."""
    return current_app.config.get("BACKUP_ENCRYPTION_KEY", "")


def _get_s3_client():
    """Create a boto3 S3 client. Returns None if not configured."""
    cfg = _get_s3_config()
    if not cfg["endpoint"] or not cfg["bucket"] or not cfg["access_key"]:
        return None

    import boto3  # noqa: PLC0415

    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        region_name=cfg["region"],
    )


def _parse_database_url() -> dict[str, str]:
    """Parse DATABASE_URL into connection components for pg_dump."""
    url = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "",
        "password": parsed.password or "",
        "db": parsed.path.lstrip("/") or "",
    }


class BackupService:
    """Backup operations — create, verify, list, delete, retention."""

    @staticmethod
    def get_config_status() -> dict:
        """Check whether S3 + encryption are configured and S3 is reachable."""
        cfg = _get_s3_config()
        s3_configured = all(
            [cfg["endpoint"], cfg["bucket"], cfg["access_key"], cfg["secret_key"]]
        )
        encryption_configured = bool(_get_encryption_key())

        s3_reachable = False
        s3_error = None
        if s3_configured:
            try:
                client = _get_s3_client()
                if client is not None:
                    client.head_bucket(Bucket=cfg["bucket"])
                    s3_reachable = True
            except Exception as exc:
                s3_error = str(exc)

        return {
            "s3_configured": s3_configured,
            "s3_reachable": s3_reachable,
            "s3_error": s3_error,
            "encryption_configured": encryption_configured,
            "endpoint": cfg["endpoint"],
            "bucket": cfg["bucket"],
            "region": cfg["region"],
        }

    @staticmethod
    def create_backup(
        backup_type: str = "manual", triggered_by: str | None = None
    ) -> BackupRecord:
        """Create a database backup: pg_dump → GPG encrypt → S3 upload.

        Args:
            backup_type: One of 'manual', 'scheduled_daily', 'scheduled_weekly',
                         'scheduled_monthly'.
            triggered_by: Member name for manual backups, or 'schedule'.

        Returns:
            The updated BackupRecord.
        """
        if backup_type not in _BACKUP_TYPES:
            raise ValueError(f"Invalid backup type: {backup_type}")

        record = BackupRecord(
            type=backup_type,
            status="pending",
            triggered_by=triggered_by,
        )
        db.session.add(record)
        db.session.commit()

        try:
            record.status = "running"
            db.session.commit()

            db_params = _parse_database_url()
            encryption_key = _get_encryption_key()

            if not encryption_key:
                raise RuntimeError(
                    "BACKUP_ENCRYPTION_KEY is not set — cannot encrypt backup"
                )

            s3_client = _get_s3_client()
            if s3_client is None:
                raise RuntimeError(
                    "S3 is not configured — set it under Platform settings or BACKUP_S3_* env vars"
                )

            cfg = _get_s3_config()

            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
            s3_key = f"backups/{timestamp}_{backup_type}.dump.gpg"

            with tempfile.TemporaryDirectory(prefix="backup_") as tmpdir:
                dump_path = os.path.join(tmpdir, "backup.dump")
                gpg_path = os.path.join(tmpdir, "backup.dump.gpg")

                # ── 1. pg_dump (custom format for pg_restore) ──────────────
                env = os.environ.copy()
                env["PGPASSWORD"] = db_params["password"]

                pg_cmd = [
                    "pg_dump",
                    "--host",
                    db_params["host"],
                    "--port",
                    db_params["port"],
                    "--username",
                    db_params["user"],
                    "--format",
                    "custom",
                    "--no-password",
                    db_params["db"],
                ]
                logger.info("Running pg_dump for backup %s", record.id)
                result = subprocess.run(
                    pg_cmd,
                    env=env,
                    capture_output=True,
                    timeout=600,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"pg_dump failed: {result.stderr.decode('utf-8', errors='replace')}"
                    )

                with open(dump_path, "wb") as f:
                    f.write(result.stdout)

                # ── 2. GPG symmetric encryption ────────────────────────────
                gpg_cmd = [
                    "gpg",
                    "--batch",
                    "--yes",
                    "--quiet",
                    "--pinentry-mode",
                    "loopback",
                    "--passphrase-fd",
                    "0",
                    "--symmetric",
                    "--cipher-algo",
                    "AES256",
                    "--output",
                    gpg_path,
                    dump_path,
                ]
                logger.info("Encrypting backup %s with GPG", record.id)
                gpg_result = subprocess.run(
                    gpg_cmd,
                    input=encryption_key.encode(),
                    capture_output=True,
                    timeout=300,
                )
                if gpg_result.returncode != 0:
                    raise RuntimeError(
                        f"GPG encryption failed: {gpg_result.stderr.decode('utf-8', errors='replace')}"
                    )

                # ── 3. SHA-256 checksum ────────────────────────────────────
                hasher = hashlib.sha256()
                with open(gpg_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        hasher.update(chunk)
                checksum = hasher.hexdigest()
                size_bytes = os.path.getsize(gpg_path)

                # ── 4. Upload to S3 ────────────────────────────────────────
                logger.info(
                    "Uploading backup %s to s3://%s/%s",
                    record.id,
                    cfg["bucket"],
                    s3_key,
                )
                s3_client.upload_file(gpg_path, cfg["bucket"], s3_key)

                # ── 5. Update record ───────────────────────────────────────
                record.status = "completed"
                record.size_bytes = size_bytes
                record.s3_key = s3_key
                record.checksum = checksum
                db.session.commit()

                logger.info(
                    "Backup %s completed: %s (%d bytes, sha256=%s)",
                    record.id,
                    s3_key,
                    size_bytes,
                    checksum[:16],
                )

            if backup_type in _RETENTION:
                BackupService.run_retention_cleanup()

        except Exception as exc:
            logger.error("Backup %s failed: %s", record.id, exc)
            record.status = "failed"
            record.error_message = str(exc)
            db.session.commit()

        return record

    @staticmethod
    def verify_backup(record_id: int) -> BackupRecord:
        """Verify a backup: download from S3, decrypt, check with pg_restore --list.

        Confirms: S3 object is retrievable, GPG decryption works, dump is valid.
        """
        record = db.session.get(BackupRecord, record_id)
        if record is None:
            raise ValueError(f"Backup record {record_id} not found")
        if record.status != "completed" or not record.s3_key:
            raise ValueError(f"Backup {record_id} is not in a verifiable state")

        encryption_key = _get_encryption_key()
        if not encryption_key:
            raise RuntimeError("BACKUP_ENCRYPTION_KEY is not set")

        s3_client = _get_s3_client()
        if s3_client is None:
            raise RuntimeError("S3 is not configured")

        cfg = _get_s3_config()

        try:
            with tempfile.TemporaryDirectory(prefix="verify_") as tmpdir:
                gpg_path = os.path.join(tmpdir, "backup.dump.gpg")
                dump_path = os.path.join(tmpdir, "backup.dump")

                # ── 1. Download from S3 ────────────────────────────────────
                logger.info("Downloading backup %s from S3 for verification", record_id)
                s3_client.download_file(cfg["bucket"], record.s3_key, gpg_path)

                # ── 2. GPG decrypt ─────────────────────────────────────────
                gpg_cmd = [
                    "gpg",
                    "--batch",
                    "--yes",
                    "--quiet",
                    "--pinentry-mode",
                    "loopback",
                    "--passphrase-fd",
                    "0",
                    "--decrypt",
                    "--output",
                    dump_path,
                    gpg_path,
                ]
                gpg_result = subprocess.run(
                    gpg_cmd,
                    input=encryption_key.encode(),
                    capture_output=True,
                    timeout=300,
                )
                if gpg_result.returncode != 0:
                    raise RuntimeError(
                        f"GPG decryption failed: {gpg_result.stderr.decode('utf-8', errors='replace')}"
                    )

                # ── 3. pg_restore --list to confirm valid archive ──────────
                restore_result = subprocess.run(
                    ["pg_restore", "--list", dump_path],
                    capture_output=True,
                    timeout=120,
                )
                if restore_result.returncode != 0:
                    raise RuntimeError(
                        f"pg_restore --list failed: {restore_result.stderr.decode('utf-8', errors='replace')}"
                    )

                listing = restore_result.stdout.decode("utf-8", errors="replace")
                table_count = sum(
                    1 for line in listing.splitlines() if "TABLE DATA" in line.upper()
                )

                record.verified_at = datetime.now(timezone.utc)
                record.verified_ok = True
                record.table_count = table_count
                record.verify_error = None
                db.session.commit()

                logger.info(
                    "Backup %s verified OK: %d tables found",
                    record_id,
                    table_count,
                )

        except Exception as exc:
            logger.error("Backup %s verification failed: %s", record_id, exc)
            record.verified_at = datetime.now(timezone.utc)
            record.verified_ok = False
            record.verify_error = str(exc)
            db.session.commit()

        return record

    @staticmethod
    def list_backups() -> list[BackupRecord]:
        """Return all backup records, newest first."""
        return list(
            db.session.scalars(
                select(BackupRecord).order_by(BackupRecord.created_at.desc())  # type: ignore[attr-defined]
            ).all()
        )

    @staticmethod
    def get_backup(record_id: int) -> BackupRecord | None:
        """Return a single backup record."""
        return db.session.get(BackupRecord, record_id)

    @staticmethod
    def delete_backup(record_id: int) -> None:
        """Delete a backup: remove S3 object, then delete the DB record."""
        record = db.session.get(BackupRecord, record_id)
        if record is None:
            raise ValueError(f"Backup record {record_id} not found")

        if record.s3_key:
            try:
                s3_client = _get_s3_client()
                cfg = _get_s3_config()
                if s3_client is not None:
                    s3_client.delete_object(Bucket=cfg["bucket"], Key=record.s3_key)
                    logger.info(
                        "Deleted S3 object %s for backup %s", record.s3_key, record_id
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to delete S3 object %s for backup %s: %s — removing DB record anyway",
                    record.s3_key,
                    record_id,
                    exc,
                )

        db.session.delete(record)
        db.session.commit()

    @staticmethod
    def run_retention_cleanup() -> dict:
        """Delete backups exceeding retention policy per type.

        Manual backups are never auto-deleted.

        Returns:
            Summary dict with counts of deleted records per type.
        """
        deleted: dict[str, int] = {}
        s3_client = _get_s3_client()
        cfg = _get_s3_config()

        for backup_type, keep_count in _RETENTION.items():
            records = db.session.scalars(
                select(BackupRecord)
                .where(BackupRecord.type == backup_type)  # type: ignore[arg-type]
                .where(BackupRecord.status == "completed")  # type: ignore[arg-type]
                .order_by(BackupRecord.created_at.desc())  # type: ignore[attr-defined]
            ).all()

            if len(records) <= keep_count:
                continue

            for record in records[keep_count:]:
                if record.s3_key:
                    try:
                        if s3_client is not None:
                            s3_client.delete_object(
                                Bucket=cfg["bucket"], Key=record.s3_key
                            )
                    except Exception as exc:
                        logger.warning(
                            "Retention: failed to delete S3 object %s: %s",
                            record.s3_key,
                            exc,
                        )
                db.session.delete(record)
                deleted[backup_type] = deleted.get(backup_type, 0) + 1

        if deleted:
            db.session.commit()
            logger.info("Retention cleanup deleted: %s", deleted)

        return deleted
