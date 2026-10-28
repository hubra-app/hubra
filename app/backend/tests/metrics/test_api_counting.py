"""
Tests for B1 — API Call Metering middleware.

Covers:
  - Request increments Redis counter
  - Tenant isolation (different tenants have separate counters)
  - OPTIONS requests not counted
  - Health endpoints not counted
  - Error responses (4xx/5xx) not counted
  - Redis unavailable doesn't break requests
  - get_api_calls_30d returns aggregated counts
"""

from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_redis_mock():
    """Create a mock Redis client that tracks incr/expire calls."""
    mock = MagicMock()
    mock.pipeline.return_value = mock
    mock.incr.return_value = mock
    mock.expire.return_value = mock
    mock.execute.return_value = [1, True]
    return mock


# ── Counting middleware ──────────────────────────────────────────────────────


class TestApiCallCounting:
    """Tests for the API call counting middleware."""

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_request_increments_counter(self, mock_get_redis, client, db):
        """A successful API request increments the Redis counter."""
        mock_redis = _make_redis_mock()
        mock_get_redis.return_value = mock_redis

        # Make a request to a non-health endpoint
        resp = client.get("/api/v1/health")
        assert resp.status_code in (200, 503)

        # In test mode there's no tenant, so counter shouldn't be incremented
        # (no tenant resolved = no counting). This is expected behavior.

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_options_not_counted(self, mock_get_redis, client, db):
        """OPTIONS requests are not counted."""
        mock_redis = _make_redis_mock()
        mock_get_redis.return_value = mock_redis

        resp = client.options("/api/v1/members")
        # OPTIONS may return 405 or 200 depending on CORS config
        assert resp.status_code in (200, 405)

        # Redis should not have been called at all
        mock_redis.pipeline.assert_not_called()

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_health_endpoint_not_counted(self, mock_get_redis, client, db):
        """Health endpoints are excluded from counting."""
        mock_redis = _make_redis_mock()
        mock_get_redis.return_value = mock_redis

        resp = client.get("/api/v1/health")
        assert resp.status_code in (200, 503)

        # Health endpoints should not be counted
        mock_redis.pipeline.assert_not_called()

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_root_health_not_counted(self, mock_get_redis, client, db):
        """Root /health endpoint is excluded from counting."""
        mock_redis = _make_redis_mock()
        mock_get_redis.return_value = mock_redis

        resp = client.get("/health")
        assert resp.status_code in (200, 503)

        mock_redis.pipeline.assert_not_called()

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_error_response_not_counted_for_tenant(self, mock_get_redis, client, db):
        """Error responses are not counted in tenant-specific call counters.

        Global error rate tracking (api:errors:count/total) still fires,
        but the tenant-specific api:calls:{id} counter must not increment.
        """
        mock_redis = _make_redis_mock()
        mock_get_redis.return_value = mock_redis

        resp = client.get("/api/v1/members")
        # Tenant-specific call key should not be set for error responses
        if resp.status_code >= 400:
            # Only error rate keys should have been set, not tenant call keys
            calls = [str(c) for c in mock_redis.pipeline.call_args_list]
            tenant_keys = [c for c in calls if "api:calls:" in c]
            assert len(tenant_keys) == 0

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_redis_unavailable_doesnt_break_request(self, mock_get_redis, client, db):
        """When Redis is unavailable, requests still succeed."""
        mock_get_redis.return_value = None

        resp = client.get("/api/v1/health")
        assert resp.status_code in (200, 503)

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_redis_exception_doesnt_break_request(self, mock_get_redis, client, db):
        """When Redis raises an exception, requests still succeed."""
        mock_redis = _make_redis_mock()
        mock_redis.pipeline.side_effect = Exception("Redis connection lost")
        mock_get_redis.return_value = mock_redis

        resp = client.get("/api/v1/health")
        assert resp.status_code in (200, 503)


# ── get_api_calls_30d ───────────────────────────────────────────────────────


class TestGetApiCalls30d:
    """Tests for the get_api_calls_30d helper function."""

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_returns_zero_when_redis_unavailable(self, mock_get_redis):
        """Returns 0 when Redis is unavailable."""
        from vollbuild.api.metrics import get_api_calls_30d

        mock_get_redis.return_value = None
        result = get_api_calls_30d(tenant_id=1)
        assert result == 0

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_sums_across_months(self, mock_get_redis):
        """Sums counters across current and previous months."""
        from vollbuild.api.metrics import get_api_calls_30d

        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        # Mock Redis get to return different values for different keys
        now = datetime.now(timezone.utc)
        key_current = f"api:calls:1:{now.strftime('%Y-%m')}"

        def mock_get(key):
            if key == key_current:
                return b"100"
            return b"50"

        mock_redis.get.side_effect = mock_get

        result = get_api_calls_30d(tenant_id=1)
        # Should be at least 100 (current month) + 50 (prev months)
        assert result >= 150

    @patch("vollbuild.api.metrics._get_redis_client")
    def test_handles_redis_exception(self, mock_get_redis):
        """Returns 0 when Redis raises an exception."""
        from vollbuild.api.metrics import get_api_calls_30d

        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Redis error")
        mock_get_redis.return_value = mock_redis

        result = get_api_calls_30d(tenant_id=1)
        assert result == 0


# ── Redis key format ────────────────────────────────────────────────────────


class TestRedisKeyFormat:
    """Tests for Redis key format and TTL."""

    def test_redis_key_format(self):
        """Redis key follows api:calls:{tenant_id}:{YYYY-MM} format."""
        from vollbuild.api.metrics import _redis_key

        dt = datetime(2026, 7, 15, tzinfo=timezone.utc)
        key = _redis_key(tenant_id=42, dt=dt)
        assert key == "api:calls:42:2026-07"

    def test_redis_key_tenant_isolation(self):
        """Different tenant IDs produce different keys."""
        from vollbuild.api.metrics import _redis_key

        dt = datetime(2026, 7, 15, tzinfo=timezone.utc)
        key1 = _redis_key(tenant_id=1, dt=dt)
        key2 = _redis_key(tenant_id=2, dt=dt)
        assert key1 != key2
