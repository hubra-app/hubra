"""A system role's admin flag cannot be switched through the API.

Before, ``PATCH /roles/<id>`` with only ``is_admin`` skipped the lock that
renames get: an admin could take admin rights from the Owner role or give
them to every member through the Member role.
"""

from hubra.core.models.role import Role


def _role(db, **fields):
    role = Role(**fields)
    db.session.add(role)
    db.session.commit()
    return role


def test_system_roles_keep_their_admin_flag(client, db, seeded_db, auth_headers):
    owner = _role(db, name="Inhaber", is_admin=True, is_owner=True, is_system=True)
    member = _role(db, name="Mitglied", is_admin=False, is_system=True)

    for role, value in ((owner, False), (member, True)):
        resp = client.patch(
            f"/api/v1/roles/{role.id}", json={"is_admin": value}, headers=auth_headers
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "ROLE_LOCKED"
        db.session.refresh(role)
        assert role.is_admin is (not value)

    # Sending the flag it already has (the edit form always does) is fine.
    resp = client.patch(
        f"/api/v1/roles/{member.id}",
        json={"is_admin": False, "description": "Alle"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_custom_roles_can_become_admin(client, db, seeded_db, auth_headers):
    role = _role(db, name="Vorstand")
    resp = client.patch(
        f"/api/v1/roles/{role.id}", json={"is_admin": True}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["is_admin"] is True
