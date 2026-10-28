"""Celery task for sending transactional emails asynchronously.

Usage:
    from hubra.core.tasks.email_tasks import send_email_task
    send_email_task.delay(
        to_email="member@example.com",
        to_name="Alice",
        subject="Welcome",
        body_html="<p>Hello</p>",
        body_text="Hello",
    )
"""

from __future__ import annotations

import logging

from hubra.core.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_email_task(
    self,
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    body_text: str,
    attachments: list | None = None,
) -> None:
    """Send a transactional email asynchronously with Celery retry.

    Retries up to 3 times on delivery failures (transient SMTP errors).
    """
    from hubra.core.services.email import _send

    try:
        sent = _send(
            to_email, to_name, subject, body_html, body_text, attachments=attachments
        )
        if not sent:
            raise RuntimeError("Email delivery returned False")
    except Exception as exc:
        logger.warning(
            "send_email_task failed (attempt %d/%d): %s",
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        raise self.retry(exc=exc)
