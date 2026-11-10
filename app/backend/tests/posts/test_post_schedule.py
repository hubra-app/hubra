"""Scheduled and expiring posts: members see a post from its publish time
until it expires; those who may edit it see it all along."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from hubra.core.extensions import db
from hubra.core.models.notification import Notification
from hubra.core.models.post import Post
from tests.settings.test_settings_kv import _login, _make_role_and_member

_PERMS = ["posts.posts.read", "posts.posts.like", "posts.posts.comment"]


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


def _new_post_bells() -> int:
    return db.session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.title == "New post")
    )


@pytest.fixture
def reader(client, app, seeded_db):
    """A plain member who may read, like and comment."""
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(db, seeded_db["tier"], name="Reader", permission_keys=_PERMS)


def _titles(client) -> list[str]:
    return [p["title"] for p in client.get("/api/v1/posts/").get_json()]


def test_a_scheduled_post_waits_then_goes_out(client, reader):
    from hubra.api.posts.services import publish_due_posts

    _login(client, "admin@test.ch")
    resp = client.post(
        "/api/v1/posts/",
        json={"title": "Later", "body": "B", "publish_at": _iso(timedelta(hours=2))},
    )
    assert resp.status_code == 201
    post = resp.get_json()
    assert post["publish_at"] is not None
    assert _new_post_bells() == 0
    # The author sees it (marked by publish_at); a member does not.
    assert "Later" in _titles(client)
    _login(client, "reader@test.ch")
    assert "Later" not in _titles(client)
    url = f"/api/v1/posts/{post['id']}"
    assert client.get(url).status_code == 404
    assert client.post(f"{url}/like").status_code == 404
    assert client.post(f"{url}/comments", json={"body": "?"}).status_code == 404

    # Not yet due: nothing happens.
    assert publish_due_posts() == 0
    # Due: out, at the top, announced.
    assert publish_due_posts(datetime.now(timezone.utc) + timedelta(hours=3)) == 1
    db.session.commit()
    row = db.session.get(Post, post["id"])
    assert row.publish_at is None
    assert _new_post_bells() > 0
    assert client.get(url).status_code == 200
    assert _titles(client)[0] == "Later"


def test_a_past_publish_time_means_now(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/posts/",
        json={"title": "Now", "body": "B", "publish_at": _iso(-timedelta(minutes=1))},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.get_json()["publish_at"] is None


def test_publish_a_scheduled_post_now_or_move_it(client, auth_headers, seeded_db):
    post = client.post(
        "/api/v1/posts/",
        json={"title": "S", "body": "B", "publish_at": _iso(timedelta(days=1))},
        headers=auth_headers,
    ).get_json()
    url = f"/api/v1/posts/{post['id']}"
    later = _iso(timedelta(days=2))
    moved = client.patch(url, json={"publish_at": later}, headers=auth_headers)
    assert moved.status_code == 200
    assert moved.get_json()["publish_at"] is not None
    out = client.patch(url, json={"publish_at": None}, headers=auth_headers)
    assert out.status_code == 200
    assert out.get_json()["publish_at"] is None
    # Once out it cannot be scheduled again.
    again = client.patch(url, json={"publish_at": later}, headers=auth_headers)
    assert again.status_code == 409
    assert again.get_json()["error"] == "POST_ALREADY_OUT"


def test_an_expired_post_is_hidden_from_members(client, reader):
    _login(client, "admin@test.ch")
    post = client.post(
        "/api/v1/posts/",
        json={
            "title": "Pitch closed",
            "body": "B",
            "hide_after": _iso(timedelta(hours=1)),
        },
    ).get_json()
    _login(client, "reader@test.ch")
    assert "Pitch closed" in _titles(client)
    row = db.session.get(Post, post["id"])
    row.hide_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()
    assert "Pitch closed" not in _titles(client)
    assert client.get(f"/api/v1/posts/{post['id']}").status_code == 404
    # The author still has it, to show again with a later date.
    _login(client, "admin@test.ch")
    assert "Pitch closed" in _titles(client)
    resp = client.patch(f"/api/v1/posts/{post['id']}", json={"hide_after": None})
    assert resp.status_code == 200
    _login(client, "reader@test.ch")
    assert "Pitch closed" in _titles(client)


def test_times_are_checked(client, auth_headers, seeded_db):
    def create(**extra):
        return client.post(
            "/api/v1/posts/",
            json={"title": "T", "body": "B", **extra},
            headers=auth_headers,
        )

    assert create(publish_at=_iso(timedelta(days=400))).status_code == 400
    assert create(hide_after=_iso(-timedelta(hours=1))).status_code == 400
    assert (
        create(
            publish_at=_iso(timedelta(days=2)), hide_after=_iso(timedelta(days=1))
        ).status_code
        == 400
    )
    assert create(publish_at="tomorrow").status_code == 400


def test_the_beat_publishes_in_every_club(app, client, auth_headers, seeded_db):
    from hubra.api.posts.tasks import _publish_scheduled_posts

    client.post(
        "/api/v1/posts/",
        json={"title": "S", "body": "B", "publish_at": _iso(timedelta(seconds=1))},
        headers=auth_headers,
    )
    row = db.session.scalar(select(Post).where(Post.title == "S"))
    row.publish_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    _publish_scheduled_posts()
    db.session.expire_all()
    assert db.session.scalar(select(Post).where(Post.title == "S")).publish_at is None


def test_scheduling_needs_sign_in(client, seeded_db):
    resp = client.post(
        "/api/v1/posts/",
        json={"title": "T", "body": "B", "publish_at": _iso(timedelta(days=1))},
    )
    assert resp.status_code == 401
