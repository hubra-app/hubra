"""Who may use a module: one access key per module, docs/roles.md.

Every module that is not ``required`` and has its own pages (``nav``) gets
the permission ``module.<code>.access``. A person whose roles hold none of it
does not see the module anywhere (sidebar, "Weitere", widgets, search), and
its API answers ``403 MODULE_ACCESS`` (``core/modules/gate.py``).

* Holding any other key of a module implies its access key: a role that
  gets ``inventory.items.read`` also gets ``module.inventory.access``
  (``RoleService.set_permissions``).
* Admin roles use every module.
* Routes that serve the caller's own data (``/mine``, ``/my-…``, or marked
  with :func:`own_data`) stay open without access, so a member keeps seeing
  their own invoices, claims and items on their profile.
* A club only enforces this once ``flask roles standardise`` has given its
  roles the access keys they need to keep what they have
  (setting ``roles.module_access``). Before that, everyone counts as holding
  every access key.

A module's ``role_defaults`` (``{"member": "view", "treasurer": "all"}``)
are given to the standard roles once, when the club first switches the
module on (:func:`apply_role_defaults`).
"""

from __future__ import annotations

import json
import re

from flask import current_app, g
from sqlalchemy import select

from hubra.core.extensions import db

ENFORCED_SETTING = "roles.module_access"
APPLIED_SETTING = "roles.defaults_applied"

LEVELS = ("none", "view", "edit", "all")

# Seeing, and taking part as a member (frontend: screens/private/system/roles/levels.ts).
VIEW_ACTIONS = frozenset(
    {
        "access",
        "read",
        "read_reminders",
        "calculate_cost",
        "register",
        "vote",
        "comment",
        "like",
        "checkin",
        "checkout",
        "instruct_self",
    }
)
# Only in "Alles": they delete, or reach past the area itself.
ALL_ONLY_ACTIONS = frozenset(
    {
        "delete",
        "moderate",
        "manage",
        "export",
        "set_permissions",
        "update.is_admin",
        "update.role_ids",
    }
)

_OWN_PATH = re.compile(r"/(mine|my-[a-z-]+|me)(/|$)")


def access_key(code: str) -> str:
    return f"module.{code}.access"


def is_gated(module) -> bool:
    """A module with pages of its own that a club can switch off."""
    return not module.required and bool(module.nav)


def gated_modules() -> list:
    from hubra.core.modules import registry

    return [m for m in registry.all() if is_gated(m)]


def access_permissions() -> list[dict]:
    """Catalog rows for the access keys (``flask sync-permissions``)."""
    return [
        {
            "key": access_key(m.code),
            "display_name": f"Use {m.name}",
            "resource": m.code,
            "action": "access",
            "blueprint": "module",
        }
        for m in gated_modules()
    ]


def own_data(fn):
    """Mark a route that only serves the caller's own data: it stays open to
    a member without access to its module."""
    fn._own_data = True
    return fn


def is_own_endpoint(endpoint: str | None, path: str | None) -> bool:
    fn = current_app.view_functions.get(endpoint or "")
    if fn is not None and getattr(fn, "_own_data", False):
        return True
    return bool(path and _OWN_PATH.search(path))


def action_level(action: str) -> str:
    if action in VIEW_ACTIONS:
        return "view"
    if action in ALL_ONLY_ACTIONS:
        return "all"
    return "edit"


# ── keys per module ──────────────────────────────────────────────────────


def module_keys() -> dict[str, set[str]]:
    """Module code -> the permission keys that belong to it (its routes,
    its extra and field permissions; not the access key). Built once per
    process from the loaded routes."""
    cache = current_app.extensions.get("hubra_module_keys")
    if cache is not None:
        return cache

    from hubra.core.fields import iter_field_perms
    from hubra.core.modules import registry
    from hubra.core.permissions import _derive_perm_key, extra_permissions

    out: dict[str, set[str]] = {}
    by_area: dict[str, str] = {}  # "<prefix>.<resource>" -> module code
    for rule in current_app.url_map.iter_rules():
        fn = current_app.view_functions.get(rule.endpoint)
        resource = getattr(fn, "_perm_resource", None)
        action = getattr(fn, "_perm_action", None)
        if resource is None or action is None:
            continue
        bp_name = rule.endpoint.rsplit(".", 1)[0] if "." in rule.endpoint else None
        module = registry.module_for_blueprint(bp_name)
        if module is None:
            continue
        key = _derive_perm_key(bp_name, resource, action)
        out.setdefault(module.code, set()).add(key)
        by_area.setdefault(key.rsplit(".", 1)[0], module.code)

    for module in registry.all():
        for key, _name in module.permissions:
            out.setdefault(module.code, set()).add(key)
            by_area.setdefault(".".join(key.split(".")[:2]), module.code)

    others = [m["key"] for m in extra_permissions()] + [m["key"] for m in iter_field_perms()]
    for key in others:
        code = by_area.get(".".join(key.split(".")[:2]))
        if code is not None:
            out.setdefault(code, set()).add(key)

    current_app.extensions["hubra_module_keys"] = out
    return out


