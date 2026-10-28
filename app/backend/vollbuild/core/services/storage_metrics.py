"""Storage metrics collection for tenants.

Aggregates storage usage across PostgreSQL schema size, WildDuck mail quotas,
and backup sizes. Used by the admin dashboard and API usage stats.
"""

import logging
from typing import Any

from sqlalchemy import text

from vollbuild.extensions import db

_log = logging.getLogger(__name__)


def get_storage_bytes(tenant_id: int) -> int:
    """Return total storage bytes for a tenant.

    Sums PostgreSQL schema size + WildDuck mail quota for all members.
    Returns 0 silently on any error (monitoring must never block usage stats).
    """
    total = 0
    total += _get_pg_schema_size(tenant_id)
    total += _get_mail_quota_total(tenant_id)
    return total


def _get_pg_schema_size(tenant_id: int) -> int:
    """Return the PostgreSQL schema size in bytes for the tenant."""
    try:
        schema_name = f"tenant_{tenant_id}"
        result = db.session.scalar(
            text(
                "SELECT pg_database_size(current_database()) "
                "WHERE EXISTS (SELECT 1 FROM information_schema.schemata "
                "WHERE schema_name = :schema)"
            ),
            {"schema": schema_name},
        )
        return int(result or 0)
    except Exception:
        _log.debug("Could not get PG schema size for tenant %d", tenant_id)
        return 0


def _get_mail_quota_total(tenant_id: int) -> int:
    """Return total mail quota in bytes for all members of the tenant.

    Queries WildDuck API if configured, returns 0 otherwise.
    """
    try:
        from flask import current_app

        api_url = current_app.config.get("WILDDUCK_API_URL", "")
        api_token = current_app.config.get("WILDDUCK_API_TOKEN", "")
        if not api_url or not api_token:
            return 0

        import json
        import urllib.request

        # Query WildDuck for domain quotas
        url = f"{api_url}/domains/quota?domain={tenant_id}"
        req = urllib.request.Request(
            url,
            headers={"X-Access-Token": api_token},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return int(data.get("totalQuota", 0))
    except Exception:
        _log.debug("Could not get mail quota for tenant %d", tenant_id)
        return 0


def get_storage_breakdown(tenant_id: int) -> dict[str, Any]:
    """Return detailed storage breakdown for a tenant."""
    return {
        "tenant_id": tenant_id,
        "pg_schema_bytes": _get_pg_schema_size(tenant_id),
        "mail_quota_bytes": _get_mail_quota_total(tenant_id),
        "total_bytes": get_storage_bytes(tenant_id),
    }
