"""Single-club mode (SINGLE_CLUB): one club, no manager plane, no SSO portal."""

from unittest.mock import patch

import pytest


@pytest.fixture
def single_club(app, db, seeded_db):
    """Run the app as a single-club install serving the club 'our-club'."""
    from hubra.core.models.tenant import Tenant

    db.session.add(Tenant(name="Our Club", slug="our-club", status="active"))
    db.session.add(Tenant(name="Other Club", slug="other-club", status="active"))
    db.session.commit()
    with patch.dict(
        app.config,
        {
            "SINGLE_CLUB": "our-club",
            "FRONTEND_BASE_URL": "https://club.example.org",
            "SSO_BASE_URL": "https://sso.example.org",
        },
    ):
        yield


def test_instance_multi_mode(client, db, app):
    with patch.dict(app.config, {"SSO_BASE_URL": "https://sso.example.org/"}):
        resp = client.get("/api/v1/instance")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "mode": "multi",
        "club": None,
        "ssoUrl": "https://sso.example.org",
        "signup": True,
    }


def test_instance_single_mode(client, single_club):
    resp = client.get("/api/v1/instance")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "mode": "single",
        "club": {"slug": "our-club", "name": "Our Club"},
        "ssoUrl": None,
        "signup": False,
    }


def test_single_club_ignores_tenant_header(client, single_club):
    resp = client.get("/api/v1/instance", headers={"X-Tenant-Slug": "other-club"})
    assert resp.get_json()["club"]["slug"] == "our-club"


def test_single_club_without_club_row(client, db, seeded_db, app):
    """Before `flask setup-club` ran, the instance still says single mode."""
    with patch.dict(app.config, {"SINGLE_CLUB": "missing"}):
        resp = client.get("/api/v1/instance")
    body = resp.get_json()
    assert body["mode"] == "single"
    assert body["club"] is None


def test_login_works_in_single_mode(client, single_club):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["tenant_slug"] == "our-club"


def test_login_without_membership_is_refused(client, db, single_club):
    from hubra.core.models.user import User

    user = User(email="nomember@test.ch", first_name="No", last_name="Member")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nomember@test.ch", "password": "password123"},
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "NO_MEMBERSHIP"


def test_signup_is_off(client, single_club):
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "New Person",
            "email": "new@test.ch",
            "password": "Str0ng!pass#1",
        },
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "SIGNUP_DISABLED"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/system/tenants",
        "/api/v2/manager/tenants/tenants",
        "/api/v1/system/tenant-requests/mine",
        "/api/v1/features/catalog",
    ],
)
def test_manager_plane_is_off(client, auth_headers, single_club, path):
    resp = client.get(path)
    assert resp.status_code == 404


def test_club_admin_api_stays_on(client, auth_headers, single_club):
    """Club-level admin endpoints are not part of the manager plane."""
    resp = client.get("/api/v1/modules/")
    assert resp.status_code == 200


def test_email_links_open_the_club_app(app, single_club):
    from hubra.core.services.email import _get_sso_base_url

    with app.test_request_context():
        assert _get_sso_base_url() == "https://club.example.org"


def test_email_links_use_sso_in_multi_mode(app):
    from hubra.core.services.email import _get_sso_base_url

    with (
        patch.dict(app.config, {"SSO_BASE_URL": "https://sso.example.org"}),
        app.test_request_context(),
    ):
        assert _get_sso_base_url() == "https://sso.example.org"


def test_setup_club_needs_an_admin(app, db):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["setup-club", "--slug", "fresh-club"])
    assert result.exit_code != 0
    assert "ADMIN_EMAIL" in result.output


def test_setup_club_is_idempotent(app, db):
    from hubra.core.models.tenant import Tenant

    db.session.add(Tenant(name="Our Club", slug="our-club", status="active"))
    db.session.commit()
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["setup-club"],
        env={"SINGLE_CLUB": "our-club", "ADMIN_EMAIL": "x@test.ch"},
    )
    assert result.exit_code == 0, result.output
    assert "already set up" in result.output
