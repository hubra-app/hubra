"""Passkeys: adding them on the account, and signing in with one.

A small software authenticator (P-256, "none" attestation) plays the
browser's part, so the real WebAuthn checks run.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import time

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

from hubra.api.auth import mfa

PASSWORD = "password123"
ORIGIN = "https://sso.example.ch"
RP_ID = "sso.example.ch"


class SoftAuthenticator:
    """One passkey, answering WebAuthn ceremonies like a browser would."""

    def __init__(self, origin: str = ORIGIN, user_verified: bool = True):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(16)
        self.origin = origin
        self.flags = 0x05 if user_verified else 0x01  # UP, UV
        self.count = 0
        self.user_handle = b""

    @property
    def id(self) -> str:
        return bytes_to_base64url(self.credential_id)

    def _client_data(self, kind: str, challenge: str) -> bytes:
        return json.dumps(
            {"type": kind, "challenge": challenge, "origin": self.origin}
        ).encode()

    def create(self, options: dict) -> dict:
        self.user_handle = base64url_to_bytes(options["user"]["id"])
        numbers = self.key.public_key().public_numbers()
        cose = cbor2.dumps(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )
        auth_data = (
            hashlib.sha256(options["rp"]["id"].encode()).digest()
            + bytes([self.flags | 0x40])
            + struct.pack(">I", self.count)
            + bytes(16)
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + cose
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": self.id,
            "rawId": self.id,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(
                    self._client_data("webauthn.create", options["challenge"])
                ),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def get(self, options: dict) -> dict:
        self.count += 1
        client_data = self._client_data("webauthn.get", options["challenge"])
        auth_data = (
            hashlib.sha256(options["rpId"].encode()).digest()
            + bytes([self.flags])
            + struct.pack(">I", self.count)
        )
        signature = self.key.sign(
            auth_data + hashlib.sha256(client_data).digest(),
            ec.ECDSA(hashes.SHA256()),
        )
        return {
            "id": self.id,
            "rawId": self.id,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(self.user_handle),
            },
            "clientExtensionResults": {},
        }


@pytest.fixture(autouse=True)
def _sso(app, monkeypatch):
    monkeypatch.setitem(app.config, "SSO_BASE_URL", ORIGIN)


def _user(db, email="solo@test.ch", **fields):
    from hubra.core.models.user import User

    user = User(email=email, first_name="Solo", last_name="User", **fields)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def _signed_in(app, email="solo@test.ch"):
    client = app.test_client()
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.get_json()
    return client


def _add(client, authenticator, name="iPhone"):
    resp = client.post(
        "/api/v1/account/passkeys/options", json={"currentPassword": PASSWORD}
    )
    assert resp.status_code == 200, resp.get_json()
    start = resp.get_json()
    assert start["options"]["rp"]["id"] == RP_ID
    assert start["options"]["authenticatorSelection"]["userVerification"] == "required"
    return client.post(
        "/api/v1/account/passkeys",
        json={
            "state": start["state"],
            "credential": authenticator.create(start["options"]),
            "name": name,
        },
    )


def _passkey_sign_in(client, authenticator, mfa_token=None):
    extra = {"mfaToken": mfa_token} if mfa_token else {}
    start = client.post("/api/v1/auth/passkey/options", json=extra).get_json()
    return client.post(
        "/api/v1/auth/passkey/login",
        json={
            "state": start["state"],
            "credential": authenticator.get(start["options"]),
            **extra,
        },
    )


def test_adding_a_passkey_turns_two_factor_on(app, db):
    _user(db)
    client = _signed_in(app)
    resp = _add(client, SoftAuthenticator())

    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["enabled"] is True and body["totpEnabled"] is False
    assert [p["name"] for p in body["passkeys"]] == ["iPhone"]
    assert len(body["recoveryCodes"]) == 10


def test_adding_needs_the_password(app, db):
    _user(db)
    client = _signed_in(app)
    resp = client.post(
        "/api/v1/account/passkeys/options", json={"currentPassword": "x"}
    )
    assert resp.status_code == 400


def test_a_second_passkey_keeps_the_recovery_codes(app, db):
    _user(db)
    client = _signed_in(app)
    _add(client, SoftAuthenticator())
    resp = _add(client, SoftAuthenticator(), "YubiKey")

    assert resp.get_json()["recoveryCodes"] == []
    assert resp.get_json()["recoveryCodesLeft"] == 10


def test_a_passkey_from_another_site_is_refused(app, db):
    _user(db)
    client = _signed_in(app)
    resp = _add(client, SoftAuthenticator(origin="https://evil.example"))
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "PASSKEY_INVALID"


def test_without_user_verification_it_is_refused(app, db):
    _user(db)
    client = _signed_in(app)
    resp = _add(client, SoftAuthenticator(user_verified=False))
    assert resp.status_code == 400


def test_sign_in_with_a_passkey_alone(app, db):
    _user(db)
    key = SoftAuthenticator()
    _add(_signed_in(app), key)

    client = app.test_client()
    resp = _passkey_sign_in(client, key)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["user"]["email"] == "solo@test.ch"
    assert client.get("/api/v1/account/profile").status_code == 200


def test_password_then_passkey(app, db):
    _user(db)
    key = SoftAuthenticator()
    _add(_signed_in(app), key)

    client = app.test_client()
    resp = client.post(
        "/api/v1/auth/login", json={"email": "solo@test.ch", "password": PASSWORD}
    )
    token = resp.get_json()["mfaToken"]
    resp = _passkey_sign_in(client, key, token)
    assert resp.status_code == 200, resp.get_json()


def test_the_step_after_the_password_takes_only_that_accounts_passkey(app, db):
    _user(db)
    _user(db, "other@test.ch")
    mine = SoftAuthenticator()
    _add(_signed_in(app), mine)
    _add(_signed_in(app, "other@test.ch"), SoftAuthenticator())

    client = app.test_client()
    token = client.post(
        "/api/v1/auth/login", json={"email": "other@test.ch", "password": PASSWORD}
    ).get_json()["mfaToken"]
    resp = _passkey_sign_in(client, mine, token)
    assert resp.status_code == 400


def test_a_challenge_works_once(app, db):
    """Without Redis the signature counter still stops a replay."""
    _user(db)
    key = SoftAuthenticator()
    _add(_signed_in(app), key)

    client = app.test_client()
    start = client.post("/api/v1/auth/passkey/options", json={}).get_json()
    answer = key.get(start["options"])
    body = {"state": start["state"], "credential": answer}
    assert client.post("/api/v1/auth/passkey/login", json=body).status_code == 200
    assert client.post("/api/v1/auth/passkey/login", json=body).status_code == 400


def test_a_forged_signature_is_refused(app, db):
    _user(db)
    key = SoftAuthenticator()
    _add(_signed_in(app), key)
    impostor = SoftAuthenticator()
    impostor.credential_id = key.credential_id  # same id, other key

    resp = _passkey_sign_in(app.test_client(), impostor)
    assert resp.status_code == 400


def test_removing_the_last_passkey_turns_it_off(app, db):
    _user(db)
    client = _signed_in(app)
    passkey_id = _add(client, SoftAuthenticator()).get_json()["passkeys"][0]["id"]

    resp = client.post(
        f"/api/v1/account/passkeys/{passkey_id}/delete", json={"currentPassword": "x"}
    )
    assert resp.status_code == 400
    resp = client.post(
        f"/api/v1/account/passkeys/{passkey_id}/delete",
        json={"currentPassword": PASSWORD},
    )
    assert resp.status_code == 200
    assert resp.get_json()["enabled"] is False
    assert resp.get_json()["recoveryCodesLeft"] == 0


def test_cannot_touch_another_accounts_passkey(app, db):
    _user(db)
    _user(db, "other@test.ch")
    theirs = _add(_signed_in(app, "other@test.ch"), SoftAuthenticator()).get_json()
    passkey_id = theirs["passkeys"][0]["id"]

    mine = _signed_in(app)
    resp = mine.patch(f"/api/v1/account/passkeys/{passkey_id}", json={"name": "x"})
    assert resp.status_code == 404
    resp = mine.post(
        f"/api/v1/account/passkeys/{passkey_id}/delete",
        json={"currentPassword": PASSWORD},
    )
    assert resp.status_code == 404


def test_rename(app, db):
    _user(db)
    client = _signed_in(app)
    passkey_id = _add(client, SoftAuthenticator()).get_json()["passkeys"][0]["id"]
    resp = client.patch(f"/api/v1/account/passkeys/{passkey_id}", json={"name": "Mac"})
    assert [p["name"] for p in resp.get_json()["passkeys"]] == ["Mac"]


def test_turning_the_app_off_keeps_passkeys_and_codes(app, db):
    _user(db)
    client = _signed_in(app)
    _add(client, SoftAuthenticator())
    setup = client.post(
        "/api/v1/account/mfa/totp/setup", json={"currentPassword": PASSWORD}
    ).get_json()
    code = mfa._code_at(setup["secret"], int(time.time() // 30))
    resp = client.post("/api/v1/account/mfa/totp/enable", json={"code": code})
    assert resp.get_json()["recoveryCodes"] == []  # kept from the passkey

    resp = client.post(
        "/api/v1/account/mfa/totp/disable", json={"currentPassword": PASSWORD}
    )
    body = resp.get_json()
    assert body["enabled"] is True and body["totpEnabled"] is False
    assert body["recoveryCodesLeft"] == 10


def test_a_passkey_satisfies_the_staff_rule(app, db, monkeypatch):
    monkeypatch.setitem(app.config, "MFA_REQUIRED_FOR_STAFF", True)
    _user(db, is_superadmin=True)
    client = _signed_in(app)
    assert client.get("/api/v1/system/tenants").status_code == 403
    _add(client, SoftAuthenticator())
    assert client.get("/api/v1/system/tenants").status_code == 200


def test_without_an_sso_address_passkeys_are_off(app, db, monkeypatch):
    monkeypatch.setitem(app.config, "SSO_BASE_URL", "")
    _user(db)
    client = _signed_in(app)
    resp = client.post(
        "/api/v1/account/passkeys/options", json={"currentPassword": PASSWORD}
    )
    assert resp.get_json()["error"] == "PASSKEYS_UNAVAILABLE"
    assert client.get("/api/v1/account/mfa").get_json()["passkeysAvailable"] is False
