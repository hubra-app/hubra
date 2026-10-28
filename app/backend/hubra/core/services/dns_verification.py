"""DNS verification service — TXT record lookup for custom domain verification."""

from __future__ import annotations

import logging
import secrets
from typing import Any

_log = logging.getLogger(__name__)

_VERIFICATION_PREFIX = "verevia-verify="


def generate_verification_token() -> str:
    """Generate a random 32-char hex verification token."""
    return secrets.token_hex(16)


def verify_domain(domain_name: str, expected_token: str) -> dict[str, Any]:
    """Look up TXT records for *domain_name* and check for the verification token.

    Returns a dict with:
      - ``verified``: True if the expected token was found in a TXT record
      - ``found_records``: list of all TXT record values found
      - ``error``: error message if the lookup failed
    """
    expected_value = f"{_VERIFICATION_PREFIX}{expected_token}"

    try:
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.timeout = 10
        resolver.lifetime = 15

        answers = resolver.resolve(domain_name, "TXT")
        found_records: list[str] = []
        for rdata in answers:
            for txt in rdata.strings:
                decoded = txt.decode() if isinstance(txt, bytes) else txt
                found_records.append(decoded)
                if decoded.strip() == expected_value:
                    _log.info(
                        "Domain %s verified successfully (TXT record matched)",
                        domain_name,
                    )
                    return {
                        "verified": True,
                        "found_records": found_records,
                        "error": None,
                    }

        _log.info(
            "Domain %s verification failed — token not found in TXT records: %s",
            domain_name,
            found_records,
        )
        return {
            "verified": False,
            "found_records": found_records,
            "error": "Verification token not found in TXT records",
        }
    except dns.resolver.NXDOMAIN:
        return {
            "verified": False,
            "found_records": [],
            "error": "Domain does not exist (NXDOMAIN)",
        }
    except dns.resolver.NoAnswer:
        return {
            "verified": False,
            "found_records": [],
            "error": "No TXT records found for this domain",
        }
    except Exception as exc:
        _log.warning("DNS lookup failed for %s: %s", domain_name, exc)
        return {
            "verified": False,
            "found_records": [],
            "error": f"DNS lookup failed: {exc}",
        }
