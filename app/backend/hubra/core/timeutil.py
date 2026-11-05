"""Small datetime helpers shared by the core."""

from __future__ import annotations

from datetime import datetime, timezone


def as_utc(value: datetime | None) -> datetime | None:
    """*value* with UTC as its zone when it has none (SQLite hands back naive
    datetimes; they are stored as UTC). ``None`` stays ``None``."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
