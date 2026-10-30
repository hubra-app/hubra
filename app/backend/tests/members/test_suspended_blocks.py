"""A member marked "suspended" cannot open the club until set back to active."""

from sqlalchemy import select

from tests.settings.test_settings_kv import _login, _make_role_and_member


def _member(db, email):
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    return db.session.scalar(
        select(Member).join(User, Member.user_id == User.id).where(User.email == email)
    )


def test_a_suspended_member_is_shut_out_and_let_back_in(client, app, db, seeded_db):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        db, seeded_db["tier"], name="Sus", permission_keys=["posts.posts.read"]
    )
    _login(client, "sus@test.ch")
    assert client.get("/api/v1/posts/").status_code == 200

    member = _member(db, "sus@test.ch")
    member.status = "suspended"
    db.session.commit()
    # The session in progress ends at once ...
    assert client.get("/api/v1/posts/").status_code == 401
    # ... and signing in again says why.
    resp = client.post(
        "/api/v1/auth/login", json={"email": "sus@test.ch", "password": "password123"}
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MEMBERSHIP_SUSPENDED"

    member.status = "active"
    db.session.commit()
    _login(client, "sus@test.ch")
    assert client.get("/api/v1/posts/").status_code == 200


def test_admins_cannot_suspend_themselves(client, auth_headers, seeded_db):
    admin = seeded_db["admin"]
    resp = client.patch(f"/api/v1/members/{admin.id}", json={"status": "suspended"})
    assert resp.status_code == 409


def test_an_admin_suspends_a_plain_member(client, app, db, seeded_db, auth_headers):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(db, seeded_db["tier"], name="Plain", permission_keys=[])
    _login(client, "admin@test.ch")
    member = _member(db, "plain@test.ch")
    resp = client.patch(f"/api/v1/members/{member.id}", json={"status": "suspended"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "suspended"
