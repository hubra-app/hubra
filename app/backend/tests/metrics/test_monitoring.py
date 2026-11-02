"""
Tests for B4 — Celery task failure alerting.

Covers:
  - task_failure_alert fires on task failure
  - Cooldown prevents repeated alerts
  - check_api_error_rate returns correct status
  - Graceful handling when Redis unavailable
"""

import time
from unittest.mock import patch, MagicMock


from hubra.core.tasks.monitoring import (
    task_failure_alert,
    check_api_error_rate,
    _failure_counts,
    _alert_cooldowns,
)


class TestTaskFailureAlert:
    """Tests for the Celery signal handler."""

    def setup_method(self):
        """Clear state between tests."""
        _failure_counts.clear()
        _alert_cooldowns.clear()

    @patch("hubra.core.tasks.monitoring.alert_error")
    def test_sends_alert_on_failure(self, mock_alert):
        """Failure triggers a Discord alert."""
        sender = MagicMock()
        sender.name = "test_task"
        task_failure_alert(
            sender=sender,
            task_id="abc-123",
            exception=ValueError("boom"),
            args=(),
            kwargs={},
            traceback=None,
        )
        mock_alert.assert_called_once()
        call_kwargs = mock_alert.call_args[1]
        assert "test_task" in call_kwargs["title"]

    @patch("hubra.core.tasks.monitoring.alert_error")
    def test_cooldown_prevents_repeated_alerts(self, mock_alert):
        """Second failure within cooldown window doesn't trigger another alert."""
        sender = MagicMock()
        sender.name = "test_task"

        # First failure
        task_failure_alert(
            sender=sender,
            task_id="1",
            exception=ValueError("boom"),
            args=(),
            kwargs={},
            traceback=None,
        )
        assert mock_alert.call_count == 1

        # Second failure immediately after
        task_failure_alert(
            sender=sender,
            task_id="2",
            exception=ValueError("boom2"),
            args=(),
            kwargs={},
            traceback=None,
        )
        # Should still be 1 (cooldown)
        assert mock_alert.call_count == 1

    @patch("hubra.core.tasks.monitoring.alert_error")
    def test_failure_count_tracked(self, mock_alert):
        """Failure count is tracked correctly."""
        sender = MagicMock()
        sender.name = "test_task"

        for i in range(3):
            task_failure_alert(
                sender=sender,
                task_id=str(i),
                exception=ValueError("boom"),
                args=(),
                kwargs={},
                traceback=None,
            )

        # Count should be 3 (even though only 1 alert sent due to cooldown)
        assert len(_failure_counts["test_task"]) == 3


class TestCheckApiErrorRate:
    """The error-rate alert: server errors in the last hour, once per incident."""

    def setup_method(self):
        from hubra.core.services import maintenance, perf_monitor
        from hubra.core.tasks import monitoring

        perf_monitor.reset_local()
        maintenance.clear_cache()
        monitoring._alerting_local["on"] = False

    def _traffic(self, ok=0, client_errors=0, server_errors=0, warming=False):
        from hubra.core.services import perf_monitor

        started = perf_monitor._process_started
        if warming:
            perf_monitor._process_started = time.monotonic()
        try:
            for status, n in ((200, ok), (401, client_errors), (500, server_errors)):
                for _ in range(n):
                    perf_monitor.record_request("GET /api/v1/x", status, 10)
        finally:
            perf_monitor._process_started = started

    def _check(self, app):
        with (
            app.app_context(),
            patch("hubra.core.services.perf_monitor._redis", return_value=None),
        ):
            return check_api_error_rate()

    @patch("hubra.core.tasks.monitoring.alert_error")
    def test_expired_sign_ins_after_a_release_are_not_errors(self, mock_alert, app):
        # A release: every open tab's access token is refused once.
        with patch("hubra.core.services.perf_monitor._redis", return_value=None):
            self._traffic(ok=40, client_errors=60)
        result = self._check(app)
        assert result["status"] == "ok"
        assert result["errors"] == 0
        mock_alert.assert_not_called()

    @patch("hubra.core.tasks.monitoring.alert_error")
    def test_errors_while_a_release_starts_do_not_count(self, mock_alert, app):
        with patch("hubra.core.services.perf_monitor._redis", return_value=None):
            self._traffic(ok=60, server_errors=30, warming=True)
        assert self._check(app)["status"] == "ok"
        mock_alert.assert_not_called()

    @patch("hubra.core.tasks.monitoring.alert_resolved")
    @patch("hubra.core.tasks.monitoring.alert_error")
    def test_a_real_outage_alerts_once_and_resolves(
        self, mock_alert, mock_resolved, app
    ):
        with patch("hubra.core.services.perf_monitor._redis", return_value=None):
            self._traffic(ok=60, server_errors=20)
        assert self._check(app)["status"] == "alert"
        assert self._check(app)["status"] == "still_high"
        mock_alert.assert_called_once()

        from hubra.core.services import perf_monitor

        perf_monitor.reset_local()
        with patch("hubra.core.services.perf_monitor._redis", return_value=None):
            self._traffic(ok=100)
        assert self._check(app)["status"] == "resolved"
        mock_resolved.assert_called_once()

    @patch("hubra.core.tasks.monitoring.alert_error")
    def test_too_few_requests_never_alert(self, mock_alert, app):
        with patch("hubra.core.services.perf_monitor._redis", return_value=None):
            self._traffic(ok=5, server_errors=5)
        result = self._check(app)
        assert result["reason"] == "too_few_requests"
        mock_alert.assert_not_called()

    @patch("hubra.core.tasks.monitoring.alert_error")
    def test_paused_in_maintenance(self, mock_alert, app):
        with patch("hubra.core.services.perf_monitor._redis", return_value=None):
            self._traffic(ok=60, server_errors=40)
        with patch("hubra.core.services.maintenance.is_active", return_value=True):
            assert self._check(app)["status"] == "maintenance"
        mock_alert.assert_not_called()
