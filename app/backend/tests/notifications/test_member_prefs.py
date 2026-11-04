"""Members choose which notifications they get: per topic, bell, push and
(for reminders) mail."""

from unittest.mock import patch

from hubra.core.notifications import prefs
from hubra.core.notifications.services import notify_all_active, notify_member
from hubra.core.models.notification import Notification
from hubra.core.models.push_subscription import PushSubscription

URL = "/api/v1/members/me/notifications"


def _count(db, member_id):
    return db.session.query(Notification).filter_by(member_id=member_id).count()


def test_everything_is_on_by_default(client, auth_headers):
    topics = client.get(URL, headers=auth_headers).get_json()["topics"]
    assert set(topics) == set(prefs.TOPICS)
    assert topics["posts"] == {"bell": True, "push": True}
    assert topics["event_reminders"] == {"bell": True, "push": True, "mail": True}


def test_change_and_keep_the_rest(client, auth_headers, db, seeded_db):
    resp = client.put(
        URL,
        json={"posts": {"push": False}, "poll_reminders": {"mail": False}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    topics = resp.get_json()["topics"]
    assert topics["posts"] == {"bell": True, "push": False}
    assert topics["poll_reminders"]["mail"] is False
    member = seeded_db["admin"]
    db.session.refresh(member)
    assert member.notify_prefs == {"posts": {"push": False}}
    assert member.poll_reminder_mail is False

    # Back on: nothing stored.
    client.put(URL, json={"posts": {"push": True}}, headers=auth_headers)
    db.session.refresh(member)
    assert member.notify_prefs is None


def test_bad_bodies(client, auth_headers):
    for body in (
        {},
        {"nope": {"bell": False}},
        {"posts": {"mail": False}},  # posts are not mailed
        {"posts": {"bell": "no"}},
        {"posts": True},
    ):
        assert client.put(URL, json=body, headers=auth_headers).status_code == 422


def test_bell_off_means_no_notification(db, seeded_db):
    member = seeded_db["admin"]
    member.notify_prefs = {"polls": {"bell": False}, "my_events": {"bell": False}}
    db.session.commit()
    before = _count(db, member.id)

    notify_all_active("info", "New poll", "Q?", topic="polls")
    notify_member(member.id, "info", "Sign-up declined", "Fest", topic="my_events")
    db.session.commit()
    assert _count(db, member.id) == before

    notify_all_active("info", "New post", "Hi", topic="posts")
    notify_member(member.id, "warning", "New device login", "Firefox")  # no topic
    db.session.commit()
    assert _count(db, member.id) == before + 2


def test_push_off_keeps_the_bell(db, seeded_db):
    from hubra.core.services import platform_settings

    platform_settings.web_push(create=True)
    db.session.add(
        PushSubscription(
            user_id=seeded_db["user"].id,
            endpoint="https://fcm.googleapis.com/fcm/send/x",
            p256dh="p",
            auth="a",
        )
    )
    member = seeded_db["admin"]
    member.notify_prefs = {"posts": {"push": False}}
    db.session.commit()
    with patch("hubra.core.tasks.push_tasks.send_push_task.delay") as delay:
        notify_member(member.id, "info", "New post", "Hi", topic="posts")
        db.session.commit()
        assert delay.call_count == 0
        notify_member(member.id, "info", "New event", "Fest", topic="events")
        db.session.commit()
        assert delay.call_count == 1
    assert _count(db, member.id) >= 2


def test_new_posts_events_polls_use_their_module_as_topic(app):
    from hubra.core.notifications import services

    with (
        app.app_context(),
        patch("hubra.core.modules.get_config", return_value={}),
        patch.object(services, "notify_all_active") as notify,
    ):
        services.notify_on_publish("events", "info", "New event", "Fest")
    assert notify.call_args.kwargs["topic"] == "events"
