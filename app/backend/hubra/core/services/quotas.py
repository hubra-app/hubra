"""Per-club limits: members, mails per month and storage.

Each plan has default limits (manage › Einstellungen › Tarife, on the plan
row, ``services.plans``; empty = no limit); a club can have its own (``Tenant.settings["limits"]``,
set in manage only: a number, or ``null`` for no limit, and a missing key
for the plan's default).

* **members** — members that are not archived.  At the limit a club gets a
  grace period (``limits.grace_days``, 14 days by default) from the first
  join past it, in which members still join while its admins see which plan
  fits (``suggest_plan``, club app banner); after it no new member joins
  (invites, applications, joining an open club) until the club is under the
  limit again or on a bigger plan.  0 days: a hard stop at the limit.
  Platform staff adding someone in manage are never stopped.
* **mail_month** — mails the relay took for the club this calendar month
  (UTC).  A soft limit: mails still go out, the club and the platform are
  warned.
* **storage_mb** — the club's schema plus mailbox space.  Soft.

Not a usage limit but set the same way: **file_mb**, the largest file the
club can upload (``hubra.core.files.put`` refuses larger ones).  The club's
own value wins, then its plan's; a plan without one uses the platform's
``files.max_mb`` (25 MB).  Whatever it says, the server takes no upload
larger than ``MAX_UPLOAD_MB`` (100 MB by default, also nginx's limit).

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
FILE_KIND = "file_mb"
WARN_PERCENT = 80
GRACE_DAYS = 14

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


def grace_days() -> int:
    from hubra.core.services import platform_settings

    value = platform_settings.int_setting("limits.grace_days", GRACE_DAYS)
    return value if 0 <= value <= 90 else GRACE_DAYS


def plan_limits(plan: str) -> dict[str, int | None]:
    from hubra.core.services import plans

    try:
        limits = plans.limits(plan)
    except Exception:  # noqa: BLE001  (database hiccup: no limits)
        return dict.fromkeys(KINDS)
    return {k: limits.get(k) for k in KINDS}


def _plan_file_mb(plan: str | None) -> int | None:
    from hubra.core.services import plans

    try:
        return plans.limits(plan).get(FILE_KIND)
    except Exception:  # noqa: BLE001  (database hiccup: the default)
        return None


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


# ── Largest file ─────────────────────────────────────────────────────────────


def upload_ceiling_mb() -> int:
    """The largest upload the server takes at all (``MAX_UPLOAD_MB``)."""
    from flask import current_app, has_app_context

    if not has_app_context():
        return 100
    return int(current_app.config.get("MAX_UPLOAD_MB", 100))


def default_file_mb() -> int:
    """``files.max_mb``: the largest file for a plan that sets none."""
    from hubra.core.services import platform_settings

    value = platform_settings.int_setting("files.max_mb", 25)
    return value if value >= 1 else 25


def _own_file_mb(tenant: Tenant) -> int | None:
    raw = ((tenant.settings or {}).get("limits") or {}).get(FILE_KIND)
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1:
        return raw
    return None


def file_limit(tenant: Tenant | None) -> dict:
    """The largest file a club can upload, in MB, and where it comes from:
    ``club`` (its own), ``plan`` or ``default`` (files.max_mb).  ``limit``
    is capped at the server's ``ceiling``."""
    ceiling = upload_ceiling_mb()
    default = default_file_mb()
    plan = _plan_file_mb(tenant.plan) if tenant is not None else None
    own = _own_file_mb(tenant) if tenant is not None else None
    wanted, source = (
        (own, "club")
        if own is not None
        else (plan, "plan")
        if plan is not None
        else (default, "default")
    )
    return {
        "limit": min(wanted, ceiling),
        "wanted": wanted,
        "source": source,
        "custom": own is not None,
        "plan_limit": plan,
        "default": default,
        "ceiling": ceiling,
    }


def max_file_mb(tenant: Tenant | None) -> int:
    return file_limit(tenant)["limit"]


def own_limits(tenant: Tenant) -> dict[str, int | None]:
    """Everything the club has of its own (for the audit log)."""
    own = overrides(tenant)
    if (mb := _own_file_mb(tenant)) is not None:
        own[FILE_KIND] = mb
    return own


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
    return {"limits": out, "warn_percent": warn, "file": file_limit(tenant)}


