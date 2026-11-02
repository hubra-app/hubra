"""Outbound mail monitoring: the event log of every send, relay checks,
alert mails to platform staff and each admin's alert choices."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from hubra.core.models.platform_event import PlatformEvent
from hubra.core.services import email, platform_monitor, platform_settings

BASE = "/api/v1/manager/platform"
MAIN = "mail.infomaniak.example"
FALLBACK = "smtp-relay.brevo.example"


class _FakeRedis:
    def __init__(self):
        self.keys = {}

    def exists(self, key):
        return key in self.keys

    def set(self, key, value, ex=None):
        self.keys[key] = value

    def get(self, key):
        return self.keys.get(key)

    def ttl(self, key):
        return 600 if key in self.keys else -2

    def delete(self, key):
        self.keys.pop(key, None)


@pytest.fixture(autouse=True)
def _fresh_checks():
    platform_monitor._local_checks.clear()
    yield
    platform_monitor._local_checks.clear()


@pytest.fixture
def relays(db):
    platform_settings.set_many(
        {
            "mail.relay.host": MAIN,
            "mail.relay.user": "infomaniak-login",
            "mail.relay.password": "secret",
            "mail.fallback.host": FALLBACK,
            "mail.fallback.user": "brevo-login",
            "mail.fallback.password": "brevo-key",
            "mail.system.sender_email": "noreply@hubra.example",
        }
    )
    db.session.commit()
    redis = _FakeRedis()
    with patch("hubra.core.redis_client.get_redis_client", return_value=redis):
        yield redis


@pytest.fixture
def staff(seeded_db, db):
    """admin@test.ch as a superadmin: the one platform admin who gets alerts."""
    seeded_db["user"].is_superadmin = True
    db.session.commit()
    return seeded_db["user"]


def _send(to="member@example.com", subject="Hi", **kw):
    return email._send_via_smtp(
        to, "Alice", "noreply@hubra.example", "Hubra", subject, "<p>Hi</p>", "Hi", **kw
    )


def _events(db, **filters):
    # By id: without ORDER BY, Postgres may return them in any order.
    return (
        db.session.query(PlatformEvent)
        .filter_by(**filters)
        .order_by(PlatformEvent.id)
        .all()
    )


def _alert_mails(deliver):
    return [c for c in deliver.call_args_list if "[Hubra]" in c.args[3]]


# ── The event log of every send ───────────────────────────────────────────────


def test_a_sent_mail_is_logged(db, relays):
    with patch.object(email, "_deliver"):
        _send(subject="Rechnung 12")
    (event,) = _events(db, category="mail")
    assert event.kind == "mail.sent"
    assert event.level == "info"
    assert event.details["to"] == "member@example.com"
    assert event.details["subject"] == "Rechnung 12"
    assert event.details["relay"] == MAIN


def test_fallback_is_logged_and_alerts_staff_once(db, relays, staff):
    def deliver(route, sender, to, message):
        if route.host == MAIN:
            raise email.smtplib.SMTPSenderRefused(452, b"Quota exceeded", "x")

    with patch.object(email, "_deliver", side_effect=deliver) as d:
        _send()
        # The main relay is marked down now: the next mail goes straight to
        # the fallback, is logged as such, and raises no second alert.
        relays.keys.pop(email._PRIMARY_DOWN_KEY)
        _send()

    # (The alert mail went out through the fallback as well.)
    events = [
        e
        for e in _events(db, kind="mail.fallback")
        if not e.details["subject"].startswith("[Hubra]")
    ]
    assert len(events) == 2
    assert events[0].level == "warning"
    assert events[0].details["primary"] == MAIN
    assert "Quota exceeded" in events[0].details["primary_error"]
    assert len(_events(db, category="alert", kind="fallback_used")) == 1
    alerts = _alert_mails(d)
    assert [c.args[2] for c in alerts] == [staff.email]


def test_both_relays_failing_logs_an_error_and_alerts(db, relays, staff):
    def deliver(route, sender, to, message):
        raise OSError(f"{route.host} unreachable")

    with patch.object(email, "_deliver", side_effect=deliver) as d:
        with pytest.raises(email.EmailDeliveryError):
            _send()

    event = _events(db, kind="mail.failed")[0]
    assert event.level == "error"
    assert event.details["primary"] == MAIN
    assert len(_events(db, category="alert", kind="delivery_failed")) == 1
    # The alert mail itself could not go out either; it is logged, without
    # raising another alert.
    assert len(_alert_mails(d)) >= 1
    assert len(_events(db, category="alert")) == 1


def test_a_refused_recipient_is_a_warning_without_alert(db, relays, staff):
    refused = email.smtplib.SMTPRecipientsRefused({"x@example.com": (550, b"no")})
    with patch.object(email, "_deliver", side_effect=refused):
        with pytest.raises(email.EmailDeliveryError):
            _send(to="x@example.com")
    (event,) = _events(db, kind="mail.failed")
    assert event.level == "warning"
    assert _events(db, category="alert") == []


def test_test_mails_never_alert(db, relays, staff):
    with patch.object(email, "_deliver", side_effect=OSError("down")):
        with pytest.raises(email.EmailDeliveryError):
            _send(via="relay")
    (event,) = _events(db, kind="mail.failed")
    assert event.details["test"] is True
    assert _events(db, category="alert") == []


def test_alerts_are_throttled_per_type(db, relays, staff):
    with patch.object(email, "_deliver", side_effect=OSError("down")):
        for _ in range(3):
            with pytest.raises(email.EmailDeliveryError):
                _send()
    assert len(_events(db, kind="mail.failed")) >= 3
    assert len(_events(db, category="alert", kind="delivery_failed")) == 1


def test_a_log_write_failure_never_stops_a_mail(db, relays):
    with (
        patch.object(email, "_deliver"),
        patch.object(platform_monitor, "record", side_effect=RuntimeError("db gone")),
    ):
        assert _send() is True


def test_prune_drops_old_events(db):
    platform_monitor.record("mail", "mail.sent", "new")
    platform_monitor.record("mail", "mail.sent", "old")
    old = _events(db, message="old")[0]
    old.created_at = datetime.now(timezone.utc) - timedelta(days=40)
    db.session.commit()
    assert platform_monitor.prune() == 1
    assert [e.message for e in _events(db)] == ["new"]


# ── Who gets alerts ───────────────────────────────────────────────────────────


def test_recipients_are_staff_who_did_not_turn_it_off(db, seeded_db, staff):
    from hubra.core.models.user import User

    other = User(email="ops@example.com", first_name="Op", last_name="S")
    other.set_password("password123")
    other.is_superadmin = True
    other.platform_alerts = {"fallback_used": False}
    disabled = User(
        email="gone@example.com", first_name="G", last_name="O", is_disabled=True
    )
    disabled.set_password("password123")
    disabled.is_superadmin = True
    db.session.add_all([other, disabled])
    db.session.commit()

    assert {u.email for u in platform_monitor.recipients("delivery_failed")} == {
        staff.email,
        "ops@example.com",
    }
    assert {u.email for u in platform_monitor.recipients("fallback_used")} == {
        staff.email
    }


def test_system_alerts_reach_staff(db, relays, staff):
    from hubra.core.services.alerts import alert_error

    with patch.object(email, "_deliver") as d:
        alert_error("Redis Unavailable", "Redis client could not be initialized")
    assert _events(db, category="system")[0].message == "Redis Unavailable"
    assert [c.args[2] for c in _alert_mails(d)] == [staff.email]


# ── Relay checks ──────────────────────────────────────────────────────────────


def _smtp(fail_login=False):
    server = MagicMock()
    if fail_login:
        server.login.side_effect = email.smtplib.SMTPAuthenticationError(
            535, b"Authentication failed"
        )
    return server


def test_check_relay_logs_in_without_sending(db, relays):
    server = _smtp()
    with patch(
        "hubra.core.services.platform_monitor.smtplib.SMTP", return_value=server
    ):
        result = platform_monitor.check_relay("relay")
    assert result["ok"] is True
    assert [s["step"] for s in result["steps"]] == [
        "connect",
        "ehlo",
        "starttls",
        "login",
    ]
    server.login.assert_called_once_with("infomaniak-login", "secret")
    server.sendmail.assert_not_called()


def test_check_relay_reports_the_failing_step(db, relays):
    with patch(
        "hubra.core.services.platform_monitor.smtplib.SMTP",
        return_value=_smtp(fail_login=True),
    ):
        result = platform_monitor.check_relay("fallback")
    assert result["ok"] is False
    assert result["steps"][-1]["step"] == "login"
    assert "Authentication failed" in result["error"]


def test_unset_fallback_is_not_configured(db):
    assert platform_monitor.check_relay("fallback")["configured"] is False


def test_relay_down_after_two_failures_and_back(db, relays, staff):
    smtp = "hubra.core.services.platform_monitor.smtplib.SMTP"
    with patch.object(email, "_deliver") as d:
        with patch(smtp, side_effect=OSError("refused")):
            assert platform_monitor.run_check("relay")["down"] is False
            assert _events(db, category="relay") == []
            assert platform_monitor.run_check("relay")["down"] is True
            assert platform_monitor.run_check("relay")["down"] is True
        assert [e.kind for e in _events(db, category="relay")] == ["relay.down"]
        with patch(smtp, return_value=_smtp()):
            assert platform_monitor.run_check("relay")["down"] is False
    assert [e.kind for e in _events(db, category="relay")] == ["relay.down", "relay.up"]
    # Down and back: two mails, never throttled.
    assert len(_alert_mails(d)) == 2


def test_beat_task_checks_both(db, relays):
    from hubra.core.tasks.mail_monitor_tasks import check_mail_relays

    with patch(
        "hubra.core.services.platform_monitor.smtplib.SMTP", return_value=_smtp()
    ):
        assert check_mail_relays.run() == {"relay": True, "fallback": True}


# ── API ───────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{BASE}/mail-relay"),
        ("POST", f"{BASE}/mail-relay/check"),
        ("POST", f"{BASE}/mail-relay/use-main"),
        ("GET", f"{BASE}/events"),
        ("GET", f"{BASE}/alerts/me"),
        ("PUT", f"{BASE}/alerts/me"),
    ],
)
def test_club_admins_cannot_look(client, auth_headers, method, path):
    assert client.open(path, method=method, json={}).status_code == 403


def test_status_shows_relays_and_counts(client, staff_headers, db, relays):
    with patch.object(email, "_deliver"):
        _send()
    relays.keys[email._PRIMARY_DOWN_KEY] = "1"
    data = client.get(f"{BASE}/mail-relay").get_json()
    assert [r["which"] for r in data["relays"]] == ["relay", "fallback"]
    assert data["relays"][1]["host"] == FALLBACK
    assert data["relays"][1]["login"] is True
    assert data["primary_down"]["active"] is True
    assert data["stats"]["sent"] == 1


def test_check_now_and_use_main(client, staff_headers, db, relays):
    with patch(
        "hubra.core.services.platform_monitor.smtplib.SMTP", return_value=_smtp()
    ):
        resp = client.post(f"{BASE}/mail-relay/check", json={"which": "fallback"})
    assert resp.status_code == 200
    assert [r["which"] for r in resp.get_json()["results"]] == ["fallback"]
    assert client.get(f"{BASE}/mail-relay").get_json()["relays"][1]["last_check"]["ok"]

    assert (
        client.post(f"{BASE}/mail-relay/check", json={"which": "x"}).status_code == 400
    )

    relays.keys[email._PRIMARY_DOWN_KEY] = "1"
    resp = client.post(f"{BASE}/mail-relay/use-main")
    assert resp.get_json()["primary_down"]["active"] is False


def test_event_log_filters_and_pages(client, staff_headers, db):
    platform_monitor.record("mail", "mail.sent", "Sent to a@example.com: Hi")
    platform_monitor.record(
        "mail", "mail.failed", "Not delivered to b@example.com", level="error"
    )
    platform_monitor.record("relay", "relay.down", "Main relay down", level="error")
    db.session.commit()

    data = client.get(f"{BASE}/events?category=mail").get_json()
    assert data["total"] == 2
    assert data["entries"][0]["kind"] == "mail.failed"  # newest first
    assert client.get(f"{BASE}/events?level=error").get_json()["total"] == 2
    assert client.get(f"{BASE}/events?q=b@example").get_json()["total"] == 1
    assert len(client.get(f"{BASE}/events?per_page=1").get_json()["entries"]) == 1
    assert client.get(f"{BASE}/events?category=nope").status_code == 400


def test_my_alert_choices(client, staff_headers, db, seeded_db):
    data = client.get(f"{BASE}/alerts/me").get_json()
    assert data["alerts"] == platform_monitor.default_prefs()

    resp = client.put(f"{BASE}/alerts/me", json={"fallback_used": False})
    assert resp.status_code == 200
    assert resp.get_json()["alerts"]["fallback_used"] is False
    assert resp.get_json()["alerts"]["relay_down"] is True
    db.session.refresh(seeded_db["user"])
    assert seeded_db["user"].platform_alerts["fallback_used"] is False

    assert client.put(f"{BASE}/alerts/me", json={"nope": True}).status_code == 400
    assert client.put(f"{BASE}/alerts/me", json={"system": "yes"}).status_code == 400


def test_support_sees_alerts_but_gets_no_mail(db, seeded_db, staff):
    from hubra.api.global_rbac_seed import seed_global_rbac
    from hubra.core.models.global_role import GlobalRole, UserGlobalRole
    from hubra.core.models.user import User

    seed_global_rbac()
    roles = {r.name: r for r in db.session.query(GlobalRole).all()}
    support = User(email="support@example.com", first_name="Su", last_name="P")
    admin = User(email="admin@example.com", first_name="Ad", last_name="M")
    for u in (support, admin):
        u.set_password("password123")
    db.session.add_all([support, admin])
    db.session.flush()
    db.session.add_all(
        [
            UserGlobalRole(user_id=support.id, role_id=roles["Support"].id),
            UserGlobalRole(user_id=admin.id, role_id=roles["Platform admin"].id),
        ]
    )
    db.session.commit()

    emails = {u.email for u in platform_monitor.recipients("delivery_failed")}
    assert "admin@example.com" in emails
    assert "support@example.com" not in emails
    assert platform_monitor.gets_alert_mails(support) is False
    assert platform_monitor.gets_alert_mails(admin) is True


def test_cooldown_and_retention_are_platform_settings(db, relays, staff):
    from hubra.core.services import platform_settings

    platform_settings.set_many(
        {"alerts.cooldown_minutes": "0", "alerts.retention_days": "7"}
    )
    db.session.commit()
    with patch.object(email, "_deliver", side_effect=OSError("down")):
        for _ in range(2):
            with pytest.raises(email.EmailDeliveryError):
                _send()
    assert len(_events(db, category="alert", kind="delivery_failed")) == 2

    old = _events(db, kind="mail.failed")[0]
    old.created_at = datetime.now(timezone.utc) - timedelta(days=8)
    db.session.commit()
    assert platform_monitor.prune() == 1


def test_alert_settings_are_validated(db):
    from hubra.core.services import platform_settings

    for key, value in (
        ("alerts.cooldown_minutes", "-5"),
        ("alerts.cooldown_minutes", "2000"),
        ("alerts.retention_days", "0"),
        ("alerts.retention_days", "400"),
        ("alerts.manage_url", "not a url"),
    ):
        with pytest.raises(platform_settings.PlatformSettingError):
            platform_settings.set_many({key: value})


def test_my_alerts_says_whether_mails_come(client, staff_headers):
    assert client.get(f"{BASE}/alerts/me").get_json()["receives"] is True
