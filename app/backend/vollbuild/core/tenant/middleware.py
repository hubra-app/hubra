"""Tenant resolver middleware — resolves tenant from path/JWT/header.

Resolution priority:
  1. Path prefix:  /api/<tenant_slug>/v1/...
  2. JWT claim:    tenant_slug in the access token
  3. Header:       X-Tenant-Slug

The middleware rewrites PATH_INFO so downstream blueprints see their
original URL (the tenant slug segment is stripped).

When no slug is present in the path (e.g. /api/v1/<resource>), the
request runs in single-tenant mode — no search_path is set, and all
queries hit the public schema.
"""

from __future__ import annotations

import logging
import time

from flask import g, request
from sqlalchemy import select

from vollbuild.extensions import db
from vollbuild.core.models.tenant import Tenant

from .context import set_search_path

_log = logging.getLogger(__name__)

# ── Redis cache helpers (same pattern as api/permissions.py) ────────────────

_CACHE_TTL = 3600  # 1 hour
_NEGATIVE_CACHE_TTL = 300  # 5 minutes
_REDIS_DOWN_WINDOW = 5.0
_redis_down_until: float = 0.0


def _get_redis_client():
    global _redis_down_until
    if time.monotonic() < _redis_down_until:
        return None
    try:
        from flask import current_app

        url = current_app.config.get("REDIS_URL", "")
        if not url or url == "memory://":
            return None
        import redis as redis_lib

        return redis_lib.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3)
    except Exception:
        return None


def _mark_redis_down() -> None:
    global _redis_down_until
    _redis_down_until = time.monotonic() + _REDIS_DOWN_WINDOW


def _cache_slug(slug: str | None, *, negative: bool = False) -> None:
    """Cache slug (or None for negative cache) in Redis for the current hostname."""
    hostname = request.host.split(":")[0].lower()
    client = _get_redis_client()
    if client is None:
        return
    try:
        if slug:
            client.setex(f"tenant:slug:{hostname}", _CACHE_TTL, slug)
        else:
            client.setex(f"tenant:slug:{hostname}", _NEGATIVE_CACHE_TTL, "")
    except Exception:
        _mark_redis_down()


def _get_cached_slug(hostname: str) -> str | None:
    client = _get_redis_client()
    if client is None:
        return None
    try:
        val = client.get(f"tenant:slug:{hostname}")
        if val is not None:
            decoded = val.decode() if isinstance(val, bytes) else val
            return decoded or None
    except Exception:
        _mark_redis_down()
    return None


# ── Slug extraction ────────────────────────────────────────────────────────


def _extract_slug_from_path(environ: dict) -> str | None:
    """Extract tenant slug from the path.

    URL structures:
      /api/v2/tenants/<slug>/<resource>  →  returns <slug>
      /api/<slug>/v1/<resource>           →  returns <slug>  (legacy v1)
      /api/v1/<resource>                  →  returns None (single-tenant mode)
      /api/v2/global/<resource>           →  returns None (global plane)
      /api/v2/manager/<resource>          →  returns None (manager plane)
    """
    path = environ.get("PATH_INFO", "")
    parts = path.strip("/").split("/")

    # v2 tenant path: /api/v2/tenants/<slug>/...
    if (
        len(parts) >= 4
        and parts[0] == "api"
        and parts[1] == "v2"
        and parts[2] == "tenants"
    ):
        return parts[3]

    # v1 tenant path: /api/<slug>/v1/...
    # Exclude v1 and v2 as "slugs" — they're version identifiers
    if len(parts) >= 3 and parts[0] == "api" and parts[1] not in ("v1", "v2"):
        return parts[1]

    return None


def _rewrite_path(environ: dict) -> None:
    """Rewrite PATH_INFO to remove the tenant slug segment.

    /api/v2/tenants/<slug>/<resource>  →  /api/v2/tenants/<resource>
    /api/<slug>/v1/<resource>           →  /api/v1/<resource>
    """
    path = environ.get("PATH_INFO", "")
    parts = path.strip("/").split("/")

    # v2 tenant path: /api/v2/tenants/<slug>/... → /api/v2/tenants/...
    if (
        len(parts) >= 4
        and parts[0] == "api"
        and parts[1] == "v2"
        and parts[2] == "tenants"
    ):
        new_parts = parts[:3] + parts[4:]
        environ["PATH_INFO"] = "/" + "/".join(new_parts)
        return

    # v1 tenant path: /api/<slug>/v1/... → /api/v1/...
    if len(parts) >= 3 and parts[0] == "api" and parts[1] not in ("v1", "v2"):
        new_parts = parts[:1] + parts[2:]
        environ["PATH_INFO"] = "/" + "/".join(new_parts)


# ── Main resolver ──────────────────────────────────────────────────────────


def resolve_tenant() -> None:
    """Before-request handler: resolve tenant and set search_path.

    Called as ``app.before_request(resolve_tenant)``.
    """
    environ = request.environ
    tenant_slug = None

    # 1. Path prefix: /api/<tenant_slug>/v1/...
    tenant_slug = _extract_slug_from_path(environ)
    if tenant_slug:
        _rewrite_path(environ)

    # 2. JWT claim (authenticated requests)
    if not tenant_slug:
        try:
            from flask_jwt_extended import get_jwt

            claims = get_jwt()
            tenant_slug = claims.get("tenant_slug")
        except Exception:
            pass

    # 3. X-Tenant-Slug header
    if not tenant_slug:
        tenant_slug = request.headers.get("X-Tenant-Slug")

    if not tenant_slug:
        g.tenant = None
        return

    # Resolve slug → Tenant record
    tenant = _lookup_tenant(tenant_slug)
    if tenant is None or tenant.status != "active":
        g.tenant = None
        return

    g.tenant = tenant
    set_search_path(tenant.id)


def _lookup_tenant(slug: str) -> Tenant | None:
    """Look up a Tenant by slug, using Redis cache if available."""
    # Check Redis
    hostname = request.host.split(":")[0].lower()
    cached = _get_cached_slug(hostname)
    if cached == slug:
        # Confirm it still exists (fast DB hit on primary key)
        return db.session.scalar(select(Tenant).where(Tenant.slug == slug))

    # DB lookup
    tenant = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant:
        _cache_slug(tenant.slug)
    else:
        _cache_slug(None, negative=True)
    return tenant
