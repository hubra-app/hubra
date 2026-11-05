"""Health of every club at a glance, for manage › Alle Vereine.

One row per club with what an operator looks at first: when someone last
used the club, how much it stores, how many mails it sent, how many plugins
it has on, and how many warnings and errors it caused.

Everything is read in a handful of batched queries, never one round trip
per club:

* **Members, last activity, active members, mailbox storage** come from
  each club's own schema (``tenant_<id>``): one ``UNION ALL`` over the
  clubs whose schema exists.  Last activity is the newest sign-in session
  (``sessions.last_active_at``); active members are the members with a
  session used in the last 30 days.
* **Database storage** is the size of the club's schema (tables, indexes
  and TOAST) from ``pg_class``, plus the mailbox space WildDuck reported
  (``managed_mail_addresses.quota_used``, synced every few hours).
* **Mail** and **alerts** come from the platform event log
  (``platform_events``): mails the relay took for the club in the last 30
  days, and warnings and errors tagged with the club in the last 24 hours.
* **Plugins** are the plugin modules switched on and allowed for the club.

SQLite (the test suite) has no schemas: members and last activity fall back
to the accounts linked to the club, storage is 0.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text

from hubra.core.extensions import db
from hubra.core.models.platform_event import PlatformEvent
from hubra.core.models.tenant import Tenant

_log = logging.getLogger(__name__)

# A club nobody used for this long is shown as idle.
IDLE_AFTER_DAYS = 30
ACTIVE_WINDOW_DAYS = 30
MAIL_WINDOW_DAYS = 30
ALERT_WINDOW_HOURS = 24

LEVELS = ("ok", "idle", "warning", "error")

_MAIL_KINDS = ("mail.sent", "mail.fallback", "mail.failed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _postgres() -> bool:
    return db.session.get_bind().dialect.name == "postgresql"


# ── Per-schema numbers ──────────────────────────────────────────────────────


def _schemas_with(tables: tuple[str, ...], ids: list[int]) -> dict[int, set[str]]:
    """Which of *tables* exist in each club schema."""
    rows = db.session.execute(
        text(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema = ANY(:schemas) AND table_name = ANY(:tables)"
        ),
        {"schemas": [f"tenant_{i}" for i in ids], "tables": list(tables)},
    ).all()
    out: dict[int, set[str]] = {}
    for schema, table in rows:
        out.setdefault(int(schema.removeprefix("tenant_")), set()).add(table)
    return out


def _schema_numbers(ids: list[int]) -> dict[int, dict]:
    """Members, last activity, active members and mailbox bytes per club."""
    if not ids:
        return {}
    since = _now() - timedelta(days=ACTIVE_WINDOW_DAYS)
    present = _schemas_with(
        ("members", "sessions", "devices", "managed_mail_addresses"), ids
    )
    parts = []
    for tid in ids:
        tables = present.get(tid, set())
        if "members" not in tables:
            continue
        s = f"tenant_{int(tid)}"
        has_sessions = {"sessions", "devices"} <= tables
        last = (
            f"(SELECT max(last_active_at) FROM {s}.sessions)"
            if has_sessions
            else "NULL::timestamptz"
        )
        active = (
            f"(SELECT count(DISTINCT d.member_id) FROM {s}.sessions x "
            f"JOIN {s}.devices d ON d.id = x.device_id "
            "WHERE x.last_active_at >= :since)"
            if has_sessions
            else "0"
        )
        mailbox = (
            f"(SELECT coalesce(sum(quota_used), 0) FROM {s}.managed_mail_addresses)"
            if "managed_mail_addresses" in tables
            else "0"
        )
        parts.append(
            f"SELECT {int(tid)} AS tid, "
            f"(SELECT count(*) FROM {s}.members WHERE archived_at IS NULL) AS members, "
            f"{last} AS last_active, {active} AS active, {mailbox} AS mailbox"
        )
    if not parts:
        return {}
    rows = db.session.execute(text(" UNION ALL ".join(parts)), {"since": since}).all()
    return {
        int(r.tid): {
            "members": int(r.members or 0),
            "last_activity": _aware(r.last_active),
            "active_members": int(r.active or 0),
            "mailbox_bytes": int(r.mailbox or 0),
        }
        for r in rows
    }


def _schema_sizes(ids: list[int]) -> dict[int, int]:
    """Bytes on disk of each club schema (tables with indexes and TOAST)."""
    if not ids:
        return {}
    rows = db.session.execute(
        text(
            "SELECT n.nspname, coalesce(sum(pg_total_relation_size(c.oid)), 0) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = ANY(:schemas) AND c.relkind IN ('r', 'm') "
            "GROUP BY n.nspname"
        ),
        {"schemas": [f"tenant_{i}" for i in ids]},
    ).all()
    return {int(name.removeprefix("tenant_")): int(size) for name, size in rows}


def _sqlite_numbers(ids: list[int]) -> dict[int, dict]:
    """Test fallback: the accounts linked to each club."""
    from hubra.core.models.user import User
    from hubra.core.models.user_tenant import UserTenant

    since = _now() - timedelta(days=ACTIVE_WINDOW_DAYS)
    rows = db.session.execute(
        select(UserTenant.tenant_id, User.last_seen)
        .join(User, User.id == UserTenant.user_id)
        .where(UserTenant.tenant_id.in_(ids), UserTenant.status == "active")
    ).all()
    out: dict[int, dict] = {}
    for tid, seen in rows:
        item = out.setdefault(
            tid,
            {
                "members": 0,
                "last_activity": None,
                "active_members": 0,
                "mailbox_bytes": 0,
            },
        )
        item["members"] += 1
        seen = _aware(seen)
        if seen and (item["last_activity"] is None or seen > item["last_activity"]):
            item["last_activity"] = seen
        if seen and seen >= since:
            item["active_members"] += 1
    return out


# ── Platform-wide tables ────────────────────────────────────────────────────


def _mail_counts(ids: list[int]) -> dict[int, dict[str, int]]:
    since = _now() - timedelta(days=MAIL_WINDOW_DAYS)
    rows = db.session.execute(
        select(PlatformEvent.tenant_id, PlatformEvent.kind, func.count())
        .where(
            PlatformEvent.tenant_id.in_(ids),
            PlatformEvent.category == "mail",
            PlatformEvent.kind.in_(_MAIL_KINDS),
            PlatformEvent.created_at >= since,
        )
        .group_by(PlatformEvent.tenant_id, PlatformEvent.kind)
    ).all()
    out: dict[int, dict[str, int]] = {}
    for tid, kind, n in rows:
        item = out.setdefault(tid, {"sent": 0, "failed": 0})
        item["failed" if kind == "mail.failed" else "sent"] += n
    return out


def _alert_counts(ids: list[int]) -> dict[int, dict[str, int]]:
    since = _now() - timedelta(hours=ALERT_WINDOW_HOURS)
    rows = db.session.execute(
        select(PlatformEvent.tenant_id, PlatformEvent.level, func.count())
        .where(
            PlatformEvent.tenant_id.in_(ids),
            PlatformEvent.level.in_(("warning", "error")),
            PlatformEvent.created_at >= since,
        )
        .group_by(PlatformEvent.tenant_id, PlatformEvent.level)
    ).all()
    out: dict[int, dict[str, int]] = {}
    for tid, level, n in rows:
        out.setdefault(tid, {"warning": 0, "error": 0})[level] = n
    return out


def _plugin_counts(ids: list[int]) -> dict[int, int]:
    from hubra.core.models.feature import TenantFeature
    from hubra.core.modules.registry import registry

    codes = [m.code for m in registry.all() if m.plugin]
    if not codes:
        return {}
    rows = db.session.execute(
        select(TenantFeature.tenant_id, func.count())
        .where(
            TenantFeature.tenant_id.in_(ids),
            TenantFeature.feature_code.in_(codes),
            TenantFeature.enabled.is_(True),
            TenantFeature.allowed.is_(True),
        )
        .group_by(TenantFeature.tenant_id)
    ).all()
    return {tid: n for tid, n in rows}


# ── Public API ──────────────────────────────────────────────────────────────


def level_of(row: dict, status: str) -> str:
    """ok, idle, warning or error, worst first."""
    if row["alerts"]["error"]:
        return "error"
    if row["alerts"]["warning"] or row["mail"]["failed"] or status == "suspended":
        return "warning"
    last = row["last_activity"]
    if status == "active" and (
        last is None or last < _now() - timedelta(days=IDLE_AFTER_DAYS)
    ):
        return "idle"
    return "ok"


def _file_bytes(ids: list[int]) -> dict[int, int]:
    from hubra.core import files

    return files.usage_bytes(ids)


def for_tenants(tenants: list[Tenant]) -> dict[int, dict]:
    """Health of each of *tenants*, by tenant id.  Never raises: a part that
    fails is left empty and logged, so the list still shows."""
    ids = [t.id for t in tenants]
    if not ids:
        return {}

    def safe(fn, *args):
        try:
            with db.session.begin_nested():
                return fn(*args)
        except Exception:
            _log.warning(
                "tenant_health_part_failed part=%s", fn.__name__, exc_info=True
            )
            return {}

    if _postgres():
        numbers = safe(_schema_numbers, ids)
        sizes = safe(_schema_sizes, ids)
    else:
        numbers = safe(_sqlite_numbers, ids)
        sizes = {}
    mail = safe(_mail_counts, ids)
    file_bytes = safe(_file_bytes, ids)
    alerts = safe(_alert_counts, ids)
    plugins = safe(_plugin_counts, ids)

    out: dict[int, dict] = {}
    for t in tenants:
        n = numbers.get(t.id, {})
        row = {
            "members": n.get("members", 0),
            "active_members": n.get("active_members", 0),
            "last_activity": n.get("last_activity"),
            "storage_bytes": sizes.get(t.id, 0)
            + n.get("mailbox_bytes", 0)
            + file_bytes.get(t.id, 0),
            "mail": mail.get(t.id, {"sent": 0, "failed": 0}),
            "plugins": plugins.get(t.id, 0),
            "alerts": alerts.get(t.id, {"warning": 0, "error": 0}),
        }
        row["level"] = level_of(row, t.status)
        out[t.id] = row
    return out


def to_json(row: dict) -> dict:
    last = row["last_activity"]
    return {**row, "last_activity": last.isoformat() if last else None}
