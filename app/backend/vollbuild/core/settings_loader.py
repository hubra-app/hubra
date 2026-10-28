"""Deployment-time settings via pydantic-settings + settings.yaml.

Operator-controlled flags (feature toggles, limits) are defined here.
Club identity (name, domain, sender address) lives in the database.
Secrets (API keys, passwords) live in .env.

Usage:
    from vollbuild.settings_loader import load_settings
    load_settings(app)   # stores AppSettings at app.config['SETTINGS']

Environment variable overrides use double-underscore as the nested delimiter:
    FEATURES__MAIL=false
    LIMITS__MAX_MEMBERS=50
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

_DEFAULT_SETTINGS_FILE = Path(__file__).parent.parent.parent.parent / "settings.yaml"


class AdminSettings(BaseModel):
    first_name: str = "Admin"
    last_name: str = ""
    email: str = "admin@example.com"


class FeaturesSettings(BaseModel):
    polls: bool = True
    events: bool = True
    finance: bool = True
    mail: bool = True


class LimitsSettings(BaseModel):
    max_members: int = 0
    max_events_per_month: int = 0


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=str(os.environ.get("SETTINGS_FILE", str(_DEFAULT_SETTINGS_FILE))),
        yaml_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    admin: AdminSettings = AdminSettings()
    features: FeaturesSettings = FeaturesSettings()
    limits: LimitsSettings = LimitsSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority: env vars > settings.yaml > defaults
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )


def load_settings(app: Any) -> None:
    """Instantiate AppSettings and attach to app.config['SETTINGS']."""
    try:
        app.config["SETTINGS"] = AppSettings()
        app.logger.debug("Deployment settings loaded from settings.yaml")
    except Exception as exc:
        app.logger.exception("Failed to load settings.yaml: %s — using defaults", exc)
        app.config["SETTINGS"] = AppSettings.model_construct(
            features=FeaturesSettings(),
            limits=LimitsSettings(),
        )
