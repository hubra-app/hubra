"""Mail service — business logic for mailboxes, aliases, and member mail provisioning."""

from __future__ import annotations

import secrets
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from sqlalchemy import select

from hubra.api.settings.services import SettingService
from hubra.api.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.group import Group
from hubra.core.models.mail import MailboxFolder
from hubra.core.models.member import Member
from hubra.core.services.wildduck import (
    WildDuckClient,
    WildDuckError,
    try_get_client,
)


def _wd_required() -> WildDuckClient:
    """Return WildDuck client or raise 503."""
    wd = try_get_client()
    if wd is None:
        raise_error(
            503, "SERVICE_UNAVAILABLE", "Mail server integration is not configured"
        )
    return wd


def _bytes_to_gb(b: int) -> float:
    return round(b / (1024**3), 3)


def _gb_to_bytes(gb: float) -> int:
    return int(gb * 1024**3)


# ── MailboxService ─────────────────────────────────────────────────────────────


class MailboxService:
    """Operations on a single WildDuck mailbox/user."""

    @staticmethod
    def get_mailbox_totals(
        wd_id: str, wd: WildDuckClient | None = None
    ) -> tuple[int, int, list[dict]]:
        """Fetch live mailbox counters from WildDuck, summed across all folders.

        Returns (message_count, unread_count, raw_mailboxes).
        """
        wd = wd or try_get_client()
        if wd is None:
            return 0, 0, []
        try:
            result = wd.list_mailboxes(wd_id, counters=True)
            mailboxes = result.get("results", [])
            total = sum(mb.get("total", 0) for mb in mailboxes)
            unseen = sum(mb.get("unseen", 0) for mb in mailboxes)
            return total, unseen, mailboxes
        except WildDuckError:
            return 0, 0, []

    @staticmethod
    def get(wd_id: str) -> dict:
        """Fetch a single WildDuck user by ID. Raises 404 if not found."""
        wd = _wd_required()
        try:
            return wd.get_user(wd_id)
        except WildDuckError as exc:
            if exc.status == 404:
                raise_error(404, "NOT_FOUND", f"Mailbox {wd_id} not found")
            raise

    @staticmethod
    def update(wd_id: str, **fields: Any) -> dict:
        """Update a WildDuck user and return the updated user."""
        wd = _wd_required()
        try:
            wd.update_user(wd_id, **fields)
            return wd.get_user(wd_id)
        except WildDuckError as exc:
            if exc.status == 404:
                raise_error(404, "NOT_FOUND", f"Mailbox {wd_id} not found")
            raise

    @staticmethod
    def delete(wd_id: str) -> dict:
        """Delete a WildDuck mailbox.

        Raises 409 if it belongs to a provisioned member.
        Returns the user dict for audit logging.
        """
        from hubra.core.models.managed_mail import ManagedMailAddress

        addr = db.session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.wildduck_user_id == wd_id
            )
        )
        if addr is not None and addr.owner_type == "member":
            member = db.session.get(Member, addr.owner_id)
            raise_error(
                409,
                "CONFLICT",
                f"Mailbox belongs to member {member.name if member else addr.owner_id} — "
                "disable their mailbox in Member Mail settings first",
            )
        wd = _wd_required()
        try:
            user = wd.get_user(wd_id)
            wd.delete_user(wd_id)
        except WildDuckError as exc:
            if exc.status == 404:
                raise_error(404, "NOT_FOUND", f"Mailbox {wd_id} not found")
            raise
        return user

    @staticmethod
    def upsert_folders(member_id: int, mailboxes: list[dict]) -> None:
        """Create or update MailboxFolder rows from WildDuck mailbox data.

        Also removes stale MailboxFolder rows whose folder no longer exists
        in WildDuck.
        """
        if not mailboxes:
            return
        now = datetime.now(timezone.utc)
        seen: set[str] = set()
        for mb in mailboxes:
            wd_mbox_id = mb.get("id")
            path = mb.get("path", "")
            seen.add(wd_mbox_id)  # type: ignore[arg-type]

            folder = db.session.scalar(
                select(MailboxFolder).where(
                    MailboxFolder.member_id == member_id,
                    MailboxFolder.path == path,
                )
            )
            if folder is None:
                folder = MailboxFolder(
                    member_id=member_id,
                    wildduck_mailbox_id=wd_mbox_id,
                    path=path,
                )
                db.session.add(folder)
            folder.message_count = mb.get("total", 0)
            folder.unread_count = mb.get("unseen", 0)
            folder.last_synced_at = now

        # Remove stale folders that no longer exist in WildDuck
        stale = db.session.scalars(
            select(MailboxFolder).where(
                MailboxFolder.member_id == member_id,
                MailboxFolder.wildduck_mailbox_id.notin_(seen),
            )
        ).all()
        for s in stale:
            db.session.delete(s)

    @staticmethod
    def map_user(
        u: dict,
        member_lookup: dict[str, tuple[int, str]] | None = None,
        wd: WildDuckClient | None = None,
    ) -> dict:
        """Map a WildDuck user object to our Mailbox API shape.

        When *wd* is provided, live folder counts are fetched from WildDuck.
        """
        quota = u.get("quota") or {}
        wd_id = u["id"]
        member_info = member_lookup.get(wd_id) if member_lookup else None

        if member_info and wd is not None:
            total, _unseen, _mailboxes = MailboxService.get_mailbox_totals(wd_id, wd)
            message_count = total
        elif member_info:
            message_count = MailboxFolder.total_message_count(member_info[0])
        else:
            message_count = u.get("storageUsed", 0)

        return {
            "id": wd_id,
            "address": u.get("address", ""),
            "displayName": u.get("name", ""),
            "messageCount": message_count,
            "quotaUsed": _bytes_to_gb(quota.get("used", u.get("storageUsed", 0))),
            "quotaTotal": _bytes_to_gb(quota.get("allowed", 0)),
            "sendOnly": u.get("sendOnly", False),
            "memberId": member_info[0] if member_info else None,
            "memberName": member_info[1] if member_info else None,
            "isProvisioned": member_info is not None,
            "wildduck": u,
        }


