"""Quiet hours: no push and no direct message at night (roadmap idea 24).

An account sets a window (``users.quiet_hours``: ``{"from": "22:00",
"to": "07:00", "tz": "Europe/Zurich"}``) on SSO › Benachrichtigungen. It
counts for every club. A browser push or a direct message through a
connected app (Discord) that falls into it waits and goes out when it
ends; the bell and mail are not held (they don't wake anyone).
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
DEFAULT_TZ = "Europe/Zurich"


def _time(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def get(user) -> dict | None:
    """The account's window, or None."""
    stored = getattr(user, "quiet_hours", None) or None
    if not isinstance(stored, dict):
        return None
    start, end = stored.get("from"), stored.get("to")
    if not (isinstance(start, str) and _HHMM.match(start)):
        return None
    if not (isinstance(end, str) and _HHMM.match(end)) or start == end:
        return None
    return {"from": start, "to": end, "tz": stored.get("tz") or DEFAULT_TZ}


def validate(body) -> str | None:
    """None when *body* is ``null`` (no quiet hours) or a valid window."""
    if body is None:
        return None
    if not isinstance(body, dict):
        return "Expected an object or null"
    unknown = set(body) - {"from", "to", "tz"}
    if unknown:
        return f"Unknown field: {sorted(unknown)[0]}"
    for key in ("from", "to"):
        if not isinstance(body.get(key), str) or not _HHMM.match(body[key]):
            return f"{key}: a time as HH:MM"
    if body["from"] == body["to"]:
        return "from and to must differ"
    tz = body.get("tz")
    if tz is not None:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            return "tz: an IANA time zone such as Europe/Zurich"
    return None


def apply(user, body) -> None:
    """Store a validated body (``None`` turns quiet hours off)."""
    user.quiet_hours = (
        None
        if body is None
        else {
            "from": body["from"],
            "to": body["to"],
            "tz": body.get("tz") or DEFAULT_TZ,
        }
    )


def wait_seconds(window: dict | None, now: datetime | None = None) -> int:
    """Seconds until *window* ends when *now* falls into it, else 0."""
    if not window:
        return 0
    zone = _zone(window.get("tz"))
    local = (now or datetime.now(timezone.utc)).astimezone(zone)
    start, end = _time(window["from"]), _time(window["to"])
    t = local.time()
    inside = start <= t < end if start < end else (t >= start or t < end)
    if not inside:
        return 0
    until = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if until <= local:
        until += timedelta(days=1)
    return max(1, int((until - local).total_seconds()))


def wait_for_user(user_id: int | None, now: datetime | None = None) -> int:
    """``wait_seconds`` for an account by id (0 without one)."""
    if not user_id:
        return 0
    from hubra.core.extensions import db
    from hubra.core.models.user import User

    return wait_seconds(get(db.session.get(User, user_id)), now)
