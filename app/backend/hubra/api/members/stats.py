"""Member statistics for the board: /api/v1/app/members/stats.

GET /members/stats?on=YYYY-MM-DD&year=YYYY
    who was a member on the reference day (``on``, default today): by status,
    tier and membership type, and by age on that day in the brackets that
    Swiss municipal and cantonal sport subsidy forms ask for; joins and
    leaves per month of ``year`` (default this year); open fees for those
    who may read invoices.
GET /members/stats.csv  the same as a spreadsheet.

A member counts on a day when they had joined by then (or the day is not
known) and had not left (archived or deleted) before it. Status, tier and
type are today's: Hubra keeps no history of them.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from flask import Response, jsonify, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.models.finance import Invoice
from hubra.core.models.member import Member, MembershipTier
from hubra.core.permissions import (
    _get_member_permission_keys,
    member_is_admin,
    permission_required,
)
from hubra.core.utils import csv_safe

from .routes import members_bp

# Age brackets (lowest age of each); J+S counts children 5–10 and youth 10–20.
BRACKETS = (
    (0, 4),
    (5, 9),
    (10, 14),
    (15, 19),
    (20, 29),
    (30, 44),
    (45, 64),
    (65, None),
)


def _bracket(lo: int, hi: int | None) -> str:
    return f"{lo}+" if hi is None else f"{lo}-{hi}"


def _age(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def _end_of(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone.utc)


def _member_on(day: date):
    end = _end_of(day)
    return (
        or_(Member.joined.is_(None), Member.joined <= day),
        or_(Member.archived_at.is_(None), Member.archived_at >= end),
        or_(Member.deleted_at.is_(None), Member.deleted_at >= end),
    )


def _left_at():
    return func.coalesce(Member.archived_at, Member.deleted_at)


def _sees_fees(member) -> bool:
    return member_is_admin(member) or (
        "finance.invoices.read" in _get_member_permission_keys(member)
    )


def build(on: date, year: int, fees: bool) -> dict:
    members = list(
        db.session.scalars(
            select(Member).options(selectinload(Member.user)).where(*_member_on(on))
        )
    )
    tiers = {t.id: t.name for t in db.session.scalars(select(MembershipTier))}
    by_status: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    by_type: dict[str, int] = {}
    ages = {_bracket(lo, hi): 0 for lo, hi in BRACKETS}
    unknown = 0
    for m in members:
        by_status[m.status] = by_status.get(m.status, 0) + 1
        tier = tiers.get(m.tier_id, "") if m.tier_id else ""
        by_tier[tier] = by_tier.get(tier, 0) + 1
        by_type[m.membership_type] = by_type.get(m.membership_type, 0) + 1
        born = m.user.birthday if m.user else None
        if born is None or born > on:
            unknown += 1
            continue
        age = _age(born, on)
        for lo, hi in reversed(BRACKETS):
            if age >= lo:
                ages[_bracket(lo, hi)] += 1
                break

    months = []
    for month in range(1, 13):
        first = date(year, month, 1)
        last = (date(year + (month == 12), month % 12 + 1, 1)) - timedelta(days=1)
        joins = db.session.scalar(
            select(func.count(Member.id)).where(
                Member.joined >= first, Member.joined <= last
            )
        )
        leaves = db.session.scalar(
            select(func.count(Member.id)).where(
                _left_at() >= _end_of(first - timedelta(days=1)),
                _left_at() < _end_of(last),
            )
        )
        months.append(
            {"month": first.isoformat()[:7], "joins": joins or 0, "leaves": leaves or 0}
        )

    out = {
        "on": on.isoformat(),
        "year": year,
        "total": len(members),
        "byStatus": by_status,
        "byTier": by_tier,
        "byType": by_type,
        # A list: JSON objects lose their order.
        "ages": [{"bracket": k, "count": n} for k, n in ages.items()],
        "ageUnknown": unknown,
        "months": months,
        "fees": None,
    }
    if fees:
        today = date.today()
        open_q = select(
            func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.amount), 0),
            func.count(func.distinct(Invoice.member_id)),
        ).where(Invoice.status != "Paid")
        n, total, people = db.session.execute(open_q).one()
        n_over, total_over, _ = db.session.execute(
            open_q.where(Invoice.due < today)
        ).one()
        out["fees"] = {
            "open": n or 0,
            "openAmount": f"{total or 0:.2f}",
            "overdue": n_over or 0,
            "overdueAmount": f"{total_over or 0:.2f}",
            "members": people or 0,
        }
    return out


def _args():
    today = date.today()
    try:
        on = date.fromisoformat(request.args["on"]) if request.args.get("on") else today
    except ValueError:
        return None, api_error("VALIDATION_ERROR", "on must be YYYY-MM-DD", 400)
    # date.max would overflow the end-of-day bound (a 500).
    if not date(1900, 1, 1) <= on <= date(today.year + 1, 12, 31):
        return None, api_error("VALIDATION_ERROR", "on is out of range", 400)
    year = request.args.get("year", type=int) or today.year
    if not 1900 <= year <= today.year + 1:
        return None, api_error("VALIDATION_ERROR", "year is out of range", 400)
    return (on, year), None


@members_bp.get("/stats")
@permission_required("members", "read", "View members")
def member_stats():
    args, err = _args()
    if err:
        return err
    on, year = args
    return jsonify(build(on, year, _sees_fees(get_current_member()))), 200


@members_bp.get("/stats.csv")
@permission_required("members", "read", "View members")
def member_stats_csv():
    args, err = _args()
    if err:
        return err
    on, year = args
    data = build(on, year, _sees_fees(get_current_member()))
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Stichtag", data["on"]])
    w.writerow(["Mitglieder", data["total"]])
    w.writerow([])
    w.writerow(["Alter", "Anzahl"])
    for a in data["ages"]:
        w.writerow([a["bracket"], a["count"]])
    w.writerow(["unbekannt", data["ageUnknown"]])
    for title, block in (
        ("Status", data["byStatus"]),
        ("Stufe", data["byTier"]),
        ("Mitgliedschaft", data["byType"]),
    ):
        w.writerow([])
        w.writerow([title, "Anzahl"])
        for key, n in sorted(block.items()):
            w.writerow([csv_safe(key or "-"), n])
    w.writerow([])
    w.writerow(["Monat", "Eintritte", "Austritte"])
    for m in data["months"]:
        w.writerow([m["month"], m["joins"], m["leaves"]])
    if data["fees"]:
        f = data["fees"]
        w.writerow([])
        w.writerow(["Offene Rechnungen", f["open"], f["openAmount"]])
        w.writerow(["Überfällig", f["overdue"], f["overdueAmount"]])
    return Response(
        "﻿" + buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="mitglieder-{data["on"]}.csv"'
        },
    )
