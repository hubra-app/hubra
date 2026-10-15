"""Member service — business logic decoupled from HTTP layer."""

from __future__ import annotations

import csv
import io
import secrets
from datetime import date, datetime, timezone
from math import ceil

from flask import current_app
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import selectinload

from vollbuild.api.mail.services import MailboxService
from vollbuild.api.settings.service import SettingsService
from vollbuild.api.utils import escape_like, log_audit
from vollbuild.core.errors import raise_error
from vollbuild.core.extensions import db
from vollbuild.core.models.group import Group
from vollbuild.core.models.member import (
    Member,
    MembershipTier,
    member_groups,
    member_roles,
)
from vollbuild.core.models.user import User
from vollbuild.core.models.role import Role
from vollbuild.core.models.setting import Setting
from vollbuild.core.services import email as email_svc
from vollbuild.core.services.wildduck import (
    WildDuckError,
    apply_email_schema,
    make_username,
    try_get_client,
)


# ── Association helpers ────────────────────────────────────────────────────────


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


def _clear_member_all_associations(member_id: int) -> set[int]:
    """Remove member from all groups. Returns affected group IDs."""
    group_ids = _clear_member_groups(member_id)
    return group_ids


def _remove_member_from_group(member_id: int, group_id: int) -> None:
    """Remove a member from a single group."""
    db.session.execute(
        delete(member_groups).where(
            member_groups.c.member_id == member_id,
            member_groups.c.group_id == group_id,
        )
    )


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
    columns — the query is expected to already have a User join.
    """
    sort = args.get("sort", "").strip()
    if not sort:
        return query.order_by(User.last_name, User.first_name)

    descending = sort.startswith("-")
    field_name = sort.lstrip("-+")

    columns = _SORT_COLUMNS.get(field_name)

    if columns is None:
        return query.order_by(User.last_name, User.first_name)

    if descending:
        columns = tuple(c.desc() for c in columns)
    return query.order_by(*columns)


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


# ── Helper for creating WildDuck mailbox for a new member ──────────────────────


def _provision_member_mailbox(member: Member, club_domain: str) -> None:
    """Create a WildDuck mailbox for the member (non-blocking, best-effort).

    Creates the ManagedMailAddress row first (provisioning_status='pending'),
    then attempts WildDuck provisioning. If WildDuck is unavailable, the MMA
    row still exists and reconcile_mail will provision it later.
    """
    if not club_domain:
        return
    from vollbuild.core.services.mail_provisioning import resolve_local_part
    from vollbuild.core.services.managed_mail import get_or_create_for_member

    prefix = member.public_email.split("@")[0] if member.public_email else member.name
    local = resolve_local_part(prefix)
    member.public_email = f"{local}@{club_domain}"
    member.club_username = local

    try:
        addr = get_or_create_for_member(member.id, local, club_domain)
        addr.provisioning_status = "pending"
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.warning(
            "Failed to create MMA for %s", member.email, exc_info=True
        )
        return

    try:
        from vollbuild.core.services.mail_provisioning import (
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

    @staticmethod
    def set_groups(member_id: int, group_ids: list[int]) -> set[int]:
        """Replace group memberships. Returns old group IDs for alias sync."""
        old_ids = _clear_member_groups(member_id)
        if group_ids:
            db.session.execute(
                insert(member_groups),
                [{"member_id": member_id, "group_id": gid} for gid in group_ids],
            )
        return old_ids

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

        _check_last_owner(member)

        affected_group_ids = _clear_member_all_associations(member_id)
        member.archived_at = datetime.now(timezone.utc)  # type: ignore[union-attr]
        # Disable the WildDuck mailbox (retain storage, block login).
        from vollbuild.core.services.managed_mail import disable_member_mail

        disable_member_mail(member_id)
        return member, affected_group_ids  # type: ignore[return-value]

    @staticmethod
    def unarchive(member_id: int) -> Member:
        """Unarchive the member. Returns member before commit."""
        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.isnot(None))
            .options(
                selectinload(Member.tier),
                selectinload(Member.roles),
                selectinload(Member.groups),
            )
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Archived member {member_id} not found")
        member.archived_at = None  # type: ignore[union-attr]
        # Re-enable WildDuck mailbox (only if member is not also disabled)
        if not member.is_disabled:
            from vollbuild.core.services.managed_mail import enable_member_mail

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

        from vollbuild.core.services.binding_engine import (
            assert_source_deletable,
            assert_mail_address_owner_deletable,
            cascade_delete_disabled,
        )

        assert_source_deletable("member", str(member_id))
        assert_mail_address_owner_deletable("member", member_id)

        from sqlalchemy import update as sql_update

        from vollbuild.core.models.audit import AuditEntry
        from vollbuild.core.models.finance import Invoice, Transaction
        from vollbuild.core.models.mail import MailboxFolder
        from vollbuild.core.models.notification import Notification

        # Delete child rows whose FK is NOT NULL (cannot be nulled out).
        db.session.execute(
            delete(Notification).where(Notification.member_id == member_id)
        )
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
        # Remove WildDuck mailbox and MMA row (permanent deletion).
        from vollbuild.core.services.managed_mail import remove_for_member

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

        if any(r.name == "Admin" for r in (member.roles or [])):
            raise_error(409, "CONFLICT", "Cannot disable an Admin role member")

        # Disable the WildDuck mailbox (retain storage, block login).
        from vollbuild.core.services.managed_mail import disable_member_mail

        disable_member_mail(member_id)
        if member.user:
            member.user.is_disabled = True
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
            from vollbuild.core.services.managed_mail import enable_member_mail

            enable_member_mail(
                member_id, member.user.password_hash if member.user else ""
            )
        if member.user:
            member.user.is_disabled = False
        return member  # type: ignore[return-value]

    @staticmethod
    def set_password(
        member_id: int, password: str, generate: bool = False, must_change: bool = False
    ) -> tuple[str, str]:
        """Set a member's password. Returns (password, action).

        If *generate* is True, a random password is created.
        Returns (password, 'generated') or (password, 'manual').
        """
        member = db.session.scalar(
            select(Member)
            .where(Member.id == member_id)
            .where(Member.archived_at.is_(None))
        )
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        if not generate:
            from vollbuild.api.auth.services import _enforce_password_strength

            _enforce_password_strength(password)
        pwd = secrets.token_urlsafe(12) if generate else password
        if member.user:
            member.user.set_password(pwd)
            member.user.must_change_password = True if generate else must_change

        # Non-blocking WildDuck password sync (sends hashed password via async task)
        if current_app.config.get("WILDDUCK_API_URL"):
            from vollbuild.core.tasks.wildduck import sync_wildduck_password

            sync_wildduck_password.delay(member_id)

        action = "generated" if generate else "manual"
        if generate:
            login_email = member.public_email or (
                member.user.email if member.user else ""
            )
            email_svc.send_welcome(
                member.user.email if member.user else "",
                member.name,
                login_email,
                pwd,
                lang=(member.user.language if member.user else "de-CH") or "de-CH",
            )

        return pwd, action

    @staticmethod
    def verify_email(member_id: int) -> bool:
        """Mark a member's private email as verified. Returns True if newly verified."""
        member = db.session.get(Member, member_id)
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        if member.private_email_verified:
            return False

        if member.user:
            member.user.private_email_verified = True
        return True

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

        from vollbuild.core.tasks.wildduck import provision_member_mail

        provision_member_mail.delay(member_id)
        return member  # type: ignore[return-value]

    @staticmethod
    def get_member_mail(member_id: int) -> dict:
        """Return the member's mailbox and aliases from WildDuck.

        Uses the shared MailboxService.get_mailbox_totals() for live counts
        and upserts MailboxFolder rows for background sync consistency.
        """
        from sqlalchemy import select as _sel

        from vollbuild.core.models.managed_mail import ManagedMailAddress as _MMA

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

        from vollbuild.core.schemas.member import MemberSchema

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
        writer = csv.writer(output)
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
            writer.writerow([row_values.get(f, "") for f in export_fields])

        return output.getvalue(), truncated

    @staticmethod
    def create(
        data: dict,
        actor_id: int | None = None,
        *,
        password: str | None = None,
        must_change_password: bool = True,
    ) -> Member:
        """Create a new member. Returns the Member object.

        If user_id is provided, links the Member to that User.
        If email is provided (without user_id), looks up or creates a User.
        """
        from vollbuild.core.schemas.member import MemberCreateSchema
        from vollbuild.core.models.user import User

        schema = MemberCreateSchema()
        try:
            validated = schema.load(data)
        except Exception as exc:
            from marshmallow import ValidationError

            if isinstance(exc, ValidationError):
                raise_error(400, "VALIDATION_ERROR", str(exc.messages))
            raise

        # Resolve or create the User
        user_id = validated.get("user_id")
        email = validated.get("email")
        first_name = validated.get("first_name", "")
        last_name = validated.get("last_name", "")
        temp_password = (
            password or validated.get("password") or secrets.token_urlsafe(12)
        )

        if user_id:
            user = db.session.get(User, user_id)
            if user is None:
                raise_error(404, "NOT_FOUND", f"User {user_id} not found")
        elif email:
            # Check if a User with this email already exists
            user = db.session.scalar(select(User).where(User.email == email))
            if user is None:
                # Create a new User
                if not first_name or not last_name:
                    name_parts = email.split("@")[0].split(".", 1)
                    first_name = (
                        first_name or name_parts[0].capitalize()
                        if name_parts
                        else "Member"
                    )
                    last_name = last_name or (
                        name_parts[1].capitalize() if len(name_parts) > 1 else ""
                    )
                user = User(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
                user.set_password(temp_password)
                user.must_change_password = must_change_password
                # Apply User-level identity fields from the validated data
                for fld in (
                    "phone",
                    "mobile",
                    "birthday",
                    "address_street",
                    "address_house_no",
                    "address_postal_code",
                    "address_city",
                    "address_country",
                    "emergency_contact",
                ):
                    val = validated.get(fld)
                    if val is not None:
                        setattr(user, fld, val)
                db.session.add(user)
                db.session.flush()
        else:
            raise_error(400, "VALIDATION_ERROR", "user_id or email is required")

        # Check if this user is already a member in this tenant
        existing = db.session.scalar(select(Member).where(Member.user_id == user.id))
        if existing is not None:
            raise_error(409, "CONFLICT", "User is already a member of this tenant")

        group_ids = validated.pop("group_ids", [])
        role_ids = validated.pop("role_ids", []) or []

        if group_ids:
            valid_group_ids = set(
                db.session.scalars(
                    select(Group.id).where(Group.id.in_(group_ids))
                ).all()
            )
            invalid = set(group_ids) - valid_group_ids
            if invalid:
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    f"Invalid group IDs: {sorted(invalid)}",
                )

        if role_ids:
            valid_role_ids = set(
                db.session.scalars(select(Role.id).where(Role.id.in_(role_ids))).all()
            )
            invalid_roles = set(role_ids) - valid_role_ids
            if invalid_roles:
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    f"Invalid role IDs: {sorted(invalid_roles)}",
                )

        club_domain = SettingsService().get("mail.domain") or ""
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
        username = (
            public_email.split("@")[0] if public_email else make_username(full_name)
        )

        joined = date.today()

        member = Member(
            user_id=user.id,
            public_email=public_email,
            club_username=username,
            tier_id=validated.get("tier_id"),
            status=validated.get("status", "trial"),
            notes=validated.get("notes"),
            joined=joined,
            membership_type=validated.get("membership_type", "regular"),
            membership_until=validated.get("membership_until"),
            custom_fields=validated.get("custom_fields"),
        )

        db.session.add(member)
        db.session.flush()

        if role_ids:
            roles = db.session.scalars(select(Role).where(Role.id.in_(role_ids))).all()
            member.roles = list(roles)

        if group_ids:
            db.session.execute(
                insert(member_groups),
                [{"member_id": member.id, "group_id": gid} for gid in group_ids],
            )

        log_audit(
            actor_id=actor_id,
            action="create_member",
            target_type="Member",
            target_id=member.id,
            target_label=member.name,
        )

        # WildDuck mailbox creation — non-blocking
        _provision_member_mailbox(member, club_domain)

        # Welcome email — non-blocking
        login_email = member.email or public_email or ""
        email_svc.send_welcome(
            member.email,
            member.name,
            login_email,
            temp_password,
            lang=getattr(member, "language", "de-CH") or "de-CH",
        )

        db.session.refresh(member)

        from vollbuild.core.services.binding_engine import sync_for_source

        sync_for_source("member", str(member.id))

        return member

    @staticmethod
    def update(member_id: int, data: dict, actor_id: int) -> dict:
        """Update a member's fields and associations. Returns serialized member."""
        from vollbuild.core.schemas.member import MemberUpdateSchema

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
            club_domain = SettingsService().get("mail.domain") or ""
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
        if member.user:
            for field in identity_fields:
                if field in validated:
                    setattr(member.user, field, validated[field])

        # Address fields — proxy to User
        address_fields = [
            "address_street",
            "address_house_no",
            "address_postal_code",
            "address_city",
            "address_country",
        ]
        if member.user:
            for field in address_fields:
                if field in validated:
                    setattr(member.user, field, validated[field])

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
        for field in tenant_fields:
            if field in validated:
                setattr(member, field, validated[field])

        # Mail flags via MMA
        from vollbuild.core.models.managed_mail import ManagedMailAddress as _MMA

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
            domain = SettingsService().get("mail.domain") or ""
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
                from vollbuild.core.models.managed_mail import ManagedMailAddress
                from vollbuild.core.services.managed_mail import change_mail_prefix

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
                        pass

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
                member.roles = list(roles)
            else:
                member.roles = []
            from vollbuild.api.permissions import invalidate_member_permissions

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
            from vollbuild.api.groups.services import _trigger_group_mail_sync

            new_group_ids = set(validated["group_ids"])
            changed = old_group_ids | new_group_ids
            for gid in changed:
                _trigger_group_mail_sync(gid)

        # Dispatch mail provisioning if mail flags changed
        if mail_flag_changed:
            from vollbuild.core.tasks.wildduck import provision_member_mail

            provision_member_mail.delay(member_id)

        from vollbuild.core.services.binding_engine import sync_for_source

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

        member.deleted_at = datetime.now(timezone.utc)  # type: ignore[union-attr]

        # Remove from all groups
        _clear_member_groups(member_id)

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
        """Import members from a list of CSV row dicts.

        Args:
            rows: List of dicts (from csv.DictReader).
            mapping: Optional dict mapping CSV column names to member fields.
                     Keys are CSV column names, values are member field names.
            actor_id: The ID of the admin performing the import.

        Returns:
            dict with keys: created, skipped, errors.
        """
        from vollbuild.core.schemas.member import MemberCreateSchema

        schema = MemberCreateSchema()
        created = 0
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
                        "phone",
                        "mobile",
                        "status",
                        "membership_type",
                        "notes",
                        "address_street",
                        "address_house_no",
                        "address_postal_code",
                        "address_city",
                        "address_country",
                    ):
                        data.setdefault(col, val)

            if "email" not in data or not data["email"]:
                errors.append({"row": i, "error": "Missing required field: email"})
                continue

            if "first_name" not in data or not data["first_name"]:
                errors.append({"row": i, "error": "Missing required field: first_name"})
                continue

            if "last_name" not in data or not data["last_name"]:
                errors.append({"row": i, "error": "Missing required field: last_name"})
                continue

            # Check email uniqueness — against User table (global) and existing Member
            existing_user = db.session.scalar(
                select(User).where(User.email == data["email"])
            )
            if existing_user:
                existing_member = db.session.scalar(
                    select(Member).where(Member.user_id == existing_user.id)
                )
                if existing_member is not None:
                    skipped += 1
                    continue

            try:
                validated = schema.load(data)
            except Exception as exc:
                from marshmallow import ValidationError

                if isinstance(exc, ValidationError):
                    errors.append({"row": i, "error": str(exc.messages)})
                else:
                    errors.append({"row": i, "error": str(exc)})
                continue

            temp_password = secrets.token_urlsafe(12)

            # Create or reuse User
            if existing_user:
                user = existing_user
            else:
                user = User(
                    email=validated["email"],
                    first_name=validated["first_name"],
                    last_name=validated["last_name"],
                )
                user.set_password(temp_password)
                user.must_change_password = True
                if validated.get("phone"):
                    user.phone = validated["phone"]
                if validated.get("mobile"):
                    user.mobile = validated["mobile"]
                db.session.add(user)
                db.session.flush()

            member = Member(
                user_id=user.id,
                tier_id=validated.get("tier_id"),
                status=validated.get("status", "trial"),
                membership_type=validated.get("membership_type", "regular"),
                joined=date.today(),
            )
            db.session.add(member)
            db.session.flush()

            log_audit(
                actor_id=actor_id,
                action="import_member",
                target_type="Member",
                target_id=member.id,
                target_label=member.name,
            )
            created += 1

        return {"created": created, "skipped": skipped, "errors": errors}

    @staticmethod
    def create_from_application(application: object) -> tuple[Member, str]:
        """Create a Member from an Application object.

        Does NOT flush or commit — caller is responsible.
        Returns (member, temp_password).
        """
        existing_user = db.session.scalar(
            select(User).where(User.email == application.email)  # type: ignore[attr-defined]
        )
        if existing_user:
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

        role = db.session.scalar(select(Role).where(Role.name == "Member"))
        if role is None:
            role = db.session.scalar(select(Role).order_by(Role.id))

        temp_password = secrets.token_urlsafe(12)
        club_domain = SettingsService().get("mail.domain") or ""
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

        parts = application.name.split(" ", 1)  # type: ignore[attr-defined]
        username = public_email.split("@")[0] if public_email else None

        # Create or reuse User
        user = db.session.scalar(select(User).where(User.email == application.email))  # type: ignore[attr-defined]
        if user is None:
            user = User(
                email=application.email,  # type: ignore[attr-defined]
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else "",
                avatar_color=application.avatar_color or "#6366f1",  # type: ignore[attr-defined]
            )
            user.set_password(temp_password)
            user.must_change_password = True
            db.session.add(user)
            db.session.flush()

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
        return member, temp_password
