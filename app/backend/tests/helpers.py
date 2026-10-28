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


def set_modules(enabled: bool = True, *codes: str) -> None:
    """Switch modules on or off for installs without a tenant.

    With no *codes*, applies to every registered module.  Writes the
    catalog rows directly, so dependency checks are skipped on purpose.
    """
    from vollbuild.core.extensions import db
    from vollbuild.core.models.feature import Feature
    from vollbuild.core.modules import registry
    from vollbuild.core.modules.state import invalidate

    registry.load()
    for code in codes or [m.code for m in registry.all()]:
        row = db.session.get(Feature, code)
        if row is None:
            db.session.add(Feature(code=code, name=code, default_enabled=enabled))
        else:
            row.default_enabled = enabled
    db.session.commit()
    invalidate()
