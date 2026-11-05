"""A sign-in from a device the account has not used before sends a mail."""

from __future__ import annotations

import pytest

PASSWORD = "password123"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"


def _seed_mail_texts(db):
    """The shipped mail texts, as flask seed puts them in the database."""
    import json
    from pathlib import Path

    from hubra.core.models.translation import Translation

    seeds = Path(__file__).parents[2] / "hubra" / "core" / "seed_data" / "translations"
    for locale in ("en-GB", "de-CH"):
        texts = json.loads((seeds / f"{locale}.json").read_text(encoding="utf-8"))
        for key, value in texts.items():
            if key.startswith("mail.email."):
                db.session.add(Translation(locale=locale, key=key, value=value))
    db.session.commit()


@pytest.fixture
def sent(monkeypatch, app, db):
    """Mails handed to _send, as (to, subject, html, text)."""
    from hubra.core.services import email as email_svc

    _seed_mail_texts(db)

    monkeypatch.setitem(app.config, "SSO_BASE_URL", "https://sso.example.ch")
    mails = []

    def fake_send(to, name, subject, body_html, body_text, *a, **kw):
        mails.append((to, subject, body_html, body_text))
        return True

    monkeypatch.setattr(email_svc, "_send", fake_send)
    # The mail is queued for the worker; the outbox runs the task's body when
    # the test looks (the eager task would push the worker's own app).
    from hubra.core.tasks import email_tasks

    task = email_tasks.send_new_device_login_task
    outbox = _Outbox(mails, task)
    monkeypatch.setattr(task, "delay", lambda *a, **kw: outbox.pending.append(a))
    return outbox


class _Outbox:
    """The mails sent, after running the queued new-device tasks."""

    def __init__(self, mails, task):
        self.mails, self.task, self.pending = mails, task, []

    def _drain(self):
        while self.pending:
            self.task.run(*self.pending.pop(0))
        return self.mails

    def __eq__(self, other):
        return self._drain() == other

    def __len__(self):
        return len(self._drain())

    def __getitem__(self, i):
        return self._drain()[i]

    def __iter__(self):
        return iter(self._drain())

    def clear(self):
        self._drain().clear()


def _user(db, email="solo@test.ch", verified=True, language="en-GB"):
    from hubra.core.models.user import User

    user = User(email=email, first_name="Solo", last_name="User")
    user.set_password(PASSWORD)
    user.private_email_verified = verified
    user.language = language
    db.session.add(user)
    db.session.commit()
    return user


def _browser(app, ua, ip="127.0.0.1"):
    client = app.test_client()
    client.environ_base["HTTP_USER_AGENT"] = ua
    client.environ_base["REMOTE_ADDR"] = ip
    return client


def _sign_in(client, email="solo@test.ch"):
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.get_json()
    return resp


def _device_cookie(resp):
    return next(
        (
            h
            for h in resp.headers.getlist("Set-Cookie")
            if h.startswith("hubra_device=")
        ),
        None,
    )


def test_first_device_is_learnt_without_a_mail(app, db, sent):
    _user(db)
    resp = _sign_in(_browser(app, CHROME))

    assert sent == []
    cookie = _device_cookie(resp)
    assert cookie is not None and "HttpOnly" in cookie


def test_same_browser_again_sends_nothing(app, db, sent):
    _user(db)
    chrome = _browser(app, CHROME)
    _sign_in(chrome)
    _sign_in(chrome)
    # Signing out keeps the device cookie.
    chrome.post("/api/v1/auth/logout")
    _sign_in(chrome)

    assert sent == []


def test_new_browser_sends_a_mail_to_the_account(app, db, sent):
    _user(db)
    _sign_in(_browser(app, CHROME))
    _sign_in(_browser(app, FIREFOX))

    assert len(sent) == 1
    to, subject, html, text = sent[0]
    assert to == "solo@test.ch"
    assert "New sign-in" in subject
    assert "Firefox 121 · Linux" in text
    assert "127.0.0.1" in text
    assert "Signed in with: Password" in text
    assert "Second step: None" in text
    assert "Active sessions: 2" in text
    assert "https://sso.example.ch/account/sitzungen" in html
    assert "https://sso.example.ch/account/passwort" in html
    assert "https://sso.example.ch/not-me#token=" in html


def test_same_kind_of_browser_on_another_computer_is_new(app, db, sent):
    """The browser's name is not enough: another Chrome on Windows
    elsewhere is new."""
    _user(db)
    _sign_in(_browser(app, CHROME))
    _sign_in(_browser(app, CHROME, ip="198.51.100.7"))

    assert len(sent) == 1


