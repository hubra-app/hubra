"""Whoever may delete posts may also remove someone else's comment; a
member who may only comment still removes only their own."""


def _post_with_comment(client, auth_headers):
    post_id = client.post(
        "/api/v1/posts/", json={"title": "T", "body": "B"}, headers=auth_headers
    ).get_json()["id"]
    comment_id = client.post(
        f"/api/v1/posts/{post_id}/comments", json={"body": "spam"}, headers=auth_headers
    ).get_json()["id"]
    return post_id, comment_id


def test_moderator_removes_a_comment(client, auth_headers, permissioned_member_factory):
    post_id, comment_id = _post_with_comment(client, auth_headers)
    url = f"/api/v1/posts/{post_id}/comments/{comment_id}"

    permissioned_member_factory(["posts.posts.read", "posts.posts.comment"])
    assert client.delete(url).status_code == 403

    permissioned_member_factory(
        ["posts.posts.read", "posts.posts.comment", "posts.posts.delete"]
    )
    assert client.delete(url).status_code == 204
