"""Marshmallow schema for club branding settings.

Validates the settings dict stored in ``Tenant.settings['branding']``.
"""

from __future__ import annotations

import re

from marshmallow import Schema, ValidationError, fields, validate

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

_VALID_TIMEZONES = [
    "Europe/Zurich",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Vienna",
    "UTC",
]

_VALID_LOCALES = ["de-CH", "en-GB", "de-DE", "fr-FR", "it-IT"]

_VALID_DATE_FORMATS = ["DD.MM.YYYY", "YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"]


def _validate_hex_color(value: str) -> None:
    if not _HEX_COLOR_RE.match(value):
        raise ValidationError(f"Invalid hex color: {value!r}")


def _validate_logo_size(value: str) -> None:
    """Validate that a base64 data URL is under 2MB.

    Rough estimate: base64 encoding is ~4/3 of raw size.
    Max 2MB raw = ~2.67MB base64. We check the string length.
    """
    if not value.startswith("data:"):
        raise ValidationError("Logo must be a data URL starting with 'data:'")
    if len(value) > 2_700_000:
        raise ValidationError("Logo too large (max 2MB)")


class ClubSettingsSchema(Schema):
    """Schema for club branding settings stored in Tenant.settings['branding']."""

    club_name = fields.Str(required=False, allow_none=True)
    club_description = fields.Str(required=False, allow_none=True)
    logo = fields.Str(required=False, allow_none=True, validate=_validate_logo_size)

    primary_color = fields.Str(
        required=False, allow_none=True, validate=_validate_hex_color
    )
    secondary_color = fields.Str(
        required=False, allow_none=True, validate=_validate_hex_color
    )
    accent_color = fields.Str(
        required=False, allow_none=True, validate=_validate_hex_color
    )

    timezone = fields.Str(
        required=False, allow_none=True, validate=validate.OneOf(_VALID_TIMEZONES)
    )
    locale = fields.Str(
        required=False, allow_none=True, validate=validate.OneOf(_VALID_LOCALES)
    )
    date_format = fields.Str(
        required=False, allow_none=True, validate=validate.OneOf(_VALID_DATE_FORMATS)
    )

    member_directory_visible = fields.Bool(required=False, allow_none=True)
    public_group_listing = fields.Bool(required=False, allow_none=True)
    # Members ask to leave and a club admin approves (off: they leave at once).
    leave_requires_approval = fields.Bool(required=False, allow_none=True)
    # Off: the club takes new members by invite only (no "ask to join").
    join_requests_open = fields.Bool(required=False, allow_none=True)
    # How long an invite link works.
    invite_valid_days = fields.Int(
        required=False, allow_none=True, validate=validate.Range(min=1, max=60)
    )

    announcement_banner_text = fields.Str(required=False, allow_none=True)
    announcement_banner_active = fields.Bool(required=False, allow_none=True)
