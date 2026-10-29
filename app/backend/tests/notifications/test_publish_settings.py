"""Clubs can switch off the "new post/event/poll" notifications per module."""

from unittest.mock import patch

import pytest


@pytest.mark.parametrize("setting, expected", [({}, 1), ({"notify_members": False}, 0)])
def test_notify_on_publish_follows_the_module_setting(app, setting, expected):
    from hubra.api.notifications import services

    with (
        app.app_context(),
        patch("hubra.core.modules.get_config", return_value=setting) as cfg,
        patch.object(services, "notify_all_active") as notify,
    ):
        services.notify_on_publish("posts", "info", "New post", "Hello")
    cfg.assert_called_once_with("posts")
    assert notify.call_count == expected


def test_new_post_without_notifications(client, auth_headers, seeded_db):
    from hubra.core.extensions import db
    from hubra.core.models.notification import Notification

    before = db.session.query(Notification).count()
    with patch("hubra.core.modules.get_config", return_value={"notify_members": False}):
        resp = client.post(
            "/api/v1/posts/",
            json={"title": "Quiet", "body": "Nobody gets told"},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    assert db.session.query(Notification).count() == before