def test_lost_cookie_on_the_same_network_is_probably_known(app, db, sent):
    """Cookies cleared (or a private window): the same browser, language and
    time zone on the same network seen lately counts as known."""
    _user(db)
    _sign_in(_browser(app, CHROME, ip="203.0.113.10"))
    resp = _sign_in(_browser(app, CHROME, ip="203.0.113.99"))  # same /24

    assert sent == []
    assert _device_cookie(resp) is not None  # a new token all the same


def test_lost_cookie_with_another_time_zone_is_new(app, db, sent):
    _user(db)
    first = _browser(app, CHROME)
    first.post(
        "/api/v1/auth/login",
        json={"email": "solo@test.ch", "password": PASSWORD, "timeZone": "Europe/Zurich"},
    )
    resp = _browser(app, CHROME).post(
        "/api/v1/auth/login",
        json={"email": "solo@test.ch", "password": PASSWORD, "timeZone": "Asia/Manila"},
    )
    assert resp.status_code == 200
    assert len(sent) == 1


def test_soft_match_expires_after_thirty_days(app, db, sent):
    from datetime import datetime, timedelta, timezone

    from hubra.core.models.known_device import KnownDevice

    _user(db)
    _sign_in(_browser(app, CHROME))
    for row in db.session.query(KnownDevice).all():
        row.last_seen_at = datetime.now(timezone.utc) - timedelta(days=31)
    db.session.commit()
    _sign_in(_browser(app, CHROME))

    assert len(sent) == 1


def test_ip_network():
    from hubra.core.auth.known_devices import ip_network

    assert ip_network("203.0.113.99") == "203.0.113.0/24"
    assert ip_network("2001:db8:1:2::5") == "2001:db8:1::/48"
    assert ip_network("::ffff:203.0.113.5") == "203.0.113.0/24"
    assert ip_network("nonsense") == ""


def test_describe_device():
    from hubra.core.auth.known_devices import describe_device

    android = (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36"
    )
    iphone = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
    )
    assert describe_device(android, "Chrome", "Android") == "Chrome 141 · Android 14"
    assert describe_device(iphone, "Safari", "iOS") == "Safari 18.1 · iOS 18.1"
    assert describe_device(CHROME, "Chrome", "Windows") == "Chrome 120 · Windows"


def test_mail_is_in_the_accounts_language(app, db, sent):
    _user(db, language="de-CH")
    _sign_in(_browser(app, CHROME))
    _sign_in(_browser(app, FIREFOX))

    _, subject, _, text = sent[0]
    assert "Neue Anmeldung" in subject
    assert "Firefox 121 · Linux" in text
    assert "Anmeldung mit: Passwort" in text


def test_unconfirmed_address_gets_no_mail(app, db, sent):
    _user(db, verified=False)
    _sign_in(_browser(app, CHROME))
    _sign_in(_browser(app, FIREFOX))

    assert sent == []


def test_shared_browser_is_new_for_the_second_account(app, db, sent):
    """One browser, two accounts: each account learns it on its own."""
    _user(db)
    _user(db, "other@test.ch")
    shared = _browser(app, CHROME)
    _sign_in(shared)
    _sign_in(_browser(app, FIREFOX), "other@test.ch")  # other's first device
    _sign_in(shared, "other@test.ch")

    assert [m[0] for m in sent] == ["other@test.ch"]
    _sign_in(shared)  # still known to the first account
    assert len(sent) == 1


def test_signup_learns_the_device(app, db, sent):
    client = _browser(app, CHROME)
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "New Person",
            "email": "new@test.ch",
            "password": "Correct-Horse-Battery-9",
        },
    )
    assert resp.status_code == 201, resp.get_json()
    from hubra.core.models.user import User

    user = db.session.query(User).filter_by(email="new@test.ch").one()
    user.private_email_verified = True
    db.session.commit()
    sent.clear()  # the verification mail

    client.post("/api/v1/auth/logout")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "new@test.ch", "password": "Correct-Horse-Battery-9"},
    )
    assert resp.status_code == 200
    assert sent == []


def test_a_mail_failure_does_not_stop_the_sign_in(app, db, monkeypatch):
    from hubra.core.services import email as email_svc

    def broken(*a, **kw):
        raise RuntimeError("relay down")

    monkeypatch.setattr(email_svc, "_send", broken)
    _user(db)
    _sign_in(_browser(app, CHROME))
    _sign_in(_browser(app, FIREFOX))


