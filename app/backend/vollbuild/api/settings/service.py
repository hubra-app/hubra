"""Backward-compatible re-export — delegates to vollbuild.api.settings.services."""

from __future__ import annotations

from vollbuild.api.settings.services import SettingService


class SettingsService:
    """Backward-compatible SettingsService — delegates to static-method services."""

    def get(self, key):
        return SettingService.get(key)

    def delete(self, key):
        SettingService.delete(key)
        from vollbuild.core.extensions import db

        db.session.commit()

    def set(self, key, value):
        data = {
            "value": value,
            "namespace": None,
            "sensitive": None,
            "required": None,
            "restricted": None,
            "validation_type": None,
            "description": None,
        }
        SettingService.upsert(key, data)
        from vollbuild.core.extensions import db

        db.session.commit()
