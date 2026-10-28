"""Backwards-compatible re-export from vollbuild.core.tasks.wildduck."""

from vollbuild.core.tasks.wildduck import (
    annotations,
    celery_app,
    logger,
    create_wildduck_user,
    sync_wildduck_password,
    remove_wildduck_alias,
    provision_member_mail,
    sync_managed_address,
    _get_club_domain_safe,
    _find_smtp_user_id,
    sync_sender_from_whitelist,
)
