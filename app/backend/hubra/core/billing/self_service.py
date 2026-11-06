"""What a club can change on its own subscription (Settings › Hubra subscription).

* :func:`catalog`: the plans a club can pick (public, not hidden, plus its
  current one) and the paid modules with their prices: those its plan
  includes, those it took as add-ons, and the public add-ons with a price.
* :func:`choose_plan`: switch to another public plan. Refused when the club
  has more members than the plan allows.
* :func:`set_addon`: take a paid module (it is switched on too) or drop it
  (switched off), and set the number of licences of a module priced per
  licence.

The club's terms (``services.club_billing``) change like manage changes
them; a running Stripe subscription takes them from its next invoice
(``service.sync``, no proration, docs/billing.md). A price manage agreed
with the club for an add-on stays when the club changes the licences.
Nothing here commits.
"""

from __future__ import annotations

from hubra.core.errors import ApiError
from hubra.core.models.tenant import Tenant


def _plan_choices(tenant: Tenant) -> list:
    from hubra.core.services import plans

    return [
        p
        for p in plans.all_plans(include_hidden=False)
        if p.public or p.key == tenant.plan
    ]


def catalog(tenant: Tenant) -> dict:
    from hubra.core.services import club_billing, licenses, plans, quotas

    names = plans._module_names()
    held = licenses.holder_rows(tenant)
    current = plans.get(tenant.plan)
    in_plan = (
        {m["code"]: m for m in plans.plan_modules(current, names)} if current else {}
    )
    terms = club_billing.stored(tenant)
    own = {a["code"]: a for a in terms["addons"]}
    addons = []
    for r in plans.addon_rows():
        code = r["code"]
        plan_line = in_plan.get(code)
        offered = r["public"] and r["price_month_chf"] is not None
        if not (offered or code in own or plan_line):
            continue
        if code in own:
            price, unit, source = own[code]["price_chf"], own[code]["unit"], "addon"
        elif plan_line:
            price, unit = plan_line["price_chf"], plan_line["unit"]
            source = "included" if plan_line["included"] else "plan"
        else:
            price, unit, source = r["price_month_chf"], r["price_unit"], None
        addons.append(
            {
                "code": code,
                "name_de": r["label_de"] or r["name"],
                "name_en": r["label_en"] or r["name"],
                "note_de": r["note_de"] or r["description"],
                "note_en": r["note_en"] or r["description"],
                "plugin": r["plugin"],
                "price_month_chf": price,
                "unit": unit,
                # included: comes with the plan at no cost; plan: the plan
                # adds it with its price; addon: the club took it; None:
                # offered, not taken.
                "source": source,
                "licenses": int(terms["licenses"].get(code, 1))
                if unit == "license"
                else None,
                # Members holding a licence (modules priced per licence).
                "holders": held.get(code, []) if unit == "license" else None,
            }
        )
    return {
        "plan": tenant.plan,
        "members": quotas.member_count(tenant),
        "plans": [plans.plan_json(p, names=names) for p in _plan_choices(tenant)],
        "addons": addons,
    }


def choose_plan(tenant: Tenant, key) -> bool:
    """Put the club on plan *key*. Returns False when nothing changed."""
    from hubra.core.services import plans, quotas

    if not isinstance(key, str) or key not in {p.key for p in _plan_choices(tenant)}:
        raise ApiError(400, "VALIDATION_ERROR", "Choose one of the plans offered")
    if key == tenant.plan:
        return False
    limit = plans.limits(key)["members"]
    count = quotas.member_count(tenant)
    if limit is not None and count > limit:
        raise ApiError(
            409,
            "PLAN_TOO_SMALL",
            f"This plan allows {limit} members; the club has {count}",
        )
    tenant.plan = key
    return True


def set_addon(tenant: Tenant, code: str, body: dict) -> None:
    """``{"on": bool, "licenses": int?}`` for one paid module."""
    from hubra.core import modules
    from hubra.core.services import club_billing

    offer = next((a for a in catalog(tenant)["addons"] if a["code"] == code), None)
    if offer is None:
        raise ApiError(404, "NOT_FOUND", "This module is not offered as an add-on")
    on = body.get("on")
    if on is not None and not isinstance(on, bool):
        raise ApiError(400, "VALIDATION_ERROR", "on is true or false")
    terms = club_billing.stored(tenant)
    change: dict = {}
    if "licenses" in body:
        n = body["licenses"]
        if offer["unit"] != "license":
            raise ApiError(
                400, "VALIDATION_ERROR", "This module is not priced per licence"
            )
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 10_000:
            raise ApiError(
                400,
                "VALIDATION_ERROR",
                "licenses is a whole number from 1 to 10000",
                {"licenses": "1 to 10000"},
            )
        change["licenses"] = {**terms["licenses"], code: n}
    if on is not None and offer["source"] in ("included", "plan"):
        raise ApiError(409, "IN_PLAN", "This module comes with the club's plan")
    if on is True and offer["source"] is None:
        state = modules.states().get(code)
        if state is not None and not state.allowed:
            raise ApiError(
                403, "MODULE_BLOCKED", "This module is not available for the club"
            )
        change["addons"] = terms["addons"] + [
            {
                "code": code,
                "label": offer["name_de"],
                "price_chf": offer["price_month_chf"],
                "unit": offer["unit"],
            }
        ]
    elif on is False and offer["source"] == "addon":
        change["addons"] = [a for a in terms["addons"] if a["code"] != code]
    if change:
        club_billing.update(tenant, change)
    if on is not None and modules.registry.get(code) is not None:
        modules.set_enabled(code, on)