# ── MailboxesService ───────────────────────────────────────────────────────────


class MailboxesService:
    """Operations on the collection of WildDuck mailboxes."""

    @staticmethod
    def list() -> list[dict]:
        """List all managed mailboxes with member linkage and DB-synced counts.

        Reads from ManagedMailAddress + MailboxFolder instead of calling
        WildDuck synchronously.  Quota is synced by ``sync_wildduck_quota``
        (every 5 min) and message counts by ``sync_wildduck_message_counts``
        (every 60 s).
        """
        from hubra.core.models.managed_mail import ManagedMailAddress
        from hubra.core.models.mail import MailboxFolder

        addrs = db.session.scalars(
            select(ManagedMailAddress)
            .where(ManagedMailAddress.address_type == "mailbox")
            .order_by(ManagedMailAddress.address)
        ).all()

        member_ids = [a.owner_id for a in addrs if a.owner_type == "member"]
        member_lookup: dict[int, Member] = {}
        if member_ids:
            member_lookup = {
                m.id: m
                for m in db.session.scalars(
                    select(Member).where(Member.id.in_(member_ids))
                ).all()
            }

        result: list[dict] = []
        for addr in addrs:
            member = (
                member_lookup.get(addr.owner_id)  # type: ignore[arg-type]
                if addr.owner_type == "member"
                else None
            )
            message_count = (
                MailboxFolder.total_message_count(addr.owner_id) if member else 0  # type: ignore[arg-type]
            )
            result.append(
                {
                    "id": addr.wildduck_id or addr.wildduck_user_id or "",
                    "address": addr.address,
                    "displayName": addr.display_name or (member.name if member else ""),
                    "messageCount": message_count,
                    "quotaUsed": _bytes_to_gb(addr.quota_used or 0),
                    "quotaTotal": _bytes_to_gb(addr.quota_bytes or 0),
                    "sendOnly": False,
                    "memberId": member.id if member else None,
                    "memberName": member.name if member else None,
                    "isProvisioned": member is not None,
                    "wildduck": {},
                }
            )
        return result

    @staticmethod
    def create(
        username: str,
        display_name: str,
        quota_gb: float,
        password: str | None = None,
    ) -> dict:
        """Create a new WildDuck mailbox. Returns the created mailbox data."""
        wd = _wd_required()
        club_domain = SettingService.get("mail.domain") or ""
        address = f"{username}@{club_domain}" if "@" not in username else username
        pwd = password or secrets.token_urlsafe(16)

        try:
            created = wd.create_user(
                username=username,
                name=display_name or username,
                password=pwd,
                quota_mb=int(quota_gb * 1024),
            )
        except WildDuckError as exc:
            if exc.status == 409:
                raise_error(409, "CONFLICT", f"Mailbox '{address}' already exists")
            raise_error(502, "INTERNAL_ERROR", f"WildDuck: {exc.message}")

        return {
            "id": created.get("id", ""),
            "address": address,
            "displayName": display_name or username,
            "quotaUsed": 0.0,
            "quotaTotal": quota_gb,
            "sendOnly": False,
            "tempPassword": pwd,
        }

    @staticmethod
    def list_members() -> list[dict]:  # type: ignore[valid-type]
        """List all members with their mail provisioning flags (from MMA).

        DB-only — no WildDuck calls.  ``mailbox_exists`` is True when the
        member has an MMA with a ``wildduck_user_id`` (i.e. it was provisioned).
        The ``reconcile_mail`` Celery task (every 15 min) removes orphaned
        MMAs whose WildDuck user no longer exists.
        """
        from hubra.core.models.managed_mail import ManagedMailAddress

        members = db.session.scalars(select(Member)).all()
        member_ids = [m.id for m in members]
        addrs = (
            list(
                db.session.scalars(
                    select(ManagedMailAddress).where(
                        ManagedMailAddress.owner_type == "member",
                        ManagedMailAddress.owner_id.in_(member_ids),
                    )
                ).all()
            )
            if member_ids
            else []
        )
        addr_map = {a.owner_id: a for a in addrs}

        return [
            {
                "id": m.id,
                "name": m.name,
                "public_email": m.public_email,
                "mailbox_enabled": m.id in addr_map,
                "forwarding_enabled": addr_map[m.id].forwarding_enabled
                if m.id in addr_map
                else False,
                "retention_days": m.retention_days,
                "wildduck_id": addr_map[m.id].wildduck_user_id
                if m.id in addr_map
                else None,
                "mailbox_exists": bool(addr_map[m.id].wildduck_user_id)
                if m.id in addr_map
                else False,
            }
            for m in members
        ]

    @staticmethod
    def update_member_mail(member_id: int, updates: dict, actor_id: int) -> dict:
        """Update member mail flags and dispatch provisioning Celery task."""
        from hubra.core.models.managed_mail import ManagedMailAddress

        member = db.session.get(Member, member_id)
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        allowed = {
            "forwarding_enabled",
            "forward_enabled",
            "retention_days",
            "quota_mb",
        }
        filtered = {k: v for k, v in updates.items() if k in allowed}

        fwd_requested = filtered.get(
            "forwarding_enabled", filtered.get("forward_enabled")
        )
        if fwd_requested is True:
            club_domain = SettingService.get("mail.domain") or ""
            private_domain = (
                (member.email or "").split("@")[-1]
                if "@" in (member.email or "")
                else ""
            )
            if club_domain and private_domain == club_domain:
                raise_error(
                    409,
                    "LOOP_DETECTED",
                    "Forwarding to a club domain address would create a mail loop",
                )

        if fwd_requested is True and not member.private_email_verified:
            raise_error(
                422,
                "VERIFICATION_REQUIRED",
                "Private email must be verified before enabling forwarding",
            )

        addr = db.session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "member",
                ManagedMailAddress.owner_id == member_id,
            )
        )

        mail_flag_changed = False
        if fwd_requested is not None and addr is not None:
            addr.forwarding_enabled = fwd_requested
            addr.forward_enabled = fwd_requested
            mail_flag_changed = True
        if "retention_days" in filtered:
            rd = filtered["retention_days"]
            if rd is not None and (not isinstance(rd, int) or rd < 1 or rd > 36500):
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    "retention_days must be between 1 and 36500",
                )
            member.retention_days = rd
            if addr is not None:
                addr.retention = rd * 86400000 if rd else None
            mail_flag_changed = True
        if "quota_mb" in filtered and addr is not None:
            qm = filtered["quota_mb"]
            if qm is not None and (not isinstance(qm, int) or qm < 1):
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    "quota_mb must be a positive integer",
                )
            if qm is not None:
                addr.quota_bytes = qm * 1024 * 1024
            mail_flag_changed = True

        log_audit(
            actor_id=actor_id,
            action="update_member_mail",
            target_type="Member",
            target_id=member_id,
            target_label=f"{member.name} ({member.email})",
        )

        if mail_flag_changed:
            from hubra.core.tasks.wildduck import provision_member_mail

            provision_member_mail.delay(member_id)

        wd_id = (addr.wildduck_id or addr.wildduck_user_id) if addr else None
        return {
            "id": member.id,
            "name": member.name,
            "public_email": member.public_email,
            "mailbox_enabled": addr is not None,
            "forwarding_enabled": addr.forwarding_enabled if addr else False,
            "forward_enabled": addr.forward_enabled if addr else False,
            "retention_days": member.retention_days,
            "quota_bytes": addr.quota_bytes if addr else None,
            "wildduck_id": wd_id,
        }


