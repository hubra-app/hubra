"""
Tests for B5 — Infrastructure health checks.

Covers:
  - check_disk_space returns usage percentage
  - check_redis_health returns ok when ping succeeds
  - check_redis_health returns error when ping fails
  - check_postgres_health returns ok when query succeeds
  - run_all_checks aggregates all results
  - Alert state tracking prevents repeated alerts
"""

from unittest.mock import patch, MagicMock


from hubra.core.tasks.infra_checks import (
    check_disk_space,
    check_redis_health,
    check_postgres_health,
    run_all_checks,
    _alert_states,
)


class TestCheckDiskSpace:
    """Tests for disk space checking."""

    @patch("hubra.core.tasks.infra_checks._get_disk_usage")
    def test_returns_ok_when_below_threshold(self, mock_usage):
        """Returns ok when disk usage is below threshold."""
        mock_usage.return_value = 50.0
        result = check_disk_space(threshold_pct=85.0)
        assert result["status"] == "ok"
        assert result["usage_pct"] == 50.0

    @patch("hubra.core.tasks.infra_checks._get_disk_usage")
    def test_returns_alert_when_above_threshold(self, mock_usage):
        """Returns alert when disk usage exceeds threshold."""
        _alert_states.clear()
        mock_usage.return_value = 90.0
        with patch("hubra.core.tasks.infra_checks.alert_error"):
            result = check_disk_space(threshold_pct=85.0)
        assert result["status"] == "alert"
        assert result["usage_pct"] == 90.0

    @patch("hubra.core.tasks.infra_checks._get_disk_usage")
    def test_returns_skipped_when_usage_unknown(self, mock_usage):
        """Returns skipped when disk usage can't be determined."""
        mock_usage.return_value = None
        result = check_disk_space()
        assert result["status"] == "skipped"


class TestCheckRedisHealth:
    """Tests for Redis health checking."""

    @patch("hubra.api.metrics._get_redis_client")
    def test_returns_ok_when_ping_succeeds(self, mock_get_redis):
        """Returns ok when Redis ping succeeds."""
        _alert_states.clear()
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        result = check_redis_health()
        assert result["status"] == "ok"
        assert "latency_ms" in result

    @patch("hubra.api.metrics._get_redis_client")
    def test_returns_error_when_ping_fails(self, mock_get_redis):
        """Returns error when Redis ping fails."""
        _alert_states.clear()
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception("Connection refused")
        mock_get_redis.return_value = mock_redis

        with patch("hubra.core.tasks.infra_checks.alert_error"):
            result = check_redis_health()
        assert result["status"] == "error"

    @patch("hubra.api.metrics._get_redis_client")
    def test_returns_error_when_client_unavailable(self, mock_get_redis):
        """Returns error when Redis client can't be created."""
        _alert_states.clear()
        mock_get_redis.return_value = None

        with patch("hubra.core.tasks.infra_checks.alert_error"):
            result = check_redis_health()
        assert result["status"] == "alert"


class TestCheckPostgresHealth:
    """Tests for PostgreSQL health checking."""

    @patch("hubra.core.tasks.infra_checks.db")
    def test_returns_ok_when_query_succeeds(self, mock_db):
        """Returns ok when SELECT 1 succeeds."""
        _alert_states.clear()
        result = check_postgres_health()
        assert result["status"] == "ok"
        assert "latency_ms" in result

    @patch("hubra.core.tasks.infra_checks.db")
    def test_returns_error_when_query_fails(self, mock_db):
        """Returns error when SELECT 1 fails."""
        _alert_states.clear()
        mock_db.session.execute.side_effect = Exception("Connection lost")

        with patch("hubra.core.tasks.infra_checks.alert_error"):
            result = check_postgres_health()
        assert result["status"] == "error"


class TestRunAllChecks:
    """Tests for aggregated health checks."""

    @patch("hubra.core.tasks.infra_checks.check_postgres_health")
    @patch("hubra.core.tasks.infra_checks.check_redis_health")
    @patch("hubra.core.tasks.infra_checks.check_disk_space")
    def test_aggregates_ok_status(self, mock_disk, mock_redis, mock_pg):
        """Returns ok when all checks pass."""
        mock_disk.return_value = {"status": "ok"}
        mock_redis.return_value = {"status": "ok"}
        mock_pg.return_value = {"status": "ok"}

        result = run_all_checks()
        assert result["overall"] == "ok"

    @patch("hubra.core.tasks.infra_checks.check_postgres_health")
    @patch("hubra.core.tasks.infra_checks.check_redis_health")
    @patch("hubra.core.tasks.infra_checks.check_disk_space")
    def test_aggregates_alert_status(self, mock_disk, mock_redis, mock_pg):
        """Returns alert when any check fails."""
        mock_disk.return_value = {"status": "ok"}
        mock_redis.return_value = {"status": "alert"}
        mock_pg.return_value = {"status": "ok"}

        result = run_all_checks()
        assert result["overall"] == "alert"
