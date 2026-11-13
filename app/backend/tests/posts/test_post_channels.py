"""One composer, all channels: the author picks where a post is announced
(the app, Discord, the messengers, ...) and only those channels get it."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from hubra.core.extensions import db
from hubra.core.models.notification import Notification
from hubra.core.modules import Module, registry
from hubra.core.modules.events import POST_PUBLISHED
from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

heard: list[dict] = []


def on_post(tenant_id=None, **payload):
    heard.append(payload)


@pytest.fixture
def chat(app, seeded_db):
    """A module that announces posts, like Discord does."""
    registry.load()
    registry._modules["chat"] = Module(
        code="chat",
        name="Chat",
        events={POST_PUBLISHED: f"{__name__}:on_post"},
    )
    set_modules(True, "chat")
    # Someone other than the author, for the bell.
    _make_role_and_member(
        db, seeded_db["tier"], name="Reader", permission_keys=["posts.posts.read"]
    )
    heard.clear()
    yield
    registry._modules.pop("chat", None)


def _bells() -> int:
    return db.session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.title == "New post")
    )


def test_the_editor_lists_the_channels(client, chat):
    _login(client, "admin@test.ch")
    resp = client.get("/api/v1/posts/channels")
    assert resp.status_code == 200
    keys = [c["key"] for c in resp.get_json()]
    assert keys[0] == "app" and "chat" in keys


def test_members_who_cannot_post_do_not_get_the_list(client, chat):
    _login(client, "reader@test.ch")
    assert client.get("/api/v1/posts/channels").status_code == 403
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/posts/channels").status_code == 401


def test_every_channel_by_default(client, chat):
    _login(client, "admin@test.ch")
    resp = client.post("/api/v1/posts/", json={"title": "All", "body": "B"})
    assert resp.status_code == 201
    assert resp.get_json()["channels"] is None
    assert len(heard) == 1 and heard[0]["channels"] is None


def test_only_the_app(client, chat):
    _login(client, "admin@test.ch")
    before = _bells()
    resp = client.post(
        "/api/v1/posts/", json={"title": "App", "body": "B", "channels": ["app"]}
    )
    assert resp.status_code == 201
    assert resp.get_json()["channels"] == ["app"]
    assert heard == []
    assert _bells() > before


def test_only_the_chat_and_no_bell(client, chat):
    _login(client, "admin@test.ch")
    before = _bells()
    resp = client.post(
        "/api/v1/posts/", json={"title": "Chat", "body": "B", "channels": ["chat"]}
    )
    assert resp.status_code == 201
    assert len(heard) == 1 and heard[0]["channels"] == ["chat"]
    assert _bells() == before


def test_naming_every_channel_means_all_and_unknown_is_refused(client, chat):
    _login(client, "admin@test.ch")
    every = [c["key"] for c in client.get("/api/v1/posts/channels").get_json()]
    resp = client.post(
        "/api/v1/posts/",
        json={"title": "Both", "body": "B", "channels": every[::-1]},
    )
    assert resp.get_json()["channels"] is None
    resp = client.post(
        "/api/v1/posts/", json={"title": "X", "body": "B", "channels": ["sms"]}
    )
    assert resp.status_code == 400
    assert "sms" in resp.get_data(as_text=True)


def test_a_scheduled_post_keeps_its_channels_until_it_goes_out(client, chat):
    from hubra.api.posts.services import publish_due_posts
    from hubra.core.models.post import Post

    _login(client, "admin@test.ch")
    later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    resp = client.post(
        "/api/v1/posts/", json={"title": "Later", "body": "B", "publish_at": later}
    )
    post_id = resp.get_json()["id"]
    url = f"/api/v1/posts/{post_id}"
    resp = client.patch(url, json={"channels": ["chat"]})
    assert resp.status_code == 200
    assert resp.get_json()["channels"] == ["chat"]
    assert heard == []

    db.session.get(Post, post_id).publish_at = datetime.now(timezone.utc) - timedelta(
        minutes=1
    )
    db.session.commit()
    publish_due_posts()
    assert [h["channels"] for h in heard] == [["chat"]]
    # Out: the channels can't change any more (sending the same is fine).
    assert client.patch(url, json={"channels": ["chat"]}).status_code == 200
    assert client.patch(url, json={"channels": ["app"]}).status_code == 409
