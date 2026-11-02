"""How a club is used over time, for manage › Alle Vereine › <club> › Nutzung.

Everything comes from data the club already keeps, so the history goes back
as far as that data and nothing new is stored:

* **logins / active members** — the club's audit log (``login`` entries,
  one per sign-in to the club; active = distinct members who signed in);
* **members / new members** — ``members.joined`` and ``archived_at``;
* **events** — events held (``club_events.date``);
* **invoices** — invoices issued (count and total);
* **mails** — mails the relay took for the club (platform event log, kept
  for ``alerts.retention_days``, so older buckets are empty).

Buckets are ISO weeks (Monday) or calendar months, oldest first, the
current (unfinished) one last.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant

RANGES = {"12w": ("week", 12), "26w": ("week", 26), "12m": ("month", 12)}
METRICS = (
    "logins",
    "active_members",
    "members",
    "new_members",
    "events",
    "invoices",
    "invoice_total",
    "mails",
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _bucket_start(day: date, unit: str) -> date:
    if unit == "week":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def _next(start: date, unit: str) -> date:
    if unit == "week":
        return start + timedelta(days=7)
    return (start.replace(day=28) + timedelta(days=4)).replace(day=1)


def buckets(unit: str, count: int, today: date | None = None) -> list[date]:
    """Start days of the last *count* buckets, the current one last."""
    current = _bucket_start(today or _today(), unit)
    out = [current]
    while len(out) < count:
        prev = out[0] - timedelta(days=1)
        out.insert(0, _bucket_start(prev, unit))
    return out


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            value = value.astimezone(timezone.utc)
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def _club_rows(first: date) -> dict:
    """The club's own numbers; the search_path points at its schema."""
    from hubra.core.models.audit import AuditEntry
    from hubra.core.models.event import ClubEvent
    from hubra.core.models.finance import Invoice
    from hubra.core.models.member import Member

    since = _start_of(first)
    logins = db.session.execute(
        select(func.date(AuditEntry.time), AuditEntry.actor_id, func.count())
        .where(AuditEntry.action == "login", AuditEntry.time >= since)
        .group_by(func.date(AuditEntry.time), AuditEntry.actor_id)
    ).all()
    members = db.session.execute(select(Member.joined, Member.archived_at)).all()
    events = db.session.execute(
        select(ClubEvent.date, func.count())
        .where(ClubEvent.date >= first)
        .group_by(ClubEvent.date)
    ).all()
    invoices = db.session.execute(
        select(Invoice.issued, func.count(), func.coalesce(func.sum(Invoice.amount), 0))
        .where(Invoice.issued >= first)
        .group_by(Invoice.issued)
    ).all()
    return {
        "logins": logins,
        "members": members,
        "events": events,
        "invoices": invoices,
    }


def _mail_rows(tenant_id: int, first: date) -> list:
    from hubra.core.models.platform_event import PlatformEvent

    return db.session.execute(
        select(func.date(PlatformEvent.created_at), func.count())
        .where(
            PlatformEvent.tenant_id == tenant_id,
            PlatformEvent.category == "mail",
            PlatformEvent.kind.in_(("mail.sent", "mail.fallback")),
            PlatformEvent.created_at >= _start_of(first),
        )
        .group_by(func.date(PlatformEvent.created_at))
    ).all()


def for_tenant(
    tenant: Tenant, range_key: str = "12w", today: date | None = None
) -> dict:
    unit, count = RANGES[range_key]
    starts = buckets(unit, count, today)
    first = starts[0]
    index = {s: i for i, s in enumerate(starts)}

    def slot(day) -> int | None:
        d = _as_date(day)
        if d is None or d < first:
            return None
        return index.get(_bucket_start(d, unit))

    from hubra.core.tenant.context import in_club

    with in_club(tenant):
        rows = _club_rows(first)
    mails = _mail_rows(tenant.id, first)

    series: dict[str, list] = {m: [0] * count for m in METRICS}
    series["invoice_total"] = [Decimal(0)] * count
    active: dict[int, set] = defaultdict(set)
    for day, actor, n in rows["logins"]:
        i = slot(day)
        if i is None:
            continue
        series["logins"][i] += int(n)
        if actor is not None:
            active[i].add(actor)
    for i, who in active.items():
        series["active_members"][i] = len(who)
    for day, n in rows["events"]:
        if (i := slot(day)) is not None:
            series["events"][i] += int(n)
    for day, n, total in rows["invoices"]:
        if (i := slot(day)) is not None:
            series["invoices"][i] += int(n)
            series["invoice_total"][i] += Decimal(str(total or 0))
    for day, n in mails:
        if (i := slot(day)) is not None:
            series["mails"][i] += int(n)

    # Members at the end of each bucket (today for the current one).
    end = today or _today()
    ends = [min(_next(s, unit) - timedelta(days=1), end) for s in starts]
    for joined, archived in rows["members"]:
        j = _as_date(joined)
        a = _as_date(archived)
        if j is not None and (i := slot(j)) is not None:
            series["new_members"][i] += 1
        for i, last in enumerate(ends):
            if (j is None or j <= last) and (a is None or a > last):
                series["members"][i] += 1

    series["invoice_total"] = [float(v) for v in series["invoice_total"]]
    return {
        "range": range_key,
        "unit": unit,
        "buckets": [s.isoformat() for s in starts],
        "series": series,
    }
