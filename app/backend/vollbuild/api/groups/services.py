"""Group service — business logic decoupled from HTTP layer."""

from __future__ import annotations


from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import selectinload

from vollbuild.api.utils import escape_like, log_audit
from vollbuild.errors import raise_error
from vollbuild.extensions import db
from vollbuild.core.models.group import Group, GroupMembership
from vollbuild.core.models.member import Member, member_groups


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

        for field in (
            "name",
            "lead_id",
            "description",
            "color",
            "icon_name",
            "sessions",
            "tools",
            "type",
            "email_alias",
            "is_public",
            "parent_group_id",
        ):
            if field in data:
                setattr(group, field, data[field])

        log_audit(
            actor_id=actor_id,
            action="update_group",
            target_type="Group",
            target_id=group.id,
            target_label=group.name,
        )

        from vollbuild.core.services.binding_engine import sync_for_source

        sync_for_source("group", str(group.id))

        return group

    @staticmethod
    def delete(group_id: int, actor_id: int) -> None:
        """Archive (delete) a group. Cleans up managed mail addresses first."""
        from vollbuild.core.services.managed_mail import remove_for_group

        group = GroupService.get_by_id(group_id)

        if group.is_default:
            raise_error(409, "CONFLICT", "Default groups cannot be deleted")

        from vollbuild.core.services.binding_engine import (
            assert_source_deletable,
            assert_mail_address_owner_deletable,
            cascade_delete_disabled,
        )

        assert_source_deletable("group", str(group_id))
        assert_mail_address_owner_deletable("group", group_id)

        remove_for_group(group_id)

        db.session.execute(
            delete(member_groups).where(member_groups.c.group_id == group.id)
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
        from vollbuild.core.models.user import User

        query = (
            select(Member)
            .join(member_groups, Member.id == member_groups.c.member_id)
            .join(User, Member.user_id == User.id, isouter=True)
            .where(member_groups.c.group_id == group_id)
            .where(Member.archived_at.is_(None))
            .order_by(User.last_name, User.first_name)
            .options(
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
    def add_member(group: Group, member: Member) -> None:
        """Add a member to a group. Raises 409 if already a member."""
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

        db.session.execute(
            insert(member_groups).values(member_id=member.id, group_id=group.id)
        )

        _trigger_group_mail_sync(group.id)

    @staticmethod
    def remove_member(member_id: int, group_id: int) -> None:
        """Remove a member from a group."""
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

        db.session.execute(
            delete(member_groups).where(
                member_groups.c.member_id == member_id,
                member_groups.c.group_id == group_id,
            )
        )

        # Also remove from GroupMembership if it exists
        db.session.execute(
            delete(GroupMembership).where(
                GroupMembership.member_id == member_id,
                GroupMembership.group_id == group_id,
            )
        )

        _trigger_group_mail_sync(group_id)

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
            .options(selectinload(Group.lead))
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
            tools=data.get("tools", 0),
            type=data.get("type", "interest_group"),
            email_alias=data.get("email_alias"),
            is_public=data.get("is_public", True),
            parent_group_id=data.get("parent_group_id"),
        )
        db.session.add(group)
        db.session.flush()

        log_audit(
            actor_id=actor_id,
            action="create_group",
            target_type="Group",
            target_id=group.id,
            target_label=group.name,
        )

        from vollbuild.core.services.binding_engine import sync_for_source

        sync_for_source("group", str(group.id))

        from vollbuild.core.services.managed_mail import auto_create_mma_for_group

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
    from vollbuild.core.models.managed_mail import ManagedMailAddress

    has_mma = db.session.scalar(
        select(ManagedMailAddress.id).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
        )
    )
    if has_mma is None:
        return

    try:
        from vollbuild.core.tasks.mail_tasks import reconcile_entity_forwarding_task

        reconcile_entity_forwarding_task.delay("group", group_id)
    except Exception:
        from vollbuild.core.services.mail_provisioning import (
            reconcile_entity_forwarding,
        )

        try:
            reconcile_entity_forwarding("group", group_id)
            db.session.commit()
        except Exception:
            db.session.rollback()
