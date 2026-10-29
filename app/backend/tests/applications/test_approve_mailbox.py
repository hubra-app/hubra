"""An approved applicant's mailbox is queued only after the member is saved.

Before, the task went to the queue before the commit; a worker that picked
it up first did not find the member and gave up, so no mailbox was made.
"""

from unittest.mock import patch

from hubra.core.extensions import db as _db
from hubra.core.models.application import Application
from hubra.core.models.setting import Setting
from hubra.core.models.user import User
from tests.members.test_invites import H, admin, club  # noqa: F401


def test_mailbox_is_queued_after_the_commit(db, admin, club):  # noqa: F811
    user = User(email="paula@test.ch", first_name="Paula", last_name="Paper")
    user.set_password("VeryStrongPass123!")
    db.session.add_all(
        [
            user,
            Setting(key="mail.domain", value="club-a.ch"),
            Application(name="Paula Paper", email="paula@test.ch"),
        ]
    )
    db.session.commit()
    application_id = db.session.query(Application.id).scalar()

    events = []
    real_commit = _db.session.commit

    def commit():
        events.append("commit")
        real_commit()

    with (
        patch.object(_db.session, "commit", side_effect=commit),
        patch(
            "hubra.core.tasks.wildduck.create_wildduck_user.delay",
            side_effect=lambda member_id: events.append("queue"),
        ),
    ):
        resp = admin.post(f"/api/v1/applications/{application_id}/approve", headers=H)

    assert resp.status_code == 201, resp.get_json()
    assert "queue" in events
    assert events.index("queue") > events.index("commit")
