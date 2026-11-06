"""Celery tasks for Discord Linked Roles (``services.discord_roles``) and
for notifications sent through a connected app (a Discord direct message).
"""

from __future__ import annotations

import logging

from hubra.core.extensions import db
from hubra.core.tasks import celery_app

_log = logging.getLogger(__name__)


@celery_app.task(
    name="hubra.core.tasks.connected_app_tasks.push_role_connection",
    bind=True,
    max_retries=3,
    ignore_result=True,
)
def push_role_connection(self, account_id: int) -> bool:
    from hubra.core.models.connected_app import ExternalAccount
    from hubra.core.services import discord_roles

    acc = db.session.get(ExternalAccount, account_id)
    if acc is None:
        return False
    try:
        sent = discord_roles.push(acc)
    except discord_roles.RoleConnectionError as exc:
        db.session.commit()  # a refreshed token is kept
        if exc.status is None or exc.status == 429 or exc.status >= 500:
            raise self.retry(exc=exc, countdown=60) from exc
        _log.info("discord: role connection for account %s: %s", account_id, exc)
        return False
    db.session.commit()
    return sent


@celery_app.task(
    name="hubra.core.tasks.connected_app_tasks.push_all_role_connections",
    ignore_result=True,
)
def push_all_role_connections() -> int:
    """Nightly: joins, leaves and archived members change the values."""
    from hubra.core.services import discord_roles

    return discord_roles.push_all()


@celery_app.task(
    name="hubra.core.tasks.connected_app_tasks.deliver_app_notification",
    ignore_result=True,
)
def deliver_app_notification(provider: str, member_id: int, payload: dict) -> int:
    """Hand one bell notification to a connected app's ``deliver_notification``
    hook (inside the club; the tenant comes with the task)."""
    from hubra.core.notifications.channels import deliver

    return deliver(provider, member_id, payload)


@celery_app.task(
    name="hubra.core.tasks.connected_app_tasks.send_account_dm",
    ignore_result=True,
)
def send_account_dm(
    external_id: str, kind: str, embed: dict, components: list | None = None
) -> bool:
    """A Discord direct message to an account, outside a club (a sign-in
    alert, an answer to a request): ``core/notifications/account_dm.py``."""
    from hubra.core.notifications.account_dm import deliver

    return deliver(external_id, kind, embed, components)
