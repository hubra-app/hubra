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

from flask import g, request
from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant

from .context import set_search_path
from hubra.core.redis_client import get_redis_client as _get_redis_client
from hubra.core.redis_client import mark_redis_down as _mark_redis_down

_log = logging.getLogger(__name__)

# ── Redis cache helpers (same pattern as api/permissions.py) ────────────────

_CACHE_TTL = 3600  # 1 hour
_NEGATIVE_CACHE_TTL = 300  # 5 minutes


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
      /api/<slug>/v1/<resource>  →  returns <slug>
      /api/v1/<resource>         →  returns None
    """
    path = environ.get("PATH_INFO", "")
    parts = path.strip("/").split("/")

    # /api/<slug>/v1/...; "v1" itself is the version, not a slug.
    if len(parts) >= 3 and parts[0] == "api" and parts[1] != "v1":
        return parts[1]

    return None


def _rewrite_path(environ: dict) -> None:
    """Rewrite PATH_INFO to remove the tenant slug segment.

    /api/<slug>/v1/<resource>  →  /api/v1/<resource>
    """
    path = environ.get("PATH_INFO", "")
    parts = path.strip("/").split("/")

    if len(parts) >= 3 and parts[0] == "api" and parts[1] != "v1":
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
        tenant_slug = _slug_from_jwt()

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


def _slug_from_jwt() -> str | None:
    """Return the tenant_slug claim of the request's token, if any.

    This runs before the route's JWT decorator, so get_jwt() has nothing to
    read yet, and verify_jwt_in_request() would load the Member before the
    search_path points at the club's schema. Decode the token directly
    instead; the route still does the full verification afterwards.
    """
    from flask import current_app
    from flask_jwt_extended import decode_token

    refresh = request.path.endswith("/auth/refresh")
    cookie = "JWT_REFRESH_COOKIE_NAME" if refresh else "JWT_ACCESS_COOKIE_NAME"
    token = request.cookies.get(current_app.config[cookie])
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    try:
        return decode_token(token).get("tenant_slug")
    except Exception:
        return None


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
