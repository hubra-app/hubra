"""Backwards-compatible re-export from vollbuild.core.services.storage_metrics."""

from vollbuild.core.services.storage_metrics import (
    Any,
    text,
    db,
    _log,
    get_storage_bytes,
    _get_pg_schema_size,
    _get_mail_quota_total,
    get_storage_breakdown,
)
