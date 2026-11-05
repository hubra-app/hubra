"""Discord direct messages for members: per topic, without the bell, the
"mute all" switch, the new topics and their senders, and the account's own
direct messages (sign-in alerts, answers to its requests)."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hubra.core.models.connected_app import ExternalAccount
from hubra.core.models.notification import Notification
from hubra.core.notifications import account_dm, channels, prefs
from hubra.core.notifications.services import notify_ending, notify_member
from tests.notifications.test_reminders import _member

URL = "/api/v1/members/me/notifications"
DM_URL = "/api/v1/account/discord-dms"


@pytest.fixture
def queued(monkeypatch):
    """Discord deliveries queued for the club's app channel, as
    (member id, payload): a club with Discord connected."""
    from hubra.core.tasks import after_commit

    out = []
    monkeypatch.setattr(
        channels, "_club_codes", lambda *a, **kw: {"discord"}
    )
    monkeypatch.setattr(
        "hubra.core.tenant.context.current_tenant",
        lambda: SimpleNamespace(id=1, slug="club-a", settings={}),
    )

    def fake(task, *args, **kwargs):
        if task.name.endswith("deliver_app_notification"):
            out.append((args[1], args[2]))

    monkeypatch.setattr(after_commit, "delay_after_commit", fake)
    return out


def _linked(db, member, discord_id="123"):
    db.session.add(
        ExternalAccount(user_id=member.user_id, provider="discord", external_id=discord_id)
    )
    db.session.flush()


def _bells(db, member_id):
    return db.session.query(Notification).filter_by(member_id=member_id).all()


# ── Topics and defaults ──────────────────────────────────────────────────────


def test_new_topics_and_their_defaults(client, auth_headers):
    topics = client.get(URL, headers=auth_headers).get_json()["topics"]
    for topic in ("bookings", "waitlist", "requests", "payments", "membership",
                  "qualifications", "digest"):
        assert topic in topics
    # A member's own sign-up is quiet in the bell until turned on.
    assert topics["bookings"] == {"bell": False, "push": False}
    assert topics["waitlist"] == {"bell": True, "push": True}
    # The digest is no bell notification: mail (and apps) only.
    assert topics["digest"] == {"mail": False}


def test_digest_has_no_bell(client, auth_headers):
    resp = client.put(URL, json={"digest": {"bell": True}}, headers=auth_headers)
    assert resp.status_code == 422
    resp = client.put(URL, json={"digest": {"mail": True}}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["digest"] is True


def test_quiet_topic_turned_on_is_stored(db, seeded_db, client, auth_headers):
    member = seeded_db["admin"]
    client.put(URL, json={"bookings": {"bell": True}}, headers=auth_headers)
    db.session.refresh(member)
    assert member.notify_prefs == {"bookings": {"bell": True}}
    client.put(URL, json={"bookings": {"bell": False}}, headers=auth_headers)
    db.session.refresh(member)
    assert member.notify_prefs is None


def test_app_channel_is_off_by_default_everywhere():
    for topic in prefs.TOPICS:
        assert prefs.wants(None, topic, "discord") is False


# ── Delivery without the bell, and mute all ──────────────────────────────────


def test_direct_message_without_the_bell(db, seeded_db, queued):
    anna = _member(db, "anna@example.com")
    anna.notify_prefs = {"payments": {"bell": False, "discord": True}}
    _linked(db, anna)
    notify_member(anna.id, "info", "Invoice due soon", "CHF 40.00", topic="payments")
    db.session.flush()

    assert _bells(db, anna.id) == []
    assert [(m, p["title"], p["topic"], p["id"]) for m, p in queued] == [
        (anna.id, "Invoice due soon", "payments", None)
    ]


def test_bell_and_direct_message(db, seeded_db, queued):
    anna = _member(db, "anna@example.com")
    anna.notify_prefs = {"waitlist": {"discord": True}}
    _linked(db, anna)
    notify_member(anna.id, "info", "You got a place", "Training", topic="waitlist")
    db.session.flush()

    assert len(_bells(db, anna.id)) == 1
    assert len(queued) == 1 and queued[0][1]["id"] is not None


def test_not_linked_gets_nothing(db, seeded_db, queued):
    anna = _member(db, "anna@example.com")
    anna.notify_prefs = {"payments": {"discord": True}}
    notify_member(anna.id, "info", "New invoice", "x", topic="payments")
    db.session.flush()
    assert queued == []


def test_mute_all_stops_every_direct_message(db, seeded_db, queued):
    anna = _member(db, "anna@example.com")
    anna.notify_prefs = {"payments": {"discord": True}, "waitlist": {"discord": True}}
    _linked(db, anna)
    anna.user.dm_prefs = {"muted": True}
    db.session.flush()
    notify_member(anna.id, "info", "New invoice", "x", topic="payments")
    notify_member(anna.id, "info", "You got a place", "x", topic="waitlist")
    db.session.flush()
    assert queued == []


def test_mute_from_the_club_settings(db, seeded_db, client, auth_headers):
    resp = client.put(URL, json={"muted": True}, headers=auth_headers)
    assert resp.status_code == 200 and resp.get_json()["muted"] is True
    user = seeded_db["admin"].user
    db.session.refresh(user)
    assert user.dm_prefs == {"muted": True}
    assert client.put(URL, json={"muted": "yes"}, headers=auth_headers).status_code == 422


def test_muted_since_queued_is_not_sent(db, seeded_db, monkeypatch):
    """The worker checks again: muted after it was queued, nothing goes."""
    anna = _member(db, "anna@example.com")
    _linked(db, anna)
    anna.user.dm_prefs = {"muted": True}
    db.session.commit()
    hook_calls = []
    monkeypatch.setattr(
        "hubra.core.tenant.context.current_tenant", lambda: SimpleNamespace(id=1)
    )
    monkeypatch.setattr("hubra.core.modules.is_enabled", lambda *a, **kw: True)
    monkeypatch.setattr(
        "hubra.core.apps.provider",
        lambda code: (SimpleNamespace(code="discord"), SimpleNamespace()),
    )
    monkeypatch.setattr(
        "hubra.core.apps.hook", lambda app, name: lambda *a: hook_calls.append(a)
    )
    assert channels.deliver("discord", anna.id, {"title": "x", "msg": ""}) == 0
    assert hook_calls == []


# ── The senders ──────────────────────────────────────────────────────────────


def _event(db, **fields):
    from hubra.core.models.event import ClubEvent

    event = ClubEvent(
        title=fields.pop("title", "Training"),
        date=fields.pop("date", date.today() + timedelta(days=5)),
        time="18:30",
        type="Meeting",
        **fields,
    )
    db.session.add(event)
    db.session.flush()
    return event


def test_sign_up_confirmation_and_waitlist(db, seeded_db, queued):
    from hubra.api.events.services import EventService

    anna = _member(db, "anna@example.com")
    ben = _member(db, "ben@example.com")
    for m in (anna, ben):
        m.notify_prefs = {"bookings": {"discord": True}, "waitlist": {"discord": True}}
        _linked(db, m, discord_id=str(m.id))
    event = _event(db, max_attendees=1)
    EventService.register(event.id, anna.id, own=True)
    EventService.register(event.id, ben.id, own=True)
    db.session.flush()

    got = {(m, p["title"], p["topic"]) for m, p in queued}
    assert got == {
        (anna.id, "Sign-up confirmed", "bookings"),
        (ben.id, "On the waitlist", "waitlist"),
    }
    # The booking confirmation is quiet in the bell; the waitlist is not.
    assert [n.title for n in _bells(db, anna.id)] == []
    assert [n.title for n in _bells(db, ben.id)] == ["On the waitlist"]
    assert queued[0][1]["msg"].startswith("Training · ")

    # Anna cancels: Ben moves up and hears about it.
    queued.clear()
    EventService.cancel_registration(event.id, anna.id)
    db.session.flush()
    assert (ben.id, "You got a place", "waitlist") in {
        (m, p["title"], p["topic"]) for m, p in queued
    }


def test_approval_outcome_is_a_request_answer(db, seeded_db, queued):
    from hubra.api.events.services import EventService

    anna = _member(db, "anna@example.com")
    anna.notify_prefs = {"requests": {"discord": True}}
    _linked(db, anna)
    event = _event(db, requires_approval=True)
    EventService.register(event.id, anna.id, own=True)
    EventService.decide(event.id, anna.id, True, seeded_db["admin"].id)
    db.session.flush()

    assert ("Sign-up confirmed", "requests") in {
        (p["title"], p["topic"]) for _m, p in queued
    }


def test_invoice_due_soon_new_and_overdue(db, seeded_db, queued, monkeypatch):
    from hubra.core.models.finance import Invoice
    from hubra.core.tasks import finance_tasks

    anna = _member(db, "anna@example.com")
    anna.notify_prefs = {"payments": {"discord": True}}
    _linked(db, anna)
    today = date.today()
    soon = Invoice(
        member_id=anna.id, issued=today, due=today + timedelta(days=3),
        amount=40, status="Open", purpose="membership",
    )
    later = Invoice(
        member_id=anna.id, issued=today, due=today + timedelta(days=10),
        amount=50, status="Open", purpose="membership",
    )
    db.session.add_all([soon, later])
    db.session.flush()

    assert finance_tasks._notify_due_soon(today) == 1
    db.session.flush()
    assert [(p["title"], p["msg"]) for _m, p in queued] == [
        ("Invoice due soon", f"CHF 40.00 · {soon.due:%d.%m.%Y}")
    ]


def test_qualification_ending(db, seeded_db, queued):
    anna = _member(db, "anna@example.com")
    anna.notify_prefs = {"qualifications": {"discord": True}}
    _linked(db, anna)
    notify_ending(anna.id, "J+S Leiterin", date(2026, 12, 5))
    db.session.flush()
    assert [(p["title"], p["msg"]) for _m, p in queued] == [
        ("Qualification ends soon", "J+S Leiterin · 05.12.2026")
    ]


def test_weekly_digest_as_a_direct_message(db, seeded_db, queued):
    from tests.notifications.test_digest import _week
    from tests.notifications.test_reminders import NOW
    from hubra.core.tasks import digest_tasks

    _week(db)
    anna = _member(db, "anna@example.com")  # mail off, Discord on
    anna.notify_prefs = {"digest": {"discord": True}}
    _linked(db, anna)
    db.session.commit()
    with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as mail:
        result = digest_tasks._send_weekly_digests(now=NOW)
    assert mail.call_count == 0
    assert result["messaged"] == 1
    (member_id, payload), = queued
    assert member_id == anna.id and payload["title"] == "Your week"
    names = [f["name"] for f in payload["fields"]]
    assert names == ["Anlässe", "Neue Beiträge", "Noch abstimmen"]
    assert "Trainingsabend" in payload["fields"][0]["value"]


# ── The account's own direct messages ────────────────────────────────────────


def test_account_dm_settings(client, db, seeded_db, auth_headers, monkeypatch):
    monkeypatch.setattr(account_dm, "bot_ready", lambda: True)
    resp = client.get(DM_URL, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == {
        "available": False,  # no Discord linked yet
        "muted": False,
        "kinds": {"sign_in": False, "requests": False},
    }
    db.session.add(
        ExternalAccount(user_id=seeded_db["admin"].user_id, provider="discord", external_id="9")
    )
    db.session.commit()
    resp = client.put(DM_URL, json={"kinds": {"sign_in": True}}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["available"] is True
    assert resp.get_json()["kinds"] == {"sign_in": True, "requests": False}
    for bad in ({}, {"kinds": {"nope": True}}, {"muted": 1}, {"other": True}):
        assert client.put(DM_URL, json=bad, headers=auth_headers).status_code == 422


def test_account_dm_needs_sign_in(client):
    assert client.get(DM_URL).status_code == 401


def _account(db, **prefs_):
    from hubra.core.models.user import User

    user = User(email="solo@test.ch", first_name="Solo", last_name="User")
    user.set_password("password123")
    user.private_email_verified = True
    user.language = "de-CH"
    user.dm_prefs = prefs_ or None
    db.session.add(user)
    db.session.flush()
    db.session.add(ExternalAccount(user_id=user.id, provider="discord", external_id="77"))
    db.session.commit()
    return user


@pytest.fixture
def account_sent(monkeypatch):
    """Account direct messages queued: (discord id, kind, embed, components)."""
    from hubra.core.tasks import connected_app_tasks

    out = []
    monkeypatch.setattr(account_dm, "bot_ready", lambda: True)
    monkeypatch.setattr(
        connected_app_tasks.send_account_dm, "delay", lambda *a: out.append(a)
    )
    return out


def test_sign_in_alert_as_direct_message(app, db, account_sent, monkeypatch):
    from hubra.core.tasks import email_tasks

    monkeypatch.setattr(email_tasks.send_new_device_login_task, "delay", lambda *a: None)
    monkeypatch.setitem(app.config, "SSO_BASE_URL", "https://sso.example.ch")
    _account(db, sign_in=True)
    for ua, ip in (("Chrome/120.0 Windows", "198.51.100.1"),
                   ("Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Firefox/121.0", "192.0.2.4")):
        c = app.test_client()
        c.environ_base.update(HTTP_USER_AGENT=ua, REMOTE_ADDR=ip)
        assert c.post(
            "/api/v1/auth/login", json={"email": "solo@test.ch", "password": "password123"}
        ).status_code == 200

    assert len(account_sent) == 1
    discord_id, kind, embed, components = account_sent[0]
    assert (discord_id, kind) == ("77", "sign_in")
    assert "Neue Anmeldung" in embed["title"]
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields["Gerät"] == "Firefox 121 · Linux"
    assert fields["IP-Adresse"] == "192.0.2.4"
    assert fields["Anmeldung mit"] == "Passwort"
    buttons = components[0]["components"]
    assert buttons[0]["label"] == "Das war ich nicht"
    assert buttons[0]["url"].startswith("https://sso.example.ch/not-me#token=")


def test_account_dm_off_or_muted(db, account_sent):
    user = _account(db, sign_in=True, muted=True)
    assert account_dm.send(user, "sign_in", {"title": "x"}) is False
    user.dm_prefs = {"requests": True}
    assert account_dm.send(user, "sign_in", {"title": "x"}) is False
    assert account_dm.send(user, "requests", {"title": "x"}, now=True) is True
    assert len(account_sent) == 1


def test_support_case_answer_as_direct_message(db, account_sent):
    user = _account(db, requests=True)
    case = SimpleNamespace(id=12, title="Login hängt", status="planned")
    account_dm.support_case_update(user, case, comment="Wir schauen es an.")
    account_dm.support_case_update(user, case)
    titles = [a[2]["title"] for a in account_sent]
    assert titles == ["Antwort zu deiner Meldung #12", "Meldung #12: geplant"]


def test_club_request_decided_as_direct_message(db, account_sent):
    user = _account(db, requests=True)
    req = SimpleNamespace(status="rejected", name="FC Test", admin_note="Name vergeben")
    account_dm.club_request_decided(user, req)
    (_id, kind, embed, _c), = account_sent
    assert kind == "requests" and "Name vergeben" in embed["description"]


def test_platform_dm_opens_a_channel_then_posts(monkeypatch):
    from hubra.core.services import platform_discord

    calls = []

    class Resp:
        status = 200

        def __init__(self, body):
            self.body = body

        def read(self):
            import json

            return json.dumps(self.body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(req, timeout=10):
        calls.append(req.full_url)
        return Resp({"id": "555"})

    monkeypatch.setattr(platform_discord, "_settings", lambda: ("", "tok"))
    monkeypatch.setattr(platform_discord.urllib.request, "urlopen", fake_open)
    platform_discord.dm("77", {"title": "x"})
    assert calls == [
        f"{platform_discord.API}/users/@me/channels",
        f"{platform_discord.API}/channels/555/messages",
    ]
