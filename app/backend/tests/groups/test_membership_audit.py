"""An admin putting a member into a group, or taking them out, is audited
(joining or leaving on one's own already was)."""

from sqlalchemy import select

from tests.groups.test_m5_groups import _create_group, _create_member


def test_admin_group_changes_are_audited(client, db, auth_headers, seeded_db):
    from hubra.core.models.audit import AuditEntry

    group_id = _create_group(client, auth_headers, name="Holz").get_json()["id"]
    member_id = _create_member(client, auth_headers).get_json()["id"]

    url = f"/api/v1/groups/{group_id}/members/{member_id}"
    assert client.post(url, headers=auth_headers).status_code == 204
    assert client.delete(url, headers=auth_headers).status_code == 204

    rows = db.session.execute(
        select(AuditEntry.action, AuditEntry.target_id).where(
            AuditEntry.action.like("%group_member")
        )
    ).all()
    assert sorted(rows) == [
        ("add_group_member", group_id),
        ("remove_group_member", group_id),
    ]
