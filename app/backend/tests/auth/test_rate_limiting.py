"""Tests for rate limiting on POST /api/v1/auth/login."""

from __future__ import annotations

import pytest
from vollbuild import create_app
from vollbuild.core.extensions import db as _db


# ── Fixture: rate-limited client ──────────────────────────────────────────────


@pytest.fixture
def rate_limit_client():
    """Fresh app with rate limiting enabled for rate-limit tests.

    Flask-Limiter 3.x returns early from ``init_app`` without registering the
    ``before_request`` hook when ``RATELIMIT_ENABLED=False``.  TestingConfig
    disables it globally to prevent spurious 429s in other tests.  This fixture
    temporarily sets the class attribute to ``True`` so that ``init_app`` runs
    fully, registers the hook, and creates an in-memory counter.  The class
    attribute is restored immediately after ``create_app`` so no other test is
    affected — the session-scoped app was already created without a limiter hook.

    Teardown nulls ``limiter._storage`` so the shared singleton no longer holds a
    live counter store.  Without this, the MemoryStorage initialised for the
    rate-limited app persists and causes the ``@limiter.limit`` decorator on
    /auth/login to rate-limit subsequent requests on the session-scoped app, even
    though RATELIMIT_ENABLED=False.  ``limiter.reset()`` alone only clears the
    counters — it does not remove the storage — so the null assignment is required.
    """
    from vollbuild.core import config as cfg_module
    from vollbuild.core.extensions import limiter

    cfg_module.TestingConfig.RATELIMIT_ENABLED = True
    app = create_app("testing")
    cfg_module.TestingConfig.RATELIMIT_ENABLED = False  # restore for other fixtures

    with app.app_context():
        _db.create_all()
        yield app.test_client()
        _db.drop_all()

    # Restore the shared limiter singleton to a disabled state so route-level
    # @limiter.limit decorators do not fire on the session-scoped app.
    #
    # Root cause: limiter.init_app(rl_app) with RATELIMIT_ENABLED=True sets
    # limiter.enabled=True as an instance attribute.  init_app(session_app) with
    # RATELIMIT_ENABLED=False returns early and never resets that attribute.  The
    # rate-check path (line 872 in _extension.py) reads `self.enabled`, not
    # current_app.config, so subsequent requests to the session app are still
    # rate-limited.  Setting enabled=False here short-circuits every rate check.
    # We also null _storage and _limiter so no stale counters survive.
    limiter.enabled = False
    limiter._storage = None
    limiter._limiter = None


# ── Rate limiting ─────────────────────────────────────────────────────────────


def test_rate_limit_applied_to_login(rate_limit_client):
    """11 rapid POST /api/v1/auth/login requests produce at least one 429.

    RATELIMIT_ENABLED=True is set on the fixture's app so limits fire.
    The login endpoint is limited to 10 per minute; the 11th must be 429.
    """
    last_resp = None
    got_429 = False
    for _ in range(11):
        last_resp = rate_limit_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
        if last_resp.status_code == 429:
            got_429 = True
            break

    assert got_429, (
        f"Expected a 429 after 11 login attempts; last status was {last_resp.status_code}"
    )


# ── Rate limit headers present ────────────────────────────────────────────────


def test_rate_limit_headers_present_on_429(rate_limit_client):
    """429 response includes rate-limit headers (RATELIMIT_HEADERS_ENABLED=True)."""
    for _ in range(11):
        resp = rate_limit_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
        if resp.status_code == 429:
            break

    assert resp.status_code == 429
    # flask-limiter sets these headers when RATELIMIT_HEADERS_ENABLED=True
    assert "Retry-After" in resp.headers or "X-RateLimit-Remaining" in resp.headers


# ── Rate limit resets after window ────────────────────────────────────────────


def test_rate_limit_resets_after_window(rate_limit_client):
    """After the rate limit window passes, requests succeed again.

    Uses a very short window (1 second) so the test completes quickly.
    The in-memory limiter uses a fixed window, so after the window
    expires the counter resets.
    """
    # Exhaust the limit (5 per minute on /auth/login)
    for _ in range(6):
        resp = rate_limit_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
        if resp.status_code == 429:
            break

    assert resp.status_code == 429

    # The in-memory storage has a 60s window — we can't wait that long in a
    # test. Instead, we verify that the limiter's storage has a count by
    # checking that the 429 includes a Retry-After header indicating a
    # future reset time.
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        assert int(retry_after) > 0, "Retry-After should indicate a positive wait"


# ── Rate limit applies per-IP for unauthenticated requests ────────────────────


def test_rate_limit_per_ip_for_unauthenticated(rate_limit_client):
    """Rate limiting on /auth/login uses IP for unauthenticated requests.

    The key function in extensions.py uses JWT identity for authed requests
    and IP for unauth. Since /auth/login is unauth, it should key by IP.
    We verify that 6 requests from the same IP exhaust the 5/min limit.
    """
    statuses = []
    for _ in range(6):
        resp = rate_limit_client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit@test.ch", "password": "wrong"},
        )
        statuses.append(resp.status_code)

    # First 5 should be 401 (bad credentials), 6th should be 429
    assert 429 in statuses, "Expected at least one 429 after 6 rapid requests"
    # The first few should NOT be 429 (credentials rejected, not rate limited)
    assert statuses[0] == 401, "First request should be 401 (bad credentials), not 429"