# ── AliasService ───────────────────────────────────────────────────────────────


class AliasService:
    """Operations on a single WildDuck forwarding alias."""

    @staticmethod
    def is_main_alias(wd_id: str, alias_address: str) -> tuple[int, str] | None:
        """Return (group_id, group_name) if alias is a group's main alias, else None."""
        from hubra.core.models.managed_mail import ManagedMailAddress

        addrs = db.session.scalars(
            select(ManagedMailAddress)
            .where(ManagedMailAddress.owner_type == "group")
            .where(ManagedMailAddress.address_type == "alias")
        ).all()
        for addr in addrs:
            is_main = addr.wildduck_id is not None and addr.wildduck_id == wd_id
            if not is_main and alias_address and addr.address == alias_address:
                is_main = True
            if is_main:
                group = db.session.get(Group, addr.owner_id)
                if group:
                    return group.id, group.name
        return None

    @staticmethod
    def get(wd_id: str) -> dict:
        wd = _wd_required()
        try:
            return wd.get_address(wd_id)
        except WildDuckError:
            raise_error(404, "NOT_FOUND", f"Alias {wd_id} not found")

    @staticmethod
    def update(wd_id: str, delivers_to: list[str]) -> None:
        wd = _wd_required()
        try:
            wd.update_forwarding_alias(wd_id, delivers_to)
        except WildDuckError as exc:
            if exc.status == 404:
                raise_error(404, "NOT_FOUND", f"Alias {wd_id} not found")
            raise

    @staticmethod
    def delete(wd_id: str) -> str:
        """Delete a WildDuck alias. Raises 409 if it's a group main alias.

        Returns the alias address for audit logging.
        """
        alias_address = ""
        wd = _wd_required()
        try:
            alias_info = wd.get_address(wd_id)
            alias_address = alias_info.get("address", "")
        except WildDuckError:
            pass

        main_group = AliasService.is_main_alias(wd_id, alias_address)
        if main_group:
            raise_error(
                409,
                "CONFLICT",
                f"Alias is tied to group {main_group[1]} — "
                "remove the managed mail address first",
            )

        try:
            wd.delete_forwarding_alias(wd_id)
        except WildDuckError as exc:
            if exc.status == 404:
                raise_error(404, "NOT_FOUND", f"Alias {wd_id} not found")
            raise

        return alias_address


