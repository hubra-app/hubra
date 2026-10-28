"""Tests for security headers (HSTS, X-Frame-Options, X-Content-Type-Options).

CSP, Permissions-Policy, and Accept-CH are set by Caddy on frontend HTML,
not on API JSON responses.
"""

from hubra.api.health.cache import HealthCache


# ── Security header tests ─────────────────────────────────────────────────────


def test_companion_security_headers_present(client):
    """X-Frame-Options and X-Content-Type-Options are set on all responses."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.get("/api/v1/health")
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_hsts_header_present(client):
    """Strict-Transport-Security is set on API responses."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.get("/api/v1/health")
    assert "Strict-Transport-Security" in resp.headers
    assert "max-age" in resp.headers["Strict-Transport-Security"]


def test_csp_not_on_api_responses(client):
    """Content-Security-Policy is NOT set on API JSON responses (moved to Caddy)."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.get("/api/v1/health")
    assert "Content-Security-Policy" not in resp.headers


def test_health_exempt_from_rate_limiting(client):
    """/health must not carry rate-limit headers (exempted from flask-limiter)."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.get("/api/v1/health")
    assert "X-Ratelimit-Limit" not in resp.headers
    assert "X-Ratelimit-Remaining" not in resp.headers
    assert "X-Ratelimit-Reset" not in resp.headers
    assert "Retry-After" not in resp.headers


def test_referrer_policy_header_present(client):
    """Referrer-Policy: strict-origin-when-cross-origin is set on API responses."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.get("/api/v1/health")
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_security_headers_on_error_response(client):
    """Security headers are present even on 404 error responses."""
    resp = client.get("/api/v1/nonexistent-endpoint")
    assert resp.status_code == 404
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Referrer-Policy" in resp.headers
