"""Encryption at rest for codes, binding values, mailbox passwords and
secret platform settings.

Every club has its own data key, and the platform has one (table
``data_keys``).  A value is encrypted with AES-256-GCM under the key of the
club it belongs to and carries that club, the key version and what it is
(``purpose``, e.g. ``codes.code``) as authenticated data::

    hk1.<scope>.<version>.<nonce + ciphertext, base64url>

``scope`` is ``c<tenant id>`` for a club and ``p`` for the platform.  A
value only opens in its own club and column: read from another club's
context (a cross-club bug) it fails instead of handing out the secret.

The data keys are stored wrapped by the master key ``FERNET_KEY``.  Every
key in ``FERNET_OLD_KEYS`` (comma-separated) and the key derived from
``SECRET_KEY`` (what installs without ``FERNET_KEY`` used) still unwrap,
so the master key can change without losing data: set the new
``FERNET_KEY``, move the old one to ``FERNET_OLD_KEYS``, run ``flask crypto
rotate`` (rewraps the data keys and moves older values to the current
scheme), and drop the old key once ``flask crypto check`` passes.

Values written before data keys existed are plain Fernet tokens under the
master key; they still open, and ``flask crypto rotate`` re-encrypts them.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app, g, has_app_context
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

__all__ = [
    "PLATFORM",
    "InvalidToken",
    "context_scope",
    "decrypt_code",
    "encrypt_code",
    "is_current",
    "new_data_key",
    "old_keys",
    "rotate_code",
    "scope_of",
    "seal",
    "unseal",
]

PLATFORM = "p"
_PREFIX = "hk1"
_NONCE = 12
_SCHEMA = re.compile(r"^tenant_(\d+)")

# wrapped key -> raw key; a wrapped key never changes meaning.
_unwrapped: dict[str, bytes] = {}


# ── Master key (FERNET_KEY) ──────────────────────────────────────────────────


def _legacy_key() -> bytes:
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(secret).digest())


def old_keys() -> list[str]:
    """The keys in ``FERNET_OLD_KEYS``, still accepted for decrypting."""
    raw = current_app.config.get("FERNET_OLD_KEYS") or ""
    return [k.strip() for k in str(raw).split(",") if k.strip()]


def _primary() -> Fernet:
    fernet_key = current_app.config.get("FERNET_KEY")
    return Fernet(fernet_key.encode("utf-8") if fernet_key else _legacy_key())


def _keyring() -> MultiFernet:
    keys = [_primary()]
    keys += [Fernet(k.encode("utf-8")) for k in old_keys()]
    if current_app.config.get("FERNET_KEY"):
        keys.append(Fernet(_legacy_key()))
    return MultiFernet(keys)


def master_is_current(token: str) -> bool:
    """True when the current master key alone opens a Fernet *token*."""
    try:
        _primary().decrypt(token.encode("utf-8"))
    except InvalidToken:
        return False
    return True


def rewrap(token: str) -> str:
    """Re-encrypt a Fernet *token* with the current master key."""
    return _keyring().rotate(token.encode("utf-8")).decode("utf-8")


# ── Scopes ───────────────────────────────────────────────────────────────────


def scope_of(schema: str | None) -> str:
    """The scope of a schema: ``c<id>`` for ``tenant_<id>…``, else platform."""
    m = _SCHEMA.match(schema or "")
    return f"c{m.group(1)}" if m else PLATFORM


def context_scope() -> str:
    """The club whose schema this context reads (its search_path), or ``p``."""
    if not has_app_context():
        return PLATFORM
    path = g.get("_search_path") or ""
    return scope_of(path.split(",")[0].strip())


# ── Data keys ────────────────────────────────────────────────────────────────


def _rows(scope: str):
    from hubra.core.extensions import db
    from hubra.core.models.data_key import DataKey

    return db.session.scalars(
        select(DataKey).where(DataKey.scope == scope).order_by(DataKey.version.desc())
    ).all()


def _unwrap(wrapped: str) -> bytes:
    key = _unwrapped.get(wrapped)
    if key is None:
        key = base64.urlsafe_b64decode(_keyring().decrypt(wrapped.encode("utf-8")))
        _unwrapped[wrapped] = key
    return key


def new_data_key(scope: str):
    """Add the next key version for *scope*; new values use it from now on."""
    from hubra.core.extensions import db
    from hubra.core.models.data_key import DataKey

    current = db.session.scalar(
        select(func.max(DataKey.version)).where(DataKey.scope == scope)
    )
    raw = os.urandom(32)
    row = DataKey(
        scope=scope,
        version=(current or 0) + 1,
        wrapped_key=_primary().encrypt(base64.urlsafe_b64encode(raw)).decode("utf-8"),
    )
    with db.session.begin_nested():
        db.session.add(row)
    _unwrapped[row.wrapped_key] = raw
    return row


def _current_key(scope: str) -> tuple[int, bytes]:
    rows = _rows(scope)
    if rows:
        return rows[0].version, _unwrap(rows[0].wrapped_key)
    try:
        row = new_data_key(scope)
    except IntegrityError:  # another process made it first
        row = _rows(scope)[0]
    return row.version, _unwrap(row.wrapped_key)


def _key(scope: str, version: int) -> bytes:
    for row in _rows(scope):
        if row.version == version:
            return _unwrap(row.wrapped_key)
    raise InvalidToken


def _aad(scope: str, version: int, purpose: str) -> bytes:
    return f"{_PREFIX}|{scope}|{version}|{purpose}".encode()


def _parse(token: str) -> tuple[str, int, bytes] | None:
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != _PREFIX:
        return None
    try:
        return parts[1], int(parts[2]), base64.urlsafe_b64decode(parts[3])
    except (ValueError, TypeError):
        raise InvalidToken from None


# ── Values ───────────────────────────────────────────────────────────────────


def encrypt_code(plaintext: str, purpose: str, scope: str | None = None) -> str:
    """Encrypt *plaintext* for *purpose* (``table.column``).

    *scope* defaults to the club this context works in; pass ``PLATFORM``
    for platform data read from inside a club (platform settings).
    """
    scope = scope or context_scope()
    version, key = _current_key(scope)
    nonce = os.urandom(_NONCE)
    sealed = AESGCM(key).encrypt(
        nonce, plaintext.encode("utf-8"), _aad(scope, version, purpose)
    )
    body = base64.urlsafe_b64encode(nonce + sealed).decode("ascii")
    return f"{_PREFIX}.{scope}.{version}.{body}"


def decrypt_code(ciphertext: str, purpose: str, scope: str | None = None) -> str:
    """Open a value written by ``encrypt_code`` (or an older Fernet token).

    Raises ``InvalidToken`` when it belongs to another club or column, or
    no key opens it.
    """
    parsed = _parse(ciphertext)
    if parsed is None:
        return _keyring().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    token_scope, version, blob = parsed
    if token_scope != (scope or context_scope()):
        raise InvalidToken
    try:
        plain = AESGCM(_key(token_scope, version)).decrypt(
            blob[:_NONCE], blob[_NONCE:], _aad(token_scope, version, purpose)
        )
    except (InvalidTag, ValueError):
        raise InvalidToken from None
    return plain.decode("utf-8")


def is_current(ciphertext: str, scope: str) -> bool:
    """True when *ciphertext* uses *scope*'s newest data key."""
    parsed = _parse(ciphertext)
    if parsed is None or parsed[0] != scope:
        return False
    rows = _rows(scope)
    return bool(rows) and parsed[1] == rows[0].version


def rotate_code(ciphertext: str, purpose: str, scope: str) -> str:
    """Re-encrypt with *scope*'s newest data key.

    Raises ``InvalidToken`` when no known key opens it.
    """
    return encrypt_code(decrypt_code(ciphertext, purpose, scope), purpose, scope)


# ── Short-lived secrets for background tasks ─────────────────────────────────


def seal(plaintext: str) -> str:
    """Encrypt a short-lived secret for a background task's arguments."""
    return _primary().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def unseal(token: str, max_age: int = 3600) -> str:
    """Open a ``seal`` token; raises ``InvalidToken`` once *max_age* passed."""
    return _keyring().decrypt(token.encode("utf-8"), ttl=max_age).decode("utf-8")
