"""Those who can act on an application or a request to leave are told;
plain members are not."""

from sqlalchemy import select

from hubra.core.models.notification import Notification
from tests.members.test_leave_club import H, _login, _needs_approval, club  # noqa: F401


def _told(db, title):
    return set(
        db.session.scalars(
            select(Notification.member_id).where(Notification.title == title)
        ).all()
    )


def test_admins_hear_of_a_request_to_leave(client, db, club, seeded_db):  # noqa: F811
    _needs_approval(db, club["tenant"], True)
    _login(client, "anna@test.ch")
    client.post("/api/v1/members/me/leave", headers=H)
    assert _told(db, "Request to leave") == {seeded_db["admin"].id}


def test_admins_hear_of_a_new_application(db, seeded_db):
    from hubra.api.applications.services import ApplicationsService

    ApplicationsService.submit("Neu", "Ling", "neu@test.ch")
    db.session.commit()
    assert _told(db, "New application") == {seeded_db["admin"].id}
