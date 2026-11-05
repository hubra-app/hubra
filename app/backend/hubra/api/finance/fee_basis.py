"""The club's yearly expenses that percentage and formula tiers divide among
members, and how that sum comes together.

The club picks a source in Finanzen › Beitragsgrundlage:

- ``recurring``: the active recurring expenses marked as counting for fees,
  each times its payments per year (from the Finances plugin);
- ``last_year``: the confirmed expenses of the last full billing year (from
  the Finances plugin);
- ``budget``: the expense lines of this year's approved budget, from a
  plugin that registers the source (the budgets plugin);
- ``manual``: one typed-in number (the old ``Club.Finance.YearlyExpenses``).

``recurring`` and ``last_year`` add an optional extra amount for costs that
are neither (repairs, events).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from hubra.core.extensions import db

logger = logging.getLogger(__name__)

SOURCES = ("manual", "recurring", "last_year", "budget")
LEGACY_SETTING = "Club.Finance.YearlyExpenses"

# A total being previewed, before the club saves its choice.
_preview_total: ContextVar[Decimal | None] = ContextVar(
    "fee_basis_preview", default=None
)

# code -> (module code that must be on, function(year) -> lines or None)
_PLUGIN_SOURCES: dict[str, tuple[str, Callable[[int], list[dict] | None]]] = {}

# Sources that work out their own period: code -> (module code that must be
# on, function(today) -> (lines, period)). The Finances plugin registers
# ``recurring`` and ``last_year`` here.
BasisSource = Callable[[date], tuple[list[dict], dict | None]]
_BASIS_SOURCES: dict[str, tuple[str, BasisSource]] = {}


def register_basis_source(code: str, module: str, fn: BasisSource):
    """Provide a source whose *fn(today)* returns (lines, period), period
    being shown as is ({"from", "to"} or {"year"}) or None."""
    _BASIS_SOURCES[code] = (module, fn)


def register_source(code: str, module: str, lines: Callable[[int], list[dict] | None]):
    """Let a plugin provide a source: *lines(year)* returns the year's lines
    ({category_id, name, color, amount, items}) or None when it has none."""
    _PLUGIN_SOURCES[code] = (module, lines)


def _decimal(value, default: Decimal = Decimal(0)) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default
    return number if number.is_finite() and number >= 0 else default


def legacy_value() -> Decimal:
    from hubra.core.models.setting import Setting

    row = db.session.get(Setting, LEGACY_SETTING)
    return _decimal(row.value if row is not None else None)


def basis_settings(overrides: dict | None = None) -> dict:
    """The club's choice, with *overrides* (a preview before saving)."""
    from hubra.core.modules import get_config

    config = {**get_config("finance"), **(overrides or {})}
    source = config.get("fee_basis_source") or "manual"
    if source not in SOURCES and source not in _BASIS_SOURCES:
        source = "manual"
    manual = config.get("fee_basis_manual")
    return {
        "source": source,
        "extra": _decimal(config.get("fee_basis_extra")),
        "manual": legacy_value() if manual in (None, "") else _decimal(manual),
    }


def _billing_year(today: date) -> tuple[date, date]:
    from hubra.api.finance.services import billing_settings
    from hubra.core.pricing import billing_period

    billing = billing_settings()
    return billing_period(
        today, "yearly", billing["fee_anchor_month"], billing["fee_anchor_day"]
    )


def _lines_by_category(rows) -> list[dict]:
    """(category, item, amount) rows as one line per category, largest first."""
    lines: dict[int | None, dict] = {}
    for category, item, amount in rows:
        key = category.id if category is not None else None
        line = lines.setdefault(
            key,
            {
                "category_id": key,
                "name": category.name if category is not None else None,
                "color": category.color if category is not None else None,
                "amount": Decimal(0),
                "items": [],
            },
        )
        line["amount"] += amount
        if item is not None:
            line["items"].append(item)
    return sorted(lines.values(), key=lambda line: -line["amount"])


def available_sources() -> list[str]:
    """``manual``, and the registered sources whose module is on."""
    from hubra.core.modules import is_enabled

    sources = ["manual"]
    for registry in (_BASIS_SOURCES, _PLUGIN_SOURCES):
        for code, (module, _fn) in registry.items():
            if code not in sources and is_enabled(module):
                sources.append(code)
    return sources


def fee_basis(overrides: dict | None = None, today: date | None = None) -> dict:
    """The yearly sum, where it comes from, and its lines per category."""
    today = today or date.today()
    settings = basis_settings(overrides)
    source = settings["source"]
    lines: list[dict] = []
    period = None
    note = None
    if source in _BASIS_SOURCES:
        if source in available_sources():
            found, period = _BASIS_SOURCES[source][1](today)
            lines = [{**line, "amount": _decimal(line.get("amount"))} for line in found]
        else:
            note = f"NO_{source.upper()}"
    elif source == "budget":
        year = _billing_year(today)[0].year
        provider = _PLUGIN_SOURCES.get("budget")
        found = (
            provider[1](year) if provider and source in available_sources() else None
        )
        if found is None:
            note = "NO_BUDGET"
        else:
            lines = [{**line, "amount": _decimal(line.get("amount"))} for line in found]
        period = {"year": year}

    if source == "manual":
        total = settings["manual"]
        extra = Decimal(0)
    else:
        extra = settings["extra"]
        total = sum((line["amount"] for line in lines), Decimal(0)) + extra
    return {
        "source": source,
        "sources": available_sources(),
        "total": float(total),
        "extra": float(extra),
        "manual": float(settings["manual"]),
        "period": period,
        "note": note,
        "lines": [
            {
                **line,
                "amount": float(line["amount"]),
                "share": float(line["amount"] / total) if total else 0.0,
            }
            for line in lines
        ],
    }


def yearly_expenses() -> Decimal:
    """The sum the percentage and formula tiers are priced from."""
    preview = _preview_total.get()
    if preview is not None:
        return preview
    try:
        return Decimal(str(fee_basis()["total"]))
    except Exception as exc:  # pricing must not fail on a broken source
        logger.warning("fee_basis_failed error=%s", exc)
        return legacy_value()


@contextmanager
def previewing(total: Decimal):
    """Price tiers from *total* instead of the saved basis."""
    token = _preview_total.set(total)
    try:
        yield
    finally:
        _preview_total.reset(token)


def tier_effects(total: Decimal) -> list[dict]:
    """What each percentage and formula tier costs a member per year, now
    and with *total*."""
    from hubra.core.models.member import MembershipTier
    from hubra.core.pricing import calculate_preview_cost

    tiers = db.session.scalars(
        select(MembershipTier)
        .where(MembershipTier.price_type.in_(("percentage", "formula")))
        .order_by(MembershipTier.name)
    ).all()

    def cost(tier) -> dict:
        return calculate_preview_cost(
            {
                "tier_id": tier.id,
                "price_type": tier.price_type,
                "billing_cycle": tier.billing_cycle,
                "percentage_value": tier.percentage_value,
                "coefficient": tier.coefficient,
                "round_to": tier.round_to,
                "deduct_tier_ids": tier.deduct_tier_ids or [],
            },
            db_session=db.session,
        )

    effects = []
    for tier in tiers:
        now = cost(tier)
        with previewing(total):
            new = cost(tier)
        effects.append(
            {
                "id": tier.id,
                "name": tier.name,
                "price_type": tier.price_type,
                "billing_cycle": tier.billing_cycle,
                "members": new["members"],
                "yearly_now": now["amount_yearly"],
                "yearly": new["amount_yearly"],
            }
        )
    return effects
