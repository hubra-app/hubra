"""Translation service — business logic for i18n."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from vollbuild.api.settings.services import SettingService
from vollbuild.core.extensions import db
from vollbuild.core.models.translation import Translation

_log = logging.getLogger(__name__)

_LOCALES_CACHE_KEY = "i18n:locales"
_LOCALES_CACHE_TTL = 3600
_TRANS_CACHE_TTL = 3600
_MEM_TRANS_TTL = 60  # in-memory fallback TTL (shorter)

_mem_locales: list[str] | None = None
_mem_translations: dict[str, tuple[dict, float]] = {}


def _get_redis_client():
    """Return a Redis client if available, else None."""
    try:
        from flask import current_app

        url = current_app.config.get("REDIS_URL", "")
        if not url or url == "memory://":
            return None
        import redis as redis_lib

        return redis_lib.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    except Exception:
        return None


def _invalidate_locales_cache() -> None:
    """Clear the cached locale list in Redis and in-memory."""
    global _mem_locales
    _mem_locales = None
    client = _get_redis_client()
    if client is not None:
        try:
            client.delete(_LOCALES_CACHE_KEY)
        except Exception:
            _log.debug("locales cache invalidation failed")


def _get_stale_threshold_seconds() -> int:
    """Read the stale-threshold setting, auto-creating it with default if missing."""
    raw = SettingService.get_or_create("I18n.StaleThresholdSeconds", default="2592000")
    try:
        return int(raw) if raw else 2592000
    except (ValueError, TypeError):
        return 2592000


def compute_is_stale(last_used_at: datetime | None, threshold_seconds: int) -> bool:
    """Return True if *last_used_at* is null or older than *threshold_seconds*."""
    if last_used_at is None:
        return True
    now = datetime.now(timezone.utc)
    if last_used_at.tzinfo is None:
        last_used_at = last_used_at.replace(tzinfo=timezone.utc)
    return (now - last_used_at).total_seconds() > threshold_seconds


def _etag_version_key(locale: str) -> str:
    return f"i18n:version:{locale}"


def _bump_etag(locale: str) -> None:
    """Increment the Redis ETag version counter for *locale*."""
    try:
        import redis as redis_lib

        from flask import current_app

        url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis_lib.from_url(url)
        r.incr(_etag_version_key(locale))
    except Exception:
        pass


def get_etag(locale: str) -> str | None:
    """Return the current ETag string for *locale*, or None if not set."""
    try:
        import redis as redis_lib

        from flask import current_app

        url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis_lib.from_url(url)
        ver = r.get(_etag_version_key(locale))
        if ver is not None:
            return f'"{ver.decode()}"'
    except Exception:
        pass
    return None


def get_translations(locale: str) -> list[Translation]:
    stmt = select(Translation).where(Translation.locale == locale)  # type: ignore[arg-type]
    stmt = stmt.order_by(Translation.key)
    return list(db.session.scalars(stmt).all())


def get_translations_dict(locale: str) -> dict[str, str]:
    # Determine ETag version for cache key
    etag = get_etag(locale)
    version = etag.strip('"') if etag else "_no_etag"
    cache_key = f"i18n:dict:{locale}:{version}"

    # Try Redis
    client = _get_redis_client()
    if client is not None:
        try:
            cached = client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            _log.debug("translation cache read failed for %s", locale)

    # Try in-memory (shorter TTL when no etag/Redis)
    mem_entry = _mem_translations.get(cache_key)
    if mem_entry is not None:
        data, expires_at = mem_entry
        if time.monotonic() < expires_at:
            return data
        _mem_translations.pop(cache_key, None)

    # DB query (uses index on locale)
    qs = get_translations(locale)
    alias_map = {t.key: t for t in qs}
    resolved: dict[str, str] = {}
    for t in qs:
        if t.alias_for:
            resolved[t.key] = _resolve_alias_chain(t.key, alias_map, resolved, {t.key})
        else:
            resolved[t.key] = t.value

    # Cache in Redis
    if client is not None:
        try:
            client.setex(cache_key, _TRANS_CACHE_TTL, json.dumps(resolved))
        except Exception:
            _log.debug("translation cache write failed for %s", locale)

    # Cache in-memory
    ttl = _MEM_TRANS_TTL if version == "_no_etag" else _TRANS_CACHE_TTL
    _mem_translations[cache_key] = (resolved, time.monotonic() + ttl)

    return resolved


def _resolve_alias_chain(
    key: str,
    alias_map: dict[str, Translation],
    resolved: dict[str, str],
    visited: set[str],
) -> str:
    if key in resolved:
        return resolved[key]
    if key in visited:
        return key
    row = alias_map.get(key)
    if not row:
        return key
    if not row.alias_for:
        resolved[key] = row.value
        return row.value
    visited.add(key)
    result = _resolve_alias_chain(row.alias_for, alias_map, resolved, visited)
    resolved[key] = result
    return result


def get_available_locales() -> list[str]:
    """Return distinct locales that have at least one translation.

    Results are cached in Redis (1h TTL) with an in-memory fallback.
    """
    global _mem_locales

    # Try Redis
    client = _get_redis_client()
    if client is not None:
        try:
            cached = client.get(_LOCALES_CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception:
            _log.debug("locales cache read failed")

    # Try in-memory
    if _mem_locales is not None:
        return _mem_locales

    # DB query (uses index on locale)
    stmt = select(Translation.locale).distinct().order_by(Translation.locale)  # type: ignore[call-overload]
    locales = list(db.session.scalars(stmt).all())

    # Cache in Redis
    if client is not None:
        try:
            client.setex(_LOCALES_CACHE_KEY, _LOCALES_CACHE_TTL, json.dumps(locales))
        except Exception:
            _log.debug("locales cache write failed")

    _mem_locales = locales
    return locales


def upsert_translation(
    locale: str,
    key: str,
    value: str,
    updated_by_id: int | None = None,
    alias_for: str | None = None,
) -> Translation:
    stmt = select(Translation).where(
        Translation.locale == locale,  # type: ignore[arg-type]
        Translation.key == key,  # type: ignore[arg-type]
    )
    existing = db.session.scalar(stmt)
    is_alias = alias_for is not None and alias_for != ""
    is_empty = not value or not value.strip()

    if existing:
        existing.value = "" if is_alias else value
        existing.alias_for = alias_for if is_alias else None
        existing.updated_by_id = updated_by_id
        if is_alias:
            existing.needs_attention = False
            existing.is_missing = False
        elif is_empty:
            existing.needs_attention = True
            existing.is_missing = False
        else:
            existing.needs_attention = False
            existing.is_missing = False
        obj = existing
    else:
        obj = Translation(
            locale=locale,
            key=key,
            value="" if is_alias else value,
            alias_for=alias_for if is_alias else None,
            updated_by_id=updated_by_id,
            needs_attention=is_alias or is_empty,
            is_missing=False,
        )
        db.session.add(obj)
    _bump_etag(locale)
    return obj


def bulk_upsert(
    locale: str,
    entries: list[dict],
    updated_by_id: int | None = None,
) -> list[Translation]:
    """Upsert multiple translations at once.

    *entries* should be a list of ``{"key": "...", "value": "...", "alias_for"?}``.
    """
    results: list[Translation] = []
    for entry in entries:
        obj = upsert_translation(
            locale=locale,
            key=entry["key"],
            value=entry.get("value", ""),
            updated_by_id=updated_by_id,
            alias_for=entry.get("alias_for"),
        )
        results.append(obj)
    return results


def duplicate_locale(
    source_locale: str,
    target_locale: str,
    copy_values: bool = False,
    updated_by_id: int | None = None,
) -> int:
    """Copy all keys from *source_locale* into *target_locale*.

    If *copy_values* is True, source values are copied verbatim.
    Otherwise, each value is replaced with a placeholder string.

    Keys that already exist in *target_locale* are skipped.
    Returns the number of newly inserted rows.
    """
    source_rows = get_translations(source_locale)
    existing_rows = get_translations(target_locale)
    existing_keys: set[str] = {t.key for t in existing_rows}

    inserted = 0
    for row in source_rows:
        if row.key in existing_keys:
            continue
        value = row.value if copy_values else ""
        obj = Translation(
            locale=target_locale,
            key=row.key,
            value=value,
            updated_by_id=updated_by_id,
        )
        db.session.add(obj)
        inserted += 1

    if inserted:
        _bump_etag(target_locale)
        _invalidate_locales_cache()
    return inserted


def delete_translation(locale: str, key: str) -> int:
    """Delete a translation key and all its aliases.

    Returns the count of deleted rows (aliases + canonical key).
    """
    alias_stmt = (
        select(Translation)
        .where(Translation.locale == locale)  # type: ignore[arg-type]
        .where(Translation.alias_for == key)  # type: ignore[arg-type]
    )
    aliases = list(db.session.scalars(alias_stmt).all())

    stmt = (
        select(Translation)
        .where(Translation.locale == locale)  # type: ignore[arg-type]
        .where(Translation.key == key)  # type: ignore[arg-type]
    )
    obj = db.session.scalar(stmt)

    deleted_count = 0
    for alias in aliases:
        db.session.delete(alias)
        deleted_count += 1

    if obj is not None:
        db.session.delete(obj)
        deleted_count += 1

    if deleted_count:
        _bump_etag(locale)
        # Check if the locale still has any rows; if not, invalidate locales cache
        remaining = db.session.scalar(
            select(Translation.id).where(Translation.locale == locale).limit(1)  # type: ignore[call-overload,arg-type]
        )
        if remaining is None:
            _invalidate_locales_cache()
    return deleted_count


def import_translations(
    locale: str,
    entries: list[dict],
    updated_by_id: int | None = None,
) -> int:
    """Upsert a list of translations for *locale*.

    *entries* is a list of ``{"key": "...", "value": "...", "alias_for"?}``.
    Returns the number of rows upserted.
    """
    count = 0
    for entry in entries:
        upsert_translation(
            locale=locale,
            key=entry["key"],
            value=entry.get("value", ""),
            updated_by_id=updated_by_id,
            alias_for=entry.get("alias_for"),
        )
        count += 1
    return count


def report_missing_keys(locale: str, keys: list[dict]) -> int:
    """Process a batch of keys reported by the frontend.

    Each item in *keys* is ``{"key": "...", "default_value": "..." | None}``.

    For each key:
      - If it doesn't exist for this locale → create it with value='',
        needs_attention=True, is_missing=True, last_used_at=now,
        default_value if provided.
      - If it exists with an empty value → set needs_attention=True,
        is_missing=False, last_used_at=now. Update default_value if a
        non-empty new value is provided (don't overwrite existing non-null
        with null).
      - If it exists with a non-empty value → just update last_used_at=now.
        Update default_value if a non-empty new value is provided.

    Returns the count of keys that are flagged (newly or still).
    """
    now = datetime.now(timezone.utc)
    flagged = 0
    for item in keys:
        key = item["key"]
        default_val = item.get("default_value")
        stmt = (
            select(Translation)
            .where(Translation.locale == locale)  # type: ignore[arg-type]
            .where(Translation.key == key)  # type: ignore[arg-type]
        )
        existing = db.session.scalar(stmt)
        if existing is None:
            obj = Translation(
                locale=locale,
                key=key,
                value="",
                default_value=default_val,
                needs_attention=True,
                is_missing=True,
                last_used_at=now,
            )
            db.session.add(obj)
            flagged += 1
        else:
            existing.last_used_at = now
            if default_val and not existing.default_value:
                existing.default_value = default_val
            if not existing.value or not existing.value.strip():
                if not existing.needs_attention:
                    existing.needs_attention = True
                    existing.is_missing = False
                flagged += 1
    if flagged:
        _bump_etag(locale)
    return flagged


def get_flagged(locale: str) -> list[Translation]:
    """Return all translations for *locale* where needs_attention is True."""
    stmt = (
        select(Translation)
        .where(Translation.locale == locale)  # type: ignore[arg-type]
        .where(Translation.needs_attention.is_(True))  # type: ignore[attr-defined]
        .order_by(Translation.key)
    )
    return list(db.session.scalars(stmt).all())


def copy_defaults(locale: str) -> int:
    """Fill empty/missing translation values from their default_value.

    For every row where value is empty OR is_missing is True AND
    default_value is non-empty, set value = default_value and clear
    needs_attention / is_missing flags.

    Returns the number of rows filled.
    """
    rows = get_translations(locale)
    filled = 0
    for row in rows:
        is_empty = not row.value or not row.value.strip()
        if (is_empty or row.is_missing) and row.default_value:
            row.value = row.default_value
            row.needs_attention = False
            row.is_missing = False
            filled += 1
    if filled:
        _bump_etag(locale)
    return filled
