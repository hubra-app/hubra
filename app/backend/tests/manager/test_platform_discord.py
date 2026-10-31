"""The Discord application's credentials are platform settings, not env."""

from __future__ import annotations

import pytest

from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.services import platform_settings
from hubra.core.services.platform_settings import PlatformSettingError

KEY = "ab" * 32


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.session.rollback()
    db.session.query(PlatformSetting).delete()
    db.session.commit()


def test_not_set_up_by_default(app, db):
    app.config["DISCORD_CLIENT_ID"] = "from-env"  # env is not read
    try:
        assert platform_settings.discord().client_id == ""
    finally:
        app.config.pop("DISCORD_CLIENT_ID")


def test_secrets_are_stored_encrypted_and_never_listed(db):
    platform_settings.set_many(
        {
            "discord.client_id": "123456789",
            "discord.public_key": KEY,
            "discord.client_secret": "the-secret",
            "discord.bot_token": "the-token",
        }
    )
    db.session.commit()
    stored = db.session.get(PlatformSetting, "discord.bot_token").value
    assert "the-token" not in stored
    app = platform_settings.discord()
    assert (app.client_id, app.public_key, app.client_secret, app.bot_token) == (
        "123456789",
        KEY,
        "the-secret",
        "the-token",
    )
    listed = {s["key"]: s for s in platform_settings.as_list()}
    assert listed["discord.bot_token"]["value"] == ""
    assert listed["discord.bot_token"]["isSet"] is True
    assert listed["discord.client_id"]["value"] == "123456789"


@pytest.mark.parametrize(
    "key,value",
    [("discord.client_id", "not-a-number"), ("discord.public_key", "xyz")],
)
def test_invalid_values_are_refused(db, key, value):
    with pytest.raises(PlatformSettingError):
        platform_settings.set_many({key: value})
