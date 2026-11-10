"""Dashboard widgets of Finance (docs/dashboards.md).

finance.invoices.ageing    list  open invoices by how long they are overdue
finance.invoices.expected  stat  what open invoices bring in this month

They read as the viewing member, who needs ``finance.invoices.read``. The
Kassen-Cockpit dashboard template puts them next to the books' and the
Kasse's widgets.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from hubra.core.extensions import db
from hubra.core.models.finance import Invoice

PATH = "/app/finance/invoices"
# (from, to) days overdue; None: open ended.
BUCKETS = ((None, 0), (1, 30), (31, 60), (61, 90), (91, None))
_LABELS = {
    "de": (
        "Noch nicht fällig",
        "1–30 Tage überfällig",
        "31–60 Tage überfällig",
        "61–90 Tage überfällig",
        "Über 90 Tage überfällig",
    ),
    "en": (
        "Not due yet",
        "1–30 days overdue",
        "31–60 days overdue",
        "61–90 days overdue",
        "Over 90 days overdue",
    ),
}


def _chf(amount) -> str:
    return f"CHF {Decimal(amount or 0):,.2f}".replace(",", "'")


def _lang(member) -> str:
    return (
        "de"
        if (getattr(member, "language", None) or "de").lower().startswith("de")
        else "en"
    )


def _open():
    return Invoice.status != "Paid"


def ageing(ctx, config: dict) -> dict:
    """One row per age bucket that has open invoices: count and amount."""
    today = date.today()
    lang = _lang(ctx.actor)
    rows = []
    total = 0
    for i, (low, high) in enumerate(BUCKETS):
        query = select(func.count(), func.coalesce(func.sum(Invoice.amount), 0)).where(
            _open()
        )
        if low is None:
            query = query.where(Invoice.due >= today)
        else:
            query = query.where(
                Invoice.due <= date.fromordinal(today.toordinal() - low)
            )
            if high is not None:
                query = query.where(
                    Invoice.due >= date.fromordinal(today.toordinal() - high)
                )
        count, amount = db.session.execute(query).one()
        total += count
        if count:
            word = (
                ("Rechnung", "Rechnungen") if lang == "de" else ("invoice", "invoices")
            )
            rows.append(
                {
                    "label": _LABELS[lang][i],
                    "sub": f"{count} {word[count != 1]} · {_chf(amount)}",
                    "path": PATH,
                }
            )
    return {"items": rows, "total": len(rows) if total else 0}


def expected(ctx, config: dict) -> dict:
    """Open invoices due by the end of this month (overdue ones included)."""
    today = date.today()
    end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    count, amount = db.session.execute(
        select(func.count(), func.coalesce(func.sum(Invoice.amount), 0))
        .where(_open())
        .where(Invoice.due <= end)
    ).one()
    word = (
        ("offene Rechnungen", "offene Rechnung")
        if _lang(ctx.actor) == "de"
        else (
            "open invoices",
            "open invoice",
        )
    )
    return {"value": _chf(amount), "sub": f"{count} {word[count == 1]}", "path": PATH}
