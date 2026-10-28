"""Backwards-compatible re-export from vollbuild.core.tasks.mail_tasks."""

from vollbuild.core.tasks.mail_tasks import (
    annotations,
    datetime,
    timezone,
    timedelta,
    celery_app,
    logger,
    _DEFAULT_RETENTION_DAYS,
    retention_cleanup,
    cleanup_token_blocklist,
    mail_reconcile,
    verify_protected_mail_addresses,
    reconcile_mail,
    reconcile_entity_forwarding_task,
    check_mailbox_quota,
    ensure_mmas_for_all_entities,
)
