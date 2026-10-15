"""KeyService — access layer for InternalKey values.

Backend-only, no HTTP exposure. Handles encrypt-on-write / decrypt-on-read.
The binding engine uses set / update / delete; consumers (invoice, senders)
use get.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select

from vollbuild.core.crypto import decrypt_code, encrypt_code
from vollbuild.core.extensions import db
from vollbuild.core.models.internal_key import InternalKey

_log = logging.getLogger(__name__)


class KeyService:
    """Access layer for InternalKey values."""

    @staticmethod
    def get(key: str) -> str | list[str] | None:
        """Decrypt and return the value.

        Returns a scalar ``str`` for scalar keys, ``list[str]`` for array
        keys, or ``None`` if the key or value is missing.
        """
        ik = db.session.scalar(select(InternalKey).where(InternalKey.key == key))
        if ik is None or ik.value is None:
            return None
        try:
            plaintext = decrypt_code(ik.value)
        except Exception:
            _log.warning("KeyService.get: failed to decrypt value for key %s", key)
            return None
        if ik.allow_multiple:
            try:
                return json.loads(plaintext)
            except (json.JSONDecodeError, TypeError):
                return []
        return plaintext

    @staticmethod
    def set(key: str, value: str | list[str] | None) -> None:
        """Encrypt and write. Overwrites existing value. Does NOT commit.

        For array keys, *value* should be a ``list[str]``.
        For scalar keys, *value* should be a ``str`` or ``None``.
        """
        ik = db.session.scalar(select(InternalKey).where(InternalKey.key == key))
        if ik is None:
            _log.warning("KeyService.set: key %s not found", key)
            return
        if value is None:
            ik.value = None
            return
        if ik.allow_multiple:
            if not isinstance(value, list):
                value = [value]
            plaintext = json.dumps(value, ensure_ascii=False)
        else:
            plaintext = value if isinstance(value, str) else str(value)
        ik.value = encrypt_code(plaintext)

    @staticmethod
    def update(key: str, value: str | list[str] | None) -> None:
        """Alias for set() — same semantics (full overwrite)."""
        KeyService.set(key, value)

    @staticmethod
    def delete(key: str) -> None:
        """Clear the value (set to None). Does NOT commit."""
        ik = db.session.scalar(select(InternalKey).where(InternalKey.key == key))
        if ik is None:
            return
        ik.value = None
