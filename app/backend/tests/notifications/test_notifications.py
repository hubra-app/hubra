"""Tests for the in-app notifications API (/api/v1/notifications)."""

import pytest

from hubra.api.notifications.services import notify_all_active, notify_member
from hubra.core.models.member import Member
from hubra.core.models.notification import Notification
from hubra.core.models.user import User


@pytest.fixture
def other_member(db, seeded_db):
    user = User(email="other@test.ch", first_name="Other", last_name="Member")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    member = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    db.session.add(member)
    db.session.commit()
    return member


def _mine(client, auth_headers):
    resp = client.get("/api/v1/notifications/", headers=auth_headers)
    assert resp.status_code == 200
    return resp.get_json()


def test_list_read_and_delete(client, auth_headers, db, seeded_db, other_member):
    admin_id = seeded_db["admin"].id
    db.session.query(Notification).delete()  # the sign-in's "new device" note
    notify_member(admin_id, "info", "Eins", "a")
    notify_member(admin_id, "info", "Zwei", "b")
    notify_member(other_member.id, "info", "Fremd", "c")
    db.session.commit()

    body = _mine(client, auth_headers)
    assert {n["title"] for n in body["data"]} == {"Eins", "Zwei"}
    assert body["meta"]["unread"] == 2

    first = body["data"][0]["id"]
    resp = client.patch(f"/api/v1/notifications/{first}/read", headers=auth_headers)
    assert resp.status_code == 200 and resp.get_json()["read"] is True
    assert _mine(client, auth_headers)["meta"]["unread"] == 1

    assert client.post("/api/v1/notifications/read-all", headers=auth_headers).status_code == 200
    assert _mine(client, auth_headers)["meta"]["unread"] == 0

    assert client.delete(f"/api/v1/notifications/{first}", headers=auth_headers).status_code == 204
    assert len(_mine(client, auth_headers)["data"]) == 1

    # read-all touched only the caller's own notifications
    other = db.session.query(Notification).filter_by(member_id=other_member.id).one()
    assert other.read is False


def test_someone_elses_notification_is_404(client, auth_headers, db, other_member):
    notify_member(other_member.id, "info", "Fremd", "c")
    db.session.commit()
    other_id = db.session.query(Notification).filter_by(member_id=other_member.id).one().id

    assert client.patch(f"/api/v1/notifications/{other_id}/read", headers=auth_headers).status_code == 404
    assert client.delete(f"/api/v1/notifications/{other_id}", headers=auth_headers).status_code == 404
    assert db.session.get(Notification, other_id) is not None


def test_notify_all_active_skips_the_actor(db, seeded_db, other_member):
    notify_all_active("info", "Neu", "x", skip_member_id=seeded_db["admin"].id)
    db.session.commit()

    assert {n.member_id for n in db.session.query(Notification).all()} == {other_member.id}


def test_long_text_is_shortened_to_fit(db, seeded_db):
    """A prefixed title ("New vote: " + a 255-character question) is longer
    than the column; Postgres would refuse it and fail the vote."""
    db.session.query(Notification).delete()
    notify_member(seeded_db["admin"].id, "info", "New vote: " + "x" * 255, "y" * 300)
    db.session.commit()

    n = db.session.query(Notification).one()
    assert len(n.title) == 255 and n.title.endswith("…")
    assert len(n.msg) == 255


def test_notifications_need_a_sign_in(client):
    assert client.get("/api/v1/notifications/").status_code == 401
