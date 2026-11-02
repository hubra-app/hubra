"""What a club pays the platform: plan status, price, discount, sponsor and
add-ons.  Stored and shown only, nothing is charged yet.

Mike chose Stripe Billing for when Hubra starts charging clubs (one
subscription per club: the plan plus one line per paid plugin or feature).
Until then manage keeps the terms per club here, in
``tenant.settings["billing"]``, so they are ready when billing starts:

* ``status`` uses Stripe's subscription statuses (``trialing``, ``active``,
  ``past_due``, ``unpaid``, ``canceled``, ``incomplete``, ``paused``), plus
  ``none`` for a club that is not billed;
* ``price_chf`` is the club's own monthly price (``None``: the plan's list
  price, ``services.plans``), ``discount_percent``
  comes off it;
* a **sponsored** club (``sponsor_name``, ``sponsored_until``; no end date:
  open-ended) pays nothing while the sponsorship runs;
* ``addons`` are paid plugins or features (module codes) with their own
  monthly price each, on top of the plan (the discount does not apply).

No Stripe code, no payment and no automatic switching here.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy.orm.attributes import flag_modified

from hubra.core.errors import ApiError
from hubra.core.models.tenant import Tenant

STATUSES = (
    "none",
    "trialing",
    "active",
    "past_due",
    "unpaid",
    "canceled",
    "incomplete",
    "paused",
)
MAX_ADDONS = 30
MAX_PRICE = Decimal("100000")
ENDING_SOON_DAYS = 30
_TEXT = {"sponsor_name": 200, "sponsor_note": 500, "note": 1000}
_DATES = ("trial_ends", "period_end", "sponsored_until")

DEFAULTS = {
    "status": "none",
    "trial_ends": None,
    "period_end": None,
    "price_chf": None,
    "discount_percent": 0,
    "sponsored": False,
    "sponsor_name": "",
    "sponsored_until": None,
    "sponsor_note": "",
    "addons": [],
    "note": "",
}


def _bad(msg: str):
    raise ApiError(400, "VALIDATION_ERROR", msg)


def _money(value, field: str) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        _bad(f"{field} is an amount in CHF")
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        _bad(f"{field} is an amount in CHF")
    if not d.is_finite() or d < 0 or d > MAX_PRICE:
        _bad(f"{field} is an amount from 0 to {MAX_PRICE} CHF")
    return str(d.quantize(Decimal("0.01"), ROUND_HALF_UP))


def _date(value, field: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        _bad(f"{field} is a date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        _bad(f"{field} is a date (YYYY-MM-DD)")


def stored(tenant: Tenant) -> dict:
    return {**DEFAULTS, **((tenant.settings or {}).get("billing") or {})}


def update(tenant: Tenant, body: dict) -> None:
    """Merge the fields in *body* into the club's terms.  Does NOT commit."""
    if not isinstance(body, dict):
        _bad("Send an object")
    unknown = set(body) - set(DEFAULTS)
    if unknown:
        _bad(f"Unknown field: {', '.join(sorted(unknown))}")
    terms = stored(tenant)
    for key, value in body.items():
        if key == "status":
            if value not in STATUSES:
                _bad(f"status is one of {', '.join(STATUSES)}")
            terms[key] = value
        elif key in _DATES:
            terms[key] = _date(value, key)
        elif key == "price_chf":
            terms[key] = _money(value, key)
        elif key == "discount_percent":
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not 0 <= value <= 100
            ):
                _bad("discount_percent is 0 to 100")
            terms[key] = round(float(value), 2)
        elif key == "sponsored":
            if not isinstance(value, bool):
                _bad("sponsored is true or false")
            terms[key] = value
        elif key in _TEXT:
            if value is None:
                value = ""
            if not isinstance(value, str) or len(value) > _TEXT[key]:
                _bad(f"{key} is text up to {_TEXT[key]} characters")
            terms[key] = value.strip()
        elif key == "addons":
            terms[key] = _addons(value)
    if terms["sponsored"] and not terms["sponsor_name"]:
        _bad("A sponsored club needs the sponsor's name")
    settings = dict(tenant.settings or {})
    settings["billing"] = terms
    tenant.settings = settings
    flag_modified(tenant, "settings")


def _addons(value) -> list[dict]:
    if not isinstance(value, list) or len(value) > MAX_ADDONS:
        _bad(f"addons is a list of up to {MAX_ADDONS}")
    out, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            _bad("Each add-on is an object with code, label and price_chf")
        code = item.get("code")
        if not isinstance(code, str) or not code.strip() or len(code) > 64:
            _bad("Each add-on needs a code")
        code = code.strip()
        if code in seen:
            _bad(f"Add-on {code} is there twice")
        seen.add(code)
        label = item.get("label") or ""
        if not isinstance(label, str) or len(label) > 120:
            _bad("An add-on label is text up to 120 characters")
        price = _money(item.get("price_chf"), f"price of {code}")
        out.append({"code": code, "label": label.strip(), "price_chf": price or "0.00"})
    return out


def plan_price(plan: str) -> str | None:
    """The plan's list price per month (manage › Einstellungen › Tarife)."""
    from hubra.core.services import plans

    return plans.month_price(plan)


def summary(tenant: Tenant, today: date | None = None) -> dict:
    """The terms with what they add up to per month."""
    today = today or date.today()
    terms = stored(tenant)
    listed = plan_price(tenant.plan)
    base = Decimal(terms["price_chf"] or listed or "0")
    discount = (base * Decimal(str(terms["discount_percent"])) / 100).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    addons = sum((Decimal(a["price_chf"]) for a in terms["addons"]), Decimal("0"))
    total = base - discount + addons
    until = (
        date.fromisoformat(terms["sponsored_until"])
        if terms["sponsored_until"]
        else None
    )
    sponsor_running = bool(terms["sponsored"]) and (until is None or until >= today)
    days_left = (until - today).days if (sponsor_running and until) else None
    trial = date.fromisoformat(terms["trial_ends"]) if terms["trial_ends"] else None
    money = lambda d: str(d.quantize(Decimal("0.01")))  # noqa: E731
    return {
        **terms,
        "plan": tenant.plan,
        "plan_price_chf": listed,
        "base_chf": money(base),
        "discount_chf": money(discount),
        "addons_chf": money(addons),
        "total_chf": money(total),
        "sponsorship_running": sponsor_running,
        "sponsorship_days_left": days_left,
        "sponsorship_ending_soon": days_left is not None
        and days_left <= ENDING_SOON_DAYS,
        "sponsorship_ended": bool(terms["sponsored"]) and not sponsor_running,
        "trial_days_left": (trial - today).days
        if trial and terms["status"] == "trialing"
        else None,
        "due_chf": "0.00"
        if sponsor_running or terms["status"] == "none"
        else money(total),
    }
