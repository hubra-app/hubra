"""Role service — business logic for club roles and permissions."""

from __future__ import annotations

from sqlalchemy import select

from hubra.api.permissions import check_grant, invalidate_role_permissions
from hubra.api.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.role import Role, RolePermission, Permission


class RoleService:
    """Operations on a single role."""

    @staticmethod
    def get(role_id: int) -> Role:
        """Return a role or raise 404."""
        role = db.session.get(Role, role_id)
        if role is None:
            raise_error(404, "NOT_FOUND", f"Role {role_id} not found")
        return role  # type: ignore[return-value]

    @staticmethod
    def update(role: Role, name: str, actor_id: int) -> Role:
        """Rename a role. Raises on conflict or if the role is a system role.

        Sending a system role's own name back is no rename: the edit form
        always sends the name, also when only the description changed.
        """
        name = name.strip()
        if name == role.name:
            return role
        if role.is_system:
            raise_error(409, "ROLE_LOCKED", "Cannot modify a system role")

        conflict = db.session.scalar(
            select(Role.id).where(Role.name == name).where(Role.id != role.id)
        )
        if conflict is not None:
            raise_error(409, "CONFLICT", f"Role '{name}' already exists")

        role.name = name

        log_audit(
            actor_id=actor_id,
            action="update_role",
            target_type="Role",
            target_id=role.id,
            target_label=role.name,
        )
        return role

    @staticmethod
    def delete(role_id: int, actor_id: int) -> None:
        """Delete a role if it's not a system/default role and not assigned to members.

        A club's own admin role can go too, but only an admin removes it.
        """
        role = RoleService.get(role_id)

        if role.is_system:
            raise_error(409, "ROLE_LOCKED", "Cannot delete a system role")
        if role.is_admin:
            from hubra.core.models.member import Member

            check_grant(db.session.get(Member, actor_id), taken=[role])
        if role.is_default:
            raise_error(409, "CONFLICT", "Cannot delete a default role")

        from hubra.core.models.member import member_roles

        member_using = db.session.scalar(
            select(member_roles.c.member_id)
            .where(member_roles.c.role_id == role.id)
            .limit(1)
        )
        if member_using is not None:
            raise_error(
                409, "CONFLICT", "Cannot delete a role that is assigned to members"
            )

        log_audit(
            actor_id=actor_id,
            action="delete_role",
            target_type="Role",
            target_id=role.id,
            target_label=role.name,
        )

        db.session.delete(role)
        invalidate_role_permissions(role_id)

    @staticmethod
    def get_permissions(role_id: int) -> list[str]:
        """Return permission keys for a role."""
        RoleService.get(role_id)  # 404 if not found
        return list(
            db.session.scalars(
                select(Permission.key)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role_id)
                .order_by(Permission.key)
            ).all()
        )

    @staticmethod
    def set_permissions(
        role: Role,
        permission_keys: list[str],
        actor_id: int | None = None,
        _internal: bool = False,
    ) -> list[str]:
        """Replace all permissions for a role. Returns sorted permission keys.

        Args:
            _internal: When True, bypasses the admin-role lock check.
                Used only by _seed_tenant during tenant provisioning.

        Admin roles hold every permission anyway, so theirs are locked. The
        other system roles (Treasurer, Member) are starting points the club
        adapts: they can't be renamed or deleted, but their permissions can
        change, or no club could e.g. let its members sign up for events.
        """
        if not _internal and role.is_admin:
            if role.is_system:
                raise_error(
                    409, "ROLE_LOCKED", "Cannot modify a system role's permissions"
                )
            raise_error(
                409, "ROLE_LOCKED", "Cannot modify an admin role's permissions"
            )

        keys = [k for k in permission_keys if isinstance(k, str) and k.strip()]
        if not _internal:
            from hubra.core.models.member import Member

            had = set(RoleService.get_permissions(role.id))
            check_grant(
                db.session.get(Member, actor_id) if actor_id else None,
                keys=[k for k in keys if k not in had],
            )

        db.session.query(RolePermission).filter_by(role_id=role.id).delete()

        if keys:
            perms = db.session.scalars(
                select(Permission).where(Permission.key.in_(keys))
            ).all()
            perm_map = {p.key: p for p in perms}
            for key in keys:
                perm = perm_map.get(key)
                if perm is not None:
                    db.session.add(
                        RolePermission(role_id=role.id, permission_id=perm.id)
                    )

        invalidate_role_permissions(role.id)

        log_audit(
            actor_id=actor_id,
            action="set_role_permissions",
            target_type="Role",
            target_id=role.id,
            target_label=role.name,
        )

        return sorted(keys)


class RolesService:
    """Operations on the role collection."""

    @staticmethod
    def list() -> list[Role]:
        """Return all roles ordered by name."""
        return db.session.scalars(  # type: ignore[return-value]
            select(Role).order_by(Role.name)
        ).all()

    @staticmethod
    def create(data: dict, actor_id: int | None = None) -> Role:
        """Create a new role. Raises 409 on name conflict."""
        existing = db.session.scalar(select(Role.id).where(Role.name == data["name"]))
        if existing is not None:
            raise_error(409, "CONFLICT", f"Role '{data['name']}' already exists")

        role = Role(
            name=data["name"],
            description=data.get("description"),
            is_admin=data.get("is_admin", False),
            is_default=data.get("is_default", False),
            # is_system and is_owner are NOT settable via API — only by _seed_tenant
        )
        db.session.add(role)
        db.session.flush()

        log_audit(
            actor_id=actor_id,
            action="create_role",
            target_type="Role",
            target_id=role.id,
            target_label=role.name,
        )

        return role  # type: ignore[return-value]
