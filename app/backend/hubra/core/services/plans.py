"""Plans and paid add-ons with their list prices (manage › Einstellungen ›
Tarife), and the public pricing the website reads.

* A **plan** (``PlatformPlan``) is what ``tenants.plan`` names: name and
  description in German and English, price per month and per year (empty:
  on request), a feature list, the limits ``services.quotas`` enforces
  (members, mails per month, storage, and the largest file a club can
  upload; empty: no limit, for the file: the platform's ``files.max_mb``), its
  place in the list, whether it is **public** (on the website) and whether
  it is **selectable** (every club can pick it itself).  The two are apart
  (hubra#261): only public plans that are not hidden appear in ``GET
  /api/v1/public/pricing``; only selectable ones in a club's plan picker.
  Any plan that is not hidden can be given to a club by manage, so a plan
  for one club's deal stays private.  A plan clubs are on cannot be deleted, only hidden.
* A plan can **include modules**: each one either comes at no extra cost,
  or with its own price in that plan.
* A plan can **build on** another plan (``builds_on``, optional): it then
  includes every module of that plan (and of the plan that one builds on),
  plus its own.  Its own entry for a module wins over the inherited one, so
  a higher plan can include a module the lower one sells.  A plan others
  build on cannot be deleted.
* A **custom plan** is offered to chosen clubs (``club_ids``): they can
  pick it in Settings › Hubra subscription although it is not selectable.
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
LIMIT_KINDS = ("members", "mail_month", "storage_mb", "file_mb")
# The largest file a plan can allow, in MB (the server's upload ceiling,
# MAX_UPLOAD_MB, caps it further).
MAX_FILE_MB = 10240
UNITS = ("flat", "member", "license")
MAX_PLAN_MODULES = 50
MAX_PLAN_CLUBS = 500


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


def file_mb(value, field: str = "file_mb") -> int | None:
    """Largest file in MB, 1 to MAX_FILE_MB; empty: the platform default."""
    if value is None or value == "":
        return None
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= MAX_FILE_MB
    ):
        _bad(f"{field} is a whole number of MB from 1 to {MAX_FILE_MB}, or empty")
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
        return dict.fromkeys(LIMIT_KINDS)
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


def _base_chain(plan: PlatformPlan) -> list[PlatformPlan]:
    """The plans *plan* builds on, nearest first (stops at a loop or a
    missing plan)."""
    out: list[PlatformPlan] = []
    seen = {plan.key}
    key = plan.builds_on
    while key and key not in seen:
        seen.add(key)
        base = db.session.get(PlatformPlan, key)
        if base is None:
            break
        out.append(base)
        key = base.builds_on
    return out


def effective_modules(plan: PlatformPlan) -> list[dict]:
    """Every module the plan comes with: those of the plans it builds on
    (lowest first) and then its own, each ``{code, price_chf, unit,
    from_plan}``; ``from_plan`` is the key of the plan it is inherited from,
    or None for the plan's own.  The nearest plan's entry for a code wins."""
    by_code: dict[str, dict] = {}
    for source in [*reversed(_base_chain(plan)), plan]:
        own = source is plan
        for m in source.modules or []:
            code = m.get("code") if isinstance(m, dict) else None
            if not code:
                continue
            by_code.pop(code, None)
            by_code[code] = {**m, "from_plan": None if own else source.key}
    return list(by_code.values())


def _builds_on(plan: PlatformPlan, value) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        _bad("builds_on is the key of another plan")
    if value == plan.key:
        _bad("A plan cannot build on itself")
    base = db.session.get(PlatformPlan, value)
    if base is None:
        _bad(f"No such plan: {value}")
    if plan.key in {p.key for p in _base_chain(base)}:
        _bad(f"{value} already builds on this plan")
    return value


def _club_ids(value) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_PLAN_CLUBS:
        _bad(f"club_ids is a list of up to {MAX_PLAN_CLUBS} clubs")
    ids: list[int] = []
    for item in value:
        if isinstance(item, str) and item.isdigit():
            item = int(item)
        if not isinstance(item, int) or isinstance(item, bool):
            _bad("club_ids is a list of club ids")
        if item not in ids:
            ids.append(item)
    if not ids:
        return []
    rows = dict(
        db.session.execute(
            select(Tenant.id, Tenant.deleted_at).where(Tenant.id.in_(ids))
        ).all()
    )
    missing = [i for i in ids if i not in rows]
    if missing:
        _bad(f"No such club: {missing[0]}")
    # A club deleted since it was picked drops out quietly.
    return [i for i in ids if rows[i] is None]


def offered_to(plan: PlatformPlan, tenant_id: int) -> bool:
    """A custom plan offered to this club."""
    return tenant_id in (plan.club_ids or [])


_PLAN_FIELDS = {
    "name_de",
    "name_en",
    "description_de",
    "description_en",
    "price_month_chf",
    "price_year_chf",
    "features",
    "modules",
    "builds_on",
    "club_ids",
    "limit_members",
    "limit_mail_month",
    "limit_storage_mb",
    "limit_file_mb",
    "public",
    "selectable",
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
        elif key == "builds_on":
            plan.builds_on = _builds_on(plan, value)
        elif key == "club_ids":
            plan.club_ids = _club_ids(value)
        elif key == "limit_file_mb":
            plan.limit_file_mb = file_mb(value, key)
        elif key.startswith("limit_"):
            setattr(plan, key, _count(value, key))
        elif key in ("public", "selectable", "highlighted"):
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
    above = db.session.scalars(
        select(PlatformPlan.key).where(PlatformPlan.builds_on == plan.key)
    ).all()
    if above:
        _bad(
            f"{', '.join(sorted(above))} build(s) on this plan; change that first",
            409,
            "PLAN_IS_BASE",
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
    """The modules a plan includes (with those of the plans it builds on),
    with names; ``included`` when they come at no extra cost,
    ``inherited_from`` the plan it comes from (None: the plan's own)."""
    names = _module_names() if names is None else names
    out = []
    for m in effective_modules(plan):
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
                "inherited_from": m.get("from_plan"),
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
        "builds_on": plan.builds_on,
        "limits": {k: getattr(plan, f"limit_{k}") for k in LIMIT_KINDS},
        "highlighted": plan.highlighted,
        "sort": plan.sort,
    }
    if with_usage:
        out.update(
            public=plan.public,
            selectable=bool(plan.selectable),
            hidden=plan.archived_at is not None,
            clubs=clubs_on(plan.key),
            club_ids=list(plan.club_ids or []),
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
        for m in effective_modules(p):
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


# ── Public ───────────────────────────────────────────────────────────────────


def public_pricing() -> dict:
    """What the website shows: public plans (with the modules they include)
    and public add-ons (with the public plans that include them)."""
    names = _module_names()
    shown = [p for p in all_plans(include_hidden=False) if p.public]
    public_keys = {p.key for p in shown}
    plans = []
    for p in shown:
        row = plan_json(p, names=names)
        # "Everything in <plan>, plus": only when the website shows that plan.
        if row["builds_on"] not in public_keys:
            row["builds_on"] = None
        plans.append(row)
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
        from hubra.core.services import support

        return _public(jsonify(support.roadmap()))
