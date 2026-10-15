"""Tests for API envelope helpers, RBAC decorators, and config security."""

from __future__ import annotations

import os


# ── API envelope helpers ──────────────────────────────────────────────────────


def test_api_envelope_success(app):
    """success_response wraps data in {"data": ..., "meta": ...} envelope."""
    with app.test_request_context("/"):
        from vollbuild.api.utils import success_response

        response, status = success_response({"id": 1})
        data = response.get_json()
        assert "data" in data
        assert data["data"]["id"] == 1
        assert status == 200


def test_api_envelope_paginated(app):
    """paginated_response includes meta.total from the supplied count."""
    with app.test_request_context("/"):
        from vollbuild.api.utils import paginated_response

        response, status = paginated_response([1, 2], 10, 1, 5)
        data = response.get_json()
        assert data["meta"]["total"] == 10
        assert data["meta"]["pages"] == 2


# ── RBAC decorators ───────────────────────────────────────────────────────────


def test_require_admin_blocks_non_admin(client):
    """Unauthenticated request to a permission-gated route returns 401.

    GET /api/v1/applications/ uses @require_permission which calls
    verify_jwt_in_request() and returns 401 when no bearer token is present.
    """
    resp = client.get("/api/v1/applications/")
    assert resp.status_code == 401


# ── Security: hardened secret key defaults ──────────────────────────────────────


def test_base_config_generates_random_secret_key_when_env_missing():
    """BaseConfig._dev_secret generates a non-static value when env var is absent."""
    from vollbuild.core.config import _dev_secret

    # Ensure env var is absent
    os.environ.pop("SECRET_KEY", None)
    # Call the helper directly to test its behavior
    key = _dev_secret("SECRET_KEY")
    assert key != "dev-secret-key-change-me"
    assert len(key) >= 32


def test_base_config_generates_random_jwt_secret_when_env_missing():
    """BaseConfig._dev_secret generates a non-static value when env var is absent."""
    from vollbuild.core.config import _dev_secret

    os.environ.pop("JWT_SECRET_KEY", None)
    # Call the helper directly to test its behavior
    key = _dev_secret("JWT_SECRET_KEY")
    assert key != "dev-jwt-key-change-me"
    assert len(key) >= 32


# ── Flask-limiter config key ──────────────────────────────────────────────────


def test_ratelimit_storage_uri_config_key(app):
    """app.config uses RATELIMIT_STORAGE_URI (flask-limiter 4.x key name)."""
    assert "RATELIMIT_STORAGE_URI" in app.config
    # The old RATE_LIMIT_STORAGE key should NOT be the one we rely on
    # (it may still exist from env but flask-limiter reads the new key)


def test_sqlalchemy_engine_options_set(app):
    """SQLALCHEMY_ENGINE_OPTIONS includes pool_pre_ping for resilience."""
    opts = app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {})
    assert opts.get("pool_pre_ping") is True
