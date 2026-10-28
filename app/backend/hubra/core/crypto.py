from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet
from flask import current_app


def _get_key() -> bytes:
    fernet_key = current_app.config.get("FERNET_KEY")
    if fernet_key:
        return fernet_key.encode("utf-8")
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(secret).digest())


def encrypt_code(plaintext: str) -> str:
    f = Fernet(_get_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_code(ciphertext: str) -> str:
    f = Fernet(_get_key())
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
