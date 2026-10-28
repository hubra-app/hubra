"""
Tests for B4 — Celery task failure alerting.

Covers:
  - task_failure_alert fires on task failure
  - Cooldown prevents repeated alerts
  - check_api_error_rate returns correct status
  - Graceful handling when Redis unavailable
"""

from unittest.mock import patch, MagicMock


from vollbuild.core.tasks.monitoring import (
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

    @patch("vollbuild.core.tasks.monitoring.alert_error")
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

    @patch("vollbuild.core.tasks.monitoring.alert_error")
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

    @patch("vollbuild.core.tasks.monitoring.alert_error")
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
    """Tests for API error rate checking."""

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_returns_ok_when_rate_low(self, mock_get_redis):
        """Returns ok when error rate is below threshold."""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda k: b"100" if "total" in k else b"5"
        mock_get_redis.return_value = mock_redis

        result = check_api_error_rate()
        assert result["status"] == "ok"
        assert result["rate"] == 0.05

    @patch("vollbuild.core.tasks.monitoring.alert_error")
    @patch("vollbuild.api.metrics._get_redis_client")
    def test_alerts_when_rate_high(self, mock_get_redis, mock_alert):
        """Alerts when error rate exceeds threshold."""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda k: b"100" if "total" in k else b"50"
        mock_get_redis.return_value = mock_redis

        result = check_api_error_rate()
        assert result["status"] == "alert"
        assert result["rate"] == 0.5
        mock_alert.assert_called_once()

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_returns_skipped_when_redis_unavailable(self, mock_get_redis):
        """Returns skipped when Redis is unavailable."""
        mock_get_redis.return_value = None
        result = check_api_error_rate()
        assert result["status"] == "skipped"

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_returns_ok_when_no_traffic(self, mock_get_redis):
        """Returns ok when there's no traffic."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        result = check_api_error_rate()
        assert result["status"] == "ok"
        assert result["total"] == 0
