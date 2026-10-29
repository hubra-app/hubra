"""A role with posts.posts.moderate may edit and remove anyone's posts and
comments, without being an admin."""

from tests.posts.test_post_ownership import _PERMS
from tests.settings.test_settings_kv import _login, _make_role_and_member


def _setup(client, app, db, seeded_db, keys):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(db, seeded_db["tier"], name="Mod", permission_keys=keys)
    _login(client, "admin@test.ch")
    post = client.post("/api/v1/posts/", json={"title": "T", "body": "B"}).get_json()
    comment = client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"body": "C"}
    ).get_json()
    _login(client, "mod@test.ch")
    return post["id"], comment["id"]


def test_sync_registers_the_moderate_right(app, db):
    from sqlalchemy import select

    from hubra.core.models.role import Permission

    app.test_cli_runner().invoke(args=["sync-permissions"])
    perm = db.session.scalar(
        select(Permission).where(Permission.key == "posts.posts.moderate")
    )
    assert perm is not None and perm.is_active


def test_a_moderator_changes_and_removes_others_posts(client, app, db, seeded_db):
    post_id, comment_id = _setup(
        client, app, db, seeded_db, _PERMS + ["posts.posts.moderate"]
    )
    url = f"/api/v1/posts/{post_id}"
    assert client.patch(url, json={"title": "Edited"}).status_code == 200
    assert client.delete(f"{url}/comments/{comment_id}").status_code == 204
    assert client.delete(url).status_code == 204


def test_without_the_right_it_stays_forbidden(client, app, db, seeded_db):
    post_id, comment_id = _setup(client, app, db, seeded_db, _PERMS)
    url = f"/api/v1/posts/{post_id}"
    assert client.patch(url, json={"title": "Edited"}).status_code == 403
    assert client.delete(f"{url}/comments/{comment_id}").status_code == 403
