"""A group's parent must exist and cannot be the group or one below it.

Before, an unknown parent id failed on the foreign key (500), and in a club
schema, which has no foreign keys, it was stored pointing at nothing.
"""


def _group(client, headers, name, **fields):
    resp = client.post("/api/v1/groups/", json={"name": name, **fields}, headers=headers)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["id"]


def test_parent_must_exist(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/groups/", json={"name": "Orphan", "parent_group_id": 99999}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_no_cycles(client, auth_headers, seeded_db):
    top = _group(client, auth_headers, "Vorstand")
    sub = _group(client, auth_headers, "Finanzen", parent_group_id=top)

    for group_id, parent in ((top, top), (top, sub)):
        resp = client.patch(
            f"/api/v1/groups/{group_id}", json={"parent_group_id": parent}, headers=auth_headers
        )
        assert resp.status_code == 400

    resp = client.patch(
        f"/api/v1/groups/{sub}", json={"parent_group_id": None}, headers=auth_headers
    )
    assert resp.status_code == 200


def test_deleting_a_parent_keeps_its_subgroups(client, auth_headers, seeded_db):
    top = _group(client, auth_headers, "Werkstatt")
    sub = _group(client, auth_headers, "Holz", parent_group_id=top)

    assert client.delete(f"/api/v1/groups/{top}", headers=auth_headers).status_code == 204
    resp = client.get(f"/api/v1/groups/{sub}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["parent_group_id"] is None
