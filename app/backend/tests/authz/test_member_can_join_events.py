"""An ordinary member can sign up for an event and give the place up.

The Member role could read events but not register, and system roles cannot
be edited, so no member could join an event in the club app.
"""

from datetime import date

from hubra.core.tenant.service import DEFAULT_ROLE_PERMISSIONS


def _event(db, **fields):
    from hubra.core.models.event import ClubEvent

    event = ClubEvent(title="Fest", date=date(2030, 1, 1), type="Social", **fields)
    db.session.add(event)
    db.session.commit()
    return event.id


def test_member_role_signs_up_and_cancels(client, db, permissioned_member_factory):
    headers = permissioned_member_factory(DEFAULT_ROLE_PERMISSIONS["Member"])
    event_id = _event(db)

    resp = client.post(f"/api/v1/events/{event_id}/register", json={}, headers=headers)
    assert resp.status_code == 201
    resp = client.post(f"/api/v1/events/{event_id}/cancel-registration", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "cancelled"


def test_leaving_when_an_organiser_put_you_on_the_list(
    client, db, permissioned_member_factory
):
    from hubra.core.models.event import event_attendees
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    headers = permissioned_member_factory(
        DEFAULT_ROLE_PERMISSIONS["Member"], email="listed@test.ch"
    )
    member_id = (
        db.session.query(Member.id)
        .join(User, User.id == Member.user_id)
        .filter(User.email == "listed@test.ch")
        .scalar()
    )
    event_id = _event(db)
    db.session.execute(event_attendees.insert().values(event_id=event_id, member_id=member_id))
    db.session.commit()

    resp = client.post(f"/api/v1/events/{event_id}/cancel-registration", headers=headers)
    assert resp.status_code == 204
    assert not db.session.execute(
        event_attendees.select().where(event_attendees.c.event_id == event_id)
    ).all()
