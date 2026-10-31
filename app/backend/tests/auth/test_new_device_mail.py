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
    return mails


def _user(db, email="solo@test.ch", verified=True, language="en-GB"):
    from hubra.core.models.user import User

    user = User(email=email, first_name="Solo", last_name="User")
    user.set_password(PASSWORD)
    user.private_email_verified = verified
    user.language = language
    db.session.add(user)
    db.session.commit()
    return user


def _browser(app, ua):
    client = app.test_client()
    client.environ_base["HTTP_USER_AGENT"] = ua
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
    assert "Firefox on Linux" in text
    assert "127.0.0.1" in text
    assert "https://sso.example.ch/account/sitzungen" in html
    assert "https://sso.example.ch/account/passwort" in html


def test_same_kind_of_browser_on_another_computer_is_new(app, db, sent):
    """The browser's name is not enough: another Chrome on Windows is new."""
    _user(db)
    _sign_in(_browser(app, CHROME))
    _sign_in(_browser(app, CHROME))

    assert len(sent) == 1


def test_mail_is_in_the_accounts_language(app, db, sent):
    _user(db, language="de-CH")
    _sign_in(_browser(app, CHROME))
    _sign_in(_browser(app, FIREFOX))

    _, subject, _, text = sent[0]
    assert "Neue Anmeldung" in subject
    assert "Firefox auf Linux" in text


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


def test_club_sign_in_alerts_the_account(app, seeded_db, sent):
    """A sign-in that opens a club uses the account's devices too."""

    def sign_in(ua):
        resp = _sign_in(_browser(app, ua), "admin@test.ch")
        assert resp.get_json().get("member") is not None  # the club path

    sign_in(CHROME)
    sign_in(CHROME)  # another computer
    assert [m[0] for m in sent] == ["admin@test.ch"]
