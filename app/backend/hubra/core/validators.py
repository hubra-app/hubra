"""Shared validators — used by both the settings service and the binding engine.

This module is the single source of truth for value validation.
``validate_value(vtype, value)`` returns an error string or None.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import urlparse

_DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)

_HOST_RE = re.compile(
    r"^([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$"
)


def _url_valid(value: str) -> bool:
    try:
        result = urlparse(value)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _validate_qr_iban(value: str) -> str | None:
    v = value.replace(" ", "").upper()
    if not re.match(r"^CH\d{19}$", v):
        return "Invalid QR-IBAN format (must be CH followed by 19 digits)"
    reordered = v[4:] + v[:4]
    numeric = ""
    for ch in reordered:
        if ch.isdigit():
            numeric += ch
        else:
            numeric += str(ord(ch) - 55)
    if int(numeric) % 97 != 1:
        return "Invalid QR-IBAN checksum"
    return None


def _validate_age_public_keys(value: str) -> str | None:
    """One or more age public keys (age1...), separated by spaces or commas."""
    from hubra.core.services.backup_crypto import split_keys, valid_public_key

    keys = split_keys(value)
    if keys and all(valid_public_key(k) for k in keys):
        return None
    return "Not an age public key (age1...)"


VALIDATORS: dict[str, Callable[[str], str | None]] = {
    "email": (
        lambda v: (
            None
            if re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v)
            else "Invalid email address"
        )
    ),
    "url": lambda v: None if _url_valid(v) else "Invalid URL",
    "domain": lambda v: None if _DOMAIN_RE.match(v) else "Invalid domain format",
    "host": lambda v: None if _HOST_RE.match(v) else "Invalid hostname",
    "port": (
        lambda v: (
            None
            if v.isdigit() and 1 <= int(v) <= 65535
            else "Invalid port (must be 1-65535)"
        )
    ),
    "number": lambda v: None if _is_numeric(v) else "Invalid number",
    "age_public_keys": _validate_age_public_keys,
    "qr_iban": _validate_qr_iban,
    "text": lambda v: None,
    "non_empty": (
        lambda v: (
            None if v is not None and v.strip() != "" else "Value must not be empty"
        )
    ),
}


def validate_value(vtype: str | None, value: str) -> str | None:
    """Validate a value against its type. Returns error string or None."""
    if vtype is None or vtype not in VALIDATORS:
        return None
    return VALIDATORS[vtype](value)
