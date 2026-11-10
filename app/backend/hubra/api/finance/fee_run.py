"""Fee run preview (Finanzen › Rechnungen): what the daily invoice run
would bill on a given day, before it does (roadmap idea 28).

Built on ``finance_tasks.plan_fee_run``, the same planning the run uses,
so nothing here can drift from what is actually billed.  Writes nothing.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from hubra.core.extensions import db

# Lines returned in full; the totals always count every member.
MAX_LINES = 500


def _money(value) -> float:
    return float(Decimal(value).quantize(Decimal("0.01")))


def preview(on: date) -> dict:
    from hubra.api.finance.services import billing_settings
    from hubra.core.models.finance import Invoice
    from hubra.core.tasks.finance_tasks import plan_fee_run

    planned, skipped = plan_fee_run(on)
    billing = billing_settings()

    tiers: dict[int, dict] = {}
    for line in planned:
        tier = line["tier"]
        row = tiers.setdefault(
            tier.id,
            {"tierId": tier.id, "tier": tier.name, "count": 0, "total": Decimal(0)},
        )
        row["count"] += 1
        row["total"] += Decimal(line["amount"])

    reasons: dict[str, int] = defaultdict(int)
    for row in skipped:
        reasons[row["reason"]] += 1

    lines = []
    for line in planned[:MAX_LINES]:
        member = line["member"]
        tier = line["tier"]
        lines.append(
            {
                "memberId": member.id,
                "name": member.name,
                "tier": tier.name,
                "amount": _money(line["amount"]),
                "periodStart": line["period_start"].isoformat(),
                "periodEnd": line["period_end"].isoformat(),
                "prorated": line["prorated"],
                # A payment plan bills more often than the tier does.
                "ownCycle": line["cycle"]
                if line["cycle"] != tier.billing_cycle
                else None,
                "noEmail": not (member.email or "").strip(),
            }
        )

    # The same kind of invoices over the twelve months before, for comparison.
    year_ago = on - timedelta(days=365)
    last_count, last_total = db.session.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.amount), 0))
        .where(Invoice.purpose == "membership")
        .where(Invoice.issued > year_ago, Invoice.issued <= on)
    ).one()

    total = sum((Decimal(line["amount"]) for line in planned), Decimal(0))
    return {
        "on": on.isoformat(),
        "count": len(planned),
        "total": _money(total),
        "dueOn": (on + timedelta(days=billing["payment_term_days"])).isoformat(),
        "mailed": billing["email_new_invoices"],
        "tiers": [
            {**row, "total": _money(row["total"])}
            for row in sorted(tiers.values(), key=lambda r: str(r["tier"]).lower())
        ],
        "lines": lines,
        "truncated": len(planned) > MAX_LINES,
        "noEmail": sum(
            1 for line in planned if not (line["member"].email or "").strip()
        ),
        "ownCycle": sum(
            1 for line in planned if line["cycle"] != line["tier"].billing_cycle
        ),
        "prorated": sum(1 for line in planned if line["prorated"]),
        "skipped": dict(reasons),
        "lastTwelveMonths": {"count": int(last_count), "total": _money(last_total)},
    }
