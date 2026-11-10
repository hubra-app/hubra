"""Group service — business logic decoupled from HTTP layer."""

from __future__ import annotations

import logging

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import selectinload

from hubra.core.utils import escape_like, log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.group import Group, GroupMembership
from hubra.core.models.member import Member, member_groups
from hubra.core.modules import emit
from hubra.core.modules.events import GROUP_MEMBERSHIP_CHANGED


def _check_parent(parent_id: int | None, group_id: int | None = None) -> None:
    """A parent group must exist, and a group cannot be its own ancestor."""
    seen = {group_id}
    while parent_id is not None:
        if parent_id in seen:
            raise_error(400, "VALIDATION_ERROR", "A group cannot be its own parent")
        parent = db.session.get(Group, parent_id)
        if parent is None or parent.archived_at is not None:
            raise_error(404, "NOT_FOUND", f"Group {parent_id} not found")
        seen.add(parent_id)
        parent_id = parent.parent_group_id


# ── Visibility ─────────────────────────────────────────────────────────────────


class GroupVisibility:
    """Who sees a private group: its members, its lead, and members who may
    update groups (for the whole club or for that group). Open and visible
    groups are seen by everyone who may read groups."""

    @staticmethod
    def _manages_all(member) -> bool:
        from hubra.core.permissions import member_has_permission

        return member_has_permission(member, "groups.groups.update")

    @staticmethod
    def hidden_ids(member) -> set[int]:
        """Ids of the private groups *member* may not see."""
        if member is None:
            return set()
        if GroupVisibility._manages_all(member):
            return set()
        from hubra.core.permissions import scoped_permission_keys

        private = db.session.execute(
            select(Group.id, Group.lead_id).where(Group.visibility == "private")
        ).all()
        if not private:
            return set()
        mine = set(
            db.session.scalars(
                select(member_groups.c.group_id).where(
                    member_groups.c.member_id == member.id
                )
            )
        )
        scoped = {
            gid
            for gid, keys in scoped_permission_keys(member).items()
            if "groups.groups.update" in keys
        }
        return {
            gid
            for gid, lead_id in private
            if gid not in mine and gid not in scoped and lead_id != member.id
        }

    @staticmethod
    def require(member, group_id: int) -> None:
        """404 when *member* may not see the group, as if it did not exist."""
        if group_id in GroupVisibility.hidden_ids(member):
            raise_error(404, "NOT_FOUND", f"Group {group_id} not found")


# ── Roles a group gives, default groups, tier groups ──────────────────────────


def _actor(actor_id: int | None):
    return db.session.get(Member, actor_id) if actor_id is not None else None


def _group_roles_from(role_ids) -> list:
    """The roles a group is to give: never Owner or an admin role (being put
    in a group must never make anyone an admin)."""
    from hubra.core.models.role import Role

    roles = []
    for rid in role_ids or []:
        role = db.session.get(Role, rid)
        if role is None:
            raise_error(
                400,
                "VALIDATION_ERROR",
                f"Role {rid} not found",
                {"role_ids": [f"Role {rid} not found"]},
            )
        if role.is_owner or role.is_admin:
            raise_error(
                400,
                "VALIDATION_ERROR",
                "A group cannot give the Owner role or an admin role",
                {"role_ids": ["A group cannot give the Owner role or an admin role"]},
            )
        if role not in roles:
            roles.append(role)
    return roles


def _tiers_from(tier_ids) -> list:
    from hubra.core.models.member import MembershipTier

    tiers = []
    for tid in tier_ids or []:
        tier = db.session.get(MembershipTier, tid)
        if tier is None:
            raise_error(
                400,
                "VALIDATION_ERROR",
                f"Tier {tid} not found",
                {"tier_ids": [f"Tier {tid} not found"]},
            )
        if tier not in tiers:
            tiers.append(tier)
    return tiers


def _no_open_group_with_roles(visibility: str, roles: list) -> None:
    """Anyone may join an open group on their own, so it cannot give roles."""
    if visibility == "open" and roles:
        raise_error(
            400,
            "VALIDATION_ERROR",
            "An open group cannot give roles: anyone could join it and get them",
            {"role_ids": ["An open group cannot give roles"]},
        )


