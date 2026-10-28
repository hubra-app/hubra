"""Tests for tenant resolver middleware — URL parsing and path rewriting."""


def test_no_slug_passes_through():
    """/api/v1/auth/bootstrap-status is not rewritten (single-tenant mode)."""
    from hubra.core.tenant.middleware import _extract_slug_from_path

    environ = {"PATH_INFO": "/api/v1/auth/bootstrap-status"}
    assert _extract_slug_from_path(environ) is None


def test_v1_not_treated_as_slug():
    """/api/v1/members does not treat 'v1' as a slug."""
    from hubra.core.tenant.middleware import _extract_slug_from_path

    environ = {"PATH_INFO": "/api/v1/members"}
    assert _extract_slug_from_path(environ) is None


def test_slug_extracted_correctly():
    """/api/acmecanoe/v1/members extracts slug 'acmecanoe'."""
    from hubra.core.tenant.middleware import _extract_slug_from_path

    environ = {"PATH_INFO": "/api/acmecanoe/v1/members"}
    assert _extract_slug_from_path(environ) == "acmecanoe"


def test_slug_path_rewritten():
    """/api/acmecanoe/v1/members is rewritten to /api/v1/members."""
    from hubra.core.tenant.middleware import _rewrite_path

    environ = {"PATH_INFO": "/api/acmecanoe/v1/members"}
    _rewrite_path(environ)
    assert environ["PATH_INFO"] == "/api/v1/members"


def test_no_slug_path_not_rewritten():
    """/api/v1/members is not rewritten."""
    from hubra.core.tenant.middleware import _rewrite_path

    environ = {"PATH_INFO": "/api/v1/members"}
    _rewrite_path(environ)
    assert environ["PATH_INFO"] == "/api/v1/members"


def test_health_not_rewritten():
    """/api/v1/health is not rewritten."""
    from hubra.core.tenant.middleware import _rewrite_path

    environ = {"PATH_INFO": "/api/v1/health"}
    _rewrite_path(environ)
    assert environ["PATH_INFO"] == "/api/v1/health"


def test_root_health_not_rewritten():
    """/health is not touched by the middleware."""
    from hubra.core.tenant.middleware import _extract_slug_from_path, _rewrite_path

    environ = {"PATH_INFO": "/health"}
    assert _extract_slug_from_path(environ) is None
    _rewrite_path(environ)
    assert environ["PATH_INFO"] == "/health"


def test_tenant_scoped_health_rewritten():
    """/api/acmecanoe/v1/health is rewritten to /api/v1/health."""
    from hubra.core.tenant.middleware import _extract_slug_from_path, _rewrite_path

    environ = {"PATH_INFO": "/api/acmecanoe/v1/health"}
    assert _extract_slug_from_path(environ) == "acmecanoe"
    _rewrite_path(environ)
    assert environ["PATH_INFO"] == "/api/v1/health"


def test_deep_path_rewritten():
    """/api/acmecanoe/v1/members/42/invoices is rewritten correctly."""
    from hubra.core.tenant.middleware import _rewrite_path

    environ = {"PATH_INFO": "/api/acmecanoe/v1/members/42/invoices"}
    _rewrite_path(environ)
    assert environ["PATH_INFO"] == "/api/v1/members/42/invoices"


def test_root_health_endpoint(client):
    """GET /health returns 200 with status field."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "status" in body


def test_resolve_tenant_single_tenant_mode(client):
    """In single-tenant mode, /api/v1/health works without a tenant slug."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_resolve_tenant_no_slug_sets_none(app):
    """resolve_tenant sets g.tenant=None when no slug source is available."""
    from flask import g
    from hubra.core.tenant.middleware import resolve_tenant

    with app.test_request_context("/api/v1/members"):
        resolve_tenant()
        assert g.tenant is None


# ── End to end: every slug source reaches the route ──────────────────────────


def _sign_in(client):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "user@test.ch", "password": "password123"}
    )
    assert resp.status_code == 200


def test_slug_in_path_routes_to_the_club(client, tenant_pair):
    """/api/<slug>/v1/... reaches the route, not a 404 from the URL map."""
    resp = client.get("/api/tenant-a/v1/health")
    assert resp.status_code == 200


def test_slug_in_path_sets_the_tenant(client, tenant_pair):
    """The club token is accepted under its own club's path slug, which
    only works when g.tenant was set from the path."""
    _sign_in(client)
    client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "tenant-a"})
    resp = client.get("/api/tenant-a/v1/account/")
    assert resp.status_code == 200
    assert resp.get_json()["roles"][0]["name"] == "Admin A"


def test_unknown_slug_in_path_has_no_tenant(client, tenant_pair):
    resp = client.get("/api/nope/v1/health")
    assert resp.status_code == 200


def test_slug_from_club_token(client, tenant_pair):
    """After switch-tenant, the token's tenant_slug claim picks the club
    without a path slug or an X-Tenant-Slug header."""
    _sign_in(client)
    resp = client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "tenant-a"})
    assert resp.status_code == 200
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 200
    assert resp.get_json()["roles"][0]["name"] == "Admin A"


def test_path_slug_wins_over_token(client, tenant_pair):
    """A club token used under another club's path is refused (401), not
    applied to the club in the token."""
    _sign_in(client)
    client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "tenant-a"})
    resp = client.get("/api/tenant-b/v1/account/")
    assert resp.status_code == 401
