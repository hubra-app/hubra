"""Tests for the QRR reference number utility."""

from __future__ import annotations

import pytest

from hubra.core.services.qr_reference import (
    _mod10recursive,
    generate_qrr_reference,
    parse_qrr_reference,
    validate_qrr_checksum,
)


_SIX_TEST_VECTORS: list[tuple[str, str]] = [
    ("21000000000313947143000901", "7"),
]


class TestMod10Recursive:
    """ISO 7064 mod-10-recursive check digit algorithm."""

    @pytest.mark.parametrize("body, expected_cd", _SIX_TEST_VECTORS)
    def test_known_six_vectors(self, body: str, expected_cd: str) -> None:
        assert str(_mod10recursive(body)) == expected_cd

    def test_short_input(self) -> None:
        cd = _mod10recursive("0")
        assert isinstance(cd, int)
        assert 0 <= cd <= 9

    def test_all_zeros(self) -> None:
        cd = _mod10recursive("00000000000000000000000000")
        assert isinstance(cd, int)
        assert 0 <= cd <= 9


class TestGenerateQrrReference:
    """Generation produces valid opaque references."""

    def test_basic_generation(self) -> None:
        ref = generate_qrr_reference(member_id=1, invoice_id=1, year=2026)
        assert len(ref) == 27
        assert ref.isdigit()

    def test_zero_ids(self) -> None:
        ref = generate_qrr_reference(member_id=0, invoice_id=0, year=2026)
        assert len(ref) == 27
        assert ref.isdigit()

    def test_large_values(self) -> None:
        ref = generate_qrr_reference(
            member_id=999999, invoice_id=9999999999999999, year=2026
        )
        assert len(ref) == 27
        assert ref.isdigit()

    def test_default_year(self) -> None:
        ref = generate_qrr_reference(member_id=1, invoice_id=1)
        assert len(ref) == 27
        assert ref.isdigit()


class TestParseQrrReference:
    """Parsing and round-trip tests."""

    def test_round_trip(self) -> None:
        member_id = 42
        invoice_id = 98765
        ref = generate_qrr_reference(
            member_id=member_id, invoice_id=invoice_id, year=2026
        )
        parsed = parse_qrr_reference(ref)
        assert parsed["member_id"] == member_id
        assert parsed["year"] == 2026
        assert parsed["invoice_id"] == invoice_id

    def test_round_trip_zero(self) -> None:
        ref = generate_qrr_reference(member_id=0, invoice_id=0, year=2026)
        parsed = parse_qrr_reference(ref)
        assert parsed["member_id"] == 0
        assert parsed["year"] == 2026
        assert parsed["invoice_id"] == 0

    def test_round_trip_large(self) -> None:
        member_id = 999999
        invoice_id = 9999999999999999
        ref = generate_qrr_reference(
            member_id=member_id, invoice_id=invoice_id, year=2099
        )
        parsed = parse_qrr_reference(ref)
        assert parsed["member_id"] == member_id
        assert parsed["year"] == 2099
        assert parsed["invoice_id"] == invoice_id

    def test_tampered_reference_raises(self) -> None:
        ref = generate_qrr_reference(member_id=1, invoice_id=1, year=2026)
        tampered = ref[:3] + ("9" if ref[3] != "9" else "0") + ref[4:]
        with pytest.raises(ValueError, match="Invalid check digit"):
            parse_qrr_reference(tampered)

    def test_short_reference_raises(self) -> None:
        with pytest.raises(ValueError, match="must be 27 digits"):
            parse_qrr_reference("12345")

    def test_empty_reference_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            parse_qrr_reference("")

    def test_non_digit_raises(self) -> None:
        with pytest.raises(ValueError, match="only digits"):
            parse_qrr_reference("A" * 27)

    def test_unknown_reference_raises(self) -> None:
        with pytest.raises(ValueError, match="No mapping found"):
            parse_qrr_reference("210000000003139471430009017")


class TestValidateChecksum:
    """Check-digit validation."""

    def test_valid_reference(self) -> None:
        ref = generate_qrr_reference(member_id=1, invoice_id=1, year=2026)
        assert validate_qrr_checksum(ref) is True

    def test_tampered_reference(self) -> None:
        ref = generate_qrr_reference(member_id=1, invoice_id=1, year=2026)
        tampered = ref[:5] + ("9" if ref[5] != "9" else "0") + ref[6:]
        assert validate_qrr_checksum(tampered) is False

    def test_too_short(self) -> None:
        assert validate_qrr_checksum("1") is False

    @pytest.mark.parametrize("body, expected_cd", _SIX_TEST_VECTORS)
    def test_six_official_reference(self, body: str, expected_cd: str) -> None:
        full_ref = f"{body}{expected_cd}"
        assert validate_qrr_checksum(full_ref) is True

    def test_unknown_reference_valid_checksum(self) -> None:
        assert validate_qrr_checksum("210000000003139471430009017") is True
