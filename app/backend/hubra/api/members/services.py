"""Member service — business logic decoupled from HTTP layer."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from math import ceil

from flask import current_app
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import selectinload

from hubra.api.mail.services import MailboxService
from hubra.api.permissions import check_grant
from hubra.api.settings.services import SettingService
from hubra.api.utils import csv_safe, escape_like, log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.group import Group
from hubra.core.models.member import (
    Member,
    MembershipTier,
    member_groups,
    member_roles,
)
from hubra.core.models.user import User
from hubra.core.models.role import Role
from hubra.core.models.setting import Setting
from hubra.core.tenant.membership import link_user_to_tenant
from hubra.core.services.wildduck import (
    WildDuckError,
    apply_email_schema,
    make_username,
    try_get_client,
)


# ── Association helpers ────────────────────────────────────────────────────────


def _check_may_remove(member: Member, actor_id: int | None) -> None:
    """403 unless the actor may take every role *member* holds (check_grant):
    archiving or deleting someone takes their roles with them."""
    actor = db.session.get(Member, actor_id) if actor_id is not None else None
    if actor_id is not None and actor is None:
        raise_error(403, "FORBIDDEN", "Insufficient permissions")
    check_grant(actor, taken=list(member.roles or []))


def _check_last_owner(member: Member) -> None:
    """Raise 409 if the member is the last Owner in the tenant.

    Called before disabling, archiving, or removing the Owner role from a member.
    Ensures every tenant always has >=1 Owner.
    """
    owner_role = db.session.scalar(select(Role).where(Role.is_owner.is_(True)))
    if owner_role is None:
        return
    if owner_role not in (member.roles or []):
        return
    owner_count = db.session.scalar(
        select(func.count())
        .select_from(member_roles)
        .where(member_roles.c.role_id == owner_role.id)
    )
    if owner_count <= 1:
        raise_error(409, "LAST_OWNER", "Cannot remove the last Owner of the tenant")


def _check_last_owner_on_role_change(member: Member, new_role_ids: list[int]) -> None:
    """Raise 409 if removing the Owner role would leave the tenant with zero Owners.

    Only triggers when the member currently holds the Owner role AND the new
    role list does not include the Owner role ID.
    """
    owner_role = db.session.scalar(select(Role).where(Role.is_owner.is_(True)))
    if owner_role is None:
        return
    if owner_role not in (member.roles or []):
        return  # Member is not an Owner, no risk
    if owner_role.id in new_role_ids:
        return  # Owner role is being kept
    # Owner role is being removed — check if there are other Owners
    other_owners = db.session.scalar(
        select(func.count())
        .select_from(member_roles)
        .where(member_roles.c.role_id == owner_role.id)
        .where(member_roles.c.member_id != member.id)
    )
    if other_owners is None or other_owners < 1:
        raise_error(409, "LAST_OWNER", "Cannot remove the last Owner of the tenant")


def _clear_member_groups(member_id: int) -> set[int]:
    """Remove member from all groups. Returns affected group IDs for alias sync."""
    group_ids = set(
        db.session.scalars(
            select(member_groups.c.group_id).where(
                member_groups.c.member_id == member_id
            )
        ).all()
    )
    db.session.execute(
        delete(member_groups).where(member_groups.c.member_id == member_id)
    )
    return group_ids


def _clear_member_functions(member_id: int) -> None:
    """Give up the member's functions (Kassier, ...), so the place is free
    for a successor instead of counting against max_holders."""
    from hubra.api.functions.services import _trigger_mail_sync
    from hubra.core.models.function import FunctionHolder

    function_ids = set(
        db.session.scalars(
            select(FunctionHolder.function_id).where(
                FunctionHolder.member_id == member_id
            )
        ).all()
    )
    db.session.execute(
        delete(FunctionHolder).where(FunctionHolder.member_id == member_id)
    )
    for function_id in function_ids:
        _trigger_mail_sync(function_id)


def _clear_member_events(member_id: int) -> None:
    """Give up places at upcoming events, so the waiting list moves up
    instead of a seat staying taken by someone who left."""
    from hubra.api.events.services import EventService
    from hubra.core.errors import ApiError
    from hubra.core.models.event import ClubEvent, EventRegistration, event_attendees

    upcoming = func.coalesce(ClubEvent.end_date, ClubEvent.date) >= date.today()
    event_ids = set(
        db.session.scalars(
            select(EventRegistration.event_id)
            .join(ClubEvent, ClubEvent.id == EventRegistration.event_id)
            .where(
                EventRegistration.member_id == member_id,
                EventRegistration.status.in_(["registered", "approved", "waitlisted"]),
                upcoming,
            )
        ).all()
    ) | set(
        db.session.scalars(
            select(event_attendees.c.event_id)
            .join(ClubEvent, ClubEvent.id == event_attendees.c.event_id)
            .where(event_attendees.c.member_id == member_id, upcoming)
        ).all()
    )
    for event_id in sorted(event_ids):
        try:
            EventService.cancel_registration(event_id, member_id)
        except ApiError:
            pass


def _clear_member_proxies(member_id: int) -> None:
    """Proxies in open polls, given or held, end with the membership."""
    from hubra.core.models.poll import Poll, PollProxy

    open_polls = select(Poll.id).where(Poll.status == "open")
    db.session.execute(
        delete(PollProxy).where(
            (PollProxy.grantor_id == member_id) | (PollProxy.holder_id == member_id),
            PollProxy.poll_id.in_(open_polls),
        )
    )


def _clear_member_all_associations(member_id: int) -> set[int]:
    """Remove member from all groups and functions, upcoming events and
    open-poll proxies. Returns affected group IDs."""
    group_ids = _clear_member_groups(member_id)
    _clear_member_functions(member_id)
    _clear_member_events(member_id)
    _clear_member_proxies(member_id)
    return group_ids


# ── Helpers (not HTTP-specific, shared across service methods) ─────────────────


def _apply_member_filters(query, args: dict[str, str]):
    """Apply search/filter query params to a Member select statement.

    Identity fields (first_name, last_name, email, phone, mobile) live on
    the User model. The query is expected to already have a User join.
    """
    search = args.get("search", "").strip()
    if search:
        pattern = f"%{escape_like(search)}%"
        query = query.where(
            User.first_name.ilike(pattern, escape="\\")
            | User.last_name.ilike(pattern, escape="\\")
            | User.email.ilike(pattern, escape="\\")
            | User.phone.ilike(pattern, escape="\\")
            | User.mobile.ilike(pattern, escape="\\")
        )

    status = args.get("status", "").strip()
    if status:
        query = query.where(Member.status == status)

    membership_type = args.get("membership_type", "").strip()
    if membership_type:
        query = query.where(Member.membership_type == membership_type)

    tier_name = args.get("tier", "").strip()
    if tier_name:
        query = query.join(MembershipTier, Member.tier_id == MembershipTier.id).where(
            MembershipTier.name == tier_name
        )

    group_name = args.get("group", "").strip()
    if group_name:
        query = (
            query.join(member_groups, Member.id == member_groups.c.member_id)
            .join(Group, member_groups.c.group_id == Group.id)
            .where(Group.name == group_name)
        )

    return query


_SORT_COLUMNS = {
    "name": (User.last_name, User.first_name),
    "first_name": (User.first_name,),
    "last_name": (User.last_name,),
    "email": (User.email,),
    "status": (Member.status,),
    "membership_type": (Member.membership_type,),
    "joined": (Member.joined,),
    "created_at": (Member.created_at,),
}


def _apply_sort(query, args: dict[str, str]):
    """Apply sort param to a query. Default: last_name, first_name ascending.

    Identity field sorts (name, first_name, last_name, email) use User
    columns — the query is expected to already have a User join. Member.id
    breaks ties, so pages of the same list never repeat or skip a member
    (Postgres returns rows with equal sort keys in any order).
    """
    sort = args.get("sort", "").strip()
    descending = sort.startswith("-")
    columns = _SORT_COLUMNS.get(sort.lstrip("-+")) if sort else None

    if columns is None:
        return query.order_by(User.last_name, User.first_name, Member.id)

    if descending:
        columns = tuple(c.desc() for c in columns)
    return query.order_by(*columns, Member.id)


def _paginate_query(query, page: int, page_size: int, schema):
    """Paginate a query and return a page dict."""
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    items = db.session.scalars(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "data": schema.dump(items),
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": ceil(total / page_size) if total else 0,
    }


def _default_role() -> Role | None:
    """The role new members get: the club's default, never an admin role.

    Falls back to a role named "Member"; with neither, no role at all (the
    old fallback, the first role by id, could be Admin or Owner).
    """
    role = db.session.scalar(
        select(Role)
        .where(Role.is_default.is_(True))
        .where(Role.is_admin.is_(False), Role.is_owner.is_(False))
        .order_by(Role.id)
        .limit(1)
    )
    if role is None:
        role = db.session.scalar(
            select(Role).where(
                Role.name == "Member",
                Role.is_admin.is_(False),
                Role.is_owner.is_(False),
            )
        )
    return role


def _welcome_back(
    former: Member, user_id: int, tier_id: int | None, tenant_id: int | None = None
) -> Member:
    """Someone who left comes back as the member they were: an ordinary
    member again, whatever roles they had, on the tier they were invited or
    applied for, and with their club mailbox open again."""
    former.archived_at = None
    # A soft-deleted member is archived as well (#42); coming back undoes both.
    former.deleted_at = None
    former.leave_requested_at = None
    role = _default_role()
    former.roles = [role] if role is not None else []
    if tier_id is not None and db.session.get(MembershipTier, tier_id) is not None:
        former.tier_id = tier_id
        former.payment_plan_id = None
    link_user_to_tenant(user_id, tenant_id)
    if not former.is_disabled:
        from hubra.core.services.managed_mail import enable_member_mail

        enable_member_mail(former.id, former.password_hash)
    return former


def _active_member_with_email(email: str) -> bool:
    """Whether the account with ``email`` is a member of the current club."""
    return (
        db.session.scalar(
            select(Member.id)
            .join(User, Member.user_id == User.id)
            .where(func.lower(User.email) == email.strip().lower())
            .where(Member.archived_at.is_(None))
        )
        is not None
    )


def _free_club_address(local: str, domain: str) -> tuple[str, str | None]:
    """A club username, and address when the club has a mail domain, that no
    other member has: ``anna.muster``, then ``anna.muster2``, ``anna.muster3``…

    Two people with the same name joining one club hit the unique
    club_username / public_email columns otherwise.
    """
    n = 1
    while True:
        candidate = local if n == 1 else f"{local}{n}"
        address = f"{candidate}@{domain}" if domain else None
        clash = Member.club_username == candidate
        if address:
            clash = clash | (Member.public_email == address)
        if db.session.scalar(select(Member.id).where(clash).limit(1)) is None:
            return candidate, address
        n += 1


# ── Helper for creating WildDuck mailbox for a new member ──────────────────────


def _provision_member_mailbox(member: Member, club_domain: str) -> None:
    """Create a WildDuck mailbox for the member (non-blocking, best-effort).

    Creates the ManagedMailAddress row first (provisioning_status='pending'),
    then attempts WildDuck provisioning. If WildDuck is unavailable, the MMA
    row still exists and reconcile_mail will provision it later.
    """
    if not club_domain:
        return
    from hubra.core.services.mail_provisioning import resolve_local_part
    from hubra.core.services.managed_mail import get_or_create_for_member

    prefix = member.public_email.split("@")[0] if member.public_email else member.name
    local = resolve_local_part(prefix)
    member.public_email = f"{local}@{club_domain}"
    member.club_username = local

    # A savepoint: a failure here must not undo the new member itself.
    try:
        with db.session.begin_nested():
            addr = get_or_create_for_member(member.id, local, club_domain)
            addr.provisioning_status = "pending"
    except Exception:
        current_app.logger.warning(
            "Failed to create MMA for %s", member.email, exc_info=True
        )
        return
    db.session.commit()

    try:
        from hubra.core.services.mail_provisioning import (
            ensure_alias,
            ensure_mailbox,
        )

        ensure_mailbox(addr, password_hash=member.password_hash)
        ensure_alias(addr)
        addr.provisioning_status = "provisioned"
        db.session.commit()
    except WildDuckError as exc:
        current_app.logger.warning(
            "WildDuck mailbox creation failed for %s: %s", member.email, exc
        )


# ── MemberService (singular) ───────────────────────────────────────────────────


def _apply_member_fk_actions(member_id: int) -> None:
    """Do what each ``ondelete`` on a foreign key to members declares.

    Club schemas are cloned with ``LIKE ... INCLUDING ALL``, which copies no
    foreign keys, so on a real club the database neither cascades nor nulls
    anything: posts, registrations, checkouts, likes and the like stayed
    behind pointing at a member that no longer exists (tests run in public,
    where the FKs exist, so they never saw it). Rows of a mapped class are
    deleted through the ORM, so their own cascades (a post's comments and
    likes) run too.
    """
    from sqlalchemy import update as sql_update

    from hubra.core.tenant.schema_manager import tables_to_clone

    club_tables = set(tables_to_clone())
    classes = {m.local_table.name: m.class_ for m in db.Model.registry.mappers}
    for table in db.metadata.sorted_tables:
        if table.name not in club_tables:
            continue
        for fk in table.foreign_keys:
            if fk.column.table.name != "members" or not fk.ondelete:
                continue
            column = fk.parent
            action = fk.ondelete.upper()
            if action == "SET NULL":
                db.session.execute(
                    sql_update(table)
                    .where(column == member_id)
                    .values({column.name: None})
                )
            elif action == "CASCADE":
                cls = classes.get(table.name)
                if cls is None:
                    db.session.execute(delete(table).where(column == member_id))
                    continue
                for row in db.session.scalars(
                    select(cls).where(column == member_id)
                ).all():
                    db.session.delete(row)
    db.session.flush()


class MemberService:
    """Operations on a single member."""

    @staticmethod
    def get(
        member_id: int, *, archived: bool = False, include_deleted: bool = False
    ) -> Member | None:
        """Return the member, or None if not found / wrong archive state."""
        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .options(
                selectinload(Member.tier),
                selectinload(Member.roles),
                selectinload(Member.groups),
            )
        )
        if member is None:
            return None
        if archived and member.archived_at is None:
            return None
        if not archived and member.archived_at is not None:
            return None
        if not include_deleted and member.deleted_at is not None:
            return None
        return member

    @staticmethod
    def get_or_404(member_id: int, *, archived: bool = False) -> Member:
        """Return member or raise 404."""
        member = MemberService.get(member_id, archived=archived)
        if member is None:
            label = "Archived member" if archived else "Member"
            raise_error(404, "NOT_FOUND", f"{label} {member_id} not found")
        return member  # type: ignore[return-value]

    # ── Association management ────────────────────────────────────────────────

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @staticmethod
    def archive(member_id: int, actor_id: int) -> tuple[Member, set[int]]:
        """Archive the member. Returns (member, affected_group_ids) before commit."""
        if member_id == actor_id:
            raise_error(403, "SELF_DELETE", "You cannot archive your own account")

        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.is_(None))
            .options(selectinload(Member.groups), selectinload(Member.roles))
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        _check_last_owner(member)  # type: ignore[arg-type]
        _check_may_remove(member, actor_id)  # type: ignore[arg-type]

        affected_group_ids = _clear_member_all_associations(member_id)
        member.archived_at = datetime.now(timezone.utc)  # type: ignore[union-attr]
        # Disable the WildDuck mailbox (retain storage, block login).
        from hubra.core.services.managed_mail import disable_member_mail

        disable_member_mail(member_id)
        return member, affected_group_ids  # type: ignore[return-value]

    @staticmethod
    def leave(member: Member) -> set[int]:
        """The member leaves the club: archived, and the account unlinked.

        Returns the affected group ids before commit. The last owner can't
        leave; another owner has to be named first.
        """
        _check_last_owner(member)
        affected_group_ids = _clear_member_all_associations(member.id)
        member.archived_at = datetime.now(timezone.utc)
        member.leave_requested_at = None
        from hubra.core.services.managed_mail import disable_member_mail

        disable_member_mail(member.id)
        if member.user_id is not None:
            from hubra.core.models.user_tenant import UserTenant
            from hubra.core.tenant.context import current_tenant

            tenant = current_tenant()
            if tenant is not None:
                db.session.query(UserTenant).filter_by(
                    user_id=member.user_id, tenant_id=tenant.id
                ).delete()
        return affected_group_ids

    @staticmethod
    def unarchive(member_id: int) -> Member:
        """Unarchive the member. Returns member before commit."""
        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.isnot(None))
            # A deleted member comes back only through a new invite.
            .where(Member.deleted_at.is_(None))
            .options(
                selectinload(Member.tier),
                selectinload(Member.roles),
                selectinload(Member.groups),
            )
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Archived member {member_id} not found")
        if member.user_id is not None:  # type: ignore[union-attr]
            # Someone who left unlinked their account; only they can come
            # back, through an invite. Restoring the row alone listed them
            # as a member who could not open the club.
            from hubra.core.models.user_tenant import UserTenant
            from hubra.core.tenant.context import current_tenant

            tenant = current_tenant()
            if tenant is not None and not db.session.scalar(
                select(UserTenant.user_id).where(
                    UserTenant.user_id == member.user_id,  # type: ignore[union-attr]
                    UserTenant.tenant_id == tenant.id,
                )
            ):
                raise_error(
                    409,
                    "MEMBER_LEFT",
                    "This member left the club; invite them to bring them back",
                )
        member.archived_at = None  # type: ignore[union-attr]
        # Re-enable WildDuck mailbox (only if member is not also disabled)
        if not member.is_disabled:
            from hubra.core.services.managed_mail import enable_member_mail

            enable_member_mail(member_id, member.password_hash)
        return member  # type: ignore[return-value]

    @staticmethod
    def delete_permanent(member_id: int, actor_id: int) -> Member:
        """Hard-delete an archived member.

        Cleans up all FK dependants and the WildDuck mailbox before returning
        so the caller can safely call db.session.delete(member).
        """
        if member_id == actor_id:
            raise_error(
                403,
                "SELF_DELETE",
                "You cannot permanently delete your own account",
            )

        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.isnot(None))
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Archived member {member_id} not found")

        from hubra.core.services.binding_engine import (
            assert_source_deletable,
            assert_mail_address_owner_deletable,
            cascade_delete_disabled,
        )

        assert_source_deletable("member", str(member_id))
        assert_mail_address_owner_deletable("member", member_id)

        from sqlalchemy import update as sql_update

        from hubra.core.models.audit import AuditEntry
        from hubra.core.models.code import Code
        from hubra.core.models.finance import Invoice, Transaction
        from hubra.core.models.mail import MailboxFolder
        from hubra.core.models.notification import Notification
        from hubra.core.models.poll import Poll, PollVote
        from hubra.core.models.translation import Translation

        # Delete child rows whose FK is NOT NULL (cannot be nulled out).
        db.session.execute(
            delete(Notification).where(Notification.member_id == member_id)
        )
        # Sign-in devices and their sessions. In public the FK cascades, but
        # club schemas get these FKs from schema_manager without ON DELETE
        # CASCADE, so there the member delete failed for anyone who had ever
        # opened the club app.
        from hubra.core.models.device_session import Device, Session

        device_ids = select(Device.id).where(Device.member_id == member_id)
        db.session.execute(delete(Session).where(Session.device_id.in_(device_ids)))
        db.session.execute(delete(Device).where(Device.member_id == member_id))
        db.session.execute(
            delete(MailboxFolder).where(MailboxFolder.member_id == member_id)
        )

        # NULL out nullable FK references so financial / audit records survive.
        db.session.execute(
            sql_update(Invoice)
            .where(Invoice.member_id == member_id)
            .values(member_id=None)
        )
        db.session.execute(
            sql_update(Transaction)
            .where(Transaction.member_id == member_id)
            .values(member_id=None)
        )
        db.session.execute(
            sql_update(AuditEntry)
            .where(AuditEntry.actor_id == member_id)
            .values(actor_id=None)
        )
        # Authorship and leadership references: the row stays, unattributed.
        for column in (
            Code.created_by_id,
            Code.updated_by_id,
            Group.lead_id,
            Poll.created_by_id,
            Translation.updated_by_id,
        ):
            db.session.execute(
                sql_update(column.class_)
                .where(column == member_id)
                .values({column.key: None})
            )
        # A vote belongs to its member (member_id is NOT NULL): it goes with them.
        db.session.execute(delete(PollVote).where(PollVote.member_id == member_id))
        _apply_member_fk_actions(member_id)
        # Remove WildDuck mailbox and MMA row (permanent deletion).
        from hubra.core.services.managed_mail import remove_for_member

        remove_for_member(member_id)

        cascade_delete_disabled("member", str(member_id))

        return member  # type: ignore[return-value]

    @staticmethod
    def disable(member_id: int, actor_id: int) -> Member:
        """Disable a member account. Raises 403 for self-disable, 409 for Admin role."""
        if member_id == actor_id:
            raise_error(409, "CONFLICT", "You cannot disable your own account")

        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.is_(None))
            .options(selectinload(Member.roles))
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        if any(r.is_owner for r in (member.roles or [])):
            _check_last_owner(member)
            raise_error(409, "CONFLICT", "Cannot disable an Owner role member")

        # Any admin role, whatever it is called: take the role away first.
        if any(r.is_admin for r in (member.roles or [])):
            raise_error(409, "CONFLICT", "Cannot disable an Admin role member")
        _check_may_remove(member, actor_id)  # type: ignore[arg-type]

        # Disable the WildDuck mailbox (retain storage, block login).
        from hubra.core.services.managed_mail import disable_member_mail

        disable_member_mail(member_id)
        # This club only: the account and the person's other clubs stay as
        # they are.
        member.disabled_at = datetime.now(timezone.utc)
        return member  # type: ignore[return-value]

    @staticmethod
    def enable(member_id: int, actor_id: int) -> Member:
        """Enable a previously disabled member account."""
        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.is_(None))
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        # Re-enable WildDuck mailbox (only if member is not also archived).
        if member.archived_at is None:
            from hubra.core.services.managed_mail import enable_member_mail

            enable_member_mail(
                member_id, member.user.password_hash if member.user else ""
            )
        # This club only; a block on the whole account is the platform's.
        member.disabled_at = None
        return member  # type: ignore[return-value]

    @staticmethod
    def provision(member_id: int, actor_id: int) -> Member:
        """Dispatch mail provisioning task and write audit log. Returns member."""
        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.is_(None))
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        log_audit(
            actor_id=actor_id,
            action="provision_member_mail",
            target_type="Member",
            target_id=member_id,
            target_label=member.name,
        )

        from hubra.core.tasks.after_commit import delay_after_commit
        from hubra.core.tasks.wildduck import provision_member_mail

        delay_after_commit(provision_member_mail, member_id)
        return member  # type: ignore[return-value]

    @staticmethod
    def get_member_mail(member_id: int) -> dict:
        """Return the member's mailbox and aliases from WildDuck.

        Uses the shared MailboxService.get_mailbox_totals() for live counts
        and upserts MailboxFolder rows for background sync consistency.
        """
        from sqlalchemy import select as _sel

        from hubra.core.models.managed_mail import ManagedMailAddress as _MMA

        member = MemberService.get(member_id)
        if member is None:
            return {"status": "not_provisioned", "mailbox": None, "aliases": []}

        addr = db.session.scalar(
            _sel(_MMA).where(_MMA.owner_type == "member", _MMA.owner_id == member_id)
        )
        wd_user_id = addr.wildduck_id or addr.wildduck_user_id if addr else None
        if wd_user_id is None:
            return {"status": "not_provisioned", "mailbox": None, "aliases": []}

        wd = try_get_client()
        if wd is None:
            return {
                "status": "service_unavailable",
                "mailbox": None,
                "aliases": [],
            }

        try:
            user = wd.get_user(wd_user_id)
            addresses_result = wd.list_user_addresses(wd_user_id)
        except WildDuckError as exc:
            current_app.logger.warning(
                "WildDuck fetch failed for member %s (wd_id=%s): %s",
                member_id,
                wd_user_id,
                exc,
            )
            return {
                "status": "service_unavailable",
                "mailbox": None,
                "aliases": [],
            }

        quota = user.get("quota") or {}
        total, unseen, mailboxes = MailboxService.get_mailbox_totals(wd_user_id, wd)

        # Upsert MailboxFolder rows for background sync consistency
        if mailboxes:
            try:
                MailboxService.upsert_folders(member_id, mailboxes)
                db.session.commit()
            except (WildDuckError, KeyError):
                pass

        def _bytes_to_gb(b: int) -> float:
            return round(b / (1024**3), 3)

        mailbox = {
            "address": user.get("address", ""),
            "displayName": user.get("name", ""),
            "quotaUsed": _bytes_to_gb(quota.get("used", user.get("storageUsed", 0))),
            "quotaTotal": _bytes_to_gb(quota.get("allowed", 0)),
            "messageCount": total,
            "inboxCount": total,
            "unreadCount": unseen,
            "targets": user.get("targets") or [],
        }

        addresses = addresses_result.get("results", [])
        aliases = [
            {
                "id": a["id"],
                "address": a.get("address", ""),
                "main": a.get("main", False),
            }
            for a in addresses
        ]

        return {
            "status": "provisioned",
            "mailbox": mailbox,
            "aliases": aliases,
        }


# ── MembersService (plural / collection) ───────────────────────────────────────


class MembersService:
    """Operations on the member collection."""

    _member_schema = None
    _members_schema = None
    _create_schema = None
    _update_schema = None

    @staticmethod
    def count() -> dict:
        """Return total non-archived, non-deleted member count with per-status breakdown."""
        rows = db.session.execute(
            select(Member.status, func.count(Member.id))
            .where(Member.archived_at.is_(None))
            .where(Member.deleted_at.is_(None))
            .group_by(Member.status)
        ).all()
        by_status = {status: count for status, count in rows}
        total = sum(by_status.values())
        return {
            "total": total,
            "by_status": {
                "active": by_status.get("active", 0),
                "trial": by_status.get("trial", 0),
                "inactive": by_status.get("inactive", 0),
                "suspended": by_status.get("suspended", 0),
            },
        }

    @staticmethod
    def list(filters: dict | None = None) -> list[dict]:
        """List members with optional filters, sort, and pagination."""
        args = filters or {}

        try:
            page = max(1, int(args.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(100, max(1, int(args.get("pageSize", 25))))
        except (TypeError, ValueError):
            page_size = 25

        archived = args.get("archived", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        archived_filter = (
            Member.archived_at.isnot(None) if archived else Member.archived_at.is_(None)
        )

        include_deleted = args.get("include_deleted", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        deleted_filter = None if include_deleted else Member.deleted_at.is_(None)

        query = select(Member).where(archived_filter)
        if deleted_filter is not None:
            query = query.where(deleted_filter)
        query = query.join(User, Member.user_id == User.id, isouter=True)
        query = _apply_member_filters(query, args)
        query = _apply_sort(query, args)
        query = query.options(
            selectinload(Member.tier),
            selectinload(Member.roles),
            selectinload(Member.groups),
            selectinload(Member.user),
        )

        from hubra.core.schemas.member import MemberSchema

        return _paginate_query(query, page, page_size, MemberSchema(many=True))

    @staticmethod
    def export(filters: dict | None = None) -> tuple[str, bool]:
        """Export filtered member list as CSV. Returns (csv_string, truncated).

        Supports field selection via the ``fields`` query param (comma-separated).
        """
        args = filters or {}

        query = (
            select(Member)
            .where(Member.archived_at.is_(None))
            .where(Member.deleted_at.is_(None))
            .join(User, Member.user_id == User.id, isouter=True)
        )
        query = _apply_member_filters(query, args)
        query = _apply_sort(query, args)
        query = query.options(
            selectinload(Member.tier),
            selectinload(Member.roles),
            selectinload(Member.groups),
            selectinload(Member.user),
        )

        EXPORT_LIMIT = 10000
        members = db.session.scalars(query.limit(EXPORT_LIMIT + 1)).all()
        truncated = len(members) > EXPORT_LIMIT
        if truncated:
            members = members[:EXPORT_LIMIT]

        all_fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "public_email",
            "status",
            "membership_type",
            "tier",
            "role",
            "joined",
            "tool_hours",
            "phone",
            "mobile",
            "birthday",
            "membership_until",
            "address_street",
            "address_house_no",
            "address_postal_code",
            "address_city",
            "address_country",
        ]

        fields_param = args.get("fields", "").strip()
        if fields_param:
            requested = [f.strip() for f in fields_param.split(",") if f.strip()]
            export_fields = [f for f in all_fields if f in requested]
            if not export_fields:
                export_fields = all_fields
        else:
            export_fields = all_fields

        output = io.StringIO()
        # A byte order mark, so Excel reads the file as UTF-8 (umlauts);
        # the member import reads it with utf-8-sig.
        output.write("\ufeff")
        # Semicolons: German and Swiss Excel open CSV with ";" (the import
        # reads both).
        writer = csv.writer(output, delimiter=";")
        writer.writerow(export_fields)
        for m in members:
            row_values = {
                "id": m.id,
                "first_name": m.first_name,
                "last_name": m.last_name,
                "email": m.email,
                "public_email": m.public_email or "",
                "status": m.status,
                "membership_type": m.membership_type,
                "tier": m.tier.name if m.tier else "",
                "role": ", ".join(r.name for r in (m.roles or [])),
                "joined": m.joined.isoformat() if m.joined else "",
                "tool_hours": m.tool_hours,
                "phone": m.phone or "",
                "mobile": m.mobile or "",
                "birthday": m.birthday.isoformat() if m.birthday else "",
                "membership_until": m.membership_until.isoformat()
                if m.membership_until
                else "",
                "address_street": m.address_street or "",
                "address_house_no": m.address_house_no or "",
                "address_postal_code": m.address_postal_code or "",
                "address_city": m.address_city or "",
                "address_country": m.address_country or "",
            }
            writer.writerow([csv_safe(row_values.get(f, "")) for f in export_fields])

        return output.getvalue(), truncated

    @staticmethod
    def invite(data: dict, actor_id: int | None = None) -> dict:
        """Invite someone to the club by email. Returns ``{"invited", "email"}``.

        A club never creates or changes an account (password, email, name and
        contact details are the person's own): the person gets a personal
        link, signs in or signs up with that address and accepts, and the
        member is made then (``add_account``). Personal details sent along
        only greet them in the mail; roles are given after they join.
        """
        from marshmallow import ValidationError

        from hubra.core.schemas.member import MemberCreateSchema
        from hubra.core.tenant.context import current_tenant
        from hubra.core.tenant.invites import send_invite

        try:
            validated = MemberCreateSchema().load(data)
        except ValidationError as exc:
            raise_error(400, "VALIDATION_ERROR", str(exc.messages))
        email = (validated.get("email") or "").strip().lower()
        if not email:
            raise_error(400, "VALIDATION_ERROR", "email is required")
        tenant = current_tenant()
        if tenant is None:
            raise_error(400, "NO_TENANT", "No club selected")
        if _active_member_with_email(email):
            raise_error(409, "CONFLICT", f"{email} is already a member of this club")

        group_ids = validated.get("group_ids") or []
        if group_ids:
            valid = set(
                db.session.scalars(select(Group.id).where(Group.id.in_(group_ids)))
            )
            invalid = set(group_ids) - valid
            if invalid:
                raise_error(
                    400, "VALIDATION_ERROR", f"Invalid group IDs: {sorted(invalid)}"
                )

        actor = db.session.get(Member, actor_id) if actor_id else None
        name = " ".join(
            filter(None, (validated.get("first_name"), validated.get("last_name")))
        )
        invite = send_invite(
            tenant,  # type: ignore[arg-type]
            email,
            actor.name if actor else tenant.name,  # type: ignore[union-attr]
            name=name,
            member_data={
                "tier_id": validated.get("tier_id"),
                "group_ids": group_ids,
                "status": validated.get("status"),
                "membership_type": validated.get("membership_type"),
                "notes": validated.get("notes"),
            },
        )
        log_audit(
            actor_id=actor_id,
            action="invite_member",
            target_type="ClubInvite",
            target_id=invite.id,
            target_label=email,
        )
        return {"invited": True, "email": email}

    @staticmethod
    def add_account(user: User, member_data: dict | None = None) -> Member:
        """Make ``user`` a member of the current club (they accepted an invite).

        Someone who left comes back as the member they were. Leaves the
        commit to the caller.
        """
        data = member_data or {}
        default_role = _default_role()

        former = db.session.scalar(select(Member).where(Member.user_id == user.id))
        if former is not None:
            if former.archived_at is None:
                raise_error(409, "CONFLICT", "You are already a member of this club")
            return _welcome_back(former, user.id, data.get("tier_id"))

        tier_id = data.get("tier_id")
        if tier_id is not None and db.session.get(MembershipTier, tier_id) is None:
            tier_id = None
        group_ids = list(
            db.session.scalars(
                select(Group.id).where(Group.id.in_(data.get("group_ids") or []))
            )
        )

        club_domain = SettingService.get("mail.domain") or ""
        _es = db.session.scalar(
            select(Setting).where(Setting.key == "club.email_schema")  # type: ignore[arg-type]
        )
        email_schema = (
            _es.value if _es and _es.value else None
        ) or "firstname.lastname"
        full_name = f"{user.first_name} {user.last_name}"
        public_email = (
            apply_email_schema(full_name, email_schema, club_domain)
            if club_domain
            else None
        )
        username, public_email = _free_club_address(
            public_email.split("@")[0] if public_email else make_username(full_name),
            club_domain if public_email else "",
        )

        member = Member(
            user_id=user.id,
            public_email=public_email,
            club_username=username,
            tier_id=tier_id,
            status=data.get("status") or "active",
            notes=data.get("notes"),
            joined=date.today(),
            membership_type=data.get("membership_type") or "regular",
        )
        if default_role:
            member.roles = [default_role]
        db.session.add(member)
        db.session.flush()
        link_user_to_tenant(user.id)

        if group_ids:
            db.session.execute(
                insert(member_groups),
                [{"member_id": member.id, "group_id": gid} for gid in group_ids],
            )

        log_audit(
            actor_id=member.id,
            action="accept_invite",
            target_type="Member",
            target_id=member.id,
            target_label=member.name,
        )

        # WildDuck mailbox creation — non-blocking
        _provision_member_mailbox(member, club_domain)

        db.session.refresh(member)

        from hubra.core.services.binding_engine import sync_for_source

        sync_for_source("member", str(member.id))

        return member

    @staticmethod
    def update(member_id: int, data: dict, actor_id: int) -> dict:
        """Update a member's fields and associations. Returns serialized member."""
        from hubra.core.schemas.member import MemberUpdateSchema

        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.is_(None))
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        schema = MemberUpdateSchema()
        try:
            validated = schema.load(data)
        except Exception as exc:
            from marshmallow import ValidationError

            if isinstance(exc, ValidationError):
                raise_error(400, "VALIDATION_ERROR", str(exc.messages))
            raise

        # Email uniqueness if changed — check against User table (global)
        if "email" in validated and validated["email"] != member.email:
            conflict = db.session.scalar(
                select(User.id)
                .where(User.email == validated["email"])
                .where(User.id != member.user_id)
            )
            if conflict is not None:
                raise_error(409, "CONFLICT", "Email already in use")

        # Mail flag loop detection
        if validated.get("forwarding_enabled") is True:
            club_domain = SettingService.get("mail.domain") or ""
            private_email = member.email or ""
            private_domain = (
                private_email.split("@")[-1] if "@" in private_email else ""
            )
            if club_domain and private_domain == club_domain:
                raise_error(
                    409,
                    "LOOP_DETECTED",
                    "Forwarding to a club domain address would create a mail loop",
                )

        # Identity fields — proxy to User
        identity_fields = [
            "first_name",
            "last_name",
            "email",
            "avatar_color",
            "must_change_password",
            "phone",
            "mobile",
            "birthday",
            "emergency_contact",
        ]
        address_fields = [
            "address_street",
            "address_house_no",
            "address_postal_code",
            "address_city",
            "address_country",
        ]
        # These live on the person's account, shared with their other clubs:
        # the club reads them, and only the person changes them.
        if member.user and any(
            field in validated and validated[field] != getattr(member.user, field)
            for field in (*identity_fields, *address_fields)
        ):
            raise_error(
                403,
                "ACCOUNT_FIELDS_READ_ONLY",
                "Name, email and contact details belong to the member's own "
                "account; they change them themselves",
            )

        # Tenant-specific scalar fields — set directly on Member
        tenant_fields = [
            "tier_id",
            "status",
            "notes",
            "tool_hours",
            "joined",
            "membership_type",
            "membership_until",
            "custom_fields",
        ]
        if (
            validated.get("tier_id") is not None
            and db.session.get(MembershipTier, validated["tier_id"]) is None
        ):
            raise_error(400, "VALIDATION_ERROR", "Unknown membership tier")
        if "tier_id" in validated and validated["tier_id"] != member.tier_id:
            # A payment plan belongs to one tier; on the new one they start
            # on its own billing cycle and may pick one of its plans.
            member.payment_plan_id = None
        for field in tenant_fields:
            if field in validated:
                setattr(member, field, validated[field])

        # Mail flags via MMA
        from hubra.core.models.managed_mail import ManagedMailAddress as _MMA

        addr = db.session.scalar(
            select(_MMA).where(_MMA.owner_type == "member", _MMA.owner_id == member_id)
        )
        mail_flag_changed = False
        if "forwarding_enabled" in validated and addr is not None:
            addr.forwarding_enabled = validated["forwarding_enabled"]
            addr.forward_enabled = validated["forwarding_enabled"]
            mail_flag_changed = True
        if "retention_days" in validated:
            member.retention_days = validated["retention_days"]
            mail_flag_changed = True

        # club_username uniqueness check
        if "club_username" in validated and validated["club_username"] is not None:
            conflict = db.session.scalar(
                select(Member.id)
                .where(Member.club_username == validated["club_username"])
                .where(Member.id != member_id)
            )
            if conflict is not None:
                raise_error(409, "CONFLICT", "Username already taken")
            member.club_username = validated["club_username"]
        elif "club_username" in validated and validated["club_username"] is None:
            member.club_username = None

        # Recompute public_email whenever name or username changes
        if any(f in validated for f in ("first_name", "last_name", "club_username")):
            domain = SettingService.get("mail.domain") or ""
            if domain:
                if member.club_username:
                    member.public_email = f"{member.club_username}@{domain}"
                else:
                    _es = db.session.scalar(
                        select(Setting).where(Setting.key == "club.email_schema")  # type: ignore[arg-type]
                    )
                    email_schema = (
                        _es.value if _es and _es.value else None
                    ) or "firstname.lastname"
                    full_name = f"{member.first_name} {member.last_name}"
                    member.public_email = apply_email_schema(
                        full_name, email_schema, domain
                    )

                # Update member MMA address if public_email changed
                from hubra.core.models.managed_mail import ManagedMailAddress
                from hubra.core.services.managed_mail import change_mail_prefix

                mma = db.session.scalar(
                    select(ManagedMailAddress).where(
                        ManagedMailAddress.owner_type == "member",
                        ManagedMailAddress.owner_id == member.id,
                        ManagedMailAddress.fixed_forward_targets.is_(None),
                    )
                )
                if mma is not None and mma.address != member.public_email:
                    new_local = (
                        member.public_email.split("@")[0]
                        if "@" in member.public_email
                        else member.public_email
                    )
                    try:
                        change_mail_prefix(mma, new_local, domain)
                    except Exception:
                        current_app.logger.exception(
                            "Could not rename mail address %s to %s@%s",
                            mma.address,
                            new_local,
                            domain,
                        )
                    # A taken name gets a numbered address (or none on
                    # failure): show the one the mail actually goes to.
                    member.public_email = mma.address

        # Replace group associations
        old_group_ids: set[int] = set()
        if "group_ids" in validated:
            if validated["group_ids"]:
                valid_group_ids = set(
                    db.session.scalars(
                        select(Group.id).where(Group.id.in_(validated["group_ids"]))
                    ).all()
                )
                invalid = set(validated["group_ids"]) - valid_group_ids
                if invalid:
                    raise_error(
                        400,
                        "VALIDATION_ERROR",
                        f"Invalid group IDs: {sorted(invalid)}",
                    )
            old_group_ids = _clear_member_groups(member_id)
            if validated["group_ids"]:
                db.session.execute(
                    insert(member_groups),
                    [
                        {"member_id": member_id, "group_id": gid}
                        for gid in validated["group_ids"]
                    ],
                )

        # Replace role associations
        if "role_ids" in validated:
            role_ids = validated["role_ids"] or []
            _check_last_owner_on_role_change(member, role_ids)
            if role_ids:
                valid_role_ids = set(
                    db.session.scalars(
                        select(Role.id).where(Role.id.in_(role_ids))
                    ).all()
                )
                invalid = set(role_ids) - valid_role_ids
                if invalid:
                    raise_error(
                        400,
                        "VALIDATION_ERROR",
                        f"Invalid role IDs: {sorted(invalid)}",
                    )
                roles = db.session.scalars(
                    select(Role).where(Role.id.in_(role_ids))
                ).all()
            else:
                roles = []
            before = {r.id: r for r in (member.roles or [])}
            after = {r.id: r for r in roles}
            check_grant(
                db.session.get(Member, actor_id) if actor_id else None,
                given=[r for rid, r in after.items() if rid not in before],
                taken=[r for rid, r in before.items() if rid not in after],
            )
            member.roles = list(roles)
            from hubra.api.permissions import invalidate_member_permissions

            invalidate_member_permissions(member_id)

        log_audit(
            actor_id=actor_id,
            action="update_member",
            target_type="Member",
            target_id=member.id,
            target_label=member.name,
        )

        # Dispatch async WildDuck alias sync for changed groups
        if "group_ids" in validated:
            from hubra.api.groups.services import _trigger_group_mail_sync

            new_group_ids = set(validated["group_ids"])
            changed = old_group_ids | new_group_ids
            for gid in changed:
                _trigger_group_mail_sync(gid)

        # Dispatch mail provisioning if mail flags changed
        if mail_flag_changed:
            from hubra.core.tasks.after_commit import delay_after_commit
            from hubra.core.tasks.wildduck import provision_member_mail

            delay_after_commit(provision_member_mail, member_id)

        from hubra.core.services.binding_engine import sync_for_source

        sync_for_source("member", str(member_id))

        return member  # type: ignore[return-value]

    @staticmethod
    def soft_delete(member_id: int, actor_id: int) -> Member:
        """Soft-delete a member by setting deleted_at. Returns member before commit."""
        if member_id == actor_id:
            raise_error(403, "SELF_DELETE", "You cannot delete your own account")

        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.is_(None))
            .where(Member.deleted_at.is_(None))
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        _check_last_owner(member)  # type: ignore[arg-type]
        _check_may_remove(member, actor_id)  # type: ignore[arg-type]
        member.deleted_at = datetime.now(timezone.utc)  # type: ignore[union-attr]

        # Remove from all groups
        _clear_member_groups(member_id)
        # Sign-in and every permission check refuse archived members; a
        # deleted one must be locked out the same way.
        member.archived_at = member.deleted_at  # type: ignore[union-attr]

        log_audit(
            actor_id=actor_id,
            action="soft_delete_member",
            target_type="Member",
            target_id=member.id,
            target_label=member.name,
        )
        return member  # type: ignore[return-value]

    @staticmethod
    def import_csv(
        rows: list[dict],
        mapping: dict[str, str] | None = None,
        actor_id: int | None = None,
    ) -> dict:
        """Invite the people in a list of CSV row dicts (see ``invite``).

        Args:
            rows: List of dicts (from csv.DictReader).
            mapping: Optional dict mapping CSV column names to member fields.
                     Keys are CSV column names, values are member field names.
            actor_id: The ID of the admin performing the import.

        Returns:
            dict with keys: invited, skipped (already members), errors.
        """
        from marshmallow import ValidationError

        from hubra.core.schemas.member import MemberCreateSchema

        schema = MemberCreateSchema()
        invited = 0
        skipped = 0
        errors: list[dict] = []

        # Default mapping: try exact field name matches
        if mapping is None:
            mapping = {}

        for i, row in enumerate(rows, start=1):
            # Apply mapping
            data = {}
            for csv_col, member_field in mapping.items():
                if csv_col in row and row[csv_col]:
                    data[member_field] = row[csv_col]

            # Also try direct field name matches for unmapped columns
            for col, val in row.items():
                if col not in mapping and val:
                    if col in (
                        "first_name",
                        "last_name",
                        "email",
                        "status",
                        "membership_type",
                        "notes",
                    ):
                        data.setdefault(col, val)

            if "email" not in data or not data["email"]:
                errors.append({"row": i, "error": "Missing required field: email"})
                continue

            try:
                schema.load(data)
            except ValidationError as exc:
                errors.append({"row": i, "error": str(exc.messages)})
                continue

            if _active_member_with_email(data["email"]):
                skipped += 1
                continue

            MembersService.invite(data, actor_id)
            invited += 1

        return {"invited": invited, "skipped": skipped, "errors": errors}

    @staticmethod
    def create_from_application(application: object) -> Member:
        """Create a Member from the application of someone with an account.

        A club never makes an account (see ``invite``); the caller invites
        applicants without one. Does NOT flush or commit — caller is
        responsible.
        """
        existing_user = db.session.scalar(
            select(User).where(
                func.lower(User.email) == application.email.lower()  # type: ignore[attr-defined]
            )
        )
        if existing_user is None:
            raise_error(409, "NO_ACCOUNT", "The applicant has no account yet")
        if existing_user:
            # Someone who left comes back as the member they were.
            former = db.session.scalar(
                select(Member)
                .where(Member.user_id == existing_user.id)
                .where(Member.archived_at.isnot(None))
            )
            if former is not None:
                return _welcome_back(
                    former,
                    existing_user.id,
                    application.wants_tier_id,  # type: ignore[attr-defined]
                )
            existing = db.session.scalar(
                select(Member.id).where(Member.user_id == existing_user.id)
            )
            if existing:
                raise_error(
                    409,
                    "CONFLICT",
                    f"A member with email {application.email} already exists",  # type: ignore[attr-defined]
                )

        tier = None
        if application.wants_tier_id is not None:  # type: ignore[attr-defined]
            tier = db.session.get(
                MembershipTier,
                application.wants_tier_id,  # type: ignore[attr-defined]
            )
        if tier is None:
            tier = db.session.scalar(select(MembershipTier).order_by(MembershipTier.id))

        role = _default_role()

        club_domain = SettingService.get("mail.domain") or ""
        _es = db.session.scalar(
            select(Setting).where(Setting.key == "club.email_schema")  # type: ignore[arg-type]
        )
        email_schema = (
            _es.value if _es and _es.value else None
        ) or "firstname.lastname"

        public_email = (
            apply_email_schema(application.name, email_schema, club_domain)  # type: ignore[attr-defined]
            if club_domain
            else None
        )

        username = None
        if public_email:
            username, public_email = _free_club_address(
                public_email.split("@")[0], club_domain
            )

        user = existing_user

        member = Member(
            user_id=user.id,
            public_email=public_email,
            club_username=username,
            tier=tier,
            status="trial",
            joined=date.today(),
        )
        if role is not None:
            member.roles = [role]
        db.session.add(member)
        link_user_to_tenant(user.id)
        return member  # type: ignore[return-value]
