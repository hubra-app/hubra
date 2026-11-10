"""The member badge in Google Wallet (core/services/google_wallet.py).

Google is never called: ``_http`` is replaced with a fake that records the
calls and answers like the Wallet API does.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from hubra.core.services import google_wallet, platform_settings

PASSWORD = "password123"
ISSUER = "3388000000023240270"


@pytest.fixture(scope="module")
def rsa_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return key, pem


@pytest.fixture
def wallet(db, rsa_key):
    _, pem = rsa_key
    platform_settings.set_many(
        {
            "wallet.google.issuer_id": ISSUER,
            "wallet.google.class_id": f"{ISSUER}.hubra",
            "wallet.google.service_account": json.dumps(
                {
                    "type": "service_account",
                    "client_email": "hubra-wallet@demo.iam.gserviceaccount.com",
                    "private_key": pem,
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            ),
            "wallet.google.logo_url": "https://sso.example.org/icon-512.png",
        }
    )
    db.session.commit()
    google_wallet._TOKENS.clear()
    yield
    google_wallet._TOKENS.clear()


class FakeGoogle:
    def __init__(self):
        self.calls: list[tuple[str, str, object]] = []
        self.objects: dict[str, dict] = {}

    def __call__(self, method, url, body, ctype, token=None):
        if url.endswith("/token"):
            form = parse_qs(body.decode())
            self.calls.append((method, "token", form["assertion"][0]))
            return 200, {"access_token": "tok", "expires_in": 3600}
        assert token == "tok"
        payload = json.loads(body) if body else None
        path = url.split("/walletobjects/v1", 1)[1]
        self.calls.append((method, path, payload))
        if method == "POST":
            if payload["id"] in self.objects:
                return 409, {"error": {"message": "exists"}}
            self.objects[payload["id"]] = payload
            return 200, payload
        if method == "PATCH":
            self.objects[payload["id"]].update(payload)
            return 200, self.objects[payload["id"]]
        return 404, {}

    def api_calls(self):
        return [c for c in self.calls if c[1] != "token"]


@pytest.fixture
def google(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(google_wallet, "_http", fake)
    return fake


def _member_user(db, seeded_db, email="wallet@test.ch"):
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    user = User(email=email, first_name="Wally", last_name="Wallet")
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.flush()
    db.session.add(Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id))
    db.session.commit()
    return user


def _login(client, email):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.get_json()


def test_off_until_set_up(client, db, seeded_db, google):
    _member_user(db, seeded_db)
    _login(client, "wallet@test.ch")
    assert client.get("/api/v1/account/badge").get_json()["googleWallet"] is False
    assert client.post("/api/v1/account/badge/google-wallet").status_code == 404
    assert google.calls == []


def test_service_account_key_is_checked(db):
    with pytest.raises(platform_settings.PlatformSettingError):
        platform_settings.set_many({"wallet.google.service_account": '{"client_email": "x"}'})
    with pytest.raises(platform_settings.PlatformSettingError):
        platform_settings.set_many({"wallet.google.issuer_id": "abc"})


def test_save_link_writes_the_pass(client, db, seeded_db, wallet, google, rsa_key, app):
    user = _member_user(db, seeded_db)
    _login(client, "wallet@test.ch")
    assert client.get("/api/v1/account/badge").get_json()["googleWallet"] is True

    resp = client.post("/api/v1/account/badge/google-wallet")
    assert resp.status_code == 200, resp.get_json()
    url = resp.get_json()["url"]
    assert url.startswith("https://pay.google.com/gp/v/save/")
    assert len(url) < 1800

    db.session.refresh(user)
    oid = f"{ISSUER}.{user.badge_code}"
    assert user.google_wallet_object == oid

    # The pass Google got: name, badge number as QR, the club's name.
    method, path, obj = google.api_calls()[0]
    assert (method, path) == ("POST", "/genericObject")
    assert obj["classId"] == f"{ISSUER}.hubra"
    assert obj["state"] == "ACTIVE"
    assert obj["header"]["defaultValue"]["value"] == "Wally Wallet"
    assert obj["barcode"] == {
        "type": "QR_CODE",
        "value": user.badge_code,
        "alternateText": user.badge_code,
    }
    clubs = obj["textModulesData"][0]
    assert clubs["header"] == "Vereine" and clubs["body"]
    assert obj["logo"]["sourceUri"]["uri"] == "https://sso.example.org/icon-512.png"

    # The link only names the object, signed with the service account key.
    key, _ = rsa_key
    claims = jwt.decode(
        url.removeprefix(google_wallet.SAVE_URL),
        key.public_key(),
        algorithms=["RS256"],
        audience="google",
    )
    assert claims["iss"] == "hubra-wallet@demo.iam.gserviceaccount.com"
    assert claims["typ"] == "savetowallet"
    assert claims["payload"] == {
        "genericObjects": [{"id": oid, "classId": f"{ISSUER}.hubra"}]
    }

    # Saving again patches the pass Google already has.
    assert client.post("/api/v1/account/badge/google-wallet").status_code == 200
    assert [c[:2] for c in google.api_calls()[1:]] == [
        ("POST", "/genericObject"),
        ("PATCH", f"/genericObject/{oid}"),
    ]


def test_sync_only_when_the_pass_changed(client, db, seeded_db, wallet, google):
    user = _member_user(db, seeded_db)
    google_wallet.save_url(user)
    before = len(google.api_calls())

    assert google_wallet.sync(user.id) is False  # nothing changed
    assert len(google.api_calls()) == before

    user.first_name = "Walter"
    db.session.commit()
    assert google_wallet.sync(user.id) is True
    method, _, obj = google.api_calls()[-1]
    assert method == "PATCH"
    assert obj["header"]["defaultValue"]["value"] == "Walter Wallet"


def test_name_change_updates_the_pass(client, db, seeded_db, wallet, google, monkeypatch):
    from hubra.core.tasks import after_commit

    queued = []
    monkeypatch.setattr(
        after_commit, "delay_after_commit", lambda task, *args: queued.append((task.name, args))
    )
    user = _member_user(db, seeded_db)
    google_wallet.save_url(user)
    _login(client, "wallet@test.ch")

    resp = client.patch("/api/v1/account/profile", json={"name": "Wanda Wallet"})
    assert resp.status_code == 200
    assert queued == [("hubra.core.tasks.wallet_tasks.sync_google_wallet_pass", (user.id,))]
    # What the worker then does:
    assert google_wallet.sync(user.id) is True
    _, _, obj = google.api_calls()[-1]
    assert obj["header"]["defaultValue"]["value"] == "Wanda Wallet"


def test_disabled_account_pass_goes_inactive(db, seeded_db, wallet, google):
    user = _member_user(db, seeded_db)
    google_wallet.save_url(user)
    user.is_disabled = True
    db.session.commit()

    assert google_wallet.refresh_all() == 1
    _, _, obj = google.api_calls()[-1]
    assert obj["state"] == "INACTIVE"
    assert "header" not in obj and "textModulesData" not in obj


def test_no_pass_no_calls(db, seeded_db, wallet, google):
    user = _member_user(db, seeded_db)
    google_wallet.queue_sync(user.id)
    db.session.commit()
    assert google_wallet.refresh_all() == 0
    assert google.calls == []


def test_google_refusing_is_a_502(client, db, seeded_db, wallet, monkeypatch):
    _member_user(db, seeded_db)
    _login(client, "wallet@test.ch")

    def refuse(method, url, body, ctype, token=None):
        if url.endswith("/token"):
            return 200, {"access_token": "tok", "expires_in": 3600}
        return 403, {"error": {"message": "issuer not allowed"}}

    monkeypatch.setattr(google_wallet, "_http", refuse)
    resp = client.post("/api/v1/account/badge/google-wallet")
    assert resp.status_code == 502
    assert resp.get_json()["error"] == "GOOGLE_WALLET_FAILED"
