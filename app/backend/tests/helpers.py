"""Small helpers shared by test modules."""

from unittest.mock import patch

from vollbuild.api.settings.services import SettingService


def patch_mail_domain(domain: str):
    """Patch SettingService.get so only ``mail.domain`` returns *domain*."""
    real_get = SettingService.get

    def fake_get(key, default=None):
        return domain if key == "mail.domain" else real_get(key, default)

    return patch(
        "vollbuild.api.settings.services.SettingService.get", side_effect=fake_get
    )
