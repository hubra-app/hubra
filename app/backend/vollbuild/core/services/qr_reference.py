"""QRR (QR-Reference) number generation and parsing for Swiss QR-bills.

Uses an opaque mapping table (qrr_references) instead of encoding
internal IDs directly in the reference number. The 27-digit reference
visible to payers is a random opaque number that cannot be reversed
to internal IDs without database access.

Usage:
    ref = generate_qrr_reference(member_id=42, invoice_id=123)
    parsed = parse_qrr_reference(ref)    # -> {member_id: 42, year: 2026, invoice_id: 123}

    # External-party invoice (no member):
    ref = generate_qrr_reference(member_id=0, invoice_id=456)
"""

from __future__ import annotations

import secrets

from datetime import date

from sqlalchemy.exc import IntegrityError

from vollbuild.core.extensions import db
from vollbuild.core.models.qrr_reference import QrrReference


TOTAL_DIGITS = 27

OPAQUE_BODY_DIGITS = TOTAL_DIGITS - 1  # 26 random digits + 1 check digit


def _mod10recursive(digits: str) -> int:
    """Calculate the ESR/QRR check digit using the Swiss modulo-10-recursive
    algorithm (as implemented by the Swiss banking industry for ESR and
    QR-reference numbers).

    This is the algorithm used by SIX and verified against stdnum.ch.esr.
    It uses a lookup table rather than the ISO 7064 MOD 10-1 definition,
    but produces the identical result required by the Swiss QR-bill spec.

    Given a string of digits, returns a single check digit (0-9).
    """
    _table = (0, 9, 4, 6, 8, 2, 7, 1, 3, 5)
    c = 0
    for char in digits:
        c = _table[(int(char) + c) % 10]
    return (10 - c) % 10


def _generate_random_body() -> str:
    """Generate a random 26-digit body for the opaque reference."""
    return f"{secrets.randbelow(10**OPAQUE_BODY_DIGITS):0{OPAQUE_BODY_DIGITS}d}"


def generate_qrr_reference(
    member_id: int, invoice_id: int, year: int | None = None
) -> str:
    """Generate an opaque 27-digit QRR reference.

    Creates a random reference and stores the mapping in the
    qrr_references table. Multiple attempts are made if a random
    collision occurs (extremely unlikely with 10^26 search space).

    Args:
        member_id: Member primary key (0 .. 999 999).
        invoice_id: Invoice primary key (0 .. 10^16 - 1).
        year: 4-digit year. Defaults to current year.

    Returns:
        27-character string of digits (the QRR reference).
    """
    if year is None:
        year = date.today().year

    for attempt in range(3):
        body = _generate_random_body()
        check_digit = _mod10recursive(body)
        opaque_reference = f"{body}{check_digit}"

        ref = QrrReference(
            opaque_reference=opaque_reference,
            member_id=member_id,
            invoice_id=invoice_id,
            year=year,
            created_at=date.today(),
        )
        db.session.add(ref)
        try:
            db.session.commit()
            return opaque_reference
        except IntegrityError:
            db.session.rollback()
            if attempt == 2:
                raise

    raise RuntimeError("Failed to generate unique QRR reference")


def parse_qrr_reference(reference: str) -> dict:
    """Parse a 27-digit QRR reference by looking up the opaque mapping.

    Validates the check digit before querying the database.

    Args:
        reference: 27-character string of digits.

    Returns:
        dict with keys: member_id (int), year (int), invoice_id (int).

    Raises:
        ValueError: If the reference is malformed, the check digit is invalid,
                    or no mapping exists.
    """
    if not reference or not isinstance(reference, str):
        raise ValueError("Reference must be a non-empty string")
    if len(reference) != TOTAL_DIGITS:
        raise ValueError(
            f"Reference must be {TOTAL_DIGITS} digits, got {len(reference)}"
        )
    if not reference.isdigit():
        raise ValueError("Reference must contain only digits")

    if not validate_qrr_checksum(reference):
        raise ValueError(
            f"Invalid check digit for reference {reference} - "
            "the reference may be malformed or tampered with"
        )

    mapping = (
        db.session.query(QrrReference).filter_by(opaque_reference=reference).first()
    )

    if not mapping:
        raise ValueError(f"No mapping found for reference {reference}")

    return {
        "member_id": mapping.member_id,
        "year": mapping.year,
        "invoice_id": mapping.invoice_id,
    }


def validate_qrr_checksum(reference: str) -> bool:
    """Validate the check digit of a QRR reference.

    Args:
        reference: A full QRR reference string (with check digit).

    Returns:
        True if the check digit matches, False otherwise.
    """
    if len(reference) < 2:
        return False
    body = reference[: TOTAL_DIGITS - 1]
    expected = str(_mod10recursive(body))
    return reference[-1] == expected
