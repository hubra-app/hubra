"""Tests for v2 API namespace registration and routing.

Verifies that v2 blueprints are registered alongside v1 and that
tenant middleware resolves slugs from v2 tenant paths.
"""

from vollbuild.core.tenant.middleware import _extract_slug_from_path, _rewrite_path


# ── Middleware slug extraction ────────────────────────────────────────────────


def test_extract_slug_from_v2_tenant_path():
    """v2 tenant path extracts slug correctly."""
    environ = {"PATH_INFO": "/api/v2/tenants/my-club/members/"}
    assert _extract_slug_from_path(environ) == "my-club"


def test_extract_slug_from_v1_tenant_path():
    """Legacy v1 tenant path still extracts slug."""
    environ = {"PATH_INFO": "/api/my-club/v1/members/"}
    assert _extract_slug_from_path(environ) == "my-club"


def test_v2_global_path_no_slug():
    """v2 global path has no slug."""
    environ = {"PATH_INFO": "/api/v2/global/auth/login"}
    assert _extract_slug_from_path(environ) is None


def test_v2_manager_path_no_slug():
    """v2 manager path has no slug."""
    environ = {"PATH_INFO": "/api/v2/manager/tenants/"}
    assert _extract_slug_from_path(environ) is None


def test_v1_standard_path_no_slug():
    """v1 standard path has no slug."""
    environ = {"PATH_INFO": "/api/v1/members/"}
    assert _extract_slug_from_path(environ) is None


# ── Middleware path rewrite ───────────────────────────────────────────────────


def test_rewrite_v2_tenant_path():
    """v2 tenant path rewrites to strip slug segment."""
    environ = {"PATH_INFO": "/api/v2/tenants/my-club/members/"}
    _rewrite_path(environ)
    assert environ["PATH_INFO"] == "/api/v2/tenants/members"


def test_rewrite_v1_tenant_path():
    """v1 tenant path still rewrites correctly."""
    environ = {"PATH_INFO": "/api/my-club/v1/members/"}
    _rewrite_path(environ)
    assert environ["PATH_INFO"] == "/api/v1/members"


# ── v2 route registration smoke tests ─────────────────────────────────────────


def test_v2_global_health_responds(client, seeded_db):
    """GET /api/v2/global/health returns 200."""
    resp = client.get("/api/v2/global/health")
    assert resp.status_code == 200


def test_v2_global_version_responds(client, seeded_db):
    """GET /api/v2/global/version returns 200."""
    resp = client.get("/api/v2/global/version")
    assert resp.status_code == 200


def test_v2_global_auth_login_responds(client, seeded_db):
    """POST /api/v2/global/auth/login returns 200 with valid credentials."""
    resp = client.post(
        "/api/v2/global/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    assert resp.status_code == 200


def test_v2_global_account_requires_auth(client, seeded_db):
    """GET /api/v2/global/account/ returns 401 without auth."""
    resp = client.get("/api/v2/global/account/")
    assert resp.status_code == 401


def test_v2_global_account_works_with_auth(client, seeded_db, auth_headers):
    """GET /api/v2/global/account/ returns 200 with auth."""
    resp = client.get("/api/v2/global/account/", headers=auth_headers)
    assert resp.status_code == 200


def test_v1_still_works(client, seeded_db, auth_headers):
    """v1 routes are not broken by v2 registration."""
    resp = client.get("/api/v1/account/", headers=auth_headers)
    assert resp.status_code == 200


def test_v2_manager_tenants_requires_auth(client, seeded_db):
    """v2 manager endpoints require auth."""
    resp = client.get("/api/v2/manager/tenants/")
    assert resp.status_code in (401, 404)


def test_v2_tenant_members_requires_auth(client, seeded_db):
    """v2 tenant endpoints require auth."""
    # Without tenant slug, the blueprint sees /api/v2/tenants/members/
    # which is the registered prefix — should still require auth
    resp = client.get("/api/v2/tenants/members/")
    assert resp.status_code == 401
