"""Posts: scheduled posts go out when their time comes; reminders for
must-read posts."""

from __future__ import annotations

from hubra.api.posts.services import publish_due_posts, remind_unread
from hubra.core.extensions import db
from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app


@celery_app.task(
    name="hubra.api.posts.tasks.publish_scheduled_posts_task",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def publish_scheduled_posts_task(self) -> dict:
    """Scheduled posts in every club with posts on."""
    return _publish_scheduled_posts()


@per_tenant_job("posts")
def _publish_scheduled_posts() -> dict:
    published = publish_due_posts()
    db.session.commit()
    return {"published": published}


@celery_app.task(
    name="hubra.api.posts.tasks.remind_unread_posts_task",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def remind_unread_posts_task(self) -> dict:
    """Must-read reminders in every club with posts on."""
    return _remind_unread_posts()


@per_tenant_job("posts")
def _remind_unread_posts() -> dict:
    reminded = remind_unread()
    db.session.commit()
    return {"reminded": reminded}