def group_member_ids(group_id: int) -> list[int]:
    return list(
        db.session.scalars(
            select(member_groups.c.member_id).where(
                member_groups.c.group_id == group_id
            )
        ).all()
    )


def _refresh_members(group_id: int) -> None:
    from hubra.core.permissions import invalidate_member_permissions

    for member_id in group_member_ids(group_id):
        invalidate_member_permissions(member_id)


def _apply_links(group: Group, data: dict, actor_id: int | None) -> None:
    """Set the roles, tiers and default flag of *group* from *data*.

    Linking a role gives it to everyone in the group, and linking a tier or
    marking the group default puts members in it later without anyone
    checking again, so the actor needs the right to give the group's roles
    for each of these, as for a function's roles.
    """
    from hubra.core.permissions import check_grant

    actor = _actor(actor_id)
    if "role_ids" in data:
        roles = _group_roles_from(data["role_ids"])
        old = list(group.roles)
        given = [r for r in roles if r not in old]
        taken = [r for r in old if r not in roles]
        if given or taken:
            check_grant(actor, given=given, taken=taken)
            group.roles = roles
            db.session.flush()
            _refresh_members(group.id)
    _no_open_group_with_roles(group.visibility, list(group.roles))

    adds_members_later = False
    if "tier_ids" in data:
        tiers = _tiers_from(data["tier_ids"])
        new_tiers = [t for t in tiers if t not in group.tiers]
        group.tiers = tiers
        db.session.flush()
        if new_tiers:
            adds_members_later = True
            for tier in new_tiers:
                _join_tier_members(group, tier.id)
    if "is_default" in data:
        if data["is_default"] and not group.is_default:
            adds_members_later = True
        group.is_default = bool(data["is_default"])
    if adds_members_later and group.roles:
        check_grant(actor, given=list(group.roles))


def _join_tier_members(group: Group, tier_id: int) -> None:
    """The tier's current members are in the group from now on (unlinking
    a tier later leaves them in it)."""
    for member in db.session.scalars(
        select(Member).where(Member.tier_id == tier_id, Member.archived_at.is_(None))
    ).all():
        _join_quietly(group, member)


def set_tier_groups(tier, group_ids, actor_id: int | None) -> None:
    """The tier side of ``tier_groups``: the groups *tier*'s members are in.
    Newly linked groups get the tier's members now; the actor needs the
    right to give the roles of those groups."""
    from hubra.core.permissions import check_grant

    groups = []
    for gid in group_ids or []:
        group = db.session.get(Group, gid)
        if (
            group is None
            or group.archived_at is not None
            or group.deleted_at is not None
        ):
            raise_error(
                400,
                "VALIDATION_ERROR",
                f"Group {gid} not found",
                {"group_ids": [f"Group {gid} not found"]},
            )
        if group not in groups:
            groups.append(group)
    new_groups = [g for g in groups if g not in tier.groups]
    given = {r.id: r for g in new_groups for r in g.roles}
    if given:
        check_grant(_actor(actor_id), given=list(given.values()))
    tier.groups = groups
    db.session.flush()
    for group in new_groups:
        _join_tier_members(group, tier.id)


def _in_group(group_id: int, member_id: int) -> bool:
    return (
        db.session.scalar(
            select(func.count())
            .select_from(member_groups)
            .where(
                member_groups.c.group_id == group_id,
                member_groups.c.member_id == member_id,
            )
        )
        or 0
    ) > 0


def _join_quietly(group: Group, member: Member) -> bool:
    """Put *member* in *group* unless they are in it already. No grant
    check: the default and tier groups were set up by someone who may give
    their roles. Returns whether they joined."""
    if group.archived_at is not None or group.deleted_at is not None:
        return False
    if _in_group(group.id, member.id):
        return False
    GroupService.add_member(group, member)
    return True


