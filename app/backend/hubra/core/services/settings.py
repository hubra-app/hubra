"""Setting service — business logic for KV settings."""

from __future__ import annotations

from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.setting import Setting
from hubra.core.models.role import Permission
from hubra.core.validators import validate_value as _validate_value


_CONFIG_FALLBACKS: dict[str, str] = {
    "mail.domain": "MAIL_DOMAIN",
}


def _ensure_namespace_permissions(namespace: str) -> None:
    """Auto-create Permission rows for a namespace if they don't exist."""
    for action in ("read", "write", "delete"):
        perm_key = f"settings.{namespace}.{action}"
        existing = db.session.execute(
            select(Permission).where(Permission.key == perm_key)
        ).scalar_one_or_none()
        if existing is None:
            display_name = f"{action.capitalize()} {namespace} settings"
            db.session.add(
                Permission(
                    key=perm_key,
                    display_name=display_name,
                    resource=namespace,
                    action=action,
                    blueprint="settings",
                    is_active=True,
                )
            )


def _ensure_key_permissions(namespace: str, key: str) -> None:
    """Auto-create per-key Permission rows if they don't exist."""
    for action in ("read", "write", "delete"):
        perm_key = f"settings.{namespace}.{key}.{action}"
        existing = db.session.execute(
            select(Permission).where(Permission.key == perm_key)
        ).scalar_one_or_none()
        if existing is None:
            display_name = f"{action.capitalize()} {namespace}/{key}"
            db.session.add(
                Permission(
                    key=perm_key,
                    display_name=display_name,
                    resource=namespace,
                    action=action,
                    blueprint="settings",
                    is_active=True,
                )
            )


class SettingService:
    """Operations on a single setting."""

    @staticmethod
    def get_setting(key: str) -> Setting | None:
        """Return the Setting ORM object or None."""
        return db.session.get(Setting, key)

    @staticmethod
    def get(key: str, default: str | None = None) -> str | None:
        """Return a setting's value or *default* if missing.

        Does NOT auto-create — use ``get_or_create()`` for that.
        Falls back to Flask config via ``_CONFIG_FALLBACKS``.
        """
        setting = db.session.scalar(select(Setting).where(Setting.key == key))  # type: ignore[arg-type]
        if setting is not None:
            return setting.value
        config_key = _CONFIG_FALLBACKS.get(key)
        if config_key:
            from flask import current_app

            val = current_app.config.get(config_key)
            return str(val) if val is not None else None
        return default

    @staticmethod
    def get_or_create(key: str, default: str | None = None) -> str | None:
        """Return a setting's value, auto-creating with *default* if missing.

        If the setting doesn't exist in DB, creates a Setting row with
        ``value=default``, ``default_value=default``, ``is_default=True``,
        flushes (no commit), and returns the value.
        """
        setting = db.session.scalar(select(Setting).where(Setting.key == key))  # type: ignore[arg-type]
        if setting is not None:
            return setting.value
        config_key = _CONFIG_FALLBACKS.get(key)
        if config_key:
            from flask import current_app

            val = current_app.config.get(config_key)
            if val is not None:
                return str(val)
        setting = Setting(
            key=key,
            value=default,
            default_value=default,
            is_default=True,
        )
        db.session.add(setting)
        db.session.flush()
        return default

    @staticmethod
    def upsert(key: str, data: dict) -> Setting:
        """Create or update a setting. Does NOT commit."""
        setting = db.session.get(Setting, key)
        if setting is not None and setting.restricted:
            raise_error(409, "SETTING_RESTRICTED", "Cannot modify a restricted setting")

        if setting is None:
            setting = Setting(key=key)
            db.session.add(setting)

        setting.value = data["value"]
        if setting.value != setting.default_value:
            setting.is_default = False
        elif setting.default_value is not None:
            setting.is_default = True
        for field in (
            "namespace",
            "sensitive",
            "required",
            "restricted",
            "validation_type",
            "description",
            "label",
        ):
            val = data.get(field)
            if val is not None:
                setattr(setting, field, val)

        db.session.flush()
        _ensure_namespace_permissions(setting.namespace)
        _ensure_key_permissions(setting.namespace, setting.key)

        from hubra.core.services.binding_engine import sync_for_source

        sync_for_source("setting", key)

        return setting

    @staticmethod
    def delete(key: str) -> None:
        """Delete a setting. Does NOT commit."""
        setting = db.session.get(Setting, key)
        if setting is None:
            raise_error(404, "NOT_FOUND", "Setting not found")
        if setting.required:
            raise_error(409, "SETTING_REQUIRED", "Cannot delete a required setting")
        if setting.restricted:
            raise_error(409, "SETTING_RESTRICTED", "Cannot delete a restricted setting")

        from hubra.core.services.binding_engine import (
            assert_source_deletable,
            cascade_delete_disabled,
        )

        assert_source_deletable("setting", key)

        db.session.delete(setting)

        cascade_delete_disabled("setting", key)

    @staticmethod
    def validate_value(vtype: str | None, value: str) -> str | None:
        """Validate a value against its type. Returns error string or None."""
        return _validate_value(vtype, value)

    @staticmethod
    def revert_to_default(key: str) -> Setting:
        """Revert a setting's value to its stored default_value. Does NOT commit."""
        setting = db.session.get(Setting, key)
        if setting is None:
            raise_error(404, "NOT_FOUND", "Setting not found")
        if setting.default_value is None:
            raise_error(409, "NO_DEFAULT", "This setting has no stored default value")
        setting.value = setting.default_value
        setting.is_default = True

        from hubra.core.services.binding_engine import sync_for_source

        sync_for_source("setting", key)

        return setting

    @staticmethod
    def get_readable_namespaces_and_keys(
        member_permissions: set[str],
    ) -> tuple[set[str] | None, dict[str, set[str]]]:
        """Determine which namespaces/keys the member can read.

        Returns (namespaces, key_map):
          - namespaces = None  → all namespaces accessible (wildcard)
          - namespaces = set() → no namespace-level access
          - key_map maps namespace → set of specific keys the member can read
            (an empty set means all keys in that namespace).
        """
        if "settings.settings.read" in member_permissions:
            return None, {}

        namespaces: set[str] = set()
        keys: dict[str, set[str]] = {}

        for p in member_permissions:
            if not p.startswith("settings."):
                continue
            parts = p.split(".")
            if len(parts) < 3:
                continue
            action = parts[-1]
            if action != "read":
                continue
            ns = parts[1]
            if len(parts) == 3:
                namespaces.add(ns)
                keys.pop(ns, None)
            elif len(parts) > 3:
                key = ".".join(parts[2:-1])
                if ns not in namespaces:
                    keys.setdefault(ns, set()).add(key)

        return namespaces, keys

    @staticmethod
    def can_write(namespace: str, key: str, member_permissions: set[str]) -> bool:
        if "settings.settings.write" in member_permissions:
            return True
        if f"settings.{namespace}.write" in member_permissions:
            return True
        if f"settings.{namespace}.{key}.write" in member_permissions:
            return True
        return False

    @staticmethod
    def can_delete(namespace: str, key: str, member_permissions: set[str]) -> bool:
        if "settings.settings.delete" in member_permissions:
            return True
        if f"settings.{namespace}.delete" in member_permissions:
            return True
        if f"settings.{namespace}.{key}.delete" in member_permissions:
            return True
        return False


class SettingsService:
    """Operations on the setting collection."""

    @staticmethod
    def list() -> list[Setting]:
        """Return all settings."""
        return db.session.scalars(select(Setting)).all()  # type: ignore[return-value]
