"""Celery task: push one bell notification to a person's browsers."""

from __future__ import annotations

from hubra.core.tasks import celery_app


@celery_app.task(
    name="hubra.core.tasks.push_tasks.send_push_task",
    bind=True,
    acks_late=True,
    ignore_result=True,
)
def send_push_task(
    self,
    user_id: int,
    tenant_id: int | None,
    notification_id: int,
    kind: str,
    title: str,
    msg: str,
    link: str | None = None,
) -> dict:
    from hubra.core.notifications.push import deliver

    return deliver(user_id, tenant_id, notification_id, kind, title, msg, link)
