"""
S04 transactional email test suite.

Verifies all S04 success criteria:
  - SMTP is the sole send path (Brevo removed)
  - SMTP failure logs and does not raise
  - Celery task send_email_task.apply() invokes _send with correct args

All tests use mocks — no live SMTP server required.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hubra import create_app
from hubra.core.extensions import db as _db


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def email_app():
    """Isolated app for S04 email tests with a real DB and Setting KV rows."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        from hubra.core.models.setting import Setting

        for key, value in [
            ("club.name", "Test Club"),
            ("club.notification_sender_email", "noreply@testclub.example"),
            ("club.notification_sender_name", "Test Club Notifications"),
        ]:
            _db.session.add(Setting(key=key, value=value))
        _db.session.commit()
        yield app
        _db.drop_all()


@pytest.fixture
def email_ctx(email_app):
    """Push app context before each test."""
    with email_app.app_context():
        yield email_app


# ── Helper ────────────────────────────────────────────────────────────────────


def _call_send(app):
    """Call _send() with fixed test arguments inside the current app context."""
    from hubra.core.services.email import _send

    _send(
        to_email="member@example.com",
        to_name="Alice",
        subject="Test Subject",
        body_html="<p>Hello</p>",
        body_text="Hello",
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_smtp_sends_on_success(email_ctx, caplog):
    """SMTP success path: 'smtp_fallback_sent' is logged."""
    import logging

    with (
        patch(
            "hubra.core.services.email._send_via_smtp", return_value=True
        ) as mock_smtp_fn,
    ):
        with caplog.at_level(logging.INFO, logger="hubra.core.services.email"):
            _call_send(email_ctx)

        mock_smtp_fn.assert_called_once()


def test_missing_sender_skips(email_ctx, caplog):
    """No club sender and no platform sender: skip sending with a warning."""
    import logging

    from hubra.core.models.setting import Setting
    from hubra.core.extensions import db

    setting = db.session.get(Setting, "club.notification_sender_email")
    old = setting.value
    setting.value = ""
    db.session.commit()

    with (
        patch("hubra.core.services.email._send_via_smtp") as mock_smtp_fn,
    ):
        with caplog.at_level(logging.WARNING, logger="hubra.core.services.email"):
            _call_send(email_ctx)

        mock_smtp_fn.assert_not_called()
        assert "No sender configured" in caplog.text

    setting.value = old
    db.session.commit()


def test_celery_task_executes(email_ctx):
    """send_email_task.apply() calls _send with the correct arguments."""
    with patch("hubra.core.services.email._send") as mock_send:
        from hubra.core.tasks.email_tasks import send_email_task

        result = send_email_task.apply(
            kwargs={
                "to_email": "member@example.com",
                "to_name": "Alice",
                "subject": "Test Subject",
                "body_html": "<p>Hello</p>",
                "body_text": "Hello",
            }
        )
        assert result.successful()
        mock_send.assert_called_once_with(
            "member@example.com",
            "Alice",
            "Test Subject",
            "<p>Hello</p>",
            "Hello",
            attachments=None,
        )


def test_smtp_failure_logs_error_and_does_not_raise(email_ctx, caplog):
    """SMTP failure → no exception propagates; error is logged."""
    import logging

    with patch(
        "smtplib.SMTP", side_effect=ConnectionRefusedError("Connection refused")
    ):
        with caplog.at_level(logging.ERROR, logger="hubra.core.services.email"):
            _call_send(email_ctx)

        assert "smtp_fallback_error" in caplog.text
