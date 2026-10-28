"""POST /auth/refresh keeps the session's claims in the new access token.

Without them a superadmin lost the manager portal as soon as the first
access token expired (user_id gone), and a club member was refused in their
own club (tenant_slug gone).
"""

from flask_jwt_extended import create_refresh_token, decode_token


def _refreshed_claims(app, client, identity, claims):
    with app.app_context():
        token = create_refresh_token(identity=identity, additional_claims=claims)
    client.set_cookie("refresh_token_cookie", token)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    access = next(
        c.split(";")[0].split("=", 1)[1]
        for c in resp.headers.getlist("Set-Cookie")
        if c.startswith("access_token_cookie=")
    )
    with app.app_context():
        return decode_token(access)


def test_refresh_keeps_user_id(app, client, seeded_db):
    user = seeded_db["user"]
    claims = _refreshed_claims(
        app, client, f"user:{user.id}", {"user_id": user.id}
    )
    assert claims["sub"] == f"user:{user.id}"
    assert claims["user_id"] == user.id


def test_refresh_keeps_impersonation_claims(app, client, seeded_db):
    user = seeded_db["user"]
    session = {
        "user_id": user.id,
        "impersonator_id": 7,
        "impersonator_user_id": 3,
        "impersonation_reason": "support",
        "impersonation_expires_at": "2030-01-01T00:00:00+00:00",
    }
    claims = _refreshed_claims(app, client, f"user:{user.id}", session)
    for key, value in session.items():
        assert claims[key] == value


def test_superadmin_still_superadmin_after_refresh(app, client, seeded_db, db):
    user = seeded_db["user"]
    user.is_superadmin = True
    db.session.commit()
    _refreshed_claims(app, client, f"user:{user.id}", {"user_id": user.id})

    resp = client.get("/api/v1/system/tenants")
    assert resp.status_code == 200


def test_ensure_superadmins_promotes_and_skips_unknown(app, seeded_db, db):
    user = seeded_db["user"]
    assert not user.is_superadmin
    result = app.test_cli_runner().invoke(
        args=["ensure-superadmins", "--emails", f" {user.email.upper()} ,nobody@x.ch"]
    )
    assert result.exit_code == 0, result.output
    assert "nobody@x.ch" in result.output
    db.session.refresh(user)
    assert user.is_superadmin