# ── AliasesService ─────────────────────────────────────────────────────────────


class AliasesService:
    """Operations on the collection of WildDuck forwarding aliases."""

    @staticmethod
    def list(group_id: int | None = None) -> list[dict]:
        """List all WildDuck forwarding aliases with optional group scoping."""
        from hubra.core.models.managed_mail import ManagedMailAddress

        wd = _wd_required()
        try:
            result = wd.list_addresses()
        except WildDuckError as exc:
            raise_error(502, "INTERNAL_ERROR", f"WildDuck: {exc.message}")

        # Build group lookup from ManagedMailAddress entries
        mma_addrs = db.session.scalars(
            select(ManagedMailAddress)
            .where(ManagedMailAddress.owner_type == "group")
            .where(ManagedMailAddress.address_type == "alias")
        ).all()
        alias_to_group: dict[str, tuple[int, str]] = {}
        alias_by_address: dict[str, tuple[int, str]] = {}
        main_ids: set[str] = set()
        main_addresses: set[str] = set()
        for addr in mma_addrs:
            group = db.session.get(Group, addr.owner_id)
            if group is None:
                continue
            if addr.wildduck_id:
                alias_to_group[addr.wildduck_id] = (group.id, group.name)
                main_ids.add(addr.wildduck_id)
            if addr.address:
                alias_by_address[addr.address] = (group.id, group.name)
                main_addresses.add(addr.address)

        addresses = result.get("results", [])
        data = []
        for a in addresses:
            if a.get("user"):
                continue
            gid, gname = alias_to_group.get(a["id"], (None, None))
            if gid is None:
                gid, gname = alias_by_address.get(a.get("address", ""), (None, None))
            if group_id is not None and (gid is None or gid != group_id):
                continue
            is_main = a["id"] in main_ids or a.get("address", "") in main_addresses
            data.append(
                {
                    "id": a["id"],
                    "address": a.get("address", ""),
                    "type": "Distribution" if a.get("targets") else "Alias",
                    "deliversTo": a.get("targets") or [],
                    "enabled": not a.get("disabled", False),
                    "groupId": gid,
                    "groupName": gname,
                    "isMainAlias": is_main,
                }
            )
        return data

    @staticmethod
    def create(
        address: str,
        delivers_to: list[str],  # type: ignore[valid-type]
        alias_type: str = "Alias",
        group_id: int | None = None,
        name: str | None = None,
    ) -> dict:
        """Create a new WildDuck forwarding alias.

        If linked to a group, ensures the group's managed mail address is
        provisioned and derives targets from it.
        Returns the created alias data.
        """
        from hubra.core.models.managed_mail import ManagedMailAddress

        wd = _wd_required()
        club_domain = SettingService.get("mail.domain") or ""

        if "@" not in address and club_domain:
            address = f"{address}@{club_domain}"

        linked_group: Group | None = None
        if group_id is not None:
            linked_group = db.session.get(Group, int(group_id))
            if linked_group is None:
                raise_error(404, "NOT_FOUND", f"Group {group_id} not found")

            # Ensure the group has a managed mail address
            mma = db.session.scalar(
                select(ManagedMailAddress).where(
                    ManagedMailAddress.owner_type == "group",
                    ManagedMailAddress.owner_id == linked_group.id,
                )
            )
            if mma is None or mma.wildduck_id is None:
                if mma is None:
                    raise_error(
                        409,
                        "CONFLICT",
                        f"Group '{linked_group.name}' has no managed mail address — "
                        "create one in Mail > Group Mail first",
                    )
                # MMA exists but not yet provisioned — sync now
                from celery.exceptions import Retry as CeleryRetry

                from hubra.core.tasks.wildduck import sync_managed_address

                try:
                    sync_managed_address.run(mma.id)
                except CeleryRetry:
                    db.session.refresh(mma)
                if mma.wildduck_id is None:
                    raise_error(
                        409,
                        "CONFLICT",
                        "Group managed mail address could not be provisioned — "
                        "check WildDuck connectivity",
                    )
            delivers_to = [mma.address]

        if not isinstance(delivers_to, list) or not delivers_to:
            raise_error(
                400, "VALIDATION_ERROR", "'deliversTo' must be a non-empty list"
            )

        try:
            created = wd.create_forwarding_alias(
                address=address,
                targets=delivers_to,
                name=name or address,
            )
        except WildDuckError as exc:
            if exc.status == 409:
                raise_error(409, "CONFLICT", f"Alias '{address}' already exists")
            raise_error(502, "INTERNAL_ERROR", f"WildDuck: {exc.message}")

        alias_wd_id = created.get("id", "")

        return {
            "id": alias_wd_id,
            "address": address,
            "type": alias_type,
            "deliversTo": delivers_to,
            "enabled": True,
            "groupId": linked_group.id if linked_group else None,
            "groupName": linked_group.name if linked_group else None,
        }


