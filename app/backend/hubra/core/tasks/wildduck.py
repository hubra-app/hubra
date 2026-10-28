"""WildDuck Celery tasks — async mailbox creation and credential sync with retry."""

from __future__ import annotations

import logging

from hubra.core.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    acks_late=True,
    reject_on_worker_lost=True,
)
def create_wildduck_user(self, member_id: int, temp_password: str = "") -> None:
    """Create a WildDuck mailbox for a newly approved member.

    Creates the ManagedMailAddress row first (provisioning_status='pending'),
    then attempts WildDuck provisioning. If WildDuck is unavailable, the MMA
    row still exists and reconcile_mail will provision it later.

    The temp_password arg is retained for backwards compatibility with
    queued tasks but ignored — the member's stored argon2id hash is used.
    Retries up to 5 times with exponential backoff (10s, 20s, 40s, 80s, 160s).
    """
    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.member import Member
    from hubra.core.services.mail_provisioning import resolve_local_part
    from hubra.core.services.managed_mail import get_or_create_for_member
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    member = db.session.scalar(select(Member).where(Member.id == member_id))
    if member is None:
        logger.warning("create_wildduck_user: member %s not found, skipping", member_id)
        return

    club_domain = _get_club_domain_safe()
    if not club_domain:
        logger.warning(
            "create_wildduck_user: mail.domain not configured, skipping member %s",
            member_id,
        )
        return

    prefix = (
        member.public_email.split("@")[0]
        if member.public_email
        else resolve_local_part(member.name)
    )

    try:
        addr = get_or_create_for_member(member_id, prefix, club_domain)
        addr.provisioning_status = "pending"
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning(
            "create_wildduck_user: failed to create MMA for member %s",
            member_id,
            exc_info=True,
        )
        return

    wd = try_get_client()
    if wd is None:
        logger.debug(
            "create_wildduck_user: WildDuck not configured, MMA pending for member %s",
            member_id,
        )
        return

    try:
        from hubra.core.services.mail_provisioning import (
            ensure_alias,
            ensure_mailbox,
        )

        ensure_mailbox(addr, password_hash=member.password_hash)
        ensure_alias(addr)
        addr.provisioning_status = "provisioned"
        db.session.commit()
        logger.info(
            "create_wildduck_user: mailbox created for member %s",
            member_id,
        )
    except WildDuckError as exc:
        db.session.rollback()
        retry_num = self.request.retries
        if retry_num < self.max_retries:
            countdown = 10 * (2**retry_num)
            logger.warning(
                "create_wildduck_user: WildDuck error for member %s, retry %s in %ss: %s",
                member_id,
                retry_num + 1,
                countdown,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error(
            "create_wildduck_user: exhausted retries for member %s: %s",
            member_id,
            exc,
        )


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_wildduck_password(self, member_id: int, new_password: str = "") -> None:
    """Sync a member's password hash to their WildDuck mailbox.

    Uses ensure_mailbox which pushes the argon2id hash with
    hashedPassword=True — plaintext never leaves the app. Also syncs
    quota/retention/name in the same call. The new_password arg is
    retained for backwards compatibility with queued tasks but ignored.
    Retries up to 5 times with exponential backoff (10s, 20s, 40s, 80s, 160s).
    A missing WildDuck config or missing wildduck_id is a no-op (not an error).
    """
    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.managed_mail import ManagedMailAddress
    from hubra.core.models.member import Member
    from hubra.core.services.mail_provisioning import (
        _migrate_legacy_id,
        ensure_mailbox,
    )
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        logger.debug(
            "sync_wildduck_password: WildDuck not configured, skipping member %s",
            member_id,
        )
        return

    addr = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )
    if addr is None:
        logger.debug(
            "sync_wildduck_password: member %s has no MMA, skipping",
            member_id,
        )
        return

    _migrate_legacy_id(addr)
    if not addr.wildduck_id:
        logger.debug(
            "sync_wildduck_password: member %s has no wildduck_id, skipping",
            member_id,
        )
        return

    member = db.session.get(Member, member_id)
    if member is None:
        return

    try:
        ensure_mailbox(addr, password_hash=member.password_hash)
        db.session.commit()
        logger.info(
            "sync_wildduck_password: synced password for member %s",
            member_id,
        )
    except WildDuckError as exc:
        retry_num = self.request.retries
        if retry_num < self.max_retries:
            countdown = 10 * (2**retry_num)
            logger.warning(
                "sync_wildduck_password: WildDuck error for member %s, retry %s in %ss: %s",
                member_id,
                retry_num + 1,
                countdown,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error(
            "sync_wildduck_password: exhausted retries for member %s: %s",
            member_id,
            exc,
        )


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
    reject_on_worker_lost=True,
)
def remove_wildduck_alias(self, alias_id: str) -> None:
    """Remove a WildDuck forwarding alias by its alias ID.

    Called after a group is archived. Best-effort — if WildDuck is
    unreachable, retries up to 3 times with exponential backoff.
    """
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        logger.debug(
            "remove_wildduck_alias: WildDuck not configured, skipping alias %s",
            alias_id,
        )
        return

    try:
        wd.delete_address(alias_id)
        logger.info("remove_wildduck_alias: removed alias %s", alias_id)
    except WildDuckError as exc:
        retry_num = self.request.retries
        if retry_num < self.max_retries:
            countdown = 10 * (2**retry_num)
            logger.warning(
                "remove_wildduck_alias: WildDuck error for alias %s, retry %s in %ss: %s",
                alias_id,
                retry_num + 1,
                countdown,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error(
            "remove_wildduck_alias: exhausted retries for alias %s: %s", alias_id, exc
        )


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    acks_late=True,
    reject_on_worker_lost=True,
)
def provision_member_mail(self, member_id: int) -> None:
    """Provision or update a WildDuck mailbox for a member.

    Uses the new-generation primitives: ensure_mailbox (with password hash),
    ensure_alias, ensure_forwarding (targets array — mailbox keeps a copy).
    Retries up to 5 times with exponential backoff on WildDuckError.
    """
    from sqlalchemy import select

    from hubra.api.utils import log_audit
    from hubra.core.extensions import db
    from hubra.core.models.managed_mail import ManagedMailAddress
    from hubra.core.models.member import Member
    from hubra.core.services.mail_provisioning import (
        _migrate_legacy_id,
        _resolve_member_forward_targets,
        ensure_alias,
        ensure_forwarding,
        ensure_mailbox,
    )
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        logger.debug(
            "provision_member_mail: WildDuck not configured, skipping member %s",
            member_id,
        )
        return

    member = db.session.scalar(select(Member).where(Member.id == member_id))
    if member is None:
        logger.warning("provision_member_mail: member %s not found", member_id)
        return

    addr = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )

    if addr is None:
        logger.debug("provision_member_mail: member %s has no MMA, skipping", member_id)
        return

    _migrate_legacy_id(addr)

    try:
        ensure_mailbox(addr, password_hash=member.password_hash)
        ensure_alias(addr)
        targets = _resolve_member_forward_targets(addr)
        ensure_forwarding(addr, targets)
        addr.provisioning_status = "provisioned"
        db.session.commit()

        log_audit(
            actor_id=None,
            action="provision_member_mail",
            target_type="Member",
            target_id=member_id,
            target_label=member.name,
        )
        logger.info("provision_member_mail: provisioned member %s", member_id)

    except WildDuckError as exc:
        db.session.rollback()
        retry_num = self.request.retries
        if retry_num < self.max_retries:
            countdown = 10 * (2**retry_num)
            logger.warning(
                "provision_member_mail: WildDuck error for member %s, retry %s in %ss: %s",
                member_id,
                retry_num + 1,
                countdown,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error(
            "provision_member_mail: exhausted retries for member %s: %s", member_id, exc
        )


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_managed_address(self, address_id: int) -> None:
    """Sync a ManagedMailAddress with WildDuck.

    For alias-type addresses: creates or updates the WildDuck forwarding alias
    with current targets (group members or function holders).
    For mailbox-type addresses with forwarding: creates/updates the forward filter.

    Retries up to 3 times with exponential backoff on WildDuckError.
    """

    from hubra.core.extensions import db
    from hubra.core.models.managed_mail import ManagedMailAddress
    from hubra.core.services.managed_mail import sync_alias, sync_mailbox_forward
    from hubra.core.services.wildduck import WildDuckError

    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        logger.warning("sync_managed_address: address %s not found", address_id)
        return

    try:
        if addr.address_type == "alias":
            sync_alias(addr)
        elif addr.address_type == "mailbox":
            forward_to = None
            if addr.owner_type == "member" and addr.owner_id is not None:
                from hubra.core.models.member import Member

                member = db.session.get(Member, addr.owner_id)
                if member and addr.forwarding_enabled and member.email:
                    forward_to = member.email
            elif addr.wildduck_filter_id is not None:
                forward_to = f"postmaster@{_get_club_domain_safe()}"
            sync_mailbox_forward(addr, forward_to)
        db.session.commit()
        logger.info(
            "sync_managed_address: synced %s (status=%s)",
            addr.address,
            addr.provisioning_status,
        )
    except WildDuckError as exc:
        db.session.rollback()
        retry_num = self.request.retries
        if retry_num < self.max_retries:
            countdown = 10 * (2**retry_num)
            logger.warning(
                "sync_managed_address: WildDuck error for %s, retry %s in %ss: %s",
                address_id,
                retry_num + 1,
                countdown,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error(
            "sync_managed_address: exhausted retries for %s: %s", address_id, exc
        )


def _get_club_domain_safe() -> str:
    from hubra.api.settings.services import SettingService

    return SettingService.get("mail.domain", default="") or ""


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_sender_from_whitelist(self) -> None:
    """Sync the WildDuck fromWhitelist for the system sender (noreply) user.

    Reads the curated ``mail.system.senders`` InternalKey (populated by
    bindings) and pushes the effective fromWhitelist to the sender's
    WildDuck user. Drift is also repaired by the periodic ``reconcile_mail``.
    """
    from sqlalchemy import select as _select

    from hubra.core.extensions import db
    from hubra.core.models.managed_mail import ManagedMailAddress
    from hubra.core.services.mail_provisioning import sync_from_whitelist_for_mma
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        logger.debug("sync_sender_from_whitelist: WildDuck not configured, skipping")
        return

    from hubra.core.services.key_service import KeyService

    sender_addr = KeyService.get("mail.smtp.user")
    if not sender_addr:
        logger.warning("sync_sender_from_whitelist: no mail.smtp.user key set")
        return

    mma = db.session.scalar(
        _select(ManagedMailAddress).where(
            ManagedMailAddress.address == str(sender_addr)
        )
    )
    if mma is None:
        logger.warning("sync_sender_from_whitelist: no MMA found for %s", sender_addr)
        return

    try:
        sync_from_whitelist_for_mma(mma)
        db.session.commit()
    except WildDuckError as exc:
        retry_num = self.request.retries
        if retry_num < self.max_retries:
            countdown = 60 * (2**retry_num)
            logger.warning(
                "sync_sender_from_whitelist: WildDuck error, retry %s in %ss: %s",
                retry_num + 1,
                countdown,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error("sync_sender_from_whitelist: exhausted retries: %s", exc)
