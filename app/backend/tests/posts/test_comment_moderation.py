"""Comment moderation: report, hide, keep, mute (hubra/api/posts/moderation.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from hubra.core.models.audit import AuditEntry
from hubra.core.models.member import Member
from hubra.core.models.notification import Notification
from hubra.core.models.post import CommentMute
from hubra.core.models.user import User
from tests.posts.test_post_ownership import _PERMS
from tests.settings.test_settings_kv import _login, _make_role_and_member

MOD = _PERMS + ["posts.posts.moderate"]


def _member_id(db, email: str) -> int:
    return db.session.scalar(
        select(Member.id)
        .join(User, User.id == Member.user_id)
        .where(User.email == email)
    )


def _setup(client, app, db, seeded_db):
    """Writer comments on admin's post; Reader and Mod come along."""
    app.test_cli_runner().invoke(args=["sync-permissions"])
    for name, keys in (("Writer", _PERMS), ("Reader", _PERMS), ("Mod", MOD)):
        _make_role_and_member(db, seeded_db["tier"], name=name, permission_keys=keys)
    _login(client, "admin@test.ch")
    post = client.post("/api/v1/posts/", json={"title": "T", "body": "B"}).get_json()
    _login(client, "writer@test.ch")
    comment = client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"body": "Rude words"}
    ).get_json()
    return post["id"], comment["id"]


def test_report_tells_the_moderators_once(client, app, db, seeded_db):
    post_id, comment_id = _setup(client, app, db, seeded_db)
    url = f"/api/v1/posts/{post_id}/comments/{comment_id}/report"
    # Not your own comment.
    assert client.post(url).status_code == 400

    _login(client, "reader@test.ch")
    resp = client.post(url, json={"reason": "Insulting"})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["reported_by_me"] is True
    assert "reports" not in resp.get_json()  # only moderators see counts
    assert client.post(url).status_code == 200  # twice: nothing new

    mod_id = _member_id(db, "mod@test.ch")
    told = db.session.scalars(
        select(Notification).where(Notification.title == "A comment was reported")
    ).all()
    assert mod_id in {n.member_id for n in told}
    assert _member_id(db, "reader@test.ch") not in {n.member_id for n in told}
    count = len(told)

    _login(client, "admin@test.ch")
    client.post(url)  # a second reporter: no new notice
    assert (
        len(
            db.session.scalars(
                select(Notification).where(
                    Notification.title == "A comment was reported"
                )
            ).all()
        )
        == count
    )

    _login(client, "mod@test.ch")
    items = client.get("/api/v1/posts/comments/reports").get_json()["items"]
    assert [(i["comment_id"], i["reports"]) for i in items] == [(comment_id, 2)]
    assert items[0]["reasons"] == ["Insulting"]
    rows = client.get(f"/api/v1/posts/{post_id}/comments").get_json()
    assert rows[0]["reports"] == 2


def test_hidden_comments_keep_their_place_but_not_their_text(
    client, app, db, seeded_db
):
    post_id, comment_id = _setup(client, app, db, seeded_db)
    base = f"/api/v1/posts/{post_id}/comments/{comment_id}"
    _login(client, "reader@test.ch")
    client.post(f"{base}/report")
    assert client.post(f"{base}/hide").status_code == 403

    _login(client, "mod@test.ch")
    resp = client.post(f"{base}/hide")
    assert resp.status_code == 200 and resp.get_json()["hidden"] is True
    # Hidden: the reports are done.
    assert client.get("/api/v1/posts/comments/reports").get_json()["items"] == []
    assert client.get(f"/api/v1/posts/{post_id}/comments").get_json()[0]["body"]

    _login(client, "reader@test.ch")
    row = client.get(f"/api/v1/posts/{post_id}/comments").get_json()[0]
    assert row["hidden"] is True and row["body"] == ""

    _login(client, "mod@test.ch")
    assert client.post(f"{base}/show").get_json()["hidden"] is False
    actions = set(db.session.scalars(select(AuditEntry.action)).all())
    assert {"hide_comment", "show_comment"} <= actions


def test_keep_clears_the_reports(client, app, db, seeded_db):
    post_id, comment_id = _setup(client, app, db, seeded_db)
    base = f"/api/v1/posts/{post_id}/comments/{comment_id}"
    _login(client, "reader@test.ch")
    client.post(f"{base}/report")
    assert client.delete(f"{base}/reports").status_code == 403
    _login(client, "mod@test.ch")
    assert client.delete(f"{base}/reports").get_json()["reports"] == 0
    assert client.get("/api/v1/posts/comments/reports").get_json()["items"] == []


def test_a_muted_member_cannot_comment_until_the_end(client, app, db, seeded_db):
    post_id, _ = _setup(client, app, db, seeded_db)
    writer = _member_id(db, "writer@test.ch")
    _login(client, "mod@test.ch")
    for bad in ({"member_id": writer, "days": 0}, {"member_id": writer, "days": "7"}):
        assert client.post("/api/v1/posts/comments/mutes", json=bad).status_code == 400
    resp = client.post(
        "/api/v1/posts/comments/mutes",
        json={"member_id": writer, "days": 7, "reason": "Cool down"},
    )
    assert resp.status_code == 200, resp.get_json()
    assert [i["member_id"] for i in resp.get_json()["items"]] == [writer]

    _login(client, "writer@test.ch")
    url = f"/api/v1/posts/{post_id}/comments"
    resp = client.post(url, json={"body": "Again"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "COMMENTS_MUTED"

    # Over: comments again.
    mute = db.session.scalar(select(CommentMute).where(CommentMute.member_id == writer))
    mute.until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()
    assert client.post(url, json={"body": "Sorry"}).status_code == 201

    _login(client, "mod@test.ch")
    client.post("/api/v1/posts/comments/mutes", json={"member_id": writer, "days": 1})
    resp = client.delete(f"/api/v1/posts/comments/mutes/{writer}")
    assert resp.status_code == 200 and resp.get_json()["items"] == []
    assert client.delete(f"/api/v1/posts/comments/mutes/{writer}").status_code == 404


def test_moderation_lists_need_the_right(client, app, db, seeded_db):
    _setup(client, app, db, seeded_db)
    _login(client, "reader@test.ch")
    assert client.get("/api/v1/posts/comments/reports").status_code == 403
    assert client.get("/api/v1/posts/comments/mutes").status_code == 403
    assert (
        client.post(
            "/api/v1/posts/comments/mutes", json={"member_id": 1, "days": 1}
        ).status_code
        == 403
    )
    anon = app.test_client()
    assert anon.get("/api/v1/posts/comments/reports").status_code == 401