# ── MailService (miscellaneous) ────────────────────────────────────────────────


class MailService:
    """Miscellaneous mail operations (test email, message log)."""

    @staticmethod
    def send_test(from_addr: str, to_addr: str, subject: str) -> dict:
        """Send a test email through the platform relay."""
        from hubra.core.services import platform_settings

        relay = platform_settings.relay()
        smtp_host = relay.host
        smtp_port = relay.port

        if not smtp_host:
            raise_error(503, "SERVICE_UNAVAILABLE", "SMTP not configured")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.attach(
            MIMEText(
                f"Test email sent from Hubra.\n\n"
                f"From: {from_addr}",
                "plain",
            )
        )

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.ehlo()
                if smtp_port != 25:
                    server.starttls()
                    server.ehlo()
                if relay.user and relay.password:
                    server.login(relay.user, relay.password)
                server.sendmail(from_addr, [to_addr], msg.as_string())
        except Exception as exc:
            raise_error(502, "INTERNAL_ERROR", f"SMTP error: {exc}")

        return {"ok": True, "from": from_addr, "to": to_addr, "subject": subject}


# ── MailAdminService (unified mail administration) ─────────────────────────────


class MailAdminService:
    """Service for the unified Mail Administration screen."""

    @staticmethod
    def resolve_local_part(prefix: str) -> str:
        """Resolve a prefix to a unique local part (server-side preview)."""
        from hubra.core.services.mail_provisioning import resolve_local_part as _rlp

        return _rlp(prefix)

    @staticmethod
    def list_wildduck_live() -> list[dict]:
        """List all live WildDuck users + addresses, annotated managed/orphan.

        Returns a unified list of dicts with:
        ``{id, type, address, name, disabled, targets, quotaUsed, quotaTotal,
           managed, mmaId, kind, linkedId, ownerName}``
        """
        from hubra.core.models.function import Function
        from hubra.core.models.managed_mail import ManagedMailAddress

        wd = _wd_required()
        users: list[dict] = []
        aliases: list[dict] = []

        try:
            user_result = wd.list_users(limit=250)
            users = user_result.get("results", [])
        except WildDuckError as exc:
            raise_error(502, "INTERNAL_ERROR", f"WildDuck: {exc.message}")

        try:
            addr_result = wd.list_addresses()
            aliases = addr_result.get("results", [])
        except WildDuckError:
            pass

        all_mmas = db.session.scalars(select(ManagedMailAddress)).all()
        wd_id_to_mma: dict[str, ManagedMailAddress] = {}
        addr_to_mma: dict[str, ManagedMailAddress] = {}
        for mma in all_mmas:
            wd_id = mma.wildduck_id or mma.wildduck_user_id
            if wd_id:
                wd_id_to_mma[wd_id] = mma
            if mma.address:
                addr_to_mma[mma.address] = mma

        member_ids = {
            mma.owner_id
            for mma in all_mmas
            if mma.owner_type == "member" and mma.owner_id is not None
        }
        group_ids = {
            mma.owner_id
            for mma in all_mmas
            if mma.owner_type == "group" and mma.owner_id is not None
        }
        function_ids = {
            mma.owner_id
            for mma in all_mmas
            if mma.owner_type == "function" and mma.owner_id is not None
        }

        members_by_id: dict[int, Member] = {}
        if member_ids:
            members_by_id = {
                m.id: m
                for m in db.session.scalars(
                    select(Member).where(Member.id.in_(member_ids))
                ).all()
            }
        groups_by_id: dict[int, Group] = {}
        if group_ids:
            groups_by_id = {
                g.id: g
                for g in db.session.scalars(
                    select(Group).where(Group.id.in_(group_ids))
                ).all()
            }
        functions_by_id: dict[int, Function] = {}
        if function_ids:
            functions_by_id = {
                f.id: f
                for f in db.session.scalars(
                    select(Function).where(Function.id.in_(function_ids))
                ).all()
            }

        def _resolve_owner(
            mma: ManagedMailAddress,
        ) -> tuple[str | None, int | None, str | None]:
            if mma.owner_type == "member":
                m = members_by_id.get(mma.owner_id) if mma.owner_id else None
                return (m.name if m else None, mma.owner_id, mma.kind or "member")
            elif mma.owner_type == "group":
                g = groups_by_id.get(mma.owner_id) if mma.owner_id else None
                return (g.name if g else None, mma.owner_id, mma.kind or "group")
            elif mma.owner_type == "function":
                f = functions_by_id.get(mma.owner_id) if mma.owner_id else None
                return (f.name if f else None, mma.owner_id, mma.kind or "function")
            return (None, mma.owner_id, mma.kind or "system")

        result: list[dict] = []

        for u in users:
            uid = u["id"]
            mma = wd_id_to_mma.get(uid)  # type: ignore[assignment]
            quota = u.get("quota") or {}
            owner_name, linked_id, kind = (
                _resolve_owner(mma) if mma else (None, None, None)
            )
            result.append(
                {
                    "id": uid,
                    "type": "mailbox",
                    "address": u.get("address", ""),
                    "name": u.get("name", ""),
                    "disabled": u.get("disabled", False),
                    "targets": u.get("targets") or [],
                    "quotaUsed": quota.get("used", 0),
                    "quotaTotal": quota.get("allowed", 0),
                    "managed": mma is not None,
                    "mmaId": mma.id if mma else None,
                    "kind": kind,
                    "linkedId": linked_id,
                    "ownerName": owner_name,
                }
            )

        for a in aliases:
            if a.get("user"):
                continue
            alias_id = a["id"]
            alias_address = a.get("address", "")
            mma = wd_id_to_mma.get(alias_id) or addr_to_mma.get(alias_address)  # type: ignore[assignment]
            owner_name, linked_id, kind = (
                _resolve_owner(mma) if mma else (None, None, None)
            )
            result.append(
                {
                    "id": alias_id,
                    "type": "alias",
                    "address": alias_address,
                    "name": a.get("name", ""),
                    "disabled": a.get("disabled", False),
                    "targets": a.get("targets") or [],
                    "quotaUsed": None,
                    "quotaTotal": None,
                    "managed": mma is not None,
                    "mmaId": mma.id if mma else None,
                    "kind": kind,
                    "linkedId": linked_id,
                    "ownerName": owner_name,
                }
            )

        return result

    @staticmethod
    def delete_orphan(entry_type: str, entry_id: str, actor_id: int) -> dict:
        """Delete an orphan WildDuck entry (no backing MMA).

        Raises 409 if the entry is managed.
        """
        from hubra.core.models.managed_mail import ManagedMailAddress

        all_mmas = db.session.scalars(select(ManagedMailAddress)).all()
        for mma in all_mmas:
            wd_id = mma.wildduck_id or mma.wildduck_user_id
            if wd_id == entry_id:
                raise_error(
                    409,
                    "CONFLICT",
                    "Cannot delete a managed entry — remove it from its category tab first",
                )
            if mma.wildduck_id == entry_id:
                raise_error(
                    409,
                    "CONFLICT",
                    "Cannot delete a managed alias — remove it from its category tab first",
                )

        wd = _wd_required()
        if entry_type == "mailbox":
            try:
                user = wd.get_user(entry_id)
            except WildDuckError as exc:
                if exc.status == 404:
                    raise_error(404, "NOT_FOUND", f"WildDuck user {entry_id} not found")
                raise
            wd.delete_user(entry_id)
            log_audit(
                actor_id=actor_id,
                action="delete_orphan_mailbox",
                target_type="wildduck_user",
                target_id=entry_id,
                target_label=user.get("address", entry_id),
            )
            return {"ok": True, "type": "mailbox", "id": entry_id}

        elif entry_type == "alias":
            try:
                wd.safe_delete_forwarding_alias(entry_id)
            except WildDuckError as exc:
                if exc.status == 404:
                    raise_error(
                        404, "NOT_FOUND", f"WildDuck alias {entry_id} not found"
                    )
                raise
            log_audit(
                actor_id=actor_id,
                action="delete_orphan_alias",
                target_type="wildduck_alias",
                target_id=entry_id,
                target_label=entry_id,
            )
            return {"ok": True, "type": "alias", "id": entry_id}

        else:
            raise_error(400, "VALIDATION_ERROR", f"Unknown type: {entry_type}")
