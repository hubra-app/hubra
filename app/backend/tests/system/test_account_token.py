"""Platform routes run on the account identity, never on a club token.

A club token (member identity) is what scripts in the club app can use —
plugin frontends included — so ``require_global_permission`` refuses it
(401 ACCOUNT_TOKEN_REQUIRED).  The dedicated ``account_token`` cookie, set
at sign-in and untouched by /auth/switch-tenant, keeps manage working while
a club is open.  Destructive actions additionally need a fresh password
(POST /account/step-up).
"""

from unittest.mock import patch

from flask_jwt_extended import create_access_token

from hubra.core.auth.account_token import ACCOUNT_COOKIE, ACCOUNT_CSRF_COOKIE
from hubra.core.extensions import db


def _make_superadmin(seeded_db):
    seeded_db["user"].is_superadmin = True
    db.session.commit()


def _club_token(app, seeded_db):
    """The token the club app holds: member identity plus user_id claim."""
    with app.app_context():
        return create_access_token(
            identity=str(seeded_db["admin"].id),
            additional_claims={"user_id": seeded_db["user"].id},
        )


class TestClubTokenRefused:
    def test_club_token_refused_on_platform_routes(self, app, client, seeded_db):
        _make_superadmin(seeded_db)
        client.set_cookie("access_token_cookie", _club_token(app, seeded_db))
        for path in ("/api/v1/system/tenants", "/api/v1/manager/plugins/"):
            resp = client.get(path)
            assert resp.status_code == 401, path
            assert resp.get_json()["error"] == "ACCOUNT_TOKEN_REQUIRED"

    def test_account_identity_in_standard_cookie_still_works(
        self, client, seeded_db, staff_headers
    ):
        """The SSO/manage flow before any club is opened: a ``user:`` token
        in the standard cookie passes (login puts one there via the member
        branch only in clubs; force the user branch by clearing the club)."""
        resp = client.get("/api/v1/system/tenants")
        # staff_headers signs in the seeded member (club token) — but login
        # now also sets the account cookie, which must carry the request.
        assert resp.status_code == 200

    def test_account_cookie_survives_club_token(self, app, client, seeded_db):
        """With a club token in the standard jar, the account cookie alone
        authenticates platform routes."""
        _make_superadmin(seeded_db)
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        # Overwrite the standard cookie with a bare club token (no account_sid),
        # as /auth/switch-tenant does.
        client.set_cookie("access_token_cookie", _club_token(app, seeded_db))
        resp = client.get("/api/v1/system/tenants")
        assert resp.status_code == 200

    def test_login_sets_account_cookie(self, client, seeded_db):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        cookies = "\n".join(resp.headers.getlist("Set-Cookie"))
        assert ACCOUNT_COOKIE + "=" in cookies
        assert ACCOUNT_CSRF_COOKIE + "=" in cookies

    def test_logout_clears_and_revokes_account_cookie(self, client, seeded_db):
        _make_superadmin(seeded_db)
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        account_cookie = client.get_cookie(ACCOUNT_COOKIE).value
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 204
        # A kept copy of the cookie no longer opens anything.
        client.set_cookie(ACCOUNT_COOKIE, account_cookie)
        resp = client.get("/api/v1/system/tenants")
        assert resp.status_code == 401

    def test_revoked_account_session_refuses_cookie(self, client, seeded_db):
        _make_superadmin(seeded_db)
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        from hubra.core.models.account_session import AccountSession
        from hubra.core.auth import session_service

        session = db.session.query(AccountSession).first()
        session_service.revoke_account_session(
            session.id, seeded_db["user"].id, "test"
        )
        db.session.commit()
        resp = client.get("/api/v1/system/tenants")
        assert resp.status_code == 401


class TestStepUp:
    def _login(self, client):
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )

    def test_destructive_route_needs_step_up(self, app, client, seeded_db):
        _make_superadmin(seeded_db)
        self._login(client)
        with patch.dict(app.config, {"STEP_UP_ENFORCED": True}):
            resp = client.post(
                "/api/v1/system/tenants/1/impersonate", json={"reason": "x"}
            )
            assert resp.status_code == 403
            assert resp.get_json()["error"] == "STEP_UP_REQUIRED"

    def test_step_up_wrong_password(self, app, client, seeded_db):
        _make_superadmin(seeded_db)
        self._login(client)
        resp = client.post("/api/v1/account/step-up", json={"password": "nope"})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "INVALID_PASSWORD"

    def test_step_up_then_allowed(self, app, client, seeded_db):
        _make_superadmin(seeded_db)
        self._login(client)
        with patch.dict(app.config, {"STEP_UP_ENFORCED": True}):
            resp = client.post(
                "/api/v1/account/step-up", json={"password": "password123"}
            )
            assert resp.status_code == 200
            assert resp.get_json()["sudoUntil"]
            # The guarded route now runs (404: the tenant does not exist,
            # which means the step-up gate was passed).
            resp = client.post(
                "/api/v1/system/tenants/999/impersonate", json={"reason": "x"}
            )
            assert resp.status_code in (404, 422)

    def test_read_routes_need_no_step_up(self, app, client, seeded_db):
        _make_superadmin(seeded_db)
        self._login(client)
        with patch.dict(app.config, {"STEP_UP_ENFORCED": True}):
            assert client.get("/api/v1/system/tenants").status_code == 200
            assert client.get("/api/v1/manager/plugins/").status_code == 200
