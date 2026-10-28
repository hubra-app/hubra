"""Backup record model — tracks each backup.

``scope`` is ``global`` (the public schema) or ``club`` (one club's schema,
``tenant_id``/``tenant_slug``).  The slug is kept so a deleted club's
backups still say whose they were.
"""

from __future__ import annotations

from datetime import datetime

from hubra.core.extensions import db


class BackupRecord(db.Model):
    __tablename__ = "backup_record"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at: datetime = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )
    type: str = db.Column(db.String(30), nullable=False)
    status: str = db.Column(db.String(20), nullable=False, default="pending")
    size_bytes: int | None = db.Column(db.BigInteger, nullable=True)
    s3_key: str | None = db.Column(db.String(500), nullable=True)
    checksum: str | None = db.Column(db.String(64), nullable=True)
    verified_at: datetime | None = db.Column(db.DateTime(timezone=True), nullable=True)
    verified_ok: bool | None = db.Column(db.Boolean, nullable=True)
    verify_error: str | None = db.Column(db.Text, nullable=True)
    error_message: str | None = db.Column(db.Text, nullable=True)
    triggered_by: str | None = db.Column(db.String(255), nullable=True)
    table_count: int | None = db.Column(db.Integer, nullable=True)
    scope: str = db.Column(
        db.String(20), nullable=False, default="global", server_default="global"
    )
    tenant_id: int | None = db.Column(
        db.Integer,
        db.ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tenant_slug: str | None = db.Column(db.String(255), nullable=True)
    restored_at: datetime | None = db.Column(db.DateTime(timezone=True), nullable=True)
    restore_error: str | None = db.Column(db.Text, nullable=True)
    safety_schema: str | None = db.Column(db.String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<BackupRecord {self.id} {self.scope} {self.type} {self.status}>"
