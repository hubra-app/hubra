"""Seed default global roles and permissions for the manager portal.

Called at app startup or via ``flask seed-global-rbac`` CLI command.
Idempotent — safe to run multiple times.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

# (key, display_name, description)
_DEFAULT_PERMISSIONS = [
    ("tenants.read", "View tenants", "List and view tenant details"),
    ("tenants.create", "Create tenants", "Provision new tenants"),
    (
        "tenants.update",
        "Update tenants",
        "Update name, plan, status, enable/disable/archive",
    ),
    ("tenants.delete", "Delete tenants", "Soft or hard delete tenants"),
    ("tenants.members.read", "View tenant members", "List members in a tenant"),
    ("tenants.members.write", "Manage tenant members", "Add or remove tenant members"),
    ("requests.read.all", "View all requests", "List all tenant requests"),
    ("requests.approve", "Approve requests", "Approve or reject tenant requests"),
    ("audit.read", "View audit log", "Read global audit entries"),
    ("impersonate", "Impersonate users", "Impersonate tenant users for support"),
    (
        "roles.manage",
        "Manage global roles",
        "Create roles, assign permissions, assign users",
    ),
]

# (role_name, description, [permission_keys])
_DEFAULT_ROLES = [
    (
        "Superadmin",
        "Full platform access (bypasses all checks)",
        [
            "tenants.read",
            "tenants.create",
            "tenants.update",
            "tenants.delete",
            "tenants.members.read",
            "tenants.members.write",
            "requests.read.all",
            "requests.approve",
            "audit.read",
            "impersonate",
            "roles.manage",
        ],
    ),
    (
        "Manager",
        "Day-to-day tenant management",
        [
            "tenants.read",
            "tenants.update",
            "tenants.members.read",
            "tenants.members.write",
            "requests.read.all",
            "requests.approve",
            "audit.read",
        ],
    ),
    (
        "Support",
        "Read-only access with impersonation",
        [
            "tenants.read",
            "audit.read",
            "impersonate",
        ],
    ),
    ("Requester", "Any authenticated user — can submit tenant requests", []),
]


def seed_global_rbac() -> None:
    """Seed default global permissions and roles. Idempotent."""
    from hubra.core.models.global_role import (
        GlobalPermission,
        GlobalRole,
        GlobalRolePermission,
    )

    # 1. Seed permissions
    perm_map: dict[str, GlobalPermission] = {}
    for key, display_name, desc in _DEFAULT_PERMISSIONS:
        existing = db.session.scalar(
            select(GlobalPermission).where(GlobalPermission.key == key)
        )
        if existing is None:
            perm = GlobalPermission(
                key=key, display_name=display_name, description=desc
            )
            db.session.add(perm)
            db.session.flush()
            perm_map[key] = perm
            _log.debug("Seeded global permission: %s", key)
        else:
            perm_map[key] = existing

    # 2. Seed roles + role-permission links
    for role_name, desc, perm_keys in _DEFAULT_ROLES:
        role = db.session.scalar(select(GlobalRole).where(GlobalRole.name == role_name))
        if role is None:
            role = GlobalRole(name=role_name, description=desc, is_system=True)
            db.session.add(role)
            db.session.flush()
            _log.debug("Seeded global role: %s", role_name)

        for pk in perm_keys:
            perm = perm_map.get(pk)
            if perm is None:
                continue
            existing = db.session.scalar(
                select(GlobalRolePermission).where(
                    GlobalRolePermission.role_id == role.id,
                    GlobalRolePermission.permission_id == perm.id,
                )
            )
            if existing is None:
                db.session.add(
                    GlobalRolePermission(role_id=role.id, permission_id=perm.id)
                )

    db.session.commit()
    _log.info(
        "Global RBAC seed complete (%d permissions, %d roles)",
        len(_DEFAULT_PERMISSIONS),
        len(_DEFAULT_ROLES),
    )