def join_automatic_groups(member: Member) -> list[int]:
    """A new (or returning) member joins the default groups and the groups
    of their tier. Returns the ids of the groups they joined."""
    groups = list(
        db.session.scalars(
            select(Group).where(
                Group.is_default.is_(True),
                Group.archived_at.is_(None),
                Group.deleted_at.is_(None),
            )
        ).all()
    )
    if member.tier_id is not None:
        groups += _tier_group_list(member.tier_id)
    joined = []
    for group in groups:
        if _join_quietly(group, member):
            joined.append(group.id)
    return joined


def _tier_group_list(tier_id: int) -> list[Group]:
    from hubra.core.models.group import tier_groups

    return list(
        db.session.scalars(
            select(Group)
            .join(tier_groups, tier_groups.c.group_id == Group.id)
            .where(
                tier_groups.c.tier_id == tier_id,
                Group.archived_at.is_(None),
                Group.deleted_at.is_(None),
            )
        ).all()
    )


def move_tier_groups(member: Member, old_tier_id: int | None) -> None:
    """After a tier change: leave the old tier's groups (unless they are
    default groups or groups of the new tier too) and join the new tier's."""
    new_tier_id = member.tier_id
    if old_tier_id == new_tier_id:
        return
    new_groups = _tier_group_list(new_tier_id) if new_tier_id is not None else []
    keep = {g.id for g in new_groups}
    if old_tier_id is not None:
        for group in _tier_group_list(old_tier_id):
            if group.id in keep or group.is_default:
                continue
            if _in_group(group.id, member.id):
                GroupService.remove_member(member.id, group.id)
    for group in new_groups:
        _join_quietly(group, member)


# ── GroupService (singular) ────────────────────────────────────────────────────


