"""Backwards-compatible re-export from vollbuild.core.tenant.middleware."""

from vollbuild.core.tenant.middleware import (
    annotations,
    g,
    request,
    select,
    db,
    Tenant,
    set_search_path,
    _log,
    _CACHE_TTL,
    _NEGATIVE_CACHE_TTL,
    _REDIS_DOWN_WINDOW,
    _redis_down_until,
    _get_redis_client,
    _mark_redis_down,
    _cache_slug,
    _get_cached_slug,
    _extract_slug_from_path,
    _rewrite_path,
    resolve_tenant,
    _lookup_tenant,
)
