"""Per-club limits: members, mails per month and storage.

Each plan has default limits (platform settings ``limits.<plan>.<kind>``,
empty = no limit); a club can have its own (``Tenant.settings["limits"]``,
set in manage only: a number, or ``null`` for no limit, and a missing key
for the plan's default).

* **members** — members that are not archived.  A hard limit: when it is
  reached, no new member joins (invites, applications, joining an open
  club); platform staff adding someone in manage are not stopped.
* **mail_month** — mails the relay took for the club this calendar month
  (UTC).  A soft limit: mails still go out, the club and the platform are
  warned.
* **storage_mb** — the club's schema plus mailbox space.  Soft.

``check_quotas`` (Celery beat, hourly) warns once per level: at
``limits.warn_percent`` (80 % by default) and at 100 %, in the club's bell
for its owners and in the platform event log (which also puts it in the
health column of manage › Alle Vereine).  Mail warnings start again each
month.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from hubra.core.errors import ApiError
from hubra.core.extensions import db
from hubra.core.models.platform_event import PlatformEvent
from hubra.core.models.tenant import Tenant

_log = logging.getLogger(__name__)

KINDS = ("members", "mail_month", "storage_mb")
PLANS = ("starter", "growth", "enterprise")
WARN_PERCENT = 80

_MAIL_KINDS = ("mail.sent", "mail.fallback")

# English bell texts (translated by notification_text / notificationText.ts).
TITLE_NEAR = "Club limit almost reached"
TITLE_OVER = "Club limit reached"
MESSAGES = {
    "members": "Members: {used} of {limit}.",
    "mail_month": "Mails this month: {used} of {limit}.",
    "storage_mb": "Storage: {used} MB of {limit} MB.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def warn_percent() -> int:
    from hubra.core.services import platform_settings

    value = platform_settings.int_setting("limits.warn_percent", WARN_PERCENT)
    return value if 1 <= value <= 100 else WARN_PERCENT


def plan_limits(plan: str) -> dict[str, int | None]:
    from hubra.core.services import platform_settings

    out: dict[str, int | None] = {}
    for kind in KINDS:
        try:
            raw = str(platform_settings.get(f"limits.{plan}.{kind}") or "").strip()
        except Exception:  # noqa: BLE001  (unknown plan, database hiccup)
            raw = ""
        out[kind] = int(raw) if raw.isdigit() else None
    return out


def overrides(tenant: Tenant) -> dict[str, int | None]:
    """The club's own limits; a kind that is missing follows the plan."""
    raw = (tenant.settings or {}).get("limits") or {}
    if not isinstance(raw, dict):
        return {}
    return {
        k: raw[k]
        for k in KINDS
        if k in raw
        and (
            raw[k] is None or (isinstance(raw[k], int) and not isinstance(raw[k], bool))
        )
    }


