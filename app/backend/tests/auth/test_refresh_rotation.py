"""POST /auth/refresh rotates the refresh token.

The token just used is blocked ("refresh-rotated") with a minute of grace
for parallel tabs; after that it is refused even though its session is
still alive. A token blocked at logout (type "refresh") is refused at once.
"""

from datetime import datetime, timedelta, timezone

from flask_jwt_extended import create_refresh_token, decode_token
from sqlalchemy import select

from hubra.core.extensions import db as _db
from hubra.core.models.token import TokenBlocklist


def _make_refresh(app, user, extra=None):
    claims = {"user_id": user.id}
    claims.update(extra or {})
    with app.app_context():
        return create_refresh_token(identity=f"user:{user.id}", additional_claims=claims)


def _cookie(resp, name):
    for header in resp.headers.getlist("Set-Cookie"):
        if header.startswith(f"{name}="):
            return header
    return None


def test_refresh_rotates_the_refresh_token(app, client, seeded_db):
    token = _make_refresh(app, seeded_db["user"])
    client.set_cookie("refresh_token_cookie", token)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200

    header = _cookie(resp, "refresh_token_cookie")
    assert header is not None, "refresh did not hand out a new refresh token"
    new_token = header.split(";")[0].split("=", 1)[1]
    with app.app_context():
        old_jti = decode_token(token)["jti"]
        assert decode_token(new_token)["jti"] != old_jti
    # The used token is on the blocklist as rotated.
    row = _db.session.scalar(
        select(TokenBlocklist).where(TokenBlocklist.jti == old_jti)
    )
    assert row is not None and row.type == "refresh-rotated"


def test_rotated_token_still_works_within_the_grace_minute(app, client, seeded_db):
    token = _make_refresh(app, seeded_db["user"])
    client.set_cookie("refresh_token_cookie", token)
    assert client.post("/api/v1/auth/refresh").status_code == 200
    # A parallel tab fires the same (now rotated) token right after.
    client.set_cookie("refresh_token_cookie", token)
    assert client.post("/api/v1/auth/refresh").status_code == 200


def test_rotated_token_is_refused_after_the_grace_minute(app, client, seeded_db):
    token = _make_refresh(app, seeded_db["user"])
    client.set_cookie("refresh_token_cookie", token)
    assert client.post("/api/v1/auth/refresh").status_code == 200

    with app.app_context():
        jti = decode_token(token)["jti"]
    row = _db.session.scalar(select(TokenBlocklist).where(TokenBlocklist.jti == jti))
    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    _db.session.commit()

    client.set_cookie("refresh_token_cookie", token)
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_blocked_token_is_refused_at_once(app, client, seeded_db):
    token = _make_refresh(app, seeded_db["user"])
    with app.app_context():
        jti = decode_token(token)["jti"]
    _db.session.add(TokenBlocklist(jti=jti, type="refresh"))
    _db.session.commit()

    client.set_cookie("refresh_token_cookie", token)
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_keep_claim_sets_the_short_cookie_lifetime(app, client, seeded_db):
    token = _make_refresh(app, seeded_db["user"], {"keep": False})
    client.set_cookie("refresh_token_cookie", token)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    header = _cookie(resp, "refresh_token_cookie")
    assert "Max-Age=86400" in header

    token = _make_refresh(app, seeded_db["user"])  # no keep claim: 30 days
    client.set_cookie("refresh_token_cookie", token)
    header = _cookie(client.post("/api/v1/auth/refresh"), "refresh_token_cookie")
    assert "Max-Age=2592000" in header
