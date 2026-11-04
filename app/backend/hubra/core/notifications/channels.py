"""Notifications through a connected app (a Discord direct message).

The hook gets ``payload`` with ``id``, ``kind``, ``title`` and ``msg`` (in
the person's language), ``link`` (a club app path), ``topic`` and
``locale``; it returns True when the message went out and raises
``apps.AppError`` with a reason when it can't.

A provider whose handler has a ``deliver_notification(connection,
external_id, payload)`` hook is a notification channel named after its code
("discord"). A member has the channel when the club has a live connection
of that provider and the member linked an account there. It is off until the
member turns it on per topic (Mein Konto › Benachrichtigungen), next to the
bell, push and mail.

Each new notification for such a member is handed to the hook from a Celery
task after the commit, inside the club.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)


def providers() -> dict[str, str]:
    """Providers that can deliver notifications: ``{code: name}``."""
    from hubra.core import apps
    from hubra.core.modules import registry

    registry.load()
    out = {}
    for module in registry.all():
        for app in module.apps:
            if apps.hook(app, "deliver_notification") is not None:
                out[app.code] = app.name
    return out


def _club_codes(
    tenant_id: int | None, connection=None, check_enabled: bool = True
) -> set[str]:
    """Codes with a live connection in the club (and, unless
    *check_enabled* is off, their module on)."""
    from hubra.core.models.connected_app import ConnectedApp

    codes = providers()
    if not codes or tenant_id is None:
        return set()
    query = select(ConnectedApp.provider).where(
        ConnectedApp.tenant_id == tenant_id,
        ConnectedApp.status == "active",
        ConnectedApp.provider.in_(codes),
    )
    rows = (connection or db.session).execute(query).scalars().all()
    if not check_enabled:
        return set(rows)
    from hubra.core.modules import is_enabled, registry

    out = set()
    for code in rows:
        found = registry.app_provider(code)
        if found and is_enabled(found[0].code, tenant_id=tenant_id):
            out.add(code)
    return out


def available(member) -> list[str]:
    """The app channels *member* can turn on (in the current club)."""
    from hubra.core.models.connected_app import ExternalAccount
    from hubra.core.tenant.context import current_tenant

    if member is None or member.user_id is None:
        return []
    tenant = current_tenant()
    codes = _club_codes(tenant.id if tenant else None)
    if not codes:
        return []
    linked = set(
        db.session.scalars(
            select(ExternalAccount.provider).where(
                ExternalAccount.user_id == member.user_id,
                ExternalAccount.provider.in_(codes),
            )
        ).all()
    )
    return sorted(codes & linked)


def queue(connection, target) -> None:
    """From the Notification ``after_insert`` listener: queue the app
    deliveries the member asked for."""
    from hubra.core.notifications.prefs import wants
    from hubra.core.models.connected_app import ExternalAccount
    from hubra.core.models.member import Member
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    if tenant is None:
        return
    # Inside a flush: only the raw connection, no module state lookups (the
    # task checks that the module is on).
    codes = _club_codes(tenant.id, connection, check_enabled=False)
    if not codes:
        return
    row = connection.execute(
        select(Member.user_id, Member.notify_prefs).where(Member.id == target.member_id)
    ).first()
    if row is None or row.user_id is None:
        return
    topic = getattr(target, "topic", None)
    wanted = [c for c in codes if wants(row.notify_prefs, topic, c)]
    if not wanted:
        return
    linked = set(
        connection.execute(
            select(ExternalAccount.provider).where(
                ExternalAccount.user_id == row.user_id,
                ExternalAccount.provider.in_(wanted),
            )
        )
        .scalars()
        .all()
    )
    if not linked:
        return
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.connected_app_tasks import deliver_app_notification

    payload = {
        "id": target.id,
        "kind": target.kind,
        "title": target.title,
        "msg": target.msg,
        "link": getattr(target, "link", None),
        "topic": topic,
    }
    for code in sorted(linked):
        delay_after_commit(deliver_app_notification, code, target.member_id, payload)


def deliver(code: str, member_id: int, payload: dict) -> int:
    """In the club: give *payload* to each live connection of *code* for the
    member's linked account. Returns how many took it."""
    from hubra.core import apps
    from hubra.core.models.connected_app import ExternalAccount
    from hubra.core.models.member import Member
    from hubra.core.tenant.context import current_tenant

    from hubra.core.modules import is_enabled

    tenant = current_tenant()
    found = apps.provider(code)
    if tenant is None or found is None or not is_enabled(found[0].code):
        return 0
    hook = apps.hook(found[1], "deliver_notification")
    member = db.session.get(Member, member_id)
    if hook is None or member is None or member.user_id is None:
        return 0
    if member.archived_at is not None or member.is_blocked:
        return 0
    external_id = db.session.scalar(
        select(ExternalAccount.external_id).where(
            ExternalAccount.user_id == member.user_id,
            ExternalAccount.provider == code,
        )
    )
    if not external_id:
        return 0
    from hubra.core.models.user import User
    from hubra.core.services.notification_text import translate

    user = db.session.get(User, member.user_id)
    locale = (user.language if user else None) or "de-CH"
    title, msg = translate(payload.get("title", ""), payload.get("msg", ""), locale)
    payload = {**payload, "title": title, "msg": msg, "locale": locale}
    sent = 0
    for conn in apps.for_tenant(tenant.id, code):
        try:
            if hook(conn, external_id, payload):
                sent += 1
                break  # one message is enough, even with two servers
        except apps.AppError as exc:
            apps.record(conn, "notified", False, str(exc)[:500])
        except Exception:
            _log.exception(
                "%s: delivering notification %s failed", code, payload.get("id")
            )
    db.session.commit()
    return sent
