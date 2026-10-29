"""The account on the SSO portal: profile, password and sessions of every club."""

from __future__ import annotations

from unittest.mock import patch

PASSWORD = "password123"


def _login(client, email):
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.get_json()


def _user_without_club(db, email="solo@test.ch"):
    from hubra.core.models.user import User

    user = User(email=email, first_name="Solo", last_name="User")
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def test_profile_works_without_a_club(client, db):
    _user_without_club(db)
    _login(client, "solo@test.ch")
    resp = client.get("/api/v1/account/profile")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["email"] == "solo@test.ch"
    assert body["name"] == "Solo User"
    assert body["emailVerified"] is False


def test_profile_update(client, db):
    user = _user_without_club(db)
    _login(client, "solo@test.ch")
    resp = client.patch(
        "/api/v1/account/profile",
        json={
            "name": "Anna Muster",
            "avatarColor": "#7441e0",
            "profileNote": "Hallo",
            "language": "en-GB",
            "isSuperadmin": True,  # ignored
        },
    )
    assert resp.status_code == 200
    db.session.refresh(user)
    assert (user.first_name, user.last_name) == ("Anna", "Muster")
    assert user.avatar_color == "#7441e0"
    assert user.language == "en-GB"
    assert user.is_superadmin is False


def test_profile_update_rejects_bad_values(client, db):
    _user_without_club(db)
    _login(client, "solo@test.ch")
    for body in (
        {"name": " "},
        {"name": "b" * 256},
        {"lastName": "a" * 256},
        {"avatarColor": "red"},
        {"language": "xx"},
    ):
        assert client.patch("/api/v1/account/profile", json=body).status_code == 400


def test_profile_from_a_club_session_is_the_same_account(client, seeded_db):
    _login(client, "admin@test.ch")
    assert client.get("/api/v1/account/profile").get_json()["email"] == "admin@test.ch"


def test_password_change(client, db):
    user = _user_without_club(db)
    _login(client, "solo@test.ch")
    resp = client.post(
        "/api/v1/account/password",
        json={"currentPassword": PASSWORD, "newPassword": "Neues-Passwort-42!"},
    )
    assert resp.status_code == 200
    db.session.refresh(user)
    assert user.check_password("Neues-Passwort-42!")


def test_password_change_needs_the_current_password(client, db):
    _user_without_club(db)
    _login(client, "solo@test.ch")
    resp = client.post(
        "/api/v1/account/password",
        json={"currentPassword": "wrong", "newPassword": "Neues-Passwort-42!"},
    )
    assert resp.status_code == 401


def test_password_change_notifies_a_verified_address(client, tenant_pair):
    _login(client, "user@test.ch")
    with patch("hubra.api.auth.routes.email_svc.send_password_changed") as notify:
        resp = client.post(
            "/api/v1/account/password",
            json={"currentPassword": PASSWORD, "newPassword": "Neues-Passwort-42!"},
        )
    assert resp.status_code == 200
    notify.assert_called_once()


def test_sessions_of_every_club(client, tenant_pair):
    _login(client, "user@test.ch")
    resp = client.get("/api/v1/account/all-sessions")
    assert resp.status_code == 200
    sessions = resp.get_json()
    assert sessions, "the sign-in should have recorded a session"
    assert all(s["club"]["slug"] in {"tenant-a", "tenant-b"} for s in sessions)


def test_sessions_without_a_club_are_empty(client, db):
    _user_without_club(db)
    _login(client, "solo@test.ch")
    assert client.get("/api/v1/account/all-sessions").get_json() == []


def test_revoke_session_in_an_unknown_club(client, tenant_pair):
    _login(client, "user@test.ch")
    resp = client.delete("/api/v1/account/all-sessions/nope/1")
    assert resp.status_code == 404


def test_sign_out_everywhere(client, tenant_pair):
    _login(client, "user@test.ch")
    resp = client.post("/api/v1/account/all-sessions/revoke-all")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