class GroupService:
    """Operations on a single group."""

    @staticmethod
    def get_by_id(id: int) -> Group:
        """Return a non-archived group or raise 404."""
        group = db.session.scalar(
            select(Group)
            .where(Group.id == id)
            .where(Group.archived_at.is_(None))
            .options(selectinload(Group.lead))
        )
        if group is None:
            raise_error(404, "NOT_FOUND", f"Group {id} not found")
        return group  # type: ignore[return-value]

    @staticmethod
    def update(group: Group, data: dict, actor_id: int) -> Group:
        """Update scalar fields on a group. Returns the group object."""
        # Validate lead_id if provided
        if "lead_id" in data and data["lead_id"] is not None:
            lead = db.session.scalar(
                select(Member)
                .where(Member.id == data["lead_id"])
                .where(Member.archived_at.is_(None))
            )
            if lead is None:
                raise_error(404, "NOT_FOUND", f"Member {data['lead_id']} not found")

        # Check name uniqueness if name is being changed
        if "name" in data and data["name"] != group.name:
            conflict = db.session.scalar(
                select(Group.id)
                .where(Group.name == data["name"])
                .where(Group.id != group.id)
            )
            if conflict is not None:
                raise_error(
                    409, "CONFLICT", f"Group name '{data['name']}' is already taken"
                )

        if data.get("parent_group_id") is not None:
            _check_parent(data["parent_group_id"], group.id)

        for field in (
            "name",
            "lead_id",
            "description",
            "color",
            "icon_name",
            "sessions",
            "type",
            "email_alias",
            "visibility",
            "parent_group_id",
        ):
            if field in data:
                setattr(group, field, data[field])
        _apply_links(group, data, actor_id)

        log_audit(
            actor_id=actor_id,
            action="update_group",
            target_type="Group",
            target_id=group.id,
            target_label=group.name,
        )

        from hubra.core.services.binding_engine import sync_for_source

        sync_for_source("group", str(group.id))

        return group

    @staticmethod
    def delete(group_id: int, actor_id: int) -> None:
        """Archive (delete) a group. Cleans up managed mail addresses first."""
        from hubra.core.services.managed_mail import remove_for_group

        group = GroupService.get_by_id(group_id)

        from hubra.core.services.binding_engine import (
            assert_source_deletable,
            assert_mail_address_owner_deletable,
            cascade_delete_disabled,
        )

        assert_source_deletable("group", str(group_id))
        assert_mail_address_owner_deletable("group", group_id)

        remove_for_group(group_id)

        from hubra.core.models.function import FunctionHolder
        from hubra.core.permissions import invalidate_member_permissions

        # The members lose the roles the group gave them, and the holders
        # of its group functions those of the functions.
        affected = set(group_member_ids(group.id)) | set(
            db.session.scalars(
                select(FunctionHolder.member_id).where(
                    FunctionHolder.group_id == group.id
                )
            ).all()
        )
        if group.roles:
            from hubra.core.permissions import check_grant

            check_grant(_actor(actor_id), taken=list(group.roles))
        group.roles = []
        group.tiers = []
        db.session.flush()
        db.session.execute(
            delete(FunctionHolder).where(FunctionHolder.group_id == group.id)
        )
        for member_id in affected:
            invalidate_member_permissions(member_id)

        db.session.execute(
            delete(member_groups).where(member_groups.c.group_id == group.id)
        )
        # Club schemas have no foreign keys: move subgroups up a level
        # instead of leaving them under a group that no longer exists.
        db.session.execute(
            update(Group)
            .where(Group.parent_group_id == group.id)
            .values(parent_group_id=group.parent_group_id)
        )
        db.session.delete(group)

        cascade_delete_disabled("group", str(group_id))

        log_audit(
            actor_id=actor_id,
            action="archive_group",
            target_type="Group",
            target_id=group.id,
            target_label=group.name,
        )

    @staticmethod
    def list_members(group_id: int, search: str = "") -> list[Member]:
        """Return members belonging to a group, with optional search."""
        from hubra.core.models.user import User

        query = (
            select(Member)
            .join(member_groups, Member.id == member_groups.c.member_id)
            .join(User, Member.user_id == User.id, isouter=True)
            .where(member_groups.c.group_id == group_id)
            .where(Member.archived_at.is_(None))
            .order_by(User.last_name, User.first_name)
            .options(
                selectinload(Member.user),
                selectinload(Member.tier),
                selectinload(Member.roles),
                selectinload(Member.groups),
            )
        )

        if search:
            pattern = f"%{escape_like(search)}%"
            query = query.where(
                User.first_name.ilike(pattern, escape="\\")
                | User.last_name.ilike(pattern, escape="\\")
                | User.email.ilike(pattern, escape="\\")
            )

        return db.session.scalars(query).all()  # type: ignore[return-value]

    @staticmethod
    def add_member(group: Group, member: Member, actor_id: int | None = None) -> None:
        """Add a member to a group. Raises 409 if already a member.

        With *actor_id*, the actor needs the right to give the roles the group
        gives (``None`` is the system: default and tier groups)."""
        existing = (
            db.session.scalar(
                select(func.count())
                .select_from(member_groups)
                .where(
                    member_groups.c.group_id == group.id,
                    member_groups.c.member_id == member.id,
                )
            )
            or 0
        )
        if existing > 0:
            raise_error(409, "CONFLICT", "Member is already in this group")
        if actor_id is not None and group.roles:
            from hubra.core.permissions import check_grant

            check_grant(_actor(actor_id), given=list(group.roles))

        db.session.execute(
            insert(member_groups).values(member_id=member.id, group_id=group.id)
        )
        from hubra.core.permissions import invalidate_member_permissions

        invalidate_member_permissions(member.id)

        _trigger_group_mail_sync(group.id)
        emit(
            GROUP_MEMBERSHIP_CHANGED,
            group_id=group.id,
            member_id=member.id,
            action="joined",
        )

    @staticmethod
    def remove_member(
        member_id: int, group_id: int, actor_id: int | None = None
    ) -> None:
        """Remove a member from a group. With *actor_id*, the actor needs the
        right to take the roles the group gives."""
        existing = (
            db.session.scalar(
                select(func.count())
                .select_from(member_groups)
                .where(
                    member_groups.c.group_id == group_id,
                    member_groups.c.member_id == member_id,
                )
            )
            or 0
        )
        if existing == 0:
            raise_error(404, "NOT_FOUND", "Member is not linked to this group")
        group = db.session.get(Group, group_id)
        if actor_id is not None and group is not None and group.roles:
            from hubra.core.permissions import check_grant

            check_grant(_actor(actor_id), taken=list(group.roles))

        db.session.execute(
            delete(member_groups).where(
                member_groups.c.member_id == member_id,
                member_groups.c.group_id == group_id,
            )
        )
        from hubra.core.permissions import invalidate_member_permissions

        invalidate_member_permissions(member_id)

        # Also remove from GroupMembership if it exists
        db.session.execute(
            delete(GroupMembership).where(
                GroupMembership.member_id == member_id,
                GroupMembership.group_id == group_id,
            )
        )

        _trigger_group_mail_sync(group_id)
        emit(
            GROUP_MEMBERSHIP_CHANGED,
            group_id=group_id,
            member_id=member_id,
            action="left",
        )

    @staticmethod
    def update_member_role(
        group_id: int, member_id: int, role: str, notes: str | None = None
    ) -> GroupMembership:
        """Update a member's role within a group. Creates GroupMembership if it doesn't exist."""
        # Verify member is in the group
        existing = (
            db.session.scalar(
                select(func.count())
                .select_from(member_groups)
                .where(
                    member_groups.c.group_id == group_id,
                    member_groups.c.member_id == member_id,
                )
            )
            or 0
        )
        if existing == 0:
            raise_error(404, "NOT_FOUND", "Member is not linked to this group")

        # Find or create GroupMembership
        membership = db.session.scalar(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.member_id == member_id,
            )
        )
        if membership is None:
            membership = GroupMembership(
                group_id=group_id,
                member_id=member_id,
                role=role,
                notes=notes,
            )
            db.session.add(membership)
        else:
            membership.role = role
            if notes is not None:
                membership.notes = notes

        return membership

    @staticmethod
    def functions(group_id: int) -> list[dict]:
        """The group functions held for this group and who holds them."""
        from hubra.core.models.function import Function, FunctionHolder

        rows = db.session.execute(
            select(FunctionHolder, Function)
            .join(Function, Function.id == FunctionHolder.function_id)
            .where(FunctionHolder.group_id == group_id)
            .order_by(Function.name, FunctionHolder.member_id)
            .options(selectinload(FunctionHolder.member).selectinload(Member.user))
        ).all()
        return [
            {
                "function_id": fn.id,
                "function_name": fn.name,
                "member_id": holder.member_id,
                "member_name": holder.member.name if holder.member else None,
                "role_names": [r.name for r in fn.roles],
            }
            for holder, fn in rows
            if holder.member is not None and holder.member.archived_at is None
        ]

    @staticmethod
    def get_mailing_list(group_id: int) -> list[dict]:
        """Return email addresses of all group members."""
        members = GroupService.list_members(group_id)
        return [
            {
                "email": m.email,
                "name": m.name,
                "public_email": m.public_email,
            }
            for m in members
        ]


