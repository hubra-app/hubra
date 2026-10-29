"""Tests for the second security review's fixes (R2-*)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from flask_jwt_extended import create_access_token

from hubra.core.errors import ApiError

from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant


def _user(db, email: str, **kw) -> User:
    user = User(
        email=email, first_name="A", last_name="B", private_email_verified=True, **kw
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    return user


def _member(db, user: User, seeded_db, roles=()) -> Member:
    member = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    member.roles = list(roles)
    db.session.add(member)
    db.session.flush()
    return member


def _login(client, email: str, password: str = "password123"):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def _account_token(app, client, user: User) -> None:
    """The cookie an SSO sign-in leaves: the account, no club, no session."""
    with app.test_request_context():
        token = create_access_token(
            identity=f"user:{user.id}", additional_claims={"user_id": user.id}
        )
    client.set_cookie("access_token_cookie", token)


def _member_by_email(db, email):
    return (
        db.session.query(Member)
        .join(User, Member.user_id == User.id)
        .filter(User.email == email)
        .one()
    )


# ── R2-H1: an SSO sign-in never opens a club ─────────────────────────────────


class TestAccountTokenInAClub:
    def test_account_token_is_refused_in_a_club(self, app, client, db, seeded_db):
        club = Tenant(name="Club", slug="club-h1", plan="starter", status="active")
        db.session.add(club)
        db.session.commit()
        _account_token(app, client, seeded_db["user"])

        resp = client.get("/api/v1/members/", headers={"X-Tenant-Slug": "club-h1"})
        assert resp.status_code == 401
        resp = client.get(
            "/api/v1/notifications/", headers={"X-Tenant-Slug": "club-h1"}
        )
        assert resp.status_code == 401

    def test_disabled_member_is_refused(self, app, client, db, seeded_db):
        seeded_db["admin"].is_disabled = True
        db.session.commit()
        _account_token(app, client, seeded_db["user"])
        assert client.get("/api/v1/members/").status_code == 401
        assert client.get("/api/v1/notifications/").status_code == 403

    def test_disabled_club_admin_cannot_manage_admins(
        self, app, client, db, seeded_db
    ):
        club = Tenant(name="Club", slug="club-adm", plan="starter", status="active")
        db.session.add(club)
        db.session.flush()
        boss = _user(db, "boss@test.ch")
        _member(db, boss, seeded_db, roles=[seeded_db["owner_role"]])
        db.session.add(UserTenant(user_id=boss.id, tenant_id=club.id))
        db.session.commit()
        _login(client, "boss@test.ch")
        assert client.get(f"/api/v1/system/tenants/{club.id}/admins").status_code == 200

        _member_by_email(db, "boss@test.ch").is_disabled = True
        db.session.commit()
        _account_token(app, client, boss)  # the manager portal's sign-in
        resp = client.get(f"/api/v1/system/tenants/{club.id}/admins")
        assert resp.status_code == 403


# ── R2-H2: email and password only with the current password ────────────────


class TestAccountChanges:
    def test_patch_account_refuses_email_and_password(
        self, client, db, seeded_db, auth_headers
    ):
        for body in ({"email": "evil@attacker.test"}, {"password": "hunter22hunter"}):
            resp = client.patch("/api/v1/account/", json=body)
            assert resp.status_code == 400
        db.session.refresh(seeded_db["user"])
        assert seeded_db["user"].email == "admin@test.ch"
        assert seeded_db["user"].check_password("password123")

    def test_no_account_change_while_impersonating(self, app, client, seeded_db):
        until = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        with app.test_request_context():
            token = create_access_token(
                identity=str(seeded_db["admin"].id),
                additional_claims={
                    "impersonator_id": 99,
                    "impersonator_user_id": 99,
                    "impersonation_expires_at": until,
                },
            )
        client.set_cookie("access_token_cookie", token)
        assert client.get("/api/v1/members/").status_code == 200

        calls = [
            ("patch", "/api/v1/account/", {"first_name": "X"}),
            ("patch", "/api/v1/account/profile", {"firstName": "X"}),
            ("patch", "/api/v1/account/email", {"email": "x@y.ch"}),
            ("post", "/api/v1/account/password", {"newPassword": "x"}),
            ("post", "/api/v1/account/change-password", {"newPassword": "x"}),
        ]
        for method, url, body in calls:
            resp = getattr(client, method)(url, json=body)
            assert resp.status_code == 403, url
            assert resp.get_json()["error"] == "IMPERSONATION_RESTRICTED"


# ── R2-M1: removing someone takes their roles, so it follows check_grant ────


class TestLifecycleFollowsRoles:
    def test_archive_holder_cannot_archive_an_admin(
        self, client, db, seeded_db, permissioned_member_factory
    ):
        admin = _member(db, _user(db, "boardadmin@test.ch"), seeded_db, [seeded_db["role"]])
        db.session.commit()
        headers = permissioned_member_factory(
            ["members.members.archive", "members.members.delete"]
        )
        resp = client.post(f"/api/v1/members/{admin.id}/archive", headers=headers)
        assert resp.status_code == 403
        resp = client.delete(f"/api/v1/members/{admin.id}/soft", headers=headers)
        assert resp.status_code == 403

    def test_custom_admin_role_cannot_be_disabled(
        self, client, db, seeded_db, auth_headers
    ):
        from hubra.core.models.role import Role

        board = Role(name="Vorstand", is_admin=True, is_default=False)
        db.session.add(board)
        db.session.flush()
        target = _member(db, _user(db, "vorstand@test.ch"), seeded_db, [board])
        db.session.commit()
        resp = client.post(f"/api/v1/members/{target.id}/disable")
        assert resp.status_code == 409


# ── R2-M2: a new password and "sign out everywhere" end the other sessions ──


class TestSessionsEndEverywhere:
    def _old_and_new(self, app, client, seeded_db):
        _account_token(app, client, seeded_db["user"])
        old = client.get_cookie("access_token_cookie").value
        time.sleep(1.1)  # tokens carry whole seconds
        return old

    def test_password_change(self, app, client, db, seeded_db):
        old = self._old_and_new(app, client, seeded_db)
        resp = client.post(
            "/api/v1/account/password",
            json={"currentPassword": "password123", "newPassword": "a-new-Passw0rd!"},
        )
        assert resp.status_code == 200
        # This browser keeps a fresh session...
        assert client.get("/api/v1/account/profile").status_code == 200
        # ...and the token from before is dead.
        client.set_cookie("access_token_cookie", old)
        assert client.get("/api/v1/account/profile").status_code == 401

    def test_sign_out_everywhere(self, app, client, db, seeded_db):
        old = self._old_and_new(app, client, seeded_db)
        resp = client.post("/api/v1/account/all-sessions/revoke-all")
        assert resp.status_code == 200
        assert client.get("/api/v1/account/profile").status_code == 200
        client.set_cookie("access_token_cookie", old)
        assert client.get("/api/v1/account/profile").status_code == 401


# ── R2-M3: club mail can't be used to spoof or phish ─────────────────────────


class TestClubMail:
    def test_test_mail_comes_from_the_platform_sender(
        self, client, monkeypatch, seeded_db, auth_headers
    ):
        from hubra.core.services import email as email_svc
        from hubra.core.services import platform_settings

        sent = {}

        def fake_send(to, to_name, sender_email, *args, **kwargs):
            sent.update(to=to, sender=sender_email)
            return True

        monkeypatch.setattr(email_svc, "_send_via_smtp", fake_send)
        monkeypatch.setattr(
            platform_settings,
            "relay",
            lambda: platform_settings.Relay(
                "smtp.example", 587, "", "", "noreply@hubra.example", "Hubra"
            ),
        )
        resp = client.post(
            "/api/v1/mail/test",
            json={"from": "ceo@bank.example", "to": "x@example.com", "subject": "Hi"},
        )
        assert resp.status_code == 200
        assert sent == {"to": "x@example.com", "sender": "noreply@hubra.example"}

    def test_mail_texts_keep_only_their_own_links(self):
        from hubra.core.services.mail_i18n import _safe_text

        assert "evil" not in _safe_text('<a href="https://evil.example">Go</a>')
        assert 'href="{{reset_url}}"' in _safe_text('<a href="{{reset_url}}">Go</a>')
        assert "<img" not in _safe_text('<img src="https://evil.example/t.png">')

    def test_invites_per_day_are_capped(self, app, db, seeded_db, monkeypatch):
        from hubra.core.models.club_invite import ClubInvite
        from hubra.core.tenant import invites

        club = Tenant(name="Spam", slug="spam", plan="starter", status="active")
        db.session.add(club)
        db.session.flush()
        monkeypatch.setattr(invites, "INVITES_PER_DAY", 2)
        monkeypatch.setattr(
            "hubra.core.services.email.send_club_invite", lambda *a, **k: None
        )
        with app.test_request_context():
            invites.send_invite(club, "a@x.ch", "Admin")
            invites.send_invite(club, "b@x.ch", "Admin")
            with pytest.raises(ApiError) as caught:
                invites.send_invite(club, "c@x.ch", "Admin")
        assert caught.value.code == "TOO_MANY_INVITES"
        assert db.session.query(ClubInvite).filter_by(tenant_id=club.id).count() == 2


# ── Forgot password works for an account in no club's schema ────────────────


def test_password_reset_for_an_account_without_a_member(client, db, monkeypatch):
    from hubra.core.services import email as email_svc

    _user(db, "nomember@test.ch")
    db.session.commit()
    links = []
    monkeypatch.setattr(
        email_svc, "send_password_reset", lambda to, name, url, **k: links.append(url)
    )
    resp = client.post(
        "/api/v1/auth/forgot-password", json={"email": "nomember@test.ch"}
    )
    assert resp.status_code == 200
    assert len(links) == 1
    token = links[0].split("#token=")[1]
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "a-brand-new-Passw0rd"},
    )
    assert resp.status_code == 200
    assert _login(client, "nomember@test.ch", "a-brand-new-Passw0rd").status_code == 200
