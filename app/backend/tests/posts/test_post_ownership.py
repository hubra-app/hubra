"""Members edit and delete only their own posts and comments; admins any."""

import pytest

from tests.settings.test_settings_kv import _login, _make_role_and_member

_PERMS = [
    "posts.posts.read",
    "posts.posts.create",
    "posts.posts.update",
    "posts.posts.delete",
    "posts.posts.comment",
]


@pytest.fixture
def two_authors(client, app, db, seeded_db):
    """The admin's post and comment, and a plain member with post rights."""
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(db, seeded_db["tier"], name="Writer", permission_keys=_PERMS)
    _login(client, "admin@test.ch")
    post = client.post("/api/v1/posts/", json={"title": "T", "body": "B"}).get_json()
    comment = client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"body": "C"}
    ).get_json()
    _login(client, "writer@test.ch")
    return post["id"], comment["id"]


def test_a_member_cannot_change_someone_elses_post(client, two_authors):
    post_id, comment_id = two_authors
    url = f"/api/v1/posts/{post_id}"
    assert client.patch(url, json={"title": "Mine now"}).status_code == 403
    assert client.delete(url).status_code == 403
    assert client.delete(f"{url}/comments/{comment_id}").status_code == 403
    # Their own post they can change (so the 403s are not missing rights).
    mine = client.post("/api/v1/posts/", json={"title": "M", "body": "B"}).get_json()
    assert (
        client.patch(f"/api/v1/posts/{mine['id']}", json={"title": "M2"}).status_code
        == 200
    )
    assert client.delete(f"/api/v1/posts/{mine['id']}").status_code == 204
    # Their own comment they can delete.
    own = client.post(f"{url}/comments", json={"body": "Mine"}).get_json()
    assert client.delete(f"{url}/comments/{own['id']}").status_code == 204


def test_an_admin_removes_anyones_comment(client, two_authors):
    post_id, _ = two_authors
    url = f"/api/v1/posts/{post_id}/comments"
    own = client.post(url, json={"body": "Spam"}).get_json()
    _login(client, "admin@test.ch")
    assert client.delete(f"{url}/{own['id']}").status_code == 204


def test_a_comment_is_only_found_under_its_post(client, two_authors):
    post_id, comment_id = two_authors
    other = client.post("/api/v1/posts/", json={"title": "O", "body": "B"}).get_json()
    url = f"/api/v1/posts/{other['id']}/comments/{comment_id}"
    assert client.delete(url).status_code == 404
