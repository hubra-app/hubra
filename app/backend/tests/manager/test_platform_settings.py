"""Platform settings: the mail relay, its API and who sends which mail."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.models.setting import Setting
from hubra.core.services import email, platform_settings
from hubra.core.services.platform_settings import PlatformSettingError


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.session.rollback()
    db.session.query(PlatformSetting).delete()
    for key in ("club.notification_sender_email", "club.notification_sender_name"):
        row = db.session.get(Setting, key)
        if row is not None:
            db.session.delete(row)
    db.session.commit()


@pytest.fixture
def superadmin(client, seeded_db, db):
    seeded_db["user"].is_superadmin = True
    db.session.commit()
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    yield
    seeded_db["user"].is_superadmin = False
    db.session.commit()


def _club_sender(db, address="club@example.org", name="Example Club"):
    db.session.add(Setting(key="club.notification_sender_email", value=address))
    db.session.add(Setting(key="club.notification_sender_name", value=name))
    db.session.commit()


# ── Service ──────────────────────────────────────────────────────────────────


def test_defaults_come_from_env(app, db):
    app.config["SMTP_HOST"] = "relay.example.net"
    app.config["MAIL_FROM"] = "noreply@hubra.example"
    try:
        relay = platform_settings.relay()
        assert relay.host == "relay.example.net"
        assert relay.sender_email == "noreply@hubra.example"
        assert relay.sender_name == "Hubra"
    finally:
        app.config["MAIL_FROM"] = ""


def test_stored_value_wins_and_null_resets(app, db):
    platform_settings.set_many({"mail.relay.host": "smtp.example.com"})
    db.session.commit()
    assert platform_settings.get("mail.relay.host") == "smtp.example.com"

    platform_settings.set_many({"mail.relay.host": None})
    db.session.commit()
    assert platform_settings.get("mail.relay.host") == app.config["SMTP_HOST"]


def test_password_is_encrypted_and_never_listed(db):
    platform_settings.set_many({"mail.relay.password": "hunter2"})
    db.session.commit()

    row = db.session.get(PlatformSetting, "mail.relay.password")
    assert row.secret and row.value and "hunter2" not in row.value
    assert platform_settings.get("mail.relay.password") == "hunter2"

    listed = {s["key"]: s for s in platform_settings.as_list()}
    assert listed["mail.relay.password"]["value"] == ""
    assert listed["mail.relay.password"]["isSet"] is True
    assert listed["mail.relay.password"]["source"] == "platform"


def test_invalid_values_are_refused_without_writing(db):
    with pytest.raises(PlatformSettingError) as exc:
        platform_settings.set_many(
            {"mail.relay.host": "ok.example.com", "mail.relay.port": "99999"}
        )
    assert "mail.relay.port" in exc.value.args[0]
    assert db.session.get(PlatformSetting, "mail.relay.host") is None

    with pytest.raises(PlatformSettingError):
        platform_settings.set_many({"nope": "x"})


# ── Who sends ────────────────────────────────────────────────────────────────


def _send(**kw):
    with patch.object(email, "_send_via_smtp", return_value=True) as smtp:
        email._send("member@example.com", "Alice", "Hi", "<p>Hi</p>", "Hi", **kw)
    return smtp


def test_system_mail_comes_from_the_platform(db):
    _club_sender(db)
    platform_settings.set_many(
        {
            "mail.system.sender_email": "noreply@hubra.example",
            "mail.system.sender_name": "Hubra",
        }
    )
    db.session.commit()

    smtp = _send(system=True)
    args, kwargs = smtp.call_args
    assert args[2:4] == ("noreply@hubra.example", "Hubra")
    assert kwargs["reply_to"] is None
    assert kwargs["route"] is None  # the platform relay


def test_club_mail_uses_the_platform_sender_with_club_reply_to(db):
    _club_sender(db)
    platform_settings.set_many({"mail.system.sender_email": "noreply@hubra.example"})
    db.session.commit()

    smtp = _send()
    args, kwargs = smtp.call_args
    assert args[2:4] == ("noreply@hubra.example", "Example Club")
    assert kwargs["reply_to"] == "club@example.org"
    assert kwargs["route"] is None


def test_club_with_its_own_mailbox_keeps_sending_as_itself(db):
    _club_sender(db)
    platform_settings.set_many({"mail.system.sender_email": "noreply@hubra.example"})
    db.session.commit()

    with patch.object(email, "_club_mailbox", return_value=("club@example.org", "pw")):
        smtp = _send()
    args, kwargs = smtp.call_args
    assert args[2] == "club@example.org"
    assert kwargs["route"].user == "club@example.org"

    with patch.object(email, "_club_mailbox", return_value=("club@example.org", "pw")):
        smtp = _send(system=True)
    assert smtp.call_args.args[2] == "noreply@hubra.example"


def test_without_a_platform_sender_the_club_sender_is_used(db):
    _club_sender(db)
    smtp = _send(system=True)
    assert smtp.call_args.args[2] == "club@example.org"


def test_auth_mails_are_system_mails(db):
    with patch.object(email, "_send") as send:
        email.send_password_reset("a@example.com", "A", "https://x/reset")
        email.send_email_verification("a@example.com", "A", "https://x/verify")
    assert all(c.kwargs.get("system") is True for c in send.call_args_list)


# ── API ──────────────────────────────────────────────────────────────────────


def test_api_needs_the_permission(client, auth_headers):
    assert client.get("/api/v1/manager/platform/settings").status_code == 403
    assert (
        client.patch(
            "/api/v1/manager/platform/settings", json={"mail.relay.host": "x.example"}
        ).status_code
        == 403
    )


def test_api_lists_and_updates(client, superadmin, db):
    body = client.get("/api/v2/manager/platform/settings").get_json()
    keys = {s["key"] for s in body["settings"]}
    assert {
        "mail.relay.host",
        "mail.relay.password",
        "mail.system.sender_email",
    } <= keys

    resp = client.patch(
        "/api/v1/manager/platform/settings",
        json={"mail.relay.host": "smtp.example.com", "mail.relay.password": "s3cret"},
    )
    assert resp.status_code == 200
    listed = {s["key"]: s for s in resp.get_json()["settings"]}
    assert listed["mail.relay.host"]["value"] == "smtp.example.com"
    assert listed["mail.relay.password"]["value"] == ""

    from hubra.core.models.tenant import GlobalAuditEntry

    entry = (
        db.session.query(GlobalAuditEntry)
        .filter_by(action="platform.settings.update")
        .order_by(GlobalAuditEntry.id.desc())
        .first()
    )
    assert entry.details["mail.relay.password"] == "***"


def test_api_reports_invalid_values(client, superadmin):
    resp = client.patch(
        "/api/v1/manager/platform/settings", json={"mail.system.sender_email": "nope"}
    )
    assert resp.status_code == 400
    assert "mail.system.sender_email" in resp.get_json()["details"]


def test_api_test_mail(client, superadmin, db):
    platform_settings.set_many(
        {
            "mail.relay.host": "smtp.example.com",
            "mail.system.sender_email": "noreply@hubra.example",
        }
    )
    db.session.commit()
    with patch.object(email, "_send_via_smtp", return_value=True) as smtp:
        resp = client.post(
            "/api/v1/manager/platform/mail/test", json={"to": "ops@example.com"}
        )
    assert resp.status_code == 200
    assert smtp.call_args.args[0] == "ops@example.com"
    assert smtp.call_args.args[2] == "noreply@hubra.example"
