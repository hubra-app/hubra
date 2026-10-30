"""What a club can change on its roles.

The Treasurer and Member system roles are starting points: their names stay
(the app translates them), but their permissions and description change. A
club's own admin role can be renamed and removed again, by an admin.
"""

from hubra.core.models.role import Role


def _role(db, **fields):
    role = Role(**fields)
    db.session.add(role)
    db.session.commit()
    return role


def test_member_role_permissions_can_change(client, db, seeded_db, auth_headers):
    member = _role(db, name="Member", is_default=True, is_system=True)

    resp = client.put(
        f"/api/v1/roles/{member.id}/permissions",
        json={"permissions": ["events.events.read", "events.events.register"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["permissions"] == [
        "events.events.read",
        "events.events.register",
    ]


def test_system_role_description_saves_with_its_name(
    client, db, seeded_db, auth_headers
):
    treasurer = _role(db, name="Treasurer", is_system=True)

    # The edit form sends the unchanged name along with the description.
    resp = client.patch(
        f"/api/v1/roles/{treasurer.id}",
        json={"name": "Treasurer", "description": "Kasse", "is_admin": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["description"] == "Kasse"

    resp = client.patch(
        f"/api/v1/roles/{treasurer.id}", json={"name": "Kasse"}, headers=auth_headers
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "ROLE_LOCKED"


def test_own_admin_role_can_be_renamed_and_removed(
    client, db, seeded_db, auth_headers
):
    board = _role(db, name="Vorstand", is_admin=True)

    resp = client.patch(
        f"/api/v1/roles/{board.id}",
        json={"name": "Präsidium", "is_admin": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Präsidium"

    resp = client.patch(
        f"/api/v1/roles/{board.id}",
        json={"name": "Präsidium", "is_admin": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["is_admin"] is False

    board.is_admin = True
    db.session.commit()
    resp = client.delete(f"/api/v1/roles/{board.id}", headers=auth_headers)
    assert resp.status_code == 204


def test_only_an_admin_removes_an_admin_role(
    client, db, seeded_db, permissioned_member_factory
):
    board = _role(db, name="Vorstand", is_admin=True)
    headers = permissioned_member_factory(["roles.roles.delete"])

    resp = client.delete(f"/api/v1/roles/{board.id}", headers=headers)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "ADMIN_ONLY"


def test_role_manager_saves_the_edit_form(
    client, db, seeded_db, permissioned_member_factory
):
    """A non-admin with roles.update saves a role; the form always sends
    is_admin, which used to answer 403 "Only admins can change is_admin"."""
    helpers = _role(db, name="Helfer")
    board = _role(db, name="Vorstand", is_admin=True)
    headers = permissioned_member_factory(["roles.roles.update"])

    resp = client.patch(
        f"/api/v1/roles/{helpers.id}",
        json={"name": "Helfende", "description": None, "is_admin": False},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Helfende"

    resp = client.patch(
        f"/api/v1/roles/{helpers.id}", json={"is_admin": True}, headers=headers
    )
    assert resp.status_code == 403

    resp = client.patch(
        f"/api/v1/roles/{board.id}",
        json={"name": "Vorstand", "description": "x", "is_admin": True},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "ADMIN_ONLY"
