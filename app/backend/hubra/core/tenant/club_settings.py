"""Read a club's own settings (Settings > Verein), kept in ``Tenant.settings``.

They live under the ``branding`` key for historical reasons; the schema is
``hubra.core.schemas.club_settings.ClubSettingsSchema``.
"""

from __future__ import annotations

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
