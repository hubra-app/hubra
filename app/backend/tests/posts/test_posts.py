"""Tests for the posts blueprint (/api/v1/posts)."""


def _post_payload(**overrides):
    payload = {
        "title": "New dust extractor installed!",
        "body": "The workshop now has a new Staubex R-30 dust extractor.",
    }
    payload.update(overrides)
    return payload


def _create_post(client, auth_headers, **overrides):
    return client.post(
        "/api/v1/posts/", json=_post_payload(**overrides), headers=auth_headers
    )


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_post(client, auth_headers, seeded_db):
    resp = _create_post(client, auth_headers)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "New dust extractor installed!"
    assert body["body"] == "The workshop now has a new Staubex R-30 dust extractor."
    assert body["author_name"] is not None
    assert body["like_count"] == 0
    assert body["comment_count"] == 0
    assert body["like_member_ids"] == []


def test_create_post_rejects_oversized_body(client, auth_headers, seeded_db):
    resp = _create_post(client, auth_headers, body="x" * 100_001)
    assert resp.status_code == 400

    post_id = _create_post(client, auth_headers).get_json()["id"]
    resp = client.patch(
        f"/api/v1/posts/{post_id}", json={"body": "x" * 100_001}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_create_post_with_summary(client, auth_headers, seeded_db):
    resp = _create_post(
        client, auth_headers, summary="Quick update about the workshop."
    )
    assert resp.status_code == 201
    assert resp.get_json()["summary"] == "Quick update about the workshop."


# ── List ──────────────────────────────────────────────────────────────────────


def test_list_posts(client, auth_headers, seeded_db):
    _create_post(client, auth_headers, title="Post A")
    _create_post(client, auth_headers, title="Post B")
    resp = client.get("/api/v1/posts/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 2
    # Newest first
    assert body[0]["title"] == "Post B"


# ── Get ───────────────────────────────────────────────────────────────────────


def test_get_post(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    resp = client.get(f"/api/v1/posts/{post_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == post_id


def test_get_post_not_found(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/posts/9999", headers=auth_headers)
    assert resp.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────


def test_update_post(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    resp = client.patch(
        f"/api/v1/posts/{post_id}",
        json={"title": "Updated title", "body": "Updated body"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Updated title"
    assert resp.get_json()["body"] == "Updated body"


# ── Delete ────────────────────────────────────────────────────────────────────


def test_delete_post(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    resp = client.delete(f"/api/v1/posts/{post_id}", headers=auth_headers)
    assert resp.status_code == 204
    resp = client.get(f"/api/v1/posts/{post_id}", headers=auth_headers)
    assert resp.status_code == 404


# ── Likes ─────────────────────────────────────────────────────────────────────


def test_like_then_unlike(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]

    resp = client.post(f"/api/v1/posts/{post_id}/like", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["like_count"] == 1
    assert seeded_db["admin"].id in body["like_member_ids"]

    resp = client.delete(f"/api/v1/posts/{post_id}/like", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["like_count"] == 0


def test_double_like_conflict(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    client.post(f"/api/v1/posts/{post_id}/like", headers=auth_headers)
    resp = client.post(f"/api/v1/posts/{post_id}/like", headers=auth_headers)
    assert resp.status_code == 409


def test_unlike_not_liked(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    resp = client.delete(f"/api/v1/posts/{post_id}/like", headers=auth_headers)
    assert resp.status_code == 404


# ── Comments ──────────────────────────────────────────────────────────────────


def test_create_comment(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    resp = client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"body": "Great news!"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["body"] == "Great news!"
    assert body["author_name"] is not None


def test_list_comments(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"body": "First!"},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"body": "Nice."},
        headers=auth_headers,
    )
    resp = client.get(f"/api/v1/posts/{post_id}/comments", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 2
    assert body[0]["body"] == "First!"


def test_delete_comment(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    comment_id = client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"body": "To be deleted"},
        headers=auth_headers,
    ).get_json()["id"]
    resp = client.delete(
        f"/api/v1/posts/{post_id}/comments/{comment_id}", headers=auth_headers
    )
    assert resp.status_code == 204
    resp = client.get(f"/api/v1/posts/{post_id}/comments", headers=auth_headers)
    assert len(resp.get_json()) == 0


def test_comment_count_in_post(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"body": "c1"},
        headers=auth_headers,
    )
    resp = client.get(f"/api/v1/posts/{post_id}", headers=auth_headers)
    assert resp.get_json()["comment_count"] == 1


# ── Validation ────────────────────────────────────────────────────────────────


def test_create_post_validation(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/posts/", json={"body": "missing title"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_create_comment_validation(client, auth_headers, seeded_db):
    post_id = _create_post(client, auth_headers).get_json()["id"]
    resp = client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 400
