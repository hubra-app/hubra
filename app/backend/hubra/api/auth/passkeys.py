"""Passkeys (WebAuthn): sign in with Face ID, a fingerprint, a PIN or a key.

Passkeys live on the SSO portal only, so the relying party is the SSO host
(``WEBAUTHN_RP_ID``, default the host of ``SSO_BASE_URL``) and the expected
origin is ``SSO_BASE_URL`` (or ``WEBAUTHN_ORIGINS``).

Each ceremony hands the browser a signed state token holding the challenge
(5 minutes); a challenge is used once (Redis, when it is reachable).  User
verification is required, so a passkey on its own counts as two factors.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from hubra.core.extensions import db
from hubra.core.models.passkey import Passkey
from hubra.core.models.user import User
from hubra.core.redis_client import get_redis_client, mark_redis_down

_log = logging.getLogger(__name__)

_STATE_MAX_AGE = 5 * 60  # seconds
MAX_PER_ACCOUNT = 20


class PasskeyError(Exception):
    """The browser's answer did not check out."""


# ── Relying party ────────────────────────────────────────────────────────────


def _origins() -> list[str]:
    raw = current_app.config.get("WEBAUTHN_ORIGINS") or current_app.config.get(
        "SSO_BASE_URL", ""
    )
    return [o.strip().rstrip("/") for o in str(raw).split(",") if o.strip()]


def _rp_id() -> str:
    configured = current_app.config.get("WEBAUTHN_RP_ID")
    if configured:
        return str(configured)
    origins = _origins()
    return urlparse(origins[0]).hostname or "" if origins else ""


def available() -> bool:
    """Passkeys need to know the SSO portal's address."""
    return bool(_rp_id() and _origins())


# ── State between the two calls of a ceremony ────────────────────────────────


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="hubra-webauthn"
    )


def _state(challenge: bytes, purpose: str, user_id: int | None) -> str:
    return _serializer().dumps(
        {"c": bytes_to_base64url(challenge), "p": purpose, "u": user_id}
    )


def _read_state(token: str, purpose: str) -> tuple[bytes, int | None]:
    try:
        data = _serializer().loads(token or "", max_age=_STATE_MAX_AGE)
    except BadSignature as exc:
        raise PasskeyError("expired") from exc
    if data.get("p") != purpose:
        raise PasskeyError("wrong purpose")
    challenge = data["c"]
    client = get_redis_client()
    if client is not None:
        try:
            if not client.set(f"webauthn:used:{challenge}", 1, nx=True, ex=600):
                raise PasskeyError("challenge used")
        except PasskeyError:
            raise
        except Exception:
            _log.debug("Redis unavailable for the WebAuthn challenge check")
            mark_redis_down()
    return base64url_to_bytes(challenge), data.get("u")


def _options(options) -> dict:
    return json.loads(options_to_json(options))


# ── Reading ──────────────────────────────────────────────────────────────────


def _of(user: User) -> list[Passkey]:
    return list(
        db.session.scalars(
            select(Passkey).where(Passkey.user_id == user.id).order_by(Passkey.id)
        )
    )


def list_for(user: User) -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "createdAt": p.created_at.isoformat() if p.created_at else None,
            "lastUsedAt": p.last_used_at.isoformat() if p.last_used_at else None,
        }
        for p in _of(user)
    ]


def _descriptor(p: Passkey) -> PublicKeyCredentialDescriptor:
    transports = []
    for t in (p.transports or "").split(","):
        try:
            transports.append(AuthenticatorTransport(t))
        except ValueError:
            pass
    return PublicKeyCredentialDescriptor(
        id=base64url_to_bytes(p.credential_id), transports=transports or None
    )


# ── Adding a passkey ─────────────────────────────────────────────────────────


def registration_options(user: User) -> dict:
    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name="Hubra",
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[_descriptor(p) for p in _of(user)],
    )
    return {
        "options": _options(options),
        "state": _state(options.challenge, "register", user.id),
    }


def register(user: User, state: str, credential: dict, name: str) -> Passkey:
    """Check the browser's new credential and keep it.  No commit."""
    challenge, user_id = _read_state(state, "register")
    if user_id != user.id:
        raise PasskeyError("state of another account")
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origins(),
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as exc:
        _log.info("passkey_register_refused user_id=%s: %s", user.id, exc)
        raise PasskeyError(str(exc)) from exc
    credential_id = bytes_to_base64url(verified.credential_id)
    if db.session.scalar(
        select(Passkey.id).where(Passkey.credential_id == credential_id)
    ):
        raise PasskeyError("already registered")
    transports = (credential.get("response") or {}).get("transports") or []
    passkey = Passkey(
        user_id=user.id,
        credential_id=credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=",".join(str(t) for t in transports)[:200] or None,
        name=(name or "").strip()[:100] or "Passkey",
    )
    db.session.add(passkey)
    db.session.flush()
    return passkey


# ── Signing in with a passkey ────────────────────────────────────────────────


def authentication_options(user: User | None = None) -> dict:
    """Options for a sign-in: any passkey of this site, or *user*'s only."""
    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=[_descriptor(p) for p in _of(user)] if user else None,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return {
        "options": _options(options),
        "state": _state(options.challenge, "login", user.id if user else None),
    }


def authenticate(state: str, credential: dict) -> Passkey:
    """The passkey that signed the challenge.  No commit."""
    challenge, user_id = _read_state(state, "login")
    passkey = db.session.scalar(
        select(Passkey).where(Passkey.credential_id == str(credential.get("id") or ""))
    )
    if passkey is None or (user_id is not None and passkey.user_id != user_id):
        raise PasskeyError("unknown passkey")
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origins(),
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        _log.info("passkey_login_refused passkey_id=%s: %s", passkey.id, exc)
        raise PasskeyError(str(exc)) from exc
    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = datetime.now(timezone.utc)
    return passkey
