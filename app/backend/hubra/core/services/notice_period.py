"""Notice periods from the statutes: "leave at the end of the year, with
three months' notice". Club settings ``leave_notice_months`` (0: none) and
``leave_at`` (``any``, ``month_end``, ``quarter_end``, ``half_year_end``,
``year_end``)."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from hubra.core.extensions import db

LEAVE_AT = ("any", "month_end", "quarter_end", "half_year_end", "year_end")

# The months a period ends in.
_PERIOD_END_MONTHS = {
    "month_end": tuple(range(1, 13)),
    "quarter_end": (3, 6, 9, 12),
    "half_year_end": (6, 12),
    "year_end": (12,),
}


def _add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def earliest_exit(asked_on: date, months: int, at: str) -> date:
    """The first day the membership can end when asked on *asked_on*:
    *months* of notice, then the next period end of *at* (or that day for
    ``any``)."""
    first = _add_months(asked_on, max(months, 0))
    if at not in _PERIOD_END_MONTHS:
        return first
    ends = _PERIOD_END_MONTHS[at]
    year, month = first.year, first.month
    while True:
        if month in ends:
            end = date(year, month, calendar.monthrange(year, month)[1])
            if end >= first:
                return end
        month += 1
        if month > 12:
            month, year = 1, year + 1


def club_notice(tenant) -> dict:
    """The club's rule: ``{"months": int, "at": str}``."""
    from hubra.core.tenant.club_settings import club_setting

    months = club_setting(tenant, "leave_notice_months", 0) or 0
    at = club_setting(tenant, "leave_at", "any") or "any"
    return {"months": int(months), "at": at if at in LEAVE_AT else "any"}


def leave_terms(member_id: int, asked_on: date, tenant) -> dict:
    """What leaving means for a member asking on *asked_on*: the club's
    notice rule, the earliest exit date (None without a rule) and the
    member's invoices still open."""
    from hubra.core.models.finance import Invoice

    notice = club_notice(tenant)
    has_rule = notice["months"] > 0 or notice["at"] != "any"
    rows = db.session.scalars(
        select(Invoice)
        .where(Invoice.member_id == member_id)
        .where(Invoice.status.in_(("Open", "Overdue")))
        .order_by(Invoice.due, Invoice.id)
    ).all()
    today = date.today()
    return {
        "notice": notice,
        "earliestExit": earliest_exit(
            asked_on, notice["months"], notice["at"]
        ).isoformat()
        if has_rule
        else None,
        "openInvoices": [
            {
                "id": inv.id,
                "due": inv.due.isoformat(),
                "amount": str(Decimal(inv.amount).quantize(Decimal("0.01"))),
                "overdue": inv.due < today,
                "description": inv.description,
            }
            for inv in rows
        ],
    }
