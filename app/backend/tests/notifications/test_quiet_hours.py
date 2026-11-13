"""Quiet hours: push and direct messages wait until they end
(hubra/core/notifications/quiet.py)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from hubra.core.models.user import User
from hubra.core.notifications import quiet

URL = "/api/v1/account/quiet-hours"
NIGHT = {"from": "22:00", "to": "07:00", "tz": "Europe/Zurich"}


def test_wait_seconds_over_midnight_and_by_day():
    # 23:30 in Zurich (winter, UTC+1) = 22:30 UTC: 7.5 hours to 07:00.
    late = datetime(2026, 1, 10, 22, 30, tzinfo=timezone.utc)
    assert quiet.wait_seconds(NIGHT, late) == 7 * 3600 + 30 * 60
    # 06:00 in Zurich: one hour left.
    early = datetime(2026, 1, 10, 5, 0, tzinfo=timezone.utc)
    assert quiet.wait_seconds(NIGHT, early) == 3600
    # Noon: not quiet.
    assert (
        quiet.wait_seconds(NIGHT, datetime(2026, 1, 10, 11, 0, tzinfo=timezone.utc))
        == 0
    )
    # A window within one day (a siesta).
    siesta = {"from": "12:00", "to": "14:00", "tz": "Europe/Zurich"}
    assert (
        quiet.wait_seconds(siesta, datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc))
        == 3600
    )
    assert quiet.wait_seconds(None, late) == 0


def test_the_account_sets_and_clears_its_quiet_hours(client, db, auth_headers):
    assert client.get(URL, headers=auth_headers).get_json() == {"quiet": None}
    resp = client.put(URL, json={"quiet": NIGHT}, headers=auth_headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["quiet"] == NIGHT
    assert (
        client.put(
            URL, json={"quiet": {"from": "25:00", "to": "07:00"}}, headers=auth_headers
        ).status_code
        == 422
    )
    assert (
        client.put(
            URL, json={"quiet": {"from": "22:00", "to": "22:00"}}, headers=auth_headers
        ).status_code
        == 422
    )
    assert client.put(URL, json={"quiet": None}, headers=auth_headers).get_json() == {
        "quiet": None
    }


def test_quiet_hours_need_a_sign_in(client):
    assert client.get(URL).status_code == 401


def test_a_push_in_quiet_hours_waits_once(db, seeded_db):
    from hubra.core.tasks import push_tasks

    user = db.session.get(User, seeded_db["user"].id)
    quiet.apply(user, NIGHT)
    db.session.commit()
    kwargs = {
        "user_id": user.id,
        "tenant_id": None,
        "notification_id": 1,
        "kind": "info",
        "title": "t",
        "msg": "m",
    }
    with (
        patch.object(quiet, "wait_seconds", return_value=600),
        patch.object(push_tasks.send_push_task, "apply_async") as later,
        patch("hubra.core.notifications.push.deliver") as now,
    ):
        assert push_tasks.send_push_task.run(**kwargs) == {"held": 600}
        later.assert_called_once()
        assert later.call_args.kwargs["countdown"] == 600
        assert later.call_args.kwargs["kwargs"]["held"] is True
        now.assert_not_called()
        # Sent again after the wait: it goes out, whatever the clock says.
        push_tasks.send_push_task.run(**kwargs, held=True)
        now.assert_called_once()
