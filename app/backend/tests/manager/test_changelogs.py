"""Release notes of Hubra and its plugins for the clubs and Hubra's own
server (``services.changelogs``)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.contract_outbox import ContractMessage
from hubra.core.models.platform_event import PlatformEvent
from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.models.tenant import Tenant
from hubra.core.modules import Module, registry
from hubra.core.modules import events as events_mod
from hubra.core.services import (
    changelogs,
    platform_bot,
    platform_discord,
    platform_settings,
)

HERE = __name__
HEARD: list = []
# Which clubs have which modules on.
ON: dict[int, set[str]] = {}


def on_hubra(tenant_id, event_id=None, **data):
    HEARD.append(("hubra", tenant_id, data["version"], event_id))


def on_plugin(tenant_id, event_id=None, **data):
    HEARD.append(
        (
            "plugin",
            tenant_id,
            data["plugin_id"],
            data["version"],
            data.get("previous_version"),
        )
    )


LISTENER = Module(
    code="listener",
    name="Listener",
    plugin="listener",
    events={
        "hubra.released": f"{HERE}:on_hubra",
        "plugin.released": f"{HERE}:on_plugin",
    },
)


def _enabled(code, tenant_id=None):
    return code in ON.get(tenant_id, set())


class FakeRedis:
    def __init__(self):
        self.data: dict = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True

    def delete(self, key):
        self.data.pop(key, None)


@pytest.fixture
def clubs(app, db, monkeypatch):
    """Two active clubs with the listener on, one suspended; the
    ``inventory`` plugin on in the first club only."""
    a = Tenant(name="Club A", slug="cl-a", plan="starter", status="active")
    b = Tenant(name="Club B", slug="cl-b", plan="starter", status="active")
    gone = Tenant(name="Club C", slug="cl-c", plan="starter", status="suspended")
    db.session.add_all([a, b, gone])
    db.session.commit()
    ON.clear()
    ON[a.id] = {"listener", "inventory"}
    ON[b.id] = {"listener"}
    ON[gone.id] = {"listener", "inventory"}
    monkeypatch.setitem(registry._modules, "listener", LISTENER)
    monkeypatch.setattr("hubra.core.modules.state.is_enabled", _enabled)
    monkeypatch.setattr("hubra.core.modules.is_enabled", _enabled)
    monkeypatch.setattr(events_mod, "is_enabled", _enabled)
    fake = FakeRedis()
    monkeypatch.setattr(platform_bot, "_redis", lambda: fake)
    HEARD.clear()
    yield a, b
    db.session.rollback()
    for model in (ContractMessage, PlatformEvent, PlatformSetting):
        db.session.query(model).delete()
    for t in (a, b, gone):
        db.session.delete(db.session.get(Tenant, t.id))
    db.session.commit()
    platform_bot._local.clear()
    HEARD.clear()
    ON.clear()


def _running(hubra="1.0.0", plugins=None):
    """What runs now: a Hubra version and plugins {id: version}."""
    release = {
        "version": hubra,
        "date": "2026-11-06",
        "sections": {"Added": ["X"]},
        "sections_de": {},
    }
    found = [
        {
            "plugin_id": pid,
            "name": pid.title(),
            "version": version,
            "notes": f"### Added\n- {pid} {version}",
            "modules": [pid],
        }
        for pid, version in (plugins or {}).items()
    ]
    return (
        patch.object(changelogs, "hubra_release", return_value=release),
        patch.object(changelogs, "plugin_releases", return_value=found),
    )


def _announce(hubra="1.0.0", plugins=None) -> int:
    first, second = _running(hubra, plugins)
    with first, second:
        return changelogs.announce()


def _marks(kind=changelogs.SENT):
    from hubra.core.extensions import db

    return sorted(
        db.session.scalars(
            select(PlatformEvent.message).where(PlatformEvent.kind == kind)
        ).all()
    )


def _start(db):
    """An install that already ran this: Hubra 1.0.0, inventory 2.0.0."""
    db.session.add(
        PlatformEvent(category="system", kind="release.announced", message="1.0.0")
    )
    db.session.commit()
    assert _announce("1.0.0", {"inventory": "2.0.0"}) == 0


def test_the_first_run_posts_nothing_already_running(clubs, db):
    _start(db)
    assert HEARD == []
    assert _marks(changelogs.BASELINE) == ["hubra@1.0.0", "inventory@2.0.0"]
    assert db.session.scalars(select(ContractMessage)).all() == []


def test_a_new_hubra_version_reaches_every_active_club_once(clubs, db):
    a, b = clubs
    _start(db)
    assert _announce("1.1.0", {"inventory": "2.0.0"}) == 1
    heard = sorted(h[:3] for h in HEARD)
    assert heard == [("hubra", a.id, "1.1.0"), ("hubra", b.id, "1.1.0")]
    # Each club's delivery has its own id, handed to the handler.
    ids = {h[3] for h in HEARD}
    rows = db.session.scalars(select(ContractMessage)).all()
    assert ids == {r.message_id for r in rows} and len(ids) == 2
    assert all(r.status == "done" for r in rows)

    HEARD.clear()
    assert _announce("1.1.0", {"inventory": "2.0.0"}) == 0  # again: nothing
    assert HEARD == []
    assert _marks() == ["hubra@1.1.0"]


def test_a_plugin_update_reaches_only_clubs_with_the_plugin_on(clubs, db):
    a, _b = clubs
    _start(db)
    assert _announce("1.0.0", {"inventory": "2.1.0"}) == 1
    assert HEARD == [("plugin", a.id, "inventory", "2.1.0", "2.0.0")]
    HEARD.clear()
    assert _announce("1.0.0", {"inventory": "2.1.0"}) == 0
    assert HEARD == []


def test_going_back_to_an_announced_version_posts_nothing(clubs, db):
    _start(db)
    _announce("1.0.0", {"inventory": "2.1.0"})
    HEARD.clear()
    assert _announce("1.0.0", {"inventory": "2.0.0"}) == 0  # rolled back
    assert _announce("1.0.0", {"inventory": "2.1.0"}) == 0  # and forward
    assert HEARD == []


def test_a_failure_marks_nothing_so_the_next_tick_tries_again(clubs, db):
    _start(db)
    with patch.object(changelogs, "_emit_everywhere", side_effect=RuntimeError("db")):
        with pytest.raises(RuntimeError):
            _announce("1.1.0", {"inventory": "2.0.0"})
    assert _marks() == []
    assert _announce("1.1.0", {"inventory": "2.0.0"}) == 1
    assert len(HEARD) == 2


def test_one_run_at_a_time(clubs, db):
    _start(db)
    platform_bot._set(changelogs.LOCK, "1", ex=300, nx=True)
    assert _announce("1.1.0") == 0
    assert HEARD == []


def test_the_platform_changelog_channel_gets_a_post_with_a_nonce(clubs, db):
    _start(db)
    platform_settings.set_many(
        {
            "discord.bot_token": "bot-token",
            "discord.changelog_channel_id": "123456789012345678",
        }
    )
    db.session.commit()
    with patch("hubra.core.tasks.after_commit.delay_after_commit") as queued:
        _announce("1.1.0", {"inventory": "2.1.0"})
    # Jobs run in the worker (eager Celery uses another app): run them here.
    with patch.object(platform_discord, "_post", return_value={}) as post:
        for call in queued.call_args_list:
            _task, kind, payload, post_nonce = call.args
            assert changelogs.post_to_platform(kind, payload, post_nonce)
    titles = sorted(c.args[0]["title"] for c in post.call_args_list)
    assert titles == ["Hubra 1.1.0 läuft", "Inventory 2.1.0"]
    nonces = {c.kwargs["nonce"] for c in post.call_args_list}
    assert len(nonces) == 2 and all(len(n) <= 25 for n in nonces)
    assert all(
        c.kwargs["channel_id"] == "123456789012345678" for c in post.call_args_list
    )
    # The same version always gets the same nonce: Discord drops a repeat.
    assert changelogs.nonce("platform", "hubra@1.1.0") in nonces


def test_no_changelog_channel_no_platform_post(clubs, db):
    _start(db)
    with patch("hubra.core.tasks.after_commit.delay_after_commit") as queued:
        _announce("1.1.0")
    queued.assert_not_called()


def test_the_platform_log_leaves_releases_to_the_changelog_channel(clubs, db):
    platform_settings.set_many(
        {
            "discord.bot_token": "bot-token",
            "discord.log_channel_id": "1",
            "discord.log_events": "releases",
            "discord.changelog_channel_id": "2",
        }
    )
    db.session.commit()
    with (
        patch.object(platform_discord, "post") as post,
        patch(
            "hubra.core.services.version.VersionService.get_version",
            return_value="9.9.8",
        ),
    ):
        assert platform_bot.announce_release() is True
    post.assert_not_called()


def test_plugin_notes_come_from_the_plugins_changelog(app, monkeypatch, tmp_path):
    from hubra.core.plugins import loader
    from hubra.core.plugins.spec import Spec

    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 2.1.0\n\n### Added\n- Barcodes\n\n## 2.0.0\n\n- Old\n"
    )
    spec = Spec(
        id="inventory",
        path=tmp_path,
        manifest={
            "id": "inventory",
            "name": "Inventory",
            "version": "2.1.0",
            "modules": ["inventory"],
        },
    )
    spec.loaded = True
    monkeypatch.setattr(loader, "_current", loader.PluginSet(specs={"inventory": spec}))
    (found,) = changelogs.plugin_releases()
    assert found["version"] == "2.1.0" and found["modules"] == ["inventory"]
    assert "Barcodes" in found["notes"] and "Old" not in found["notes"]


def test_hubra_release_has_both_languages(app):
    release = changelogs.hubra_release()
    assert release is not None and release["version"]
    assert isinstance(release["sections"], dict)
