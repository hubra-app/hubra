"""Backwards-compatible re-export from vollbuild.core.schemas.club_settings."""

from vollbuild.core.schemas.club_settings import (
    annotations,
    Schema,
    ValidationError,
    fields,
    validate,
    _HEX_COLOR_RE,
    _VALID_TIMEZONES,
    _VALID_LOCALES,
    _VALID_DATE_FORMATS,
    _validate_hex_color,
    _validate_logo_size,
    ClubSettingsSchema,
)
