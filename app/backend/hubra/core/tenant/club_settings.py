"""Read a club's own settings (Settings > Verein), kept in ``Tenant.settings``.

They live under the ``branding`` key for historical reasons; the schema is
``hubra.core.schemas.club_settings.ClubSettingsSchema``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Any

from hubra.core.models.tenant import Tenant


def club_setting(tenant: Tenant | None, key: str, default: Any = None) -> Any:
    """One club setting, or *default* when the club never saved it."""
    if tenant is None:
        return default
    value = (tenant.settings or {}).get("branding", {}).get(key)
    return default if value is None else value


def accepts_join_requests(tenant: Tenant | None) -> bool:
    """False when the club takes new members by invite only."""
    return club_setting(tenant, "join_requests_open", True) is not False


def club_logo(tenant: Tenant | None) -> tuple[str, bytes] | None:
    """The club's logo as (MIME type, bytes), or None without one.

    The logo is kept as a base64 data URL (Settings > Verein > Logo).
    """
    value = club_setting(tenant, "logo")
    if not isinstance(value, str) or not value.startswith("data:"):
        return None
    header, _, payload = value.partition(",")
    mime = header[len("data:") :].split(";", 1)[0]
    if not mime.startswith("image/") or ";base64" not in header:
        return None
    try:
        return mime, base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None


def club_logo_version(tenant: Tenant | None) -> str | None:
    """A short hash of the logo for cache-busting its URL, or None."""
    value = club_setting(tenant, "logo")
    if not isinstance(value, str) or not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()[:12]
