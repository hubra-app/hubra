"""The bell gets the newest notifications, not every one ever sent; the
unread count still counts them all."""

from unittest.mock import patch

from hubra.api.notifications.services import notify_member
from hubra.core.models.notification import Notification


def test_list_is_capped_and_unread_counts_all(client, auth_headers, db, seeded_db):
    db.session.query(Notification).delete()  # the sign-in's "new device" note
    for i in range(7):
        notify_member(seeded_db["admin"].id, "info", f"Note {i}", "x")
    db.session.commit()

    with patch("hubra.api.notifications.services.LIST_LIMIT", 5):
        body = client.get("/api/v1/notifications/", headers=auth_headers).get_json()
    assert [n["title"] for n in body["data"]] == [f"Note {i}" for i in range(6, 1, -1)]
    assert body["meta"]["unread"] == 7