def set_overrides(tenant: Tenant, values: dict) -> None:
    """Body from manage: ``{kind: number | null | "plan"}``; "plan" drops the
    club's own value.  ``file_mb`` takes a number of MB or "plan" (no null:
    a file always has a largest size)."""
    settings = dict(tenant.settings or {})
    own = dict(settings.get("limits") or {})
    for kind, value in values.items():
        if kind == FILE_KIND:
            from hubra.core.services import plans

            if value == "plan":
                own.pop(kind, None)
            else:
                mb = plans.file_mb(value, kind)
                if mb is None:
                    raise ApiError(
                        400, "VALIDATION_ERROR", f"{kind} is a number of MB or 'plan'"
                    )
                own[kind] = mb
            continue
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
    if member_count(tenant) < limit:
        return
    until = grace_until(tenant, start=True)
    if until is not None and _now() < until:
        return
    raise ApiError(
        409,
        "MEMBER_LIMIT_REACHED",
        f"This club has reached its limit of {limit} members",
    )


# ── Grace period and the plan that fits ────────────────────────────────────


def _over_since(tenant: Tenant) -> datetime | None:
    raw = ((tenant.settings or {}).get("limits_over_since") or {}).get("members")
    try:
        return datetime.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def grace_until(tenant: Tenant, *, start: bool = False) -> datetime | None:
    """When the member grace period ends (None: no grace, 0 days). With
    *start*, the first join past the limit starts it (saved with the
    caller's transaction)."""
    from datetime import timedelta

    days = grace_days()
    if days <= 0:
        return None
    since = _over_since(tenant)
    if since is None:
        if not start:
            return None
        since = _now()
        settings = dict(tenant.settings or {})
        settings["limits_over_since"] = {
            **(settings.get("limits_over_since") or {}),
            "members": since.isoformat(),
        }
        tenant.settings = settings
    return since + timedelta(days=days)


def end_grace(tenant: Tenant) -> None:
    """Under the limit again: the next time starts a new grace period."""
    over = dict((tenant.settings or {}).get("limits_over_since") or {})
    if over.pop("members", None) is not None:
        settings = dict(tenant.settings or {})
        settings["limits_over_since"] = over
        tenant.settings = settings


def suggest_plan(tenant: Tenant, state: dict | None = None) -> dict | None:
    """The cheapest plan the club may pick whose limits hold what it uses
    now with room (every kind near or over its limit fits under the new
    plan's warning line). None when no offered plan fits better."""
    from decimal import Decimal

    from hubra.core.billing.self_service import _plan_choices
    from hubra.core.services import plans

    state = state or status(tenant)["limits"]
    tight = {k: r["used"] for k, r in state.items() if r["level"] != "ok"}
    if not tight:
        return None
    warn = warn_percent()
    best = None
    for plan in _plan_choices(tenant):
        if plan.key == tenant.plan:
            continue
        lim = plans.limits(plan.key)
        if not all(
            lim.get(k) is None or used * 100 < lim[k] * warn
            for k, used in tight.items()
        ):
            continue
        price = plans.month_price(plan.key)
        cost = Decimal(price) if price not in (None, "") else Decimal("Infinity")
        if best is None or cost < best[0]:
            best = (cost, plan, price, lim)
    if best is None:
        return None
    _, plan, price, lim = best
    return {
        "key": plan.key,
        "name_de": plan.name_de,
        "name_en": plan.name_en or plan.name_de,
        "price_month_chf": price,
        "limits": {k: lim.get(k) for k in KINDS},
    }


def club_view(tenant: Tenant) -> dict:
    """What a club's billing admins see: usage against the limits, the
    member grace period and the plan that fits."""
    state = status(tenant)
    members = state["limits"]["members"]
    until = grace_until(tenant) if members["level"] == "over" else None
    return {
        "plan": tenant.plan,
        **state,
        "grace_days": grace_days(),
        "grace_until": until.isoformat() if until else None,
        "suggestion": suggest_plan(tenant, state["limits"]),
    }


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
    if state["members"]["level"] != "over":
        end_grace(tenant)
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
    from hubra.core.notifications.services import notify_member
    from hubra.core.permissions import held_roles
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
