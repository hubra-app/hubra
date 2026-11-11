"""Must-read posts: members confirm, the board sees who hasn't, and those
missing get one reminder."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.notification import Notification
from hubra.core.models.post import Post
from tests.settings.test_settings_kv import _login, _make_role_and_member

_PERMS = ["posts.posts.read", "posts.posts.like", "posts.posts.comment"]


@pytest.fixture
def must_read(client, app, seeded_db):
    """The admin's must-read post, and a plain member who reads posts."""
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(db, seeded_db["tier"], name="Reader", permission_keys=_PERMS)
    _login(client, "admin@test.ch")
    post = client.post(
        "/api/v1/posts/", json={"title": "Safety rules", "body": "B", "must_read": True}
    ).get_json()
    assert post["must_read"] is True
    assert post["read_count"] == 0 and post["read_by_me"] is False
    return post["id"]


def _reminders() -> list[int]:
    return list(
        db.session.scalars(
            select(Notification.member_id).where(
                Notification.title == "Please confirm you read this"
            )
        )
    )


def test_members_confirm_and_the_author_sees_who_has_not(client, must_read):
    url = f"/api/v1/posts/{must_read}"
    _login(client, "reader@test.ch")
    # Members do not see the list.
    assert client.get(f"{url}/reads").status_code == 403
    resp = client.post(f"{url}/read")
    assert resp.status_code == 200
    assert resp.get_json()["read_by_me"] is True
    assert resp.get_json()["read_count"] == 1
    # Twice is fine.
    assert client.post(f"{url}/read").status_code == 200
    listed = client.get("/api/v1/posts/").get_json()[0]
    assert listed["read_by_me"] is True and listed["read_count"] == 1

    _login(client, "admin@test.ch")
    status = client.get(f"{url}/reads").get_json()
    assert len(status["confirmed"]) == 1
    assert status["missing"]  # the admin has not confirmed
    assert all(r["member_id"] for r in status["missing"])


def test_a_plain_post_takes_no_confirmation(client, auth_headers, seeded_db):
    post = client.post(
        "/api/v1/posts/", json={"title": "T", "body": "B"}, headers=auth_headers
    ).get_json()
    resp = client.post(f"/api/v1/posts/{post['id']}/read", headers=auth_headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "NOT_MUST_READ"


def test_one_reminder_to_those_missing(client, must_read):
    from hubra.api.posts.services import remind_unread

    _login(client, "reader@test.ch")
    client.post(f"/api/v1/posts/{must_read}/read")
    now = datetime.now(timezone.utc)
    # Too early: nothing.
    assert remind_unread(now) == 0
    later = now + timedelta(days=8)
    reminded = remind_unread(later)
    db.session.commit()
    assert reminded >= 1
    status = db.session.get(Post, must_read)
    assert status.read_reminder_sent_at is not None
    readers = {r["member_id"] for r in _read_status(must_read)["confirmed"]}
    assert readers and not readers & set(_reminders())
    # Only once.
    assert remind_unread(later + timedelta(days=1)) == 0


def _read_status(post_id: int) -> dict:
    from hubra.api.posts.services import PostService

    return PostService.read_status(db.session.get(Post, post_id))


def test_reminders_can_be_off(client, must_read):
    from unittest.mock import patch

    from hubra.api.posts.services import remind_unread

    with patch(
        "hubra.core.modules.get_config", return_value={"must_read_reminder_days": 0}
    ):
        assert remind_unread(datetime.now(timezone.utc) + timedelta(days=30)) == 0


def test_must_read_needs_sign_in(app, must_read):
    anonymous = app.test_client()
    assert anonymous.post(f"/api/v1/posts/{must_read}/read").status_code == 401
    assert anonymous.get(f"/api/v1/posts/{must_read}/reads").status_code == 401
