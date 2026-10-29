"""Admin notes and emergency contacts are not for every member.

Every Member role can read the member list, which carried the notes the
board writes about a member and their emergency contact.
"""

from hubra.core.tenant.service import DEFAULT_ROLE_PERMISSIONS


def _member_ids(db):
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    rows = db.session.query(User.email, Member.id).join(Member, Member.user_id == User.id)
    return dict(rows.all())


def _note_everyone(db):
    from hubra.core.models.member import Member

    for member in db.session.query(Member).all():
        member.notes = "Board note"
        member.user.emergency_contact = {"name": "Mama", "phone": "079"}
    db.session.commit()


def test_plain_member_sees_them_only_for_themselves(
    client, db, permissioned_member_factory
):
    headers = permissioned_member_factory(
        DEFAULT_ROLE_PERMISSIONS["Member"], email="viewer@test.ch"
    )
    _note_everyone(db)
    me = _member_ids(db)["viewer@test.ch"]

    rows = client.get("/api/v1/members?pageSize=100", headers=headers).get_json()["data"]
    assert len(rows) > 1
    for row in rows:
        if row["id"] == me:
            assert row["notes"] == "Board note"
            assert row["emergency_contact"]["name"] == "Mama"
        else:
            assert "notes" not in row
            assert "emergency_contact" not in row

    other = next(row["id"] for row in rows if row["id"] != me)
    single = client.get(f"/api/v1/members/{other}", headers=headers).get_json()
    assert "notes" not in single and "emergency_contact" not in single


def test_member_editors_still_see_them(client, db, permissioned_member_factory):
    headers = permissioned_member_factory(
        ["members.members.read", "members.members.update"]
    )
    _note_everyone(db)
    rows = client.get("/api/v1/members?pageSize=100", headers=headers).get_json()["data"]
    assert all(row["notes"] == "Board note" for row in rows)


def test_plain_member_cannot_list_former_members(client, db, permissioned_member_factory):
    from datetime import datetime, timezone

    from hubra.core.models.member import Member

    headers = permissioned_member_factory(DEFAULT_ROLE_PERMISSIONS["Member"])
    others = db.session.query(Member).all()
    gone = others[0]
    gone.archived_at = datetime.now(timezone.utc)
    db.session.commit()

    rows = client.get(
        "/api/v1/members?archived=true&include_deleted=true&pageSize=100", headers=headers
    ).get_json()["data"]
    assert gone.id not in [row["id"] for row in rows]
    assert rows  # the current members, as without the filters
