"""
Tests for GET /api/v1/health

Covers:
  - Public /health reads from cache (no live checks)
  - Cache miss returns degraded with HTTP 200
  - HTTP 503 returned when cached status is "error"
  - HTTP 200 returned for ok/degraded (load-balancer requirement)
  - /health/detailed runs concurrent checks, includes version + stale flag
"""

from unittest.mock import patch

from vollbuild.api.health.cache import HealthCache

_SVC = "vollbuild.api.health.services.HealthService"


def _all_ok_patches():
    """Context manager that mocks all HealthService checks as healthy."""
    return (
        patch(f"{_SVC}.check_db"),
        patch(f"{_SVC}.check_redis"),
        patch(f"{_SVC}.check_smtp"),
        patch(f"{_SVC}.check_imap"),
    )


def _seed_cache(status: str) -> None:
    """Seed the health cache with a given status (clears first to isolate)."""
    HealthCache.clear()
    HealthCache.set({"status": status, "services": {}, "checked_at": 0})


# ── Public /health (cached) ───────────────────────────────────────────────────


def test_health_reads_cache_no_live_checks(client):
    """Public /health reads from cache — no HealthService.check_* is called."""
    _seed_cache("ok")
    with patch(f"{_SVC}.run_all_checks") as mock_run:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        mock_run.assert_not_called()


def test_health_cache_miss_returns_degraded_200(client):
    """Empty cache → {'status': 'degraded'} with HTTP 200 (no LB flapping)."""
    HealthCache.clear()
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "degraded"


def test_health_cache_error_returns_503(client):
    """Cached 'error' status → HTTP 503."""
    _seed_cache("error")
    resp = client.get("/api/v1/health")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["status"] == "error"


def test_health_cache_degraded_returns_200(client):
    """Cached 'degraded' status → HTTP 200."""
    _seed_cache("degraded")
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "degraded"


def test_health_returns_200_with_status_key(client):
    """Public /health returns only a 'status' key — no infra details exposed."""
    _seed_cache("ok")
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert "status" in data
    assert "services" not in data


def test_health_no_auth_required(client):
    """Health endpoint must be accessible without any Authorization header."""
    _seed_cache("ok")
    resp = client.get("/api/v1/health")
    assert resp.status_code not in (401, 403)


def test_health_public_does_not_include_version(client):
    """Public /health must not leak the version string."""
    _seed_cache("ok")
    resp = client.get("/api/v1/health")
    data = resp.get_json()
    assert "version" not in data


# ── /health/detailed (live concurrent checks, admin-only) ─────────────────────


def test_health_detailed_services_structure(client, auth_headers):
    """Detailed breakdown (admin-only) includes all expected service sub-keys."""
    resp = client.get("/api/v1/health/detailed", headers=auth_headers)
    assert resp.status_code in (200, 503)
    data = resp.get_json()
    services = data["services"]
    for key in ("db", "redis", "smtp", "imap"):
        assert key in services, f"'{key}' missing from services"


def test_health_detailed_db_ok_field_is_bool(client, auth_headers):
    """Detailed: db.ok must be a boolean."""
    resp = client.get("/api/v1/health/detailed", headers=auth_headers)
    data = resp.get_json()
    assert isinstance(data["services"]["db"]["ok"], bool)


def test_health_detailed_latency_ms_present(client, auth_headers):
    """Detailed: each service entry must include latency_ms."""
    resp = client.get("/api/v1/health/detailed", headers=auth_headers)
    data = resp.get_json()
    for svc in ("db", "redis", "smtp"):
        assert "latency_ms" in data["services"][svc], f"latency_ms missing for {svc}"


def test_health_detailed_includes_version(client, auth_headers):
    """Detailed health payload includes the backend version."""
    from vollbuild.api.version.services import VersionService

    resp = client.get("/api/v1/health/detailed", headers=auth_headers)
    data = resp.get_json()
    assert data["version"] == VersionService.get_version()


def test_health_detailed_includes_stale_flag(client, auth_headers):
    """Detailed health payload includes a 'stale' boolean flag."""
    resp = client.get("/api/v1/health/detailed", headers=auth_headers)
    data = resp.get_json()
    assert "stale" in data
    assert isinstance(data["stale"], bool)


# ── Basic health checks (from S01 foundation) ─────────────────────────────────


def test_health_endpoint_returns_200(client):
    """GET /api/v1/health returns 200 or 503 with only a 'status' key."""
    _seed_cache("ok")
    resp = client.get("/api/v1/health")
    assert resp.status_code in (200, 503)
    data = resp.get_json()
    assert data is not None
    assert "status" in data
    assert "services" not in data


def test_health_db_checked(client, auth_headers):
    """Detailed health shows db.ok is True — SQLite in-memory DB is always reachable in tests."""
    resp = client.get("/api/v1/health/detailed", headers=auth_headers)
    data = resp.get_json()
    assert data["services"]["db"]["ok"] is True
