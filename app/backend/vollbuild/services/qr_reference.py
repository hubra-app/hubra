"""Backwards-compatible re-export from vollbuild.core.services.qr_reference."""

from vollbuild.core.services.qr_reference import (
    annotations,
    date,
    IntegrityError,
    db,
    QrrReference,
    TOTAL_DIGITS,
    OPAQUE_BODY_DIGITS,
    _mod10recursive,
    _generate_random_body,
    generate_qrr_reference,
    parse_qrr_reference,
    validate_qrr_checksum,
)
