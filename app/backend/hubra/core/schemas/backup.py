"""Marshmallow schema for BackupRecord."""

from __future__ import annotations

from marshmallow import fields

from hubra.core.extensions import ma


class BackupRecordSchema(ma.Schema):
    """Read schema for a single backup record."""

    id = fields.Int()
    created_at = fields.DateTime()
    type = fields.Str()
    status = fields.Str()
    size_bytes = fields.Int(allow_none=True)
    s3_key = fields.Str(allow_none=True)
    checksum = fields.Str(allow_none=True)
    verified_at = fields.DateTime(allow_none=True)
    verified_ok = fields.Bool(allow_none=True)
    verify_error = fields.Str(allow_none=True)
    error_message = fields.Str(allow_none=True)
    triggered_by = fields.Str(allow_none=True)
    table_count = fields.Int(allow_none=True)


class BackupConfigSchema(ma.Schema):
    """Schema for backup configuration status."""

    s3_configured = fields.Bool()
    s3_reachable = fields.Bool()
    s3_error = fields.Str(allow_none=True)
    encryption_configured = fields.Bool()
    endpoint = fields.Str()
    bucket = fields.Str()
    region = fields.Str()