def test_club_sign_in_does_not_alert(app, seeded_db, sent):
    """Only sign-ins to the account (SSO) alert; opening a club does not,
    and does not teach the browser either."""
    from hubra.core.models.known_device import KnownDevice
    from hubra.core.models.notification import Notification

    def sign_in(ua, ip):
        resp = _sign_in(_browser(app, ua, ip), "admin@test.ch")
        assert resp.get_json().get("member") is not None  # the club path
        assert _device_cookie(resp) is None

    sign_in(CHROME, "198.51.100.1")
    sign_in(FIREFOX, "192.0.2.1")
    assert sent == []
    from hubra.core.extensions import db

    assert db.session.query(KnownDevice).count() == 0
    assert (
        db.session.query(Notification)
        .filter(Notification.title == "New device login")
        .count()
        == 0
    )


def test_the_mail_is_queued_not_sent_inside_the_sign_in(app, db, monkeypatch):
    """The SMTP hand-off costs a few hundred ms; the worker does it."""
    from hubra.core.services import email as email_svc
    from hubra.core.tasks import email_tasks

    queued = []
    monkeypatch.setattr(
        email_tasks.send_new_device_login_task,
        "delay",
        lambda *a, **kw: queued.append(a),
    )
    monkeypatch.setattr(
        email_svc, "_send", lambda *a, **kw: pytest.fail("sent inside the request")
    )
    _user(db)
    _sign_in(_browser(app, CHROME))
    _sign_in(_browser(app, FIREFOX))

    assert len(queued) == 1
    to, name, ip, browser, platform, _ua, _ts, lang, details = queued[0]
    assert details["method"] == "Password"
    assert (to, ip, browser, platform, lang) == (
        "solo@test.ch",
        "127.0.0.1",
        "Firefox",
        "Linux",
        "en-GB",
    )


def test_staff_new_device_ping_is_sent(app, db, sent, monkeypatch):
    """The platform-log ping waits for a commit; the account sign-in used to
    queue it after its last commit, so it was dropped."""
    from hubra.core.tasks import platform_bot_tasks

    pings = []
    monkeypatch.setattr(
        platform_bot_tasks.post_security, "delay", lambda *a, **kw: pings.append(a)
    )
    user = _user(db)
    user.is_superadmin = True
    db.session.commit()
    _sign_in(_browser(app, CHROME))
    _sign_in(_browser(app, FIREFOX))

    assert len(pings) == 1
    assert "neuem Gerät" in pings[0][0]


def test_alert_after_the_second_step_names_it(app, db, sent, monkeypatch):
    from hubra.core.auth import mfa

    _user(db)
    _sign_in(_browser(app, CHROME))
    monkeypatch.setattr(mfa, "enabled", lambda user: True)
    monkeypatch.setattr(mfa, "verify", lambda user, code: "totp")
    firefox = _browser(app, FIREFOX)
    resp = firefox.post(
        "/api/v1/auth/login", json={"email": "solo@test.ch", "password": PASSWORD}
    )
    token = resp.get_json()["mfaToken"]
    resp = firefox.post("/api/v1/auth/login/mfa", json={"mfaToken": token, "code": "1"})
    assert resp.status_code == 200, resp.get_json()

    assert "Second step: Code from the app" in sent[0][3]


def _not_me_link(sent) -> str:
    import re

    text = sent[0][3]
    return re.search(r"not-me#token=(\S+)", text).group(1)


def test_not_me_ends_every_session_once(app, db, sent):
    from hubra.core.models.account_session import AccountSession
    from hubra.core.models.user import User

    _user(db)
    chrome = _browser(app, CHROME)
    _sign_in(chrome)
    _sign_in(_browser(app, FIREFOX))
    token = _not_me_link(sent)

    resp = app.test_client().post("/api/v1/auth/not-me", json={"token": token})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["ended"] == 2
    user = db.session.query(User).filter_by(email="solo@test.ch").one()
    assert user.tokens_valid_after is not None
    assert (
        db.session.query(AccountSession)
        .filter(AccountSession.revoked_at.is_(None))
        .count()
        == 0
    )
    # The old sign-in no longer works.
    assert chrome.get("/api/v1/account/discord-dms").status_code == 401

    again = app.test_client().post("/api/v1/auth/not-me", json={"token": token})
    assert again.status_code == 400


def test_not_me_refuses_a_forged_token(app, db):
    resp = app.test_client().post("/api/v1/auth/not-me", json={"token": "x.y.z"})
    assert resp.status_code == 400
