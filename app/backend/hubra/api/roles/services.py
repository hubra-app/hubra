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

            # Adding a right gives it to every holder, removing takes it
            # away: either way only someone who holds it themselves.
            had = set(RoleService.get_permissions(role.id))
            check_grant(
                db.session.get(Member, actor_id) if actor_id else None,
                keys=set(keys) ^ had,
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
    def member_counts() -> dict[int, int]:
        """Role id -> how many current members hold it, themselves or through
        a function whose term runs."""
        from datetime import date

        from sqlalchemy import func, union

        from hubra.api.permissions import _active_term
        from hubra.core.models.function import Function, FunctionHolder
        from hubra.core.models.member import Member, member_roles

        holds = union(
            select(member_roles.c.role_id, member_roles.c.member_id),
            select(Function.grants_tenant_role_id, FunctionHolder.member_id)
            .join(Function, Function.id == FunctionHolder.function_id)
            .where(Function.grants_tenant_role_id.is_not(None), *_active_term(date.today())),
        ).subquery()
        rows = db.session.execute(
            select(holds.c[0], func.count())
            .join(Member, Member.id == holds.c[1])
            .where(Member.archived_at.is_(None), Member.deleted_at.is_(None))
            .group_by(holds.c[0])
        ).all()
        return {role_id: count for role_id, count in rows}

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


class RoleScopeService:
    """Roles held for one group only (``member_role_scopes``)."""

    @staticmethod
    def list(role: Role) -> list[dict]:
        from hubra.core.models.group import Group
        from hubra.core.models.member import Member
        from hubra.core.models.role import MemberRoleScope

        rows = db.session.execute(
            select(MemberRoleScope, Member, Group)
            .join(Member, Member.id == MemberRoleScope.member_id)
            .join(Group, Group.id == MemberRoleScope.group_id)
            .where(MemberRoleScope.role_id == role.id, Member.archived_at.is_(None))
            .order_by(Group.name)
        ).all()
        return [
            {
                "id": scope.id,
                "member_id": member.id,
                "member_name": member.name,
                "group_id": group.id,
                "group_name": group.name,
            }
            for scope, member, group in rows
        ]

    @staticmethod
    def add(role: Role, member_id, group_id, actor_id: int | None):
        from hubra.api.permissions import check_grant, invalidate_member_permissions
        from hubra.core.models.group import Group
        from hubra.core.models.member import Member
        from hubra.core.models.role import MemberRoleScope

        if role.is_admin or role.is_owner:
            # An admin role passes every check, whatever group it is for.
            raise_error(400, "VALIDATION_ERROR", "Admin roles apply to the whole club")
        member = db.session.get(Member, member_id) if isinstance(member_id, int) else None
        if member is None or member.archived_at is not None:
            raise_error(404, "NOT_FOUND", "Member not found")
        group = db.session.get(Group, group_id) if isinstance(group_id, int) else None
        if group is None:
            raise_error(404, "NOT_FOUND", "Group not found")
        check_grant(db.session.get(Member, actor_id) if actor_id else None, given=[role])

        exists = db.session.scalar(
            select(MemberRoleScope.id).where(
                MemberRoleScope.member_id == member.id,
                MemberRoleScope.role_id == role.id,
                MemberRoleScope.group_id == group.id,
            )
        )
        if exists is not None:
            raise_error(409, "CONFLICT", "The member already has this role for the group")
        scope = MemberRoleScope(member_id=member.id, role_id=role.id, group_id=group.id)
        db.session.add(scope)
        db.session.flush()
        invalidate_member_permissions(member.id)
        log_audit(
            actor_id=actor_id,
            action="give_group_role",
            target_type="Member",
            target_id=member.id,
            target_label=f"{role.name} @ {group.name}",
        )
        return scope

    @staticmethod
    def remove(role: Role, scope_id: int, actor_id: int | None) -> None:
        from hubra.api.permissions import check_grant, invalidate_member_permissions
        from hubra.core.models.member import Member
        from hubra.core.models.role import MemberRoleScope

        scope = db.session.get(MemberRoleScope, scope_id)
        if scope is None or scope.role_id != role.id:
            raise_error(404, "NOT_FOUND", "Not found")
        check_grant(db.session.get(Member, actor_id) if actor_id else None, taken=[role])
        member_id = scope.member_id
        log_audit(
            actor_id=actor_id,
            action="take_group_role",
            target_type="Member",
            target_id=member_id,
            target_label=f"{role.name} @ {scope.group.name}",
        )
        db.session.delete(scope)
        invalidate_member_permissions(member_id)
