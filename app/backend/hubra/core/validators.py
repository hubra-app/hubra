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


def _validate_fee_percent(value: str) -> str | None:
    """0 to 10 percent, at most two decimals (1.5 or 1,5)."""
    if not re.fullmatch(r"\d{1,2}([.,]\d{1,2})?", value):
        return "A percentage like 1.5, 0 to 10"
    return None if float(value.replace(",", ".")) <= 10 else "At most 10 percent"


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


def _validate_log_events(value: str) -> str | None:
    from hubra.core.services.platform_discord import CATEGORIES

    unknown = [c.strip() for c in value.split(",") if c.strip() not in CATEGORIES]
    if unknown:
        return "Unknown categories: " + ", ".join(unknown)
    return None


def _validate_alert_types(value: str) -> str | None:
    from hubra.core.services.platform_monitor import ALERT_TYPES

    unknown = [t.strip() for t in value.split(",") if t.strip() not in ALERT_TYPES]
    if unknown:
        return "Unknown alert types: " + ", ".join(unknown)
    return None


def _validate_iso_datetime(value: str) -> str | None:
    from datetime import datetime

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "Not a date and time (2026-11-02T22:00)"
    return None


def _validate_google_service_account(v: str) -> str | None:
    from hubra.core.services.google_wallet import parse_service_account

    if parse_service_account(v) is None:
        return "Paste the whole JSON key of the service account"
    return None


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
    "chf": lambda v: (
        None
        if re.fullmatch(r"\d{1,6}(\.\d{1,2})?", v) and float(v) <= 100000
        else "An amount in CHF, 0 to 100000, at most 2 decimals"
    ),
    "minutes": lambda v: (
        None if v.isdigit() and int(v) <= 1440 else "Whole minutes, 0 to 1440"
    ),
    "milliseconds": lambda v: (
        None if v.isdigit() and int(v) <= 600000 else "Whole milliseconds, 0 to 600000"
    ),
    "on_off": lambda v: None if v in ("on", "off") else "on or off",
    "discord_language": lambda v: None if v in ("de", "en") else "de or en",
    "alert_types": lambda v: _validate_alert_types(v),
    "iso_datetime": lambda v: _validate_iso_datetime(v),
    "percent": lambda v: (
        None if v.isdigit() and 1 <= int(v) <= 100 else "Whole percent, 1 to 100"
    ),
    "fee_percent": lambda v: _validate_fee_percent(v),
    "k8s_name": lambda v: (
        None
        if re.fullmatch(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?", v)
        else "A Kubernetes name: lower-case letters, digits and -"
    ),
    "stripe_live_key": lambda v: (
        None
        if re.fullmatch(r"(sk|rk)_live_[A-Za-z0-9]{10,}", v)
        else "A live Stripe key (sk_live_... or a restricted rk_live_...)"
    ),
    "stripe_test_key": lambda v: (
        None
        if re.fullmatch(r"(sk|rk)_test_[A-Za-z0-9]{10,}", v)
        else "A sandbox Stripe key (sk_test_... or a restricted rk_test_...)"
    ),
    "stripe_mode": lambda v: None if v in ("sandbox", "live") else "sandbox or live",
    "count": lambda v: (
        None if v.isdigit() and int(v) <= 10**9 else "A whole number, or empty"
    ),
    "retention_days": lambda v: (
        None if v.isdigit() and 1 <= int(v) <= 365 else "Whole days, 1 to 365"
    ),
    "age_public_keys": _validate_age_public_keys,
    "qr_iban": _validate_qr_iban,
    "discord_log_events": lambda v: _validate_log_events(v),
    "discord_public_key": lambda v: (
        None if re.fullmatch(r"[0-9a-fA-F]{64}", v) else "Must be 64 hex characters"
    ),
    "google_issuer_id": lambda v: (
        None if re.fullmatch(r"\d{10,25}", v) else "The issuer id is a long number"
    ),
    "google_wallet_class": lambda v: (
        None
        if re.fullmatch(r"(\d{10,25}\.)?[A-Za-z0-9._-]{1,100}", v)
        else "Letters, digits, '.', '_' and '-' only"
    ),
    "google_service_account": lambda v: _validate_google_service_account(v),
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