def module_of_key(key: str) -> str | None:
    """The module a permission key belongs to, None for core keys no module
    owns (dashboard, notifications, settings)."""
    if key.startswith("module.") and key.endswith(".access"):
        return key[len("module.") : -len(".access")]
    by_key = current_app.extensions.get("hubra_key_modules")
    if by_key is None:
        by_key = {k: code for code, ks in module_keys().items() for k in ks}
        current_app.extensions["hubra_key_modules"] = by_key
    return by_key.get(key)


def implied_access_keys(keys) -> set[str]:
    """The access keys that come with *keys* (any key of a gated module)."""
    from hubra.core.modules import registry

    out = set()
    for key in keys:
        code = module_of_key(key)
        if code is None:
            continue
        module = registry.get(code)
        if module is not None and is_gated(module):
            out.add(access_key(code))
    return out


def level_keys(code: str, level: str) -> set[str]:
    """The keys one level gives in a module, access key included."""
    from hubra.core.modules import registry

    if level not in LEVELS or level == "none":
        return set()
    rank = LEVELS.index(level)
    keys = {
        k
        for k in module_keys().get(code, set())
        if LEVELS.index(action_level(k.split(".", 2)[2] if k.count(".") >= 2 else "")) <= rank
    }
    module = registry.get(code)
    if module is not None and is_gated(module):
        keys.add(access_key(code))
    return keys


# ── the club's state ─────────────────────────────────────────────────────


def _setting(key: str) -> str | None:
    from hubra.core.models.setting import Setting

    row = db.session.get(Setting, key)
    return row.value if row is not None else None


def _write_setting(key: str, value: str) -> None:
    from hubra.core.models.setting import Setting

    row = db.session.get(Setting, key)
    if row is None:
        row = Setting(
            key=key,
            namespace="roles",
            restricted=True,
            description="Managed by Hubra (docs/roles.md)",
        )
        db.session.add(row)
    row.value = value
    db.session.flush()


def enforced() -> bool:
    """Whether this club hides modules from people without access."""
    if "_module_access_enforced" not in g:
        try:
            g._module_access_enforced = _setting(ENFORCED_SETTING) == "on"
        except Exception:  # no settings table (platform backend, early boot)
            g._module_access_enforced = False
    return g._module_access_enforced


def set_enforced(on: bool) -> None:
    _write_setting(ENFORCED_SETTING, "on" if on else "off")
    g.pop("_module_access_enforced", None)


def applied_modules() -> set[str]:
    raw = _setting(APPLIED_SETTING)
    try:
        return set(json.loads(raw)) if raw else set()
    except ValueError:
        return set()


def mark_applied(codes) -> None:
    _write_setting(APPLIED_SETTING, json.dumps(sorted(applied_modules() | set(codes))))


def may_use(member, code: str) -> bool:
    """Whether *member* may use module *code* (its pages and API)."""
    from hubra.core.modules import registry
    from hubra.core.permissions import (
        _get_member_permission_keys,
        member_is_admin,
        scoped_permission_keys,
    )

    module = registry.get(code)
    if module is None or not is_gated(module) or not enforced():
        return True
    if member is None or not hasattr(member, "roles"):
        return True  # not a club member: the route's own check answers
    if member_is_admin(member):
        return True
    key = access_key(code)
    if key in _get_member_permission_keys(member):
        return True
    return any(key in keys for keys in scoped_permission_keys(member).values())


# ── role defaults ────────────────────────────────────────────────────────


def apply_role_defaults(code: str, *, only_roles=None) -> bool:
    """Give the standard roles the levels module *code* names in its
    ``role_defaults``, once per club. Adds keys, never takes any away.

    ``only_roles`` limits it to those Role rows (the ones a first
    ``standardise`` just created). Returns whether anything was given.
    """
    from hubra.core.models.role import Role
    from hubra.core.modules import registry
    from hubra.core.services.roles import RoleService

    module = registry.get(code)
    if module is None or code in applied_modules():
        return False
    changed = False
    for role_key, level in (module.role_defaults or {}).items():
        role = db.session.scalar(select(Role).where(Role.key == role_key))
        if role is None or role.is_admin:
            continue
        if only_roles is not None and role not in only_roles:
            continue
        keys = level_keys(code, level)
        held = set(RoleService.get_permissions(role.id))
        if keys - held:
            RoleService.set_permissions(role, sorted(held | keys), actor_id=None, _internal=True)
            changed = True
    mark_applied([code])
    return changed
