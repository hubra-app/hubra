"""Plans and paid add-ons with their list prices (manage › Einstellungen ›
Tarife), and the public pricing the website reads.

* A **plan** (``PlatformPlan``) is what ``tenants.plan`` names: name and
  description in German and English, price per month and per year (empty:
  on request), a feature list, the limits ``services.quotas`` enforces, its
  place in the list, and whether it is **public**.  Only public plans that
  are not hidden appear in ``GET /api/v1/public/pricing``; any plan that
  is not hidden can be given to a club, so a plan for one club's deal stays
  private.  A plan clubs are on cannot be deleted, only hidden.
* A plan can **include modules**: each one either comes at no extra cost,
  or with its own price in that plan.
* An **add-on** (``PlatformAddon``) is a module, built in or from a plugin,
  with a default monthly price on top of the plan.  On a club, manage can
  set its own price for each add-on (``services.club_billing``).
* Every module price has a **unit**: ``flat`` (once per club), ``member``
  (each member that is not archived) or ``license`` (each licence the club
  takes, counted on the club).

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
UNITS = ("flat", "member", "license")
MAX_PLAN_MODULES = 50


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


def unit(value, field: str = "unit") -> str:
    """flat, member or license (empty: flat)."""
    if value is None or value == "":
        return "flat"
    if value not in UNITS:
        _bad(f"{field} is one of {', '.join(UNITS)}")
    return value


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


def _plan_modules(value, current: list | None) -> list[dict]:
    """[{code, price_chf, unit}]; a code must be a module that can be an
    add-on (one already on the plan may stay after its plugin is gone)."""
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_PLAN_MODULES:
        _bad(f"modules is a list of up to {MAX_PLAN_MODULES}")
    known = {m.code for m in _modules()} | {
        m.get("code") for m in current or [] if isinstance(m, dict)
    }
    out, seen = [], set()
    for item in value:
        if isinstance(item, str):
            item = {"code": item}
        if not isinstance(item, dict):
            _bad("Each module is {code, price_chf, unit}")
        code = item.get("code")
        if not isinstance(code, str) or code not in known:
            _bad(f"No such module: {code}")
        if code in seen:
            _bad(f"Module {code} is there twice")
        seen.add(code)
        unknown = set(item) - {"code", "price_chf", "unit"}
        if unknown:
            _bad(f"Unknown field: {', '.join(sorted(unknown))}")
        price = _money(item.get("price_chf"), f"price of {code}")
        out.append(
            {
                "code": code,
                "price_chf": _chf(price),
                "unit": unit(item.get("unit"), f"unit of {code}"),
            }
        )
    return out


_PLAN_FIELDS = {
    "name_de",
    "name_en",
    "description_de",
    "description_en",
    "price_month_chf",
    "price_year_chf",
    "features",
    "modules",
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
        elif key == "modules":
            plan.modules = _plan_modules(value, plan.modules)
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


def _module_names() -> dict[str, dict]:
    """code -> {name_de, name_en, plugin}: the add-on label if set, else the
    module's own name."""
    rows = {a.code: a for a in db.session.scalars(select(PlatformAddon)).all()}
    out = {}
    for m in _modules():
        a = rows.get(m.code)
        out[m.code] = {
            "name_de": (a.label_de if a else "") or m.name,
            "name_en": (a.label_en if a else "") or m.name,
            "plugin": m.plugin,
        }
    return out


def plan_modules(plan: PlatformPlan, names: dict | None = None) -> list[dict]:
    """The modules a plan includes, with names; ``included`` when they come
    at no extra cost."""
    names = _module_names() if names is None else names
    out = []
    for m in plan.modules or []:
        n = names.get(m["code"]) or {
            "name_de": m["code"],
            "name_en": m["code"],
            "plugin": None,
        }
        out.append(
            {
                "code": m["code"],
                **n,
                "price_chf": m.get("price_chf"),
                "unit": m.get("unit") or "flat",
                "included": m.get("price_chf") is None,
            }
        )
    return out


