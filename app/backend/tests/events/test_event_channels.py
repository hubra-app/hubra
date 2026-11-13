"""One composer, all channels, for events too: the event form picks where
a new event is announced (the app, Discord, the messengers, ...)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from hubra.core.extensions import db
from hubra.core.models.notification import Notification
from hubra.core.modules import Module, registry
from hubra.core.modules.events import EVENT_PUBLISHED
from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

heard: list[dict] = []


def on_event(tenant_id=None, **payload):
    heard.append(payload)


@pytest.fixture
def chat(app, seeded_db):
    """A module that announces events, like Discord does."""
    registry.load()
    registry._modules["chat"] = Module(
        code="chat",
        name="Chat",
        events={EVENT_PUBLISHED: f"{__name__}:on_event"},
    )
    set_modules(True, "chat")
    # Someone other than the author, for the bell.
    _make_role_and_member(
        db, seeded_db["tier"], name="Reader", permission_keys=["events.events.read"]
    )
    heard.clear()
    yield
    registry._modules.pop("chat", None)


def _bells() -> int:
    return db.session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.title == "New event")
    )


def _create(client, **extra):
    return client.post(
        "/api/v1/events/",
        json={"title": "Grillabend", "date": "2030-06-06", "type": "Social", **extra},
    )


def test_the_form_lists_the_channels(client, chat):
    _login(client, "admin@test.ch")
    resp = client.get("/api/v1/events/channels")
    assert resp.status_code == 200
    keys = [c["key"] for c in resp.get_json()]
    assert keys[0] == "app" and "chat" in keys and "events" not in keys
    _login(client, "reader@test.ch")
    assert client.get("/api/v1/events/channels").status_code == 403


def test_every_channel_by_default(client, chat):
    _login(client, "admin@test.ch")
    before = _bells()
    assert _create(client).status_code == 201
    assert len(heard) == 1 and heard[0]["channels"] is None
    assert _bells() > before


def test_only_the_chat_and_no_bell(client, chat):
    _login(client, "admin@test.ch")
    before = _bells()
    assert _create(client, channels=["chat"]).status_code == 201
    assert len(heard) == 1 and heard[0]["channels"] == ["chat"]
    assert _bells() == before


def test_only_the_app(client, chat):
    _login(client, "admin@test.ch")
    before = _bells()
    assert _create(client, channels=["app"]).status_code == 201
    assert heard == [] and _bells() > before


def test_an_unknown_channel_is_refused(client, chat):
    _login(client, "admin@test.ch")
    resp = _create(client, channels=["sms"])
    assert resp.status_code == 400 and "sms" in resp.get_data(as_text=True)
    assert heard == []
