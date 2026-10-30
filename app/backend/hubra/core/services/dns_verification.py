"""DNS verification service — TXT record lookup for custom domain verification."""

from __future__ import annotations

import logging
import secrets
from typing import Any

_log = logging.getLogger(__name__)

_VERIFICATION_PREFIX = "hubra-verify="
# Records published before the rename still count.
_LEGACY_PREFIXES = ("verevia-verify=",)
# The record sits on its own label: a host that points at Hubra needs a
# CNAME, and DNS allows no other record next to a CNAME.
_RECORD_LABEL = "_hubra-verify"


def verification_record_name(domain_name: str) -> str:
    """The name the club publishes its TXT record under."""
    return f"{_RECORD_LABEL}.{domain_name}"


def generate_verification_token() -> str:
    """Generate a random 32-char hex verification token."""
    return secrets.token_hex(16)


def verify_domain(domain_name: str, expected_token: str) -> dict[str, Any]:
    """Look for the verification token in the domain's TXT records.

    Checks ``_hubra-verify.<domain>`` first, then the domain itself, where
    records were published before the label existed.

    Returns a dict with:
      - ``verified``: True if the expected token was found in a TXT record
      - ``found_records``: list of all TXT record values found
      - ``error``: error message if the lookup failed
    """
    expected_values = {
        f"{prefix}{expected_token}"
        for prefix in (_VERIFICATION_PREFIX, *_LEGACY_PREFIXES)
    }
    found_records: list[str] = []
    error = None
    for name in (verification_record_name(domain_name), domain_name):
        records, error = _txt_records(name)
        found_records.extend(records)
        if any(r.strip() in expected_values for r in records):
            _log.info("Domain %s verified (TXT record on %s)", domain_name, name)
            return {"verified": True, "found_records": found_records, "error": None}

    _log.info(
        "Domain %s verification failed, token not in TXT records: %s",
        domain_name,
        found_records,
    )
    return {
        "verified": False,
        "found_records": found_records,
        "error": "Verification token not found in TXT records"
        if found_records
        else error,
    }


def _txt_records(name: str) -> tuple[list[str], str | None]:
    """Return the TXT strings published on *name*, and why there are none."""
    import dns.resolver

    resolver = dns.resolver.Resolver()
    resolver.timeout = 10
    resolver.lifetime = 15
    try:
        answers = resolver.resolve(name, "TXT")
    except dns.resolver.NXDOMAIN:
        return [], "Domain does not exist (NXDOMAIN)"
    except dns.resolver.NoAnswer:
        return [], "No TXT records found for this domain"
    except Exception as exc:
        _log.warning("DNS lookup failed for %s: %s", name, exc)
        return [], f"DNS lookup failed: {exc}"
    records: list[str] = []
    for rdata in answers:
        # A long value comes in 255-byte chunks that make up one string.
        records.append(
            "".join(t.decode() if isinstance(t, bytes) else t for t in rdata.strings)
        )
    return records, None
