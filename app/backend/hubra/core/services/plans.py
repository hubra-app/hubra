"""Plans and paid add-ons with their list prices (manage › Einstellungen ›
Tarife), and the public pricing the website reads.

* A **plan** (``PlatformPlan``) is what ``tenants.plan`` names: name and
  description in German and English, price per month and per year (empty:
  on request), a feature list, the limits ``services.quotas`` enforces, its
  place in the list, and whether it is **public**.  Only public plans that
  are not hidden appear in ``GET /api/v1/public/pricing``; any plan that
  is not hidden can be given to a club, so a plan for one club's deal stays
  private.  A plan clubs are on cannot be deleted, only hidden.
* An **add-on** (``PlatformAddon``) is a module, built in or from a plugin,
  with a default monthly price on top of the plan.  On a club, manage can
  set its own price for each add-on (``services.club_billing``).

The club's own price, discount and sponsor stay on the club.  Nothing here
charges anyone; Stripe comes later.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import func, select

from hubra.core.errors import ApiError
from hubra.core.extensions import db
from hubra.core.models.platform_plan import PlatformAddon, PlatformPlan
from hubra.core.models.tenant import Tenant

KEY_RE = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
MAX_PRICE = Decimal("100000")
MAX_FEATURES = 30
MAX_PLANS = 30
DEFAULTS = (("starter", "Starter"), ("growth", "Growth"), ("enterprise", "Enterprise"))
LIMIT_KINDS = ("members", "mail_month", "storage_mb")


def _bad(msg: str, status: int = 400, code: str = "VALIDATION_ERROR"):
    raise ApiError(status, code, msg)


def _money(value, field: str) -> Decimal | None:
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
    return d.quantize(Decimal("0.01"), ROUND_HALF_UP)


def _text(value, field: str, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > limit:
        _bad(f"{field} is text up to {limit} characters")
    return value.strip()


def _count(value, field: str) -> int | None:
    if value is None or value == "":
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10**9:
        _bad(f"{field} is a whole number, or empty for no limit")
    return value


def _chf(d: Decimal | None) -> str | None:
    return None if d is None else str(Decimal(d).quantize(Decimal("0.01")))


# ── Plans ────────────────────────────────────────────────────────────────────


def ensure_defaults() -> None:
    """The three plans Hubra always had, when there are no plans at all
    (a new database; the migration carries existing values over)."""
    if db.session.scalar(select(func.count()).select_from(PlatformPlan)):
        return
    for sort, (key, name) in enumerate(DEFAULTS, start=1):
        db.session.add(
            PlatformPlan(key=key, name_de=name, name_en=name, sort=sort, features=[])
        )
    db.session.flush()


def all_plans(include_hidden: bool = True) -> list[PlatformPlan]:
    ensure_defaults()
    q = select(PlatformPlan).order_by(PlatformPlan.sort, PlatformPlan.key)
    if not include_hidden:
        q = q.where(PlatformPlan.archived_at.is_(None))
    return list(db.session.scalars(q).all())


def get(key: str | None) -> PlatformPlan | None:
    if not key:
        return None
    ensure_defaults()
    return db.session.get(PlatformPlan, key)


def assignable(key) -> bool:
    """A plan a club can be put on: exists and is not hidden."""
    plan = get(key) if isinstance(key, str) else None
    return plan is not None and plan.archived_at is None


def keys() -> list[str]:
    return [p.key for p in all_plans(include_hidden=False)]


def limits(key: str | None) -> dict[str, int | None]:
    plan = get(key)
    if plan is None:
        return {k: None for k in LIMIT_KINDS}
    return {k: getattr(plan, f"limit_{k}") for k in LIMIT_KINDS}


def month_price(key: str | None) -> str | None:
    plan = get(key)
    return _chf(plan.price_month_chf) if plan else None


def clubs_on(key: str) -> int:
    return (
        db.session.scalar(
            select(func.count())
            .select_from(Tenant)
            .where(Tenant.plan == key, Tenant.deleted_at.is_(None))
        )
        or 0
    )


def _features(value) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_FEATURES:
        _bad(f"features is a list of up to {MAX_FEATURES}")
    out = []
    for item in value:
        if not isinstance(item, dict):
            _bad("Each feature is {de, en}")
        de = _text(item.get("de"), "feature (de)", 200)
        en = _text(item.get("en"), "feature (en)", 200)
        if de or en:
            out.append({"de": de, "en": en})
    return out


_PLAN_FIELDS = {
    "name_de",
    "name_en",
    "description_de",
    "description_en",
    "price_month_chf",
    "price_year_chf",
    "features",
    "limit_members",
    "limit_mail_month",
    "limit_storage_mb",
    "public",
    "highlighted",
    "sort",
    "hidden",
}


def _apply(plan: PlatformPlan, body: dict) -> None:
    unknown = set(body) - _PLAN_FIELDS
    if unknown:
        _bad(f"Unknown field: {', '.join(sorted(unknown))}")
    for key, value in body.items():
        if key in ("name_de", "name_en"):
            setattr(plan, key, _text(value, key, 80))
        elif key in ("description_de", "description_en"):
            setattr(plan, key, _text(value, key, 1000))
        elif key in ("price_month_chf", "price_year_chf"):
            setattr(plan, key, _money(value, key))
        elif key == "features":
            plan.features = _features(value)
        elif key.startswith("limit_"):
            setattr(plan, key, _count(value, key))
        elif key in ("public", "highlighted"):
            if not isinstance(value, bool):
                _bad(f"{key} is true or false")
            setattr(plan, key, value)
        elif key == "sort":
            if not isinstance(value, int) or isinstance(value, bool):
                _bad("sort is a whole number")
            plan.sort = value
        elif key == "hidden":
            if not isinstance(value, bool):
                _bad("hidden is true or false")
            plan.archived_at = datetime.now(timezone.utc) if value else None
    if not plan.name_de:
        _bad("A plan needs a name")


def create(body: dict) -> PlatformPlan:
    if not isinstance(body, dict):
        _bad("Send an object")
    key = body.get("key")
    if not isinstance(key, str) or not KEY_RE.match(key):
        _bad("key: 2 to 40 lower-case letters, digits or dashes, a letter first")
    if get(key) is not None:
        _bad("There is already a plan with this key", 409, "CONFLICT")
    if len(all_plans()) >= MAX_PLANS:
        _bad(f"At most {MAX_PLANS} plans")
    last = db.session.scalar(select(func.max(PlatformPlan.sort))) or 0
    plan = PlatformPlan(key=key, name_de="", name_en="", sort=last + 1, features=[])
    _apply(plan, {k: v for k, v in body.items() if k != "key"})
    db.session.add(plan)
    db.session.flush()
    return plan


def update(plan: PlatformPlan, body: dict) -> None:
    if not isinstance(body, dict):
        _bad("Send an object")
    _apply(plan, body)


def delete(plan: PlatformPlan) -> None:
    n = clubs_on(plan.key)
    if n:
        _bad(
            f"{n} club(s) are on this plan; hide it instead",
            409,
            "PLAN_IN_USE",
        )
    if len(all_plans(include_hidden=False)) <= 1 and plan.archived_at is None:
        _bad("Keep at least one plan", 409, "LAST_PLAN")
    db.session.delete(plan)


def plan_json(plan: PlatformPlan, with_usage: bool = False) -> dict:
    out = {
        "key": plan.key,
        "name_de": plan.name_de,
        "name_en": plan.name_en or plan.name_de,
        "description_de": plan.description_de,
        "description_en": plan.description_en,
        "price_month_chf": _chf(plan.price_month_chf),
        "price_year_chf": _chf(plan.price_year_chf),
        "features": plan.features or [],
        "limits": {k: getattr(plan, f"limit_{k}") for k in LIMIT_KINDS},
        "highlighted": plan.highlighted,
        "sort": plan.sort,
    }
    if with_usage:
        out.update(
            public=plan.public,
            hidden=plan.archived_at is not None,
            clubs=clubs_on(plan.key),
        )
    return out


# ── Add-ons ──────────────────────────────────────────────────────────────────


def _modules() -> list:
    from hubra.core.modules import registry

    registry.load()
    return [m for m in registry.all() if not m.required]


def addon_rows() -> list[dict]:
    """Every module that can be an add-on, with its list price (if set)."""
    rows = {a.code: a for a in db.session.scalars(select(PlatformAddon)).all()}
    out = []
    for m in _modules():
        a = rows.get(m.code)
        out.append(
            {
                "code": m.code,
                "name": m.name,
                "description": m.description,
                "plugin": m.plugin,
                "price_month_chf": _chf(a.price_month_chf) if a else None,
                "public": bool(a and a.public),
                "label_de": a.label_de if a else "",
                "label_en": a.label_en if a else "",
                "note_de": a.note_de if a else "",
                "note_en": a.note_en if a else "",
            }
        )
    return sorted(out, key=lambda r: (r["plugin"] is not None, r["name"].lower()))


def set_addon(code: str, body: dict) -> None:
    if code not in {m.code for m in _modules()}:
        _bad("No such module", 404, "NOT_FOUND")
    if not isinstance(body, dict):
        _bad("Send an object")
    unknown = set(body) - {
        "price_month_chf",
        "public",
        "label_de",
        "label_en",
        "note_de",
        "note_en",
    }
    if unknown:
        _bad(f"Unknown field: {', '.join(sorted(unknown))}")
    row = db.session.get(PlatformAddon, code) or PlatformAddon(code=code)
    for key, value in body.items():
        if key == "price_month_chf":
            row.price_month_chf = _money(value, key)
        elif key == "public":
            if not isinstance(value, bool):
                _bad("public is true or false")
            row.public = value
        elif key in ("label_de", "label_en"):
            setattr(row, key, _text(value, key, 120))
        else:
            setattr(row, key, _text(value, key, 1000))
    if row.public is None:
        row.public = False
    db.session.add(row)
    db.session.flush()


def addon_price(code: str) -> str | None:
    row = db.session.get(PlatformAddon, code)
    return _chf(row.price_month_chf) if row else None


# ── Public ───────────────────────────────────────────────────────────────────


def public_pricing() -> dict:
    """What the website shows: public plans and public add-ons."""
    plans = [plan_json(p) for p in all_plans(include_hidden=False) if p.public]
    addons = [
        {
            "code": a["code"],
            "name_de": a["label_de"] or a["name"],
            "name_en": a["label_en"] or a["name"],
            "note_de": a["note_de"] or a["description"],
            "note_en": a["note_en"] or a["description"],
            "plugin": a["plugin"],
            "price_month_chf": a["price_month_chf"],
        }
        for a in addon_rows()
        if a["public"]
    ]
    return {"currency": "CHF", "plans": plans, "addons": addons}


def public_plugins() -> list[dict]:
    """The plugins clubs on this platform can switch on, with the add-on
    price of each of their modules."""
    from hubra.core.plugins import installer

    prices = {a["code"]: a["price_month_chf"] for a in addon_rows() if a["public"]}
    out = []
    for p in installer.marketplace(fetch=False)["plugins"]:
        if not p.get("installed") or not p.get("loaded", True):
            continue
        modules = [
            {
                "code": m.get("code") if isinstance(m, dict) else m,
                "price_month_chf": prices.get(
                    m.get("code") if isinstance(m, dict) else m
                ),
            }
            for m in p.get("modules") or []
        ]
        out.append(
            {
                "id": p["id"],
                "name": p.get("name") or p["id"],
                "description": p.get("description") or "",
                "version": p.get("installedVersion") or p.get("version"),
                "author": p.get("author") or "",
                "tags": p.get("tags") or [],
                "official": bool(p.get("official")),
                "modules": modules,
            }
        )
    return sorted(out, key=lambda p: p["name"].lower())


def install(app) -> None:
    """GET /api/v1/public/pricing and /public/plugins: no sign-in, any
    origin may read them (no cookies), cached for five minutes."""
    from flask import jsonify

    def _public(resp):
        resp.headers["Cache-Control"] = "public, max-age=300"
        resp.headers["Vary"] = "Accept-Language"
        return resp

    @app.get("/api/v1/public/pricing")
    def public_pricing_view():
        return _public(jsonify(public_pricing()))

    @app.get("/api/v1/public/plugins")
    def public_plugins_view():
        return _public(jsonify({"plugins": public_plugins()}))