# ── GroupsService (plural / collection) ───────────────────────────────────────


class GroupsService:
    """Operations on the group collection."""

    @staticmethod
    def count() -> dict:
        """Return total non-archived group count and archived count."""
        total: int = (
            db.session.scalar(
                select(func.count(Group.id)).where(Group.archived_at.is_(None))
            )
            or 0
        )
        archived: int = (
            db.session.scalar(
                select(func.count(Group.id)).where(Group.archived_at.isnot(None))
            )
            or 0
        )
        return {"total": total, "archived": archived}

    @staticmethod
    def list() -> list[Group]:
        """Return all non-archived groups ordered by name."""
        return db.session.scalars(  # type: ignore[return-value]
            select(Group)
            .where(Group.archived_at.is_(None))
            .order_by(Group.name)
            .options(
                selectinload(Group.lead).selectinload(Member.user),
                selectinload(Group.parent_group),
                selectinload(Group.roles),
                selectinload(Group.tiers),
            )
        ).all()

    @staticmethod
    def create(data: dict, actor_id: int | None = None) -> Group:
        """Create a new group. Returns the group object after commit."""
        # Validate lead_id if provided
        if data.get("lead_id") is not None:
            lead = db.session.scalar(
                select(Member)
                .where(Member.id == data["lead_id"])
                .where(Member.archived_at.is_(None))
            )
            if lead is None:
                raise_error(404, "NOT_FOUND", f"Member {data['lead_id']} not found")

        _check_parent(data.get("parent_group_id"))

        # Check name uniqueness
        existing = db.session.scalar(select(Group.id).where(Group.name == data["name"]))
        if existing is not None:
            raise_error(
                409, "CONFLICT", f"Group name '{data['name']}' is already taken"
            )

        group = Group(
            name=data["name"],
            lead_id=data.get("lead_id"),
            description=data.get("description"),
            color=data.get("color"),
            icon_name=data.get("icon_name"),
            sessions=data.get("sessions"),
            type=data.get("type", "interest_group"),
            email_alias=data.get("email_alias"),
            visibility=data.get("visibility", "visible"),
            parent_group_id=data.get("parent_group_id"),
        )
        db.session.add(group)
        db.session.flush()
        _apply_links(group, data, actor_id)

        log_audit(
            actor_id=actor_id,
            action="create_group",
            target_type="Group",
            target_id=group.id,
            target_label=group.name,
        )

        from hubra.core.services.binding_engine import sync_for_source

        sync_for_source("group", str(group.id))

        from hubra.core.services.managed_mail import auto_create_mma_for_group

        auto_create_mma_for_group(group.id)

        db.session.refresh(group)
        return group  # type: ignore[return-value]


