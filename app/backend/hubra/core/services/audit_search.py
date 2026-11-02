"""Search the audit logs of the platform and of every club at once.

Manage › Audit-Log.  Two kinds of entries:

* **platform** — ``global_audit_logs`` (public): what platform staff and the
  system did, with ``details``.
* **club** — each club's own ``audit_entries`` in its schema
  (``tenant_<id>``): what the club's admins did, with the actor's and the
  target's name as they were at the time.

On Postgres one ``UNION ALL`` over the platform log and every club schema
that has the table is filtered, counted and paged in the database, never one
round trip per club.  SQLite (the test suite) has no schemas: club entries
are read from the one ``audit_entries`` table, and only when a club is
chosen.

Export is CSV (``;``, UTF-8 with BOM, as the member export) with at most
``EXPORT_LIMIT`` rows; cells that a spreadsheet would run as a formula are
prefixed with ``'``.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select, text

from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant

EXPORT_LIMIT = 10_000
SOURCES = ("all", "platform", "club")


@dataclass
class Filters:
    q: str = ""
    source: str = "all"
    tenant_id: int | None = None
    action: str = ""
    date_from: date | None = None
    date_to: date | None = None
    # Sign-ins are most of a club's log; manage hides them by default.
    hide_logins: bool = False
    errors: list[str] = field(default_factory=list)


def _date(value: str | None, name: str, errors: list[str]) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{name} is a date (YYYY-MM-DD)")
        return None


def parse(args) -> Filters:
    """Filters from the query string; problems end up in ``errors``."""
    f = Filters()
    f.q = (args.get("q") or "").strip()[:200]
    f.action = (args.get("action") or "").strip()[:100]
    f.source = args.get("source") or "all"
    if f.source not in SOURCES:
        f.errors.append("source is all, platform or club")
    tid = args.get("tenant_id")
    if tid:
        if not str(tid).isdigit():
            f.errors.append("tenant_id must be a number")
        else:
            f.tenant_id = int(tid)
    f.hide_logins = args.get("hide_logins") in ("1", "true")
    f.date_from = _date(args.get("from"), "from", f.errors)
    f.date_to = _date(args.get("to"), "to", f.errors)
    if f.date_from and f.date_to and f.date_from > f.date_to:
        f.errors.append("from is after to")
    return f


def _postgres() -> bool:
    return db.session.get_bind().dialect.name == "postgresql"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _club_ids(f: Filters) -> list[int]:
    if f.source == "platform":
        return []
    if f.tenant_id is not None:
        return [f.tenant_id]
    return list(db.session.scalars(select(Tenant.id).order_by(Tenant.id)))


def _club_tables(ids: list[int]) -> dict[int, str]:
    """``{club id: its audit table}`` for the clubs that have one."""
    if not ids:
        return {}
    if not _postgres():
        return {ids[0]: "audit_entries"} if len(ids) == 1 else {}
    rows = db.session.execute(
        text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_schema = ANY(:schemas) AND table_name = 'audit_entries'"
        ),
        {"schemas": [f"tenant_{int(i)}" for i in ids]},
    ).scalars()
    return {int(s.removeprefix("tenant_")): f"{s}.audit_entries" for s in rows}


def _union(f: Filters) -> str | None:
    """The entries both logs have in common, one row shape."""
    cast_text = "::text" if _postgres() else ""
    parts = []
    if f.source in ("all", "platform"):
        tenant = " WHERE tenant_id = :tenant_id" if f.tenant_id is not None else ""
        parts.append(
            "SELECT 'platform' AS source, id, tenant_id, time, action, actor_id, "
            "CAST(NULL AS VARCHAR) AS actor_name, target_type, target_id, "
            f"CAST(NULL AS VARCHAR) AS target_label, details{cast_text} AS details, "
            f"ip_address FROM global_audit_logs{tenant}"
        )
    for tid, table in _club_tables(_club_ids(f)).items():
        parts.append(
            f"SELECT 'club' AS source, id, {int(tid)} AS tenant_id, time, action, "
            f"actor_id, actor_name, target_type, CAST(target_id AS VARCHAR) AS "
            f"target_id, target_label, CAST(NULL AS VARCHAR) AS details, "
            f"CAST(NULL AS VARCHAR) AS ip_address FROM {table}"
        )
    return " UNION ALL ".join(parts) if parts else None


def _where(f: Filters) -> tuple[str, dict]:
    conds, params = [], {}
    if f.tenant_id is not None:
        params["tenant_id"] = f.tenant_id
    if f.q:
        params["q"] = f"%{_escape_like(f.q.lower())}%"
        text_of = " || ' ' || ".join(
            f"coalesce(lower({c}), '')"
            for c in (
                "action",
                "actor_name",
                "target_type",
                "target_id",
                "target_label",
                "details",
                "ip_address",
            )
        )
        conds.append(f"({text_of}) LIKE :q ESCAPE '\\'")
    if f.action:
        params["action"] = f"{_escape_like(f.action.lower())}%"
        conds.append("lower(action) LIKE :action ESCAPE '\\'")
    if f.hide_logins:
        conds.append("action <> 'login'")
    if f.date_from:
        params["from"] = datetime.combine(f.date_from, time.min, timezone.utc)
        conds.append("time >= :from")
    if f.date_to:
        params["to"] = datetime.combine(
            f.date_to + timedelta(days=1), time.min, timezone.utc
        )
        conds.append("time < :to")
    return (" WHERE " + " AND ".join(conds)) if conds else "", params


def _aware(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):  # SQLite
        value = datetime.fromisoformat(value)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _rows(f: Filters, limit: int, offset: int = 0) -> tuple[list, int]:
    union = _union(f)
    if union is None:
        return [], 0
    where, params = _where(f)
    total = db.session.execute(
        text(f"SELECT count(*) FROM ({union}) u{where}"), params
    ).scalar_one()
    rows = db.session.execute(
        text(
            f"SELECT * FROM ({union}) u{where} "
            "ORDER BY time DESC, source, id DESC LIMIT :limit OFFSET :offset"
        ),
        {**params, "limit": limit, "offset": offset},
    ).all()
    return rows, int(total)


def _people(rows) -> dict[int, dict]:
    """Platform actors are accounts (users.id); clubs keep the name."""
    from hubra.core.models.user import User

    ids = {r.actor_id for r in rows if r.source == "platform" and r.actor_id}
    if not ids:
        return {}
    users = db.session.scalars(select(User).where(User.id.in_(ids))).all()
    return {u.id: {"name": u.name, "email": u.email} for u in users}


def _clubs(rows) -> dict[int, str]:
    ids = {r.tenant_id for r in rows if r.tenant_id}
    if not ids:
        return {}
    return dict(
        db.session.execute(
            select(Tenant.id, Tenant.name).where(Tenant.id.in_(ids))
        ).all()
    )


def _entry(r, people: dict, clubs: dict) -> dict:
    details = r.details
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except ValueError:
            pass
    if r.source == "platform":
        person = people.get(r.actor_id) or {}
        actor = person.get("name") or person.get("email")
    else:
        actor = r.actor_name
    return {
        "key": f"{r.source}-{r.tenant_id or 0}-{r.id}",
        "source": r.source,
        "id": r.id,
        "tenant_id": r.tenant_id,
        "club": clubs.get(r.tenant_id),
        "time": _aware(r.time).isoformat() if r.time else None,
        "action": r.action,
        "actor_id": r.actor_id,
        "actor": actor,
        "actor_email": (people.get(r.actor_id) or {}).get("email")
        if r.source == "platform"
        else None,
        "target_type": r.target_type,
        "target_id": r.target_id,
        "target_label": r.target_label,
        "details": details,
        "ip_address": r.ip_address,
    }


def search(f: Filters, page: int, per_page: int) -> dict:
    rows, total = _rows(f, per_page, (page - 1) * per_page)
    people, clubs = _people(rows), _clubs(rows)
    return {
        "entries": [_entry(r, people, clubs) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _cell(value) -> str:
    if value is None:
        return ""
    s = value if isinstance(value, str) else str(value)
    return "'" + s if s.startswith(_FORMULA) else s


def export_csv(f: Filters) -> tuple[str, int, bool]:
    """``(csv, rows, truncated)``."""
    rows, total = _rows(f, EXPORT_LIMIT)
    people, clubs = _people(rows), _clubs(rows)
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out, delimiter=";")
    writer.writerow(
        ["time", "source", "club_id", "club", "action", "actor", "actor_email",
         "target_type", "target_id", "target", "details", "ip_address"]
    )  # fmt: skip
    for r in rows:
        e = _entry(r, people, clubs)
        details = e["details"]
        writer.writerow(
            [
                _cell(v)
                for v in (
                    e["time"],
                    e["source"],
                    e["tenant_id"],
                    e["club"],
                    e["action"],
                    e["actor"],
                    e["actor_email"],
                    e["target_type"],
                    e["target_id"],
                    e["target_label"],
                    json.dumps(details, ensure_ascii=False)
                    if details not in (None, "")
                    else "",
                    e["ip_address"],
                )
            ]
        )
    return out.getvalue(), len(rows), total > len(rows)
