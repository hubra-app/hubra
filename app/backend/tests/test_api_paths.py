"""Tests for the API path layout.

The tenant middleware reads the club slug from /api/<slug>/v1/... paths.
The old /api/v2 aliases are gone and answer 404.
"""

from hubra.core.tenant.middleware import _extract_slug_from_path, _rewrite_path


def test_extract_slug_from_tenant_path():
    environ = {"PATH_INFO": "/api/my-club/v1/members/"}
    assert _extract_slug_from_path(environ) == "my-club"


def test_standard_path_has_no_slug():
    environ = {"PATH_INFO": "/api/v1/members/"}
    assert _extract_slug_from_path(environ) is None


def test_rewrite_tenant_path():
    environ = {"PATH_INFO": "/api/my-club/v1/members/"}
    _rewrite_path(environ)
    assert environ["PATH_INFO"] == "/api/v1/members"


def test_v1_works(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/account/", headers=auth_headers)
    assert resp.status_code == 200


def test_v2_aliases_are_gone(client, seeded_db, auth_headers):
    for path in (
        "/api/v2/global/health",
        "/api/v2/global/account/",
        "/api/v2/tenants/members/",
        "/api/v2/manager/features/catalog",
    ):
        assert client.get(path, headers=auth_headers).status_code == 404, path
