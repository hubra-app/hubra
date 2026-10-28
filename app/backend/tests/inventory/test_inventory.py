"""Integration tests for the inventory module."""

BASE = "/api/v1/inventory"


# ── helpers ───────────────────────────────────────────────────────────────────


def _create_item(client, auth_headers, **kwargs):
    payload = {"name": "Test Drill", "category": "Tool", **kwargs}
    return client.post(f"{BASE}/", json=payload, headers=auth_headers)


def _make_member(db, seeded_db, first="Alice", last="Smith", email="alice@inv.ch"):
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    user = User(email=email, first_name=first, last_name=last)
    user.set_password("pw")
    db.session.add(user)
    db.session.flush()

    m = Member(user_id=user.id, status="active")
    m.roles = [seeded_db["role"]]
    m.tier_id = seeded_db["tier"].id
    db.session.add(m)
    db.session.flush()
    return m


# ── list / filter ─────────────────────────────────────────────────────────────


def test_list_empty(client, auth_headers, seeded_db):
    resp = client.get(f"{BASE}/", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_requires_auth(client, seeded_db):
    resp = client.get(f"{BASE}/")
    assert resp.status_code == 401


def test_list_returns_created_items(client, db, auth_headers, seeded_db):
    _create_item(client, auth_headers, name="Lathe", category="Tool")
    _create_item(client, auth_headers, name="Wood plank", category="Material")

    resp = client.get(f"{BASE}/", headers=auth_headers)
    assert resp.status_code == 200
    names = [i["name"] for i in resp.get_json()]
    assert "Lathe" in names
    assert "Wood plank" in names


def test_list_filter_by_category(client, db, auth_headers, seeded_db):
    _create_item(client, auth_headers, name="Hammer", category="Tool")
    _create_item(client, auth_headers, name="Bolt bag", category="Material")

    resp = client.get(f"{BASE}/?category=Tool", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert all(i["category"] == "Tool" for i in data)
    names = [i["name"] for i in data]
    assert "Hammer" in names
    assert "Bolt bag" not in names


def test_list_filter_by_status(client, db, auth_headers, seeded_db):
    _create_item(client, auth_headers, name="Welder", category="Tool", status="in_use")
    _create_item(
        client, auth_headers, name="Sander", category="Tool", status="available"
    )

    resp = client.get(f"{BASE}/?status=in_use", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert all(i["status"] == "in_use" for i in data)


# ── create ────────────────────────────────────────────────────────────────────


def test_create_minimal(client, db, auth_headers, seeded_db):
    resp = _create_item(client, auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Test Drill"
    assert data["category"] == "Tool"
    assert data["status"] == "available"
    assert data["visibility"] == "shared"
    assert data["instruction_required"] is False
    assert data["links"] == []


def test_create_full(client, db, auth_headers, seeded_db):
    member = _make_member(db, seeded_db)
    payload = {
        "name": "CNC Router",
        "category": "Tool",
        "description": "Big 3-axis CNC",
        "owner_id": member.id,
        "responsible_id": member.id,
        "visibility": "shared",
        "status": "available",
        "cost": "3500.00",
        "links": [{"label": "Manual", "url": "https://example.com/manual"}],
        "instruction_required": True,
    }
    resp = client.post(f"{BASE}/", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["instruction_required"] is True
    assert data["owner_name"] == f"{member.first_name} {member.last_name}"
    assert len(data["links"]) == 1


def test_create_invalid_category(client, db, auth_headers, seeded_db):
    resp = client.post(
        f"{BASE}/", json={"name": "X", "category": "Furniture"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_create_missing_name(client, db, auth_headers, seeded_db):
    resp = client.post(f"{BASE}/", json={"category": "Tool"}, headers=auth_headers)
    assert resp.status_code == 400


# ── get single ────────────────────────────────────────────────────────────────


def test_get_item(client, db, auth_headers, seeded_db):
    created = _create_item(client, auth_headers).get_json()
    resp = client.get(f"{BASE}/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == created["id"]


def test_get_item_not_found(client, db, auth_headers, seeded_db):
    resp = client.get(f"{BASE}/99999", headers=auth_headers)
    assert resp.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────


def test_update_item(client, db, auth_headers, seeded_db):
    created = _create_item(client, auth_headers).get_json()
    resp = client.patch(
        f"{BASE}/{created['id']}",
        json={"status": "in_use", "description": "In workshop"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "in_use"
    assert data["description"] == "In workshop"


def test_update_invalid_status(client, db, auth_headers, seeded_db):
    created = _create_item(client, auth_headers).get_json()
    resp = client.patch(
        f"{BASE}/{created['id']}",
        json={"status": "missing"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_update_not_found(client, db, auth_headers, seeded_db):
    resp = client.patch(f"{BASE}/99999", json={"name": "X"}, headers=auth_headers)
    assert resp.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────


def test_delete_item(client, db, auth_headers, seeded_db):
    created = _create_item(client, auth_headers).get_json()
    resp = client.delete(f"{BASE}/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204
    # Gone after deletion
    assert (
        client.get(f"{BASE}/{created['id']}", headers=auth_headers).status_code == 404
    )


def test_delete_not_found(client, db, auth_headers, seeded_db):
    resp = client.delete(f"{BASE}/99999", headers=auth_headers)
    assert resp.status_code == 404


# ── instruction tracking ──────────────────────────────────────────────────────


def test_add_instruction(client, db, auth_headers, seeded_db):
    created = _create_item(client, auth_headers).get_json()
    member = _make_member(db, seeded_db)

    resp = client.post(
        f"{BASE}/{created['id']}/instructions/{member.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    item = client.get(f"{BASE}/{created['id']}", headers=auth_headers).get_json()
    assert member.id in item["instructed_member_ids"]


def test_add_instruction_duplicate(client, db, auth_headers, seeded_db):
    created = _create_item(client, auth_headers).get_json()
    member = _make_member(db, seeded_db)

    client.post(
        f"{BASE}/{created['id']}/instructions/{member.id}", headers=auth_headers
    )
    resp = client.post(
        f"{BASE}/{created['id']}/instructions/{member.id}", headers=auth_headers
    )
    assert resp.status_code == 409


def test_remove_instruction(client, db, auth_headers, seeded_db):
    created = _create_item(client, auth_headers).get_json()
    member = _make_member(db, seeded_db)

    client.post(
        f"{BASE}/{created['id']}/instructions/{member.id}", headers=auth_headers
    )
    resp = client.delete(
        f"{BASE}/{created['id']}/instructions/{member.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    item = client.get(f"{BASE}/{created['id']}", headers=auth_headers).get_json()
    assert member.id not in item["instructed_member_ids"]


def test_remove_instruction_not_found(client, db, auth_headers, seeded_db):
    created = _create_item(client, auth_headers).get_json()
    resp = client.delete(
        f"{BASE}/{created['id']}/instructions/99999", headers=auth_headers
    )
    assert resp.status_code == 404


def test_self_instruction(client, db, auth_headers, seeded_db):
    """The logged-in admin can self-record instruction receipt."""
    created = _create_item(client, auth_headers).get_json()

    resp = client.post(
        f"{BASE}/{created['id']}/instructions/self",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    item = client.get(f"{BASE}/{created['id']}", headers=auth_headers).get_json()
    admin_id = seeded_db["admin"].id
    assert admin_id in item["instructed_member_ids"]


def test_self_instruction_duplicate(client, db, auth_headers, seeded_db):
    created = _create_item(client, auth_headers).get_json()
    client.post(f"{BASE}/{created['id']}/instructions/self", headers=auth_headers)
    resp = client.post(
        f"{BASE}/{created['id']}/instructions/self", headers=auth_headers
    )
    assert resp.status_code == 409
