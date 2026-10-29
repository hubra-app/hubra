"""Ids the club app reads that auto schemas left out (they skip foreign keys).

Without author_id, members could not edit or delete their own posts and
comments in the club app (only admins could); without lead_id, owner_id
and responsible_id, the edit forms could not show the current choice.
"""



def _first(client, url, headers):
    body = client.get(url, headers=headers).get_json()
    rows = body.get("data", body) if isinstance(body, dict) else body
    return rows[0]


def test_ids_are_in_the_answers(client, db, auth_headers, seeded_db):
    from hubra.core.models.application import Application
    from hubra.core.models.group import Group
    from hubra.core.models.inventory import InventoryItem
    from hubra.core.models.post import Post, PostComment

    admin_id = seeded_db["admin"].id
    tier_id = seeded_db["tier"].id
    post = Post(author_id=admin_id, title="Hallo", body="Text")
    db.session.add_all(
        [
            post,
            Group(name="Vorstand", lead_id=admin_id),
            InventoryItem(
                name="Bohrer", category="Tool", owner_id=admin_id, responsible_id=admin_id
            ),
            Application(name="Ada Muster", email="ada@test.ch", wants_tier_id=tier_id),
        ]
    )
    db.session.flush()
    db.session.add(PostComment(post_id=post.id, author_id=admin_id, body="Ok"))
    db.session.commit()

    assert _first(client, "/api/v1/posts/", auth_headers)["author_id"] == admin_id
    comment = _first(client, f"/api/v1/posts/{post.id}/comments", auth_headers)
    assert (comment["author_id"], comment["post_id"]) == (admin_id, post.id)
    assert _first(client, "/api/v1/groups/", auth_headers)["lead_id"] == admin_id
    item = _first(client, "/api/v1/inventory/", auth_headers)
    assert (item["owner_id"], item["responsible_id"]) == (admin_id, admin_id)
    assert _first(client, "/api/v1/applications/", auth_headers)["wants_tier_id"] == tier_id
