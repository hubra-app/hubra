"""Two-factor sign-in: a code from an authenticator app (TOTP, RFC 6238).

Setting it up: ``start_setup`` keeps a new secret as pending and returns it
with an ``otpauth://`` link and its QR code; ``confirm_setup`` with a code
from the app turns it on and hands out ten one-time recovery codes.

Signing in: after the password, an account with two-factor gets a
short-lived challenge instead of tokens (``challenge_for``); the code (or a
recovery code) is checked against it by ``/auth/login/mfa``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlencode

from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer

from hubra.core.crypto import decrypt_code, encrypt_code
from hubra.core.models.user import User

ISSUER = "Hubra"
_STEP = 30  # seconds
_DIGITS = 6
_WINDOW = 1  # steps either side, for clocks a little off
_RECOVERY_CODES = 10
_CHALLENGE_MAX_AGE = 5 * 60  # seconds


# ── TOTP ─────────────────────────────────────────────────────────────────────


def _new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**_DIGITS).zfill(_DIGITS)


def _matching_step(secret: str, code: str, now: float | None = None) -> int | None:
    """The time step *code* belongs to, within the window, else None."""
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != _DIGITS:
        return None
    current = int((now if now is not None else time.time()) // _STEP)
    for step in range(current - _WINDOW, current + _WINDOW + 1):
        if hmac.compare_digest(_code_at(secret, step), code):
            return step
    return None


def provisioning_uri(user: User, secret: str) -> str:
    label = quote(f"{ISSUER}:{user.email}", safe=":@")
    query = urlencode(
        {"secret": secret, "issuer": ISSUER, "digits": _DIGITS, "period": _STEP}
    )
    return f"otpauth://totp/{label}?{query}"


def qr_svg(data: str) -> str:
    import qrcode
    import qrcode.image.svg

    image = qrcode.make(
        data, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2
    )
    buf = io.BytesIO()
    image.save(buf)
    return buf.getvalue().decode()


# ── State ────────────────────────────────────────────────────────────────────


def enabled(user: User) -> bool:
    return user.totp_enabled_at is not None and bool(user.totp_secret)


def is_staff(user: User) -> bool:
    """Superadmins and holders of a global role: the platform's staff."""
    if user.is_superadmin:
        return True
    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.global_role import UserGlobalRole

    return (
        db.session.scalar(
            select(UserGlobalRole.user_id).where(UserGlobalRole.user_id == user.id)
        )
        is not None
    )


def required(user: User) -> bool:
    """Whether this account has to turn two-factor on (staff, by config)."""
    return bool(current_app.config.get("MFA_REQUIRED_FOR_STAFF")) and is_staff(user)


def status(user: User) -> dict:
    return {
        "enabled": enabled(user),
        "enabledAt": user.totp_enabled_at.isoformat() if user.totp_enabled_at else None,
        "recoveryCodesLeft": len(user.recovery_codes or []) if enabled(user) else 0,
        "required": required(user),
    }


# ── Setup ────────────────────────────────────────────────────────────────────


def start_setup(user: User) -> dict:
    """Keep a new pending secret and return what the app needs.  No commit."""
    secret = _new_secret()
    user.totp_pending_secret = encrypt_code(secret)
    uri = provisioning_uri(user, secret)
    return {"secret": secret, "uri": uri, "qrSvg": qr_svg(uri)}


def confirm_setup(user: User, code: str) -> list[str] | None:
    """Turn two-factor on if *code* matches the pending secret.  No commit.

    Returns the new recovery codes, or None for a wrong code.
    """
    if not user.totp_pending_secret:
        return None
    secret = decrypt_code(user.totp_pending_secret)
    step = _matching_step(secret, code)
    if step is None:
        return None
    user.totp_secret = user.totp_pending_secret
    user.totp_pending_secret = None
    user.totp_enabled_at = datetime.now(timezone.utc)
    user.totp_last_step = step
    return new_recovery_codes(user)


def disable(user: User) -> None:
    """Turn two-factor off.  No commit."""
    user.totp_secret = None
    user.totp_pending_secret = None
    user.totp_enabled_at = None
    user.totp_last_step = None
    user.recovery_codes = None


# ── Recovery codes ───────────────────────────────────────────────────────────


def _normalise(code: str) -> str:
    return "".join(ch for ch in code.lower() if ch.isalnum())


def _hash_recovery(code: str) -> str:
    return hashlib.sha256(_normalise(code).encode()).hexdigest()


def new_recovery_codes(user: User) -> list[str]:
    """Replace the recovery codes; returns them once, in plain.  No commit."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i
    codes = [
        "-".join("".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(2))
        for _ in range(_RECOVERY_CODES)
    ]
    user.recovery_codes = [_hash_recovery(c) for c in codes]
    return codes


# ── Checking a code ──────────────────────────────────────────────────────────


def verify(user: User, code: str) -> str | None:
    """Check an app code or a recovery code.  No commit.

    Returns ``"totp"`` or ``"recovery"`` when it is accepted, else None.  An
    app code works once; a recovery code is used up.
    """
    if not enabled(user) or not code:
        return None
    step = _matching_step(decrypt_code(user.totp_secret), code)
    if step is not None:
        if user.totp_last_step is not None and step <= user.totp_last_step:
            return None
        user.totp_last_step = step
        return "totp"
    hashed = _hash_recovery(code)
    left = list(user.recovery_codes or [])
    for stored in left:
        if hmac.compare_digest(stored, hashed):
            left.remove(stored)
            user.recovery_codes = left
            return "recovery"
    return None


# ── Sign-in challenge ────────────────────────────────────────────────────────


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="hubra-mfa-login"
    )


def _password_tag(user: User) -> str:
    # A password change ends every challenge handed out before it.
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def challenge_for(user: User, email: str, keep_signed_in: bool) -> str:
    return _serializer().dumps(
        {"u": user.id, "e": email, "k": keep_signed_in, "p": _password_tag(user)}
    )


def read_challenge(token: str) -> tuple[User, str, bool] | None:
    """The user, sign-in address and keep-signed-in flag of a live challenge."""
    from hubra.core.extensions import db

    try:
        data = _serializer().loads(token, max_age=_CHALLENGE_MAX_AGE)
    except BadSignature:
        return None
    user = db.session.get(User, int(data.get("u", 0)))
    if user is None or data.get("p") != _password_tag(user):
        return None
    return user, str(data.get("e") or user.email), bool(data.get("k", True))
