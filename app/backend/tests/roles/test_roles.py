"""Integration tests for GET/PUT /api/v1/roles and /api/v1/roles/{id}/permissions."""

from hubra.core.models.role import Permission, Role

BASE = "/api/v1/roles"


def _seed_permissions(db, keys):
    """Create Permission rows for the given keys and return them."""
    perms = []
    for key in keys:
        p = Permission(
            key=key,
            display_name=key,
            resource=key.split(".")[1] if "." in key else key,
            action=key.split(".")[2] if "." in key and len(key.split(".")) > 2 else key,
            blueprint=key.split(".")[0] if "." in key else "",
        )
        db.session.add(p)
        perms.append(p)
    db.session.commit()
    return perms


def _create_non_admin_role(db):
    """Create a non-admin, non-default role for permission tests."""
    role = Role(name="TestRole", is_default=False, is_admin=False)
    db.session.add(role)
    db.session.commit()
    return role


# ── 1. List roles ──────────────────────────────────────────────────────────────


def test_list_roles_returns_array(client, seeded_db, auth_headers):
    resp = client.get(BASE + "/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    role = data[0]
    assert "id" in role
    assert "name" in role
    assert "is_default" in role


# ── 2. Get permissions (empty) ─────────────────────────────────────────────────


def test_get_role_permissions_empty(client, seeded_db, auth_headers):
    role_id = seeded_db["role"].id
    resp = client.get(f"{BASE}/{role_id}/permissions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["role_id"] == role_id
    assert data["permissions"] == []


# ── 3. Set permissions ─────────────────────────────────────────────────────────


def test_set_role_permissions(client, db, seeded_db, auth_headers):
    _seed_permissions(db, ["members.read", "finance.overview.read"])
    role = _create_non_admin_role(db)
    role_id = role.id
    perms = ["members.read", "finance.overview.read"]
    resp = client.put(
        f"{BASE}/{role_id}/permissions",
        json={"permissions": perms},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["role_id"] == role_id
    assert data["permissions"] == sorted(perms)


# ── 4. Replace semantics ───────────────────────────────────────────────────────


def test_set_role_permissions_replaces(client, db, seeded_db, auth_headers):
    _seed_permissions(
        db, ["members.read", "finance.overview.read", "roles.manage.read"]
    )
    role = _create_non_admin_role(db)
    role_id = role.id
    first = ["members.read", "finance.overview.read"]
    second = ["roles.manage.read"]

    client.put(
        f"{BASE}/{role_id}/permissions",
        json={"permissions": first},
        headers=auth_headers,
    )
    resp = client.put(
        f"{BASE}/{role_id}/permissions",
        json={"permissions": second},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["permissions"] == sorted(second)

    # Verify GET also reflects the replacement
    get_resp = client.get(f"{BASE}/{role_id}/permissions", headers=auth_headers)
    assert get_resp.get_json()["permissions"] == sorted(second)


# ── 5. GET 404 ─────────────────────────────────────────────────────────────────


def test_get_role_permissions_not_found(client, seeded_db, auth_headers):
    resp = client.get(f"{BASE}/99999/permissions", headers=auth_headers)
    assert resp.status_code == 404


# ── 6. PUT 404 ─────────────────────────────────────────────────────────────────


def test_set_role_permissions_not_found(client, db, seeded_db, auth_headers):
    _seed_permissions(db, ["members.read"])
    resp = client.put(
        f"{BASE}/99999/permissions",
        json={"permissions": ["members.read"]},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── 7. PUT 400 — permissions not a list ───────────────────────────────────────


def test_set_role_permissions_requires_list(client, db, seeded_db, auth_headers):
    role = _create_non_admin_role(db)
    role_id = role.id
    resp = client.put(
        f"{BASE}/{role_id}/permissions",
        json={"permissions": "not-a-list"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ── 8. Admin role is locked ──────────────────────────────────────────────────


def test_delete_admin_role_returns_409(client, seeded_db, auth_headers):
    """Cannot delete an admin role."""
    role_id = seeded_db["role"].id
    resp = client.delete(f"{BASE}/{role_id}", headers=auth_headers)
    assert resp.status_code == 409


def test_update_admin_role_returns_409(client, seeded_db, auth_headers):
    """Cannot update an admin role's name."""
    role_id = seeded_db["role"].id
    resp = client.patch(
        f"{BASE}/{role_id}",
        json={"name": "SuperAdmin"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_set_permissions_on_admin_role_returns_409(client, db, seeded_db, auth_headers):
    """Cannot set permissions on an admin role."""
    _seed_permissions(db, ["members.read"])
    role_id = seeded_db["role"].id
    resp = client.put(
        f"{BASE}/{role_id}/permissions",
        json={"permissions": ["members.read"]},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_create_role_and_tier_are_audited_with_their_ids(client, auth_headers, db):
    from hubra.core.models.audit import AuditEntry

    role = client.post("/api/v1/roles/", json={"name": "Kasse"}, headers=auth_headers)
    assert role.status_code == 201, role.get_json()
    tier = client.post(
        "/api/v1/tiers/",
        json={"name": "Passiv", "price_chf": 20, "color": "#123456", "price_type": "fixed"},
        headers=auth_headers,
    )
    assert tier.status_code == 201, tier.get_json()

    by_type = {e.target_type: e.target_id for e in db.session.query(AuditEntry).all()}
    assert by_type["Role"] == role.get_json()["id"]
    assert by_type["tier"] == tier.get_json()["id"]
