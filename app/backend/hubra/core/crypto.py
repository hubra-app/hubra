"""Encryption at rest for codes, binding values, mailbox passwords and
secret platform settings.

``FERNET_KEY`` encrypts.  Every key in ``FERNET_OLD_KEYS`` (comma-separated)
and the key derived from ``SECRET_KEY`` (what installs without
``FERNET_KEY`` used) still decrypt, so a key can be changed without losing
data: set the new ``FERNET_KEY``, move the old one to ``FERNET_OLD_KEYS``,
run ``flask crypto rotate``, and drop the old key once ``flask crypto check``
reports nothing left on it.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from flask import current_app

__all__ = [
    "InvalidToken",
    "decrypt_code",
    "encrypt_code",
    "is_current",
    "old_keys",
    "rotate_code",
]


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


def encrypt_code(plaintext: str) -> str:
    return _primary().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_code(ciphertext: str) -> str:
    return _keyring().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def rotate_code(ciphertext: str) -> str:
    """Re-encrypt *ciphertext* with the current key.

    Raises ``InvalidToken`` when no known key opens it.
    """
    return _keyring().rotate(ciphertext.encode("utf-8")).decode("utf-8")


def is_current(ciphertext: str) -> bool:
    """True when the current key alone opens *ciphertext*."""
    try:
        _primary().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken:
        return False
    return True
