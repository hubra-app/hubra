"""Who was instructed on a machine, and by whom, is in the audit log; an
archived member can no longer be marked as instructed."""

from sqlalchemy import select

from tests.inventory.test_m5_inventory import _create_item, _create_member


def _actions(db):
    from hubra.core.models.audit import AuditEntry

    return db.session.scalars(
        select(AuditEntry.action).where(AuditEntry.action.like("%item_instruction"))
    ).all()


def test_instructions_are_audited(client, db, auth_headers, seeded_db):
    item_id = _create_item(client, auth_headers, name="Laser").get_json()["id"]
    member_id = _create_member(client, auth_headers).get_json()["id"]

    url = f"/api/v1/inventory/{item_id}/instructions/{member_id}"
    assert client.post(url, headers=auth_headers).status_code == 204
    assert client.delete(url, headers=auth_headers).status_code == 204
    assert sorted(_actions(db)) == ["add_item_instruction", "remove_item_instruction"]


def test_archived_member_cannot_be_instructed(client, db, auth_headers, seeded_db):
    item_id = _create_item(client, auth_headers, name="Saw").get_json()["id"]
    member_id = _create_member(client, auth_headers).get_json()["id"]
    client.post(f"/api/v1/members/{member_id}/archive", json={}, headers=auth_headers)

    resp = client.post(
        f"/api/v1/inventory/{item_id}/instructions/{member_id}", headers=auth_headers
    )
    assert resp.status_code == 404
