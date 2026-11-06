"""Licences of modules priced per licence, assigned to members.

A module priced per licence (``unit: license`` on the club's add-on, or on
a module its plan adds at a price) is billed for ``licenses[code]``
licences (``services.club_billing``). The club gives each licence to a
member; only those members may use the module: the module gate refuses
everyone else with ``403 LICENSE_REQUIRED`` and their navigation hides it.

* Holders live on the club: ``tenants.settings["license_holders"]``,
  ``{code: [member id, ...]}`` in the order they were given.
* At most as many holders as licences. When the count drops below the
  holders (manage lowers it), the first ones keep theirs, the rest wait
  until a licence is free again.
* A module the plan includes at no cost, or priced flat or per member,
  needs no licence.
"""

from __future__ import annotations

from flask import g, has_request_context
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from hubra.core.errors import ApiError
from hubra.core.models.tenant import Tenant

KEY = "license_holders"


def licensed_modules(tenant: Tenant) -> dict[str, int]:
    """``{module code: licences bought}`` for the modules that need one."""
    cache = getattr(g, "_licensed_modules", None) if has_request_context() else None
    if cache is not None and cache[0] == tenant.id:
        return cache[1]
    from hubra.core.services import club_billing, plans

    terms = club_billing.stored(tenant)
    own = {a["code"]: a for a in terms["addons"]}
    out: dict[str, int] = {}
    plan = plans.get(tenant.plan)
    for m in (plan.modules or []) if plan else []:
        code = m.get("code")
        if code in own or m.get("price_chf") is None:
            continue
        if (m.get("unit") or "flat") == "license":
            out[code] = int(terms["licenses"].get(code, 1))
    for code, a in own.items():
        if a.get("unit") == "license":
            out[code] = int(terms["licenses"].get(code, 1))
    if has_request_context():
        g._licensed_modules = (tenant.id, out)
    return out


def holders(tenant: Tenant) -> dict[str, list[int]]:
    raw = (tenant.settings or {}).get(KEY) or {}
    return {
        str(code): [int(i) for i in ids if isinstance(i, int)]
        for code, ids in raw.items()
        if isinstance(ids, list)
    }


def may_use(tenant: Tenant, code: str, member_id: int | None) -> bool:
    count = licensed_modules(tenant).get(code)
    if count is None:
        return True
    if member_id is None:
        return False
    return member_id in holders(tenant).get(code, [])[:count]


def unlicensed_for(tenant: Tenant, member_id: int | None) -> set[str]:
    """The licensed modules *member_id* holds no licence for."""
    return {c for c in licensed_modules(tenant) if not may_use(tenant, c, member_id)}


def set_holders(tenant: Tenant, code: str, member_ids) -> list[int]:
    """Give the module's licences to exactly these members. Does NOT commit."""
    from hubra.core.extensions import db
    from hubra.core.models.member import Member

    count = licensed_modules(tenant).get(code)
    if count is None:
        raise ApiError(404, "NOT_FOUND", "This module has no licences")
    if not isinstance(member_ids, list) or not all(
        isinstance(i, int) and not isinstance(i, bool) for i in member_ids
    ):
        raise ApiError(400, "VALIDATION_ERROR", "memberIds is a list of member ids")
    ids = list(dict.fromkeys(member_ids))
    if len(ids) > count:
        raise ApiError(
            409,
            "TOO_MANY_HOLDERS",
            f"The club has {count} licences for this module",
        )
    if ids:
        found = set(
            db.session.scalars(
                select(Member.id).where(
                    Member.id.in_(ids), Member.archived_at.is_(None)
                )
            )
        )
        missing = [i for i in ids if i not in found]
        if missing:
            raise ApiError(400, "VALIDATION_ERROR", f"No such member: {missing[0]}")
    settings = dict(tenant.settings or {})
    all_holders = dict(settings.get(KEY) or {})
    all_holders[code] = ids
    settings[KEY] = all_holders
    tenant.settings = settings
    flag_modified(tenant, "settings")
    return ids


def holder_rows(tenant: Tenant) -> dict[str, list[dict]]:
    """``{code: [{id, name}]}`` of the licensed modules, for the club."""
    from hubra.core.extensions import db
    from hubra.core.models.member import Member

    held = holders(tenant)
    codes = licensed_modules(tenant)
    ids = {i for c in codes for i in held.get(c, [])}
    names = {
        m.id: m.name
        for m in (
            db.session.scalars(select(Member).where(Member.id.in_(ids))) if ids else []
        )
    }
    return {
        c: [{"id": i, "name": names.get(i, f"#{i}")} for i in held.get(c, [])]
        for c in codes
    }