def plan_json(
    plan: PlatformPlan, with_usage: bool = False, names: dict | None = None
) -> dict:
    out = {
        "key": plan.key,
        "name_de": plan.name_de,
        "name_en": plan.name_en or plan.name_de,
        "description_de": plan.description_de,
        "description_en": plan.description_en,
        "price_month_chf": _chf(plan.price_month_chf),
        "price_year_chf": _chf(plan.price_year_chf),
        "features": plan.features or [],
        "modules": plan_modules(plan, names),
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


def _included_in(public_only: bool = False) -> dict[str, list[str]]:
    """code -> keys of the (not hidden) plans that include the module."""
    out: dict[str, list[str]] = {}
    for p in all_plans(include_hidden=False):
        if public_only and not p.public:
            continue
        for m in p.modules or []:
            out.setdefault(m["code"], []).append(p.key)
    return out


def addon_rows() -> list[dict]:
    """Every module that can be an add-on, with its list price (if set) and
    the plans that include it."""
    rows = {a.code: a for a in db.session.scalars(select(PlatformAddon)).all()}
    included = _included_in()
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
                "price_unit": (a.price_unit if a else None) or "flat",
                "public": bool(a and a.public),
                "label_de": a.label_de if a else "",
                "label_en": a.label_en if a else "",
                "note_de": a.note_de if a else "",
                "note_en": a.note_en if a else "",
                "included_in": included.get(m.code, []),
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
        "price_unit",
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
        elif key == "price_unit":
            row.price_unit = unit(value, key)
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
    if not row.price_unit:
        row.price_unit = "flat"
    db.session.add(row)
    db.session.flush()


def addon_price(code: str) -> str | None:
    row = db.session.get(PlatformAddon, code)
    return _chf(row.price_month_chf) if row else None


def addon_unit(code: str) -> str:
    row = db.session.get(PlatformAddon, code)
    return (row.price_unit if row else None) or "flat"


# ── Public ───────────────────────────────────────────────────────────────────


def public_pricing() -> dict:
    """What the website shows: public plans (with the modules they include)
    and public add-ons (with the public plans that include them)."""
    names = _module_names()
    plans = [
        plan_json(p, names=names) for p in all_plans(include_hidden=False) if p.public
    ]
    included = _included_in(public_only=True)
    addons = [
        {
            "code": a["code"],
            "name_de": a["label_de"] or a["name"],
            "name_en": a["label_en"] or a["name"],
            "note_de": a["note_de"] or a["description"],
            "note_en": a["note_en"] or a["description"],
            "plugin": a["plugin"],
            "price_month_chf": a["price_month_chf"],
            "price_unit": a["price_unit"],
            "included_in": included.get(a["code"], []),
        }
        for a in addon_rows()
        if a["public"]
    ]
    return {"currency": "CHF", "plans": plans, "addons": addons}


def public_plugins() -> list[dict]:
    """The plugins clubs on this platform can switch on, with the add-on
    price of each of their modules."""
    from hubra.core.plugins import installer

    public = {a["code"]: a for a in addon_rows() if a["public"]}
    included = _included_in(public_only=True)

    def module(m) -> dict:
        code = m.get("code") if isinstance(m, dict) else m
        a = public.get(code)
        return {
            "code": code,
            "price_month_chf": a["price_month_chf"] if a else None,
            "price_unit": a["price_unit"] if a else None,
            "included_in": included.get(code, []),
        }

    out = []
    for p in installer.marketplace(fetch=False)["plugins"]:
        if not p.get("installed") or not p.get("loaded", True):
            continue
        modules = [module(m) for m in p.get("modules") or []]
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
    """GET /api/v1/public/pricing, /public/plugins and /public/roadmap: no
    sign-in, any origin may read them (no cookies), cached for five minutes."""
    from flask import jsonify

    def _public(resp):
        resp.headers["Cache-Control"] = "public, max-age=300"
        resp.headers["Vary"] = "Accept-Language"
        return resp

    # Both may add the default plans on a new database (ensure_defaults):
    # commit, or the request leaves its transaction open with the rows.
    @app.get("/api/v1/global/public/pricing")
    def public_pricing_view():
        body = public_pricing()
        db.session.commit()
        return _public(jsonify(body))

    @app.get("/api/v1/global/public/plugins")
    def public_plugins_view():
        body = {"plugins": public_plugins()}
        db.session.commit()
        return _public(jsonify(body))

    # The one roadmap for the website (hubra.club/roadmap/): the same list as
    # /global/roadmap, readable from any site. Votes happen on SSO /roadmap.
    @app.get("/api/v1/global/public/roadmap")
    def public_roadmap_view():
        from hubra.api.support import services as support

        return _public(jsonify(support.roadmap()))
