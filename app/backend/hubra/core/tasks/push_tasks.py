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
    held: bool = False,
) -> dict:
    from hubra.core.notifications.push import deliver
    from hubra.core.notifications.quiet import wait_for_user

    # In the account's quiet hours the push waits until they end (once).
    wait = 0 if held else wait_for_user(user_id)
    if wait:
        send_push_task.apply_async(
            kwargs={
                "user_id": user_id,
                "tenant_id": tenant_id,
                "notification_id": notification_id,
                "kind": kind,
                "title": title,
                "msg": msg,
                "link": link,
                "held": True,
            },
            countdown=wait,
        )
        return {"held": wait}
    return deliver(user_id, tenant_id, notification_id, kind, title, msg, link)
