"""An event that started yesterday and ends tomorrow is still on today.

The calendar's `from` filter and the dashboard looked only at the start
date, so a running multi-day event vanished from both.
"""

from datetime import date, timedelta


def _running_event(db):
    from hubra.core.models.event import ClubEvent

    today = date.today()
    event = ClubEvent(
        title="Lager",
        type="Social",
        date=today - timedelta(days=1),
        end_date=today + timedelta(days=1),
    )
    db.session.add(event)
    db.session.commit()
    return event.id


def test_running_event_is_listed_from_today(client, db, auth_headers, seeded_db):
    event_id = _running_event(db)
    resp = client.get(
        f"/api/v1/events/?from={date.today().isoformat()}", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.get_json()
    rows = body["data"] if isinstance(body, dict) else body
    assert event_id in [e["id"] for e in rows]


def test_running_event_is_on_the_dashboard(client, db, auth_headers, seeded_db):
    event_id = _running_event(db)
    body = client.get("/api/v1/dashboard/summary", headers=auth_headers).get_json()
    assert body["stats"]["upcomingEvents"] == 1
    assert [e["id"] for e in body["upcomingEvents"]] == [event_id]
