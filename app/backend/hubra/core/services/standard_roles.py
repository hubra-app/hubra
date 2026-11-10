"""The standard roles and functions every club has (docs/roles.md).

Roles (``Role.key``): owner, admin, member, board (Vorstand), secretary
(Aktuar/in), treasurer (Kassier/in). Functions (``Function.key``): president
and vice_president give Admin and Vorstand, secretary gives Vorstand and
Aktuar/in, treasurer gives Vorstand and Kassier/in.

:func:`standardise` adds what a club is missing and never renames, removes
or narrows anything the club has. New clubs get it from ``_seed_tenant``;
existing clubs from ``flask roles standardise`` (part of ``flask seed``).
The first run in an existing club also gives every role the module access
keys it needs to keep seeing what it saw before, then switches module access
on for the club (``core/module_access.py``).
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

# What every member may do (unchanged from before the standard set).
MEMBER_KEYS = [
    "members.members.read",
    "groups.groups.read",
    "events.events.read",
    "events.events.register",
    "polls.polls.read",
    "polls.polls.vote",
    "posts.posts.read",
    "posts.posts.like",
    "posts.posts.comment",
    "dashboard.dashboard.read",
    "notifications.notifications.read",
]

TREASURER_KEYS = [
    "finance.transactions.read",
    "finance.transactions.create",
    "finance.transactions.update",
    "finance.transactions.delete",
    "finance.invoices.read",
    "finance.invoices.create",
    "finance.invoices.update",
    "finance.invoices.delete",
    "finance.invoices.remind",
    "finance.invoices.read_reminders",
    "finance.overview.read",
    "finance.transaction_categories.read",
    "finance.transaction_categories.create",
    "finance.transaction_categories.update",
    "finance.transaction_categories.delete",
    "finance.external_parties.read",
    "finance.external_parties.create",
    "finance.external_parties.update",
    "finance.external_parties.delete",
    "members.members.read",
    "tiers.tiers.read",
    "tiers.tiers.calculate_cost",
    "tiers.tiers.read_members",
    "tiers.fee_adjustments.read",
    "tiers.fee_adjustments.update",
    "audit.audit.read",
    "dashboard.dashboard.read",
]

# Rights that reach past a module: giving roles, making admins. Only admins.
_NEVER_BY_LEVEL = {
    "members.members.update.role_ids",
    "roles.roles.update.is_admin",
    "roles.roles.set_permissions",
}

# key -> (name, description, is_admin, is_owner, is_default, module levels, extra keys)
STANDARD_ROLES: dict[str, dict] = {
    "owner": {
        "name": "Owner",
        "description": "Full access. Only owners give or take this role; a club always has at least one.",
        "is_admin": True,
        "is_owner": True,
    },
    "admin": {
        "name": "Admin",
        "description": "Full access to the club, except giving or taking the Owner role.",
        "is_admin": True,
    },
    "member": {
        "name": "Member",
        "description": "What every member may do: events, polls, posts. The permissions can be changed.",
        "is_default": True,
        "keys": MEMBER_KEYS,
    },
    "board": {
        "name": "Board",
        "description": "The board (Vorstand): sees the club's members, finances and mail, runs events, polls, posts and groups.",
        "levels": {
            "members": "view",
            "functions": "view",
            "finance": "view",
            "mail": "view",
            "events": "edit",
            "polls": "edit",
            "posts": "edit",
            "groups": "edit",
        },
        "keys": MEMBER_KEYS + ["tiers.tiers.read_members"],
    },
    "secretary": {
        "name": "Secretary",
        "description": "Aktuar/in: keeps the member register, applications, functions, mail and the club's records.",
        "levels": {
            "members": "all",
            "functions": "edit",
            "mail": "edit",
            "events": "edit",
            "polls": "edit",
            "posts": "edit",
            "groups": "edit",
        },
        "keys": ["audit.audit.read"],
    },
    "treasurer": {
        "name": "Treasurer",
        "description": "Manages the finances, sees members and the audit log.",
        "levels": {"finance": "all"},
        "keys": TREASURER_KEYS,
    },
}

# key -> (name, description, role keys). Präsident/in and Vize get Admin (D1).
STANDARD_FUNCTIONS: dict[str, dict] = {
    "president": {
        "name": "Präsident/in",
        "description": "President",
        "roles": ["admin", "board"],
        "aliases": ["Präsident", "Präsidentin", "Präsidium", "President"],
    },
    "vice_president": {
        "name": "Vizepräsident/in",
        "description": "Vice president",
        "roles": ["admin", "board"],
        "aliases": ["Vizepräsident", "Vizepräsidentin", "Vice President"],
    },
    "secretary": {
        "name": "Aktuar/in",
        "description": "Secretary and archive",
        "roles": ["board", "secretary"],
        "aliases": ["Aktuar", "Aktuarin", "Secretary", "Archivar", "Archivar/in"],
    },
    "treasurer": {
        "name": "Kassier/in",
        "description": "Treasurer",
        "roles": ["board", "treasurer"],
        "aliases": ["Kassier", "Kassierin", "Treasurer", "Finanzen"],
    },
}


def role_keys(key: str) -> set[str]:
    """The permission keys a standard role starts with."""
    from hubra.core.module_access import level_keys

    spec = STANDARD_ROLES[key]
    keys = set(spec.get("keys", ()))
    for code, level in spec.get("levels", {}).items():
        keys |= level_keys(code, level)
    return keys - _NEVER_BY_LEVEL


def _ensure_roles() -> tuple[dict[str, object], list]:
    """Find or make each standard role. Returns (key -> Role, created)."""
    from hubra.core.models.role import Role
    from hubra.core.services.roles import RoleService

    roles: dict[str, object] = {}
    created = []
    for key, spec in STANDARD_ROLES.items():
        role = db.session.scalar(select(Role).where(Role.key == key))
        if role is None:
            role = db.session.scalar(select(Role).where(Role.name == spec["name"]))
            if role is not None:
                # The club already has it (a system role from before keys, or
                # one it made itself): adopt it, leave its rights alone.
                role.key = key
        if role is None:
            if key == "owner":
                continue  # an owner role is only made with the club
            role = Role(
                name=spec["name"],
                key=key,
                description=spec["description"],
                is_admin=spec.get("is_admin", False),
                is_owner=spec.get("is_owner", False),
                is_default=spec.get("is_default", False),
                is_system=True,
            )
            db.session.add(role)
            db.session.flush()
            if not role.is_admin:
                RoleService.set_permissions(
                    role, sorted(role_keys(key)), actor_id=None, _internal=True
                )
            created.append(role)
        roles[key] = role
    db.session.flush()
    return roles, created


def _ensure_functions(roles: dict[str, object]) -> list:
    """Find or make each standard function. A function the club already has
    keeps the roles it gives and gets the standard ones it lacks, except
    Admin."""
    from hubra.core.models.function import Function
    from hubra.core.services.binding_engine import sync_for_source
    from hubra.core.services.managed_mail import auto_create_mma_for_function

    created = []
    for key, spec in STANDARD_FUNCTIONS.items():
        fn = db.session.scalar(select(Function).where(Function.key == key))
        if fn is None:
            for name in [spec["name"], *spec["aliases"]]:
                fn = db.session.scalar(
                    select(Function).where(Function.name == name, Function.key.is_(None))
                )
                if fn is not None:
                    fn.key = key
                    break
        wanted = [roles[r] for r in spec["roles"] if r in roles]
        if fn is None:
            if db.session.scalar(select(Function.id).where(Function.name == spec["name"])):
                continue  # the name is taken by a function the club made itself
            fn = Function(
                name=spec["name"], description=spec["description"], max_holders=1, key=key
            )
            fn.roles = wanted
            db.session.add(fn)
            db.session.flush()
            sync_for_source("function", str(fn.id))
            auto_create_mma_for_function(fn.id)
            created.append(fn)
        else:
            # A function the club already had gets the standard roles it is
            # missing, but never an admin role: making its holders admins on
            # an upgrade is the club's call (docs/roles.md).
            have = list(fn.roles)
            fn.roles = have + [r for r in wanted if r not in have and not r.is_admin]
    db.session.flush()
    return created


def _backfill_access() -> int:
    """First run in an existing club: every role keeps the modules it could
    use. A role gets a module's access key when it holds any key of the
    module, or when the module has a page that needed no key (everyone saw
    it). Returns how many roles changed."""
    from hubra.core.models.role import Role
    from hubra.core.module_access import access_key, gated_modules, implied_access_keys
    from hubra.core.services.roles import RoleService

    open_to_all = {
        access_key(m.code)
        for m in gated_modules()
        if any(not n.perms and not n.parent for n in m.nav)
    }
    changed = 0
    for role in db.session.scalars(select(Role).where(Role.is_admin.is_(False))).all():
        held = set(RoleService.get_permissions(role.id))
        want = implied_access_keys(held) | open_to_all
        if want - held:
            RoleService.set_permissions(role, sorted(held | want), actor_id=None, _internal=True)
            changed += 1
    return changed


def standardise(*, fresh: bool = False, tenant_id=None) -> dict:
    """Give the current club the standard roles, functions and module access.

    ``fresh`` is a club being made right now: every standard role is new,
    so the modules' role defaults apply to all of them. Idempotent.
    """
    from hubra.core import module_access
    from hubra.core.modules.state import CURRENT, states

    first = module_access._setting(module_access.ENFORCED_SETTING) is None
    roles, created_roles = _ensure_roles()
    created_functions = _ensure_functions(roles)

    backfilled = 0
    enabled = [
        code
        for code, st in states(CURRENT if tenant_id is None else tenant_id).items()
        if st.effective
    ]
    if first:
        if not fresh:
            backfilled = _backfill_access()
        only = None if fresh else created_roles
        for code in enabled:
            module_access.apply_role_defaults(code, only_roles=only)
        module_access.set_enforced(True)
    else:
        for code in enabled:
            module_access.apply_role_defaults(code)
    db.session.flush()
    return {
        "roles": [r.name for r in created_roles],
        "functions": [f.name for f in created_functions],
        "backfilled": backfilled,
        "first": first,
    }