# ── WildDuck helpers ──────────────────────────────────────────────────────────


def _trigger_group_mail_sync(group_id: int) -> None:
    """Dispatch reconcile_entity_forwarding task for a group.

    Only dispatches when at least one ManagedMailAddress exists for the
    group — avoids unnecessary Celery calls (and Redis connections
    in test environments) when no mail is configured.
    Falls back to inline sync when Celery is unavailable.
    """
    from hubra.core.models.managed_mail import ManagedMailAddress

    has_mma = db.session.scalar(
        select(ManagedMailAddress.id).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
        )
    )
    if has_mma is None:
        return

    try:
        from hubra.core.tasks.mail_tasks import reconcile_entity_forwarding_task

        reconcile_entity_forwarding_task.delay("group", group_id)
    except Exception:
        from hubra.core.services.mail_provisioning import (
            reconcile_entity_forwarding,
        )

        # A savepoint: a failure here must not undo the change that
        # triggered the sync, which the caller has not committed yet.
        try:
            with db.session.begin_nested():
                reconcile_entity_forwarding("group", group_id)
        except Exception:
            logging.getLogger(__name__).warning(
                "Inline mail sync failed for group %s", group_id, exc_info=True
            )


class SelfJoinService:
    """Members joining and leaving self-join groups on their own."""

    @staticmethod
    def joinable(member_id: int) -> list[dict]:
        groups = db.session.scalars(
            select(Group)
            .where(
                Group.visibility == "open",
                Group.archived_at.is_(None),
                Group.deleted_at.is_(None),
            )
            .order_by(Group.name)
        ).all()
        mine = set(
            db.session.scalars(
                select(member_groups.c.group_id).where(
                    member_groups.c.member_id == member_id
                )
            )
        )
        counts = dict(
            db.session.execute(
                select(member_groups.c.group_id, func.count()).group_by(
                    member_groups.c.group_id
                )
            ).all()
        )
        return [
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "color": g.color,
                "iconName": g.icon_name,
                "type": g.type,
                "memberCount": counts.get(g.id, 0),
                "joined": g.id in mine,
            }
            for g in groups
        ]

    @staticmethod
    def _open_group(group_id: int) -> Group:
        group = db.session.get(Group, group_id)
        if group is None or group.deleted_at is not None or group.archived_at:
            raise_error(404, "NOT_FOUND", "Group not found")
        if group.visibility != "open":
            raise_error(403, "GROUP_NOT_SELF_JOIN", "Ask a group lead to add you")
        return group

    @staticmethod
    def join(group_id: int, member: Member) -> None:
        group = SelfJoinService._open_group(group_id)
        GroupService.add_member(group, member)
        log_audit(member.id, "join_group", "Group", group.id, group.name)

    @staticmethod
    def leave(group_id: int, member: Member) -> None:
        group = SelfJoinService._open_group(group_id)
        GroupService.remove_member(member.id, group.id)
        log_audit(member.id, "leave_group", "Group", group.id, group.name)