def limits_for(tenant: Tenant) -> dict[str, int | None]:
    return {**plan_limits(tenant.plan), **overrides(tenant)}


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def usage(tenants: list[Tenant]) -> dict[int, dict[str, int]]:
    """Members, mails this month and storage (MB, rounded up) per club."""
    from hubra.core.services import tenant_health

    ids = [t.id for t in tenants]
    if not ids:
        return {}
    health = tenant_health.for_tenants(tenants)
    mails = dict(
        db.session.execute(
            select(PlatformEvent.tenant_id, func.count())
            .where(
                PlatformEvent.tenant_id.in_(ids),
                PlatformEvent.category == "mail",
                PlatformEvent.kind.in_(_MAIL_KINDS),
                PlatformEvent.created_at >= _month_start(_now()),
            )
            .group_by(PlatformEvent.tenant_id)
        ).all()
    )
    return {
        t.id: {
            "members": health[t.id]["members"],
            "mail_month": int(mails.get(t.id, 0)),
            "storage_mb": -(-health[t.id]["storage_bytes"] // (1024 * 1024)),
        }
        for t in tenants
    }


def _level(used: int, limit: int | None, warn: int) -> str:
    if limit is None:
        return "ok"
    if used >= limit:
        return "over"
    if limit and used * 100 >= limit * warn:
        return "warning"
    return "ok"


def status(tenant: Tenant, used: dict[str, int] | None = None) -> dict:
    """Used, limit, percent and level (ok, warning, over) per kind."""
    used = used if used is not None else usage([tenant])[tenant.id]
    limits = limits_for(tenant)
    own = overrides(tenant)
    plan = plan_limits(tenant.plan)
    warn = warn_percent()
    out = {}
    for kind in KINDS:
        limit = limits[kind]
        out[kind] = {
            "used": used[kind],
            "limit": limit,
            "plan_limit": plan[kind],
            "custom": kind in own,
            "percent": round(used[kind] * 100 / limit) if limit else None,
            "level": _level(used[kind], limit, warn),
        }
    return {"limits": out, "warn_percent": warn}


def set_overrides(tenant: Tenant, values: dict) -> None:
    """Body from manage: ``{kind: number | null | "plan"}``; "plan" drops the
    club's own value."""
    settings = dict(tenant.settings or {})
    own = dict(settings.get("limits") or {})
    for kind, value in values.items():
        if kind not in KINDS:
            raise ApiError(400, "VALIDATION_ERROR", f"Unknown limit {kind!r}")
        if value == "plan":
            own.pop(kind, None)
        elif value is None:
            own[kind] = None
        elif (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value <= 10**9
        ):
            own[kind] = value
        else:
            raise ApiError(
                400,
                "VALIDATION_ERROR",
                f"{kind} must be a whole number, null or 'plan'",
            )
    settings["limits"] = own
    tenant.settings = settings


# ── Hard limit: members ─────────────────────────────────────────────────────


def member_count(tenant: Tenant) -> int:
    """Members of the club that are not archived (only this count, not the
    whole health row: it runs on every join)."""
    from sqlalchemy import text

    from hubra.core.models.user_tenant import UserTenant
    from hubra.core.services import tenant_health

    if tenant_health._postgres():
        return int(
            db.session.scalar(
                text(
                    f"SELECT count(*) FROM tenant_{int(tenant.id)}.members "
                    "WHERE archived_at IS NULL"
                )
            )
            or 0
        )
    # SQLite (tests) has no schemas: the accounts linked to the club.
    return int(
        db.session.scalar(
            select(func.count())
            .select_from(UserTenant)
            .where(UserTenant.tenant_id == tenant.id, UserTenant.status == "active")
        )
        or 0
    )


def ensure_room_for_member(tenant: Tenant | None = None) -> None:
    """Refuse a new member when the club is at its member limit (409)."""
    if tenant is None:
        from hubra.core.tenant.context import current_tenant

        tenant = current_tenant()
    if tenant is None:
        return
    limit = limits_for(tenant)["members"]
    if limit is None:
        return
    if member_count(tenant) >= limit:
        raise ApiError(
            409,
            "MEMBER_LIMIT_REACHED",
            f"This club has reached its limit of {limit} members",
        )


# ── Warnings ────────────────────────────────────────────────────────────────


def _notified(tenant: Tenant) -> dict:
    return dict((tenant.settings or {}).get("limits_notified") or {})


def _period(kind: str, now: datetime) -> str:
    return now.strftime("%Y-%m") if kind == "mail_month" else ""


def check_tenant(tenant: Tenant, used: dict[str, int]) -> list[tuple[str, str]]:
    """Warn about every kind that reached a new level; returns (kind, level)."""
    from hubra.core.services import platform_monitor

    now = _now()
    state = status(tenant, used)["limits"]
    seen = _notified(tenant)
    changed: list[tuple[str, str]] = []
    for kind, row in state.items():
        level = row["level"]
        mark = f"{_period(kind, now)}:{level}"
        before = seen.get(kind, "")
        if level == "ok":
            if before:
                seen.pop(kind, None)
            continue
        # Warn once per level (and per month for mail); a club that drops
        # back below warns again next time.
        if before == mark or (
            level == "warning"
            and before.endswith(":over")
            and before.startswith(_period(kind, now))
        ):
            continue
        seen[kind] = mark
        changed.append((kind, level))
        msg = MESSAGES[kind].format(used=row["used"], limit=row["limit"])
        platform_monitor.record(
            "system",
            "quota.over" if level == "over" else "quota.warning",
            f"{tenant.name}: {msg}",
            level="warning",
            details={"kind": kind, **{k: row[k] for k in ("used", "limit", "percent")}},
            tenant_id=tenant.id,
        )
        _tell_owners(tenant, TITLE_OVER if level == "over" else TITLE_NEAR, msg)
    settings = dict(tenant.settings or {})
    settings["limits_notified"] = seen
    tenant.settings = settings
    return changed


def _tell_owners(tenant: Tenant, title: str, msg: str) -> None:
    from hubra.api.notifications.services import notify_member
    from hubra.api.permissions import held_roles
    from hubra.core.models.member import Member
    from hubra.core.tenant.context import in_club

    try:
        with in_club(tenant):
            for m in db.session.scalars(
                select(Member).where(Member.archived_at.is_(None))
            ).all():
                if any(r.is_owner for r in held_roles(m)):
                    notify_member(m.id, "warning", title, msg, link="/app/settings")
            db.session.flush()
    except Exception:  # noqa: BLE001
        _log.warning("quota_notice_failed tenant=%s", tenant.id, exc_info=True)


def check_all() -> dict:
    """Every active club with a limit: warn about new levels."""
    tenants = list(
        db.session.scalars(
            select(Tenant).where(Tenant.deleted_at.is_(None), Tenant.status == "active")
        ).all()
    )
    tenants = [t for t in tenants if any(v is not None for v in limits_for(t).values())]
    used = usage(tenants)
    changed = {}
    for t in tenants:
        c = check_tenant(t, used[t.id])
        if c:
            changed[t.slug] = c
    db.session.commit()
    return {"checked": len(tenants), "changed": changed}
