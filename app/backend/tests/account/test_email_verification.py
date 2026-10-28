"""Email verification as a step after sign-in on the SSO portal.

Covers who has to verify (unverified user, verified user, superadmin with and
without system mail), sending, confirming, changing the address, and the
switch-tenant check that keeps clubs closed until the step is done.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from hubra.core.models.email_verification import EmailVerificationToken
from hubra.core.models.setting import Setting
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant
from hubra.core.services import email_verification, platform_settings

PASSWORD = "password123"
SEND = "hubra.core.services.email_verification.email_svc.send_email_verification"


@pytest.fixture
def mail_on(db):
    """System mail configured: the platform relay has a host and a sender."""
    platform_settings.set_many(
        {
            "mail.relay.host": "smtp.hubra.test",
            "mail.system.sender_email": "noreply@hubra.test",
        }
    )
    db.session.commit()


@pytest.fixture(autouse=True)
def _reset_warning():
    email_verification._warned = False
    yield


def _user(db, email="new@test.ch", *, verified=False, superadmin=False) -> User:
    user = User(
        email=email,
        first_name="New",
        last_name="Person",
        private_email_verified=verified,
        is_superadmin=superadmin,
    )
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, email="new@test.ch"):
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.get_json()
    return resp


def _status(client):
    resp = client.get("/api/v1/account/email-verification")
    assert resp.status_code == 200
    return resp.get_json()


def _token(db, user, raw="raw-token", *, email=None, hours=24) -> str:
    db.session.add(
        EmailVerificationToken(
            user_id=user.id,
            email=email or user.email,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        )
    )
    db.session.commit()
    return raw


# ── Who has to verify ─────────────────────────────────────────────────────────


def test_unverified_user_must_verify_after_login(client, db, mail_on):
    _user(db)
    resp = _login(client)
    assert resp.get_json()["noTenant"] is True  # sign-in itself is not blocked

    status = _status(client)
    assert status == {
        "email": "new@test.ch",
        "verified": False,
        "required": True,
        "mailConfigured": True,
        "sentAt": None,
    }


def test_verified_user_goes_straight_on(client, db, mail_on):
    _user(db, verified=True)
    _login(client)
    status = _status(client)
    assert status["verified"] is True
    assert status["required"] is False


def test_superadmin_is_verified_on_login_when_mail_is_configured(client, db, mail_on):
    user = _user(db, superadmin=True)
    _login(client)
    db.session.refresh(user)
    assert user.private_email_verified is True
    assert _status(client)["required"] is False


def test_superadmin_is_not_flagged_without_mail(client, db, caplog):
    user = _user(db, superadmin=True)
    _login(client)
    with caplog.at_level(
        logging.WARNING, logger="hubra.core.services.email_verification"
    ):
        status = _status(client)
    db.session.refresh(user)
    assert user.private_email_verified is False
    assert status["required"] is False
    assert status["mailConfigured"] is False
    assert "system mail is not configured" in caplog.text


def test_nobody_is_blocked_without_mail(client, db, caplog):
    _user(db)
    _login(client)
    with caplog.at_level(
        logging.WARNING, logger="hubra.core.services.email_verification"
    ):
        status = _status(client)
    assert status["required"] is False
    assert status["mailConfigured"] is False
    assert "system mail is not configured" in caplog.text


def test_a_club_sender_alone_is_not_system_mail(client, db):
    """A fresh install seeds a club sender; system mail needs the platform sender."""
    db.session.add(
        Setting(
            key="club.notification_sender_email",
            value="noreply@hubra.test",
            namespace="club",
        )
    )
    db.session.commit()
    _user(db)
    _login(client)
    assert _status(client)["required"] is False


def test_a_relay_without_a_system_sender_is_not_mail(client, db):
    platform_settings.set_many({"mail.relay.host": "smtp.hubra.test"})
    db.session.commit()
    _user(db)
    _login(client)
    assert _status(client)["mailConfigured"] is False


def test_status_needs_a_session(client, db):
    assert client.get("/api/v1/account/email-verification").status_code == 401


# ── Sending the link ──────────────────────────────────────────────────────────


def test_send_mails_a_link_to_the_sso_portal(app, client, db, mail_on):
    user = _user(db)
    _login(client)
    with (
        patch.dict(app.config, {"SSO_BASE_URL": "https://sso.example.test"}),
        patch(SEND) as send,
    ):
        resp = client.post("/api/v1/account/request-email-verification")
    assert resp.status_code == 202
    to, _name, url = send.call_args.args
    assert to == "new@test.ch"
    assert url.startswith("https://sso.example.test/verify-email#token=")

    token = db.session.query(EmailVerificationToken).filter_by(user_id=user.id).one()
    assert token.email == "new@test.ch"
    assert _status(client)["sentAt"] is not None


def test_resend_invalidates_the_previous_link(client, db, mail_on):
    user = _user(db)
    old = _token(db, user, "old-link")
    _login(client)
    with patch(SEND):
        assert (
            client.post("/api/v1/account/request-email-verification").status_code == 202
        )
    assert (
        client.post("/api/v1/account/verify-email", json={"token": old}).status_code
        == 400
    )


def test_send_without_mail_is_refused(client, db):
    _user(db)
    _login(client)
    with patch(SEND) as send:
        resp = client.post("/api/v1/account/request-email-verification")
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "MAIL_NOT_CONFIGURED"
    send.assert_not_called()


def test_send_when_already_verified_is_refused(client, db, mail_on):
    _user(db, verified=True)
    _login(client)
    with patch(SEND) as send:
        resp = client.post("/api/v1/account/request-email-verification")
    assert resp.status_code == 409
    send.assert_not_called()


def test_signup_sends_the_first_link(client, db, mail_on):
    with patch(SEND) as send:
        resp = client.post(
            "/api/v1/auth/signup",
            json={
                "name": "Neu Mitglied",
                "email": "neu@test.ch",
                "password": "Sicher-Passwort-42!",
            },
        )
    assert resp.status_code == 201
    send.assert_called_once()
    assert _status(client)["required"] is True


# ── Confirming ────────────────────────────────────────────────────────────────


def test_confirm_marks_the_user_verified(client, db, mail_on):
    user = _user(db)
    raw = _token(db, user)
    resp = client.post("/api/v1/account/verify-email", json={"token": raw})
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "verified": True}
    db.session.refresh(user)
    assert user.private_email_verified is True

    # Single use.
    assert (
        client.post("/api/v1/account/verify-email", json={"token": raw}).status_code
        == 400
    )


def test_confirm_works_for_a_user_without_a_club(client, db, mail_on):
    """The old flow looked up a Member and failed for people in no club."""
    user = _user(db)
    raw = _token(db, user)
    assert (
        client.post("/api/v1/account/verify-email", json={"token": raw}).status_code
        == 200
    )


def test_expired_link_is_refused(client, db, mail_on):
    user = _user(db)
    raw = _token(db, user, hours=-1)
    resp = client.post("/api/v1/account/verify-email", json={"token": raw})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "INVALID_TOKEN"


def test_link_for_an_old_address_is_refused(client, db, mail_on):
    user = _user(db)
    raw = _token(db, user, email="old@test.ch")
    assert (
        client.post("/api/v1/account/verify-email", json={"token": raw}).status_code
        == 400
    )
    db.session.refresh(user)
    assert user.private_email_verified is False


def test_unknown_link_is_refused(client, db):
    resp = client.post("/api/v1/account/verify-email", json={"token": "nope"})
    assert resp.status_code == 400


# ── Changing the address ──────────────────────────────────────────────────────


def test_change_email_resets_verification_and_sends_a_link(client, db, mail_on):
    user = _user(db, verified=True)
    _login(client)
    with patch(SEND) as send:
        resp = client.patch(
            "/api/v1/account/email",
            json={"email": "Other@Test.ch", "currentPassword": PASSWORD},
        )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["email"] == "other@test.ch"
    assert body["required"] is True
    assert send.call_args.args[0] == "other@test.ch"
    db.session.refresh(user)
    assert user.email == "other@test.ch"
    assert user.private_email_verified is False


def test_change_email_needs_the_password(client, db, mail_on):
    _user(db)
    _login(client)
    resp = client.patch(
        "/api/v1/account/email", json={"email": "x@test.ch", "currentPassword": "wrong"}
    )
    assert resp.status_code == 401


def test_change_email_to_a_taken_address(client, db, mail_on):
    _user(db)
    _user(db, "taken@test.ch")
    _login(client)
    resp = client.patch(
        "/api/v1/account/email",
        json={"email": "taken@test.ch", "currentPassword": PASSWORD},
    )
    assert resp.status_code == 409


# ── Clubs stay closed until the step is done ──────────────────────────────────


def _club_member(db, user, slug="club-x"):
    from hubra.core.models.member import Member

    tenant = Tenant(name="Club X", slug=slug, plan="starter", status="active")
    db.session.add(tenant)
    db.session.flush()
    db.session.add(UserTenant(user_id=user.id, tenant_id=tenant.id))
    db.session.add(Member(user_id=user.id, status="active"))
    db.session.commit()
    return tenant


def test_switch_tenant_refuses_an_unverified_user(client, db, seeded_db, mail_on):
    user = _user(db)
    _club_member(db, user)
    _login(client)
    resp = client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "club-x"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "EMAIL_NOT_VERIFIED"


def test_switch_tenant_lets_a_verified_user_in(client, db, seeded_db, mail_on):
    user = _user(db, verified=True)
    _club_member(db, user)
    _login(client)
    resp = client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "club-x"})
    assert resp.status_code == 200


def test_switch_tenant_does_not_block_without_mail(client, db, seeded_db):
    user = _user(db)
    _club_member(db, user)
    _login(client)
    resp = client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "club-x"})
    assert resp.status_code == 200


def test_switch_tenant_lets_a_superadmin_in_with_mail(client, db, seeded_db, mail_on):
    user = _user(db, superadmin=True)
    _club_member(db, user)
    _login(client)
    resp = client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "club-x"})
    assert resp.status_code == 200
    db.session.refresh(user)
    assert user.private_email_verified is True
