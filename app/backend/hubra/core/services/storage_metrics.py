"""Storage metrics collection for tenants.

Aggregates storage usage across PostgreSQL schema size, WildDuck mail quotas,
and backup sizes. Used by the admin dashboard and API usage stats.
"""

import logging


from hubra.core.extensions import db

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
    """Return the size in bytes of the tenant's own schema (tables, indexes
    and TOAST), not of the whole database."""
    try:
        if db.session.get_bind().dialect.name != "postgresql":
            return 0
        from hubra.core.services.tenant_health import _schema_sizes

        return _schema_sizes([tenant_id]).get(tenant_id, 0)
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

