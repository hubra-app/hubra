"""Recurring events: weekly rules, skip dates, and edits of one date or all
following ones."""

from datetime import date

from hubra.api.events.series import rule_dates
from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent, EventAttendance, EventSeries
from hubra.core.models.notification import Notification

from tests.helpers import add_member

# 2030-01-01 is a Tuesday.
TUESDAY = "2030-01-01"


def _series(client, headers, **rule):
    rule.setdefault("until", "2030-01-29")
    resp = client.post(
        "/api/v1/events/",
        json={
            "title": "Training U12",
            "date": TUESDAY,
            "time": "18:00-19:30",
            "type": "Workshop",
            "category": "training",
            "recurrence": rule,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def _dates(series_id):
    return [
        (e.date.isoformat(), e.series_date.isoformat())
        for e in db.session.query(ClubEvent)
        .filter(ClubEvent.series_id == series_id)
        .order_by(ClubEvent.date)
    ]


def test_rule_dates():
    start = date(2030, 1, 1)
    # Tuesdays and Thursdays, every other week, without the 15th.
    assert rule_dates(start, date(2030, 1, 31), [1, 3], 2, ["2030-01-15"]) == [
        date(2030, 1, 1),
        date(2030, 1, 3),
        date(2030, 1, 17),
        date(2030, 1, 29),
        date(2030, 1, 31),
    ]


def test_create_weekly_series(client, auth_headers, seeded_db):
    first = _series(client, auth_headers, skip_dates=["2030-01-15"])
    assert first["series_id"]
    assert first["series_date"] == TUESDAY
    assert first["recurrence"] == {
        "start_date": TUESDAY,
        "until": "2030-01-29",
        "interval": 1,
        "weekdays": [1],
        "skip_dates": ["2030-01-15"],
    }
    assert [d for d, _ in _dates(first["series_id"])] == [
        "2030-01-01",
        "2030-01-08",
        "2030-01-22",
        "2030-01-29",
    ]
    listed = client.get(
        "/api/v1/events/?from=2030-01-01&to=2030-01-31", headers=auth_headers
    ).get_json()
    assert {e["time"] for e in listed} == {"18:00-19:30"}
    assert all(e["series_id"] == first["series_id"] for e in listed)


def test_first_date_moves_to_the_rule(client, auth_headers, seeded_db):
    # Tuesday start, but the rule is Wednesdays.
    first = _series(client, auth_headers, weekdays=[2])
    assert first["date"] == "2030-01-02"
    assert _dates(first["series_id"])[0] == ("2030-01-02", "2030-01-02")


def test_rule_limits(client, auth_headers, seeded_db):
    base = {"title": "T", "date": TUESDAY, "type": "Workshop"}
    for rule in (
        {"until": "2029-12-01"},  # before the first date
        {"until": "2040-01-01"},  # longer than three years
        {"until": "2030-01-02", "weekdays": [4]},  # no date at all
        {"until": "2030-02-01", "weekdays": [9]},
        {"until": "2030-02-01", "interval": 0},
    ):
        resp = client.post(
            "/api/v1/events/", json={**base, "recurrence": rule}, headers=auth_headers
        )
        assert resp.status_code == 400, rule


def test_edit_this_date_only(client, auth_headers, seeded_db):
    first = _series(client, auth_headers)
    events = client.get(
        "/api/v1/events/?from=2030-01-01&to=2030-01-31", headers=auth_headers
    ).get_json()
    second = events[1]
    resp = client.patch(
        f"/api/v1/events/{second['id']}",
        json={"date": "2030-01-09", "location": "Halle B"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["date"] == "2030-01-09"
    # It still stands for the rule's date.
    assert body["series_date"] == "2030-01-08"
    others = [e for e in events if e["id"] != second["id"]]
    for e in others:
        assert client.get(f"/api/v1/events/{e['id']}", headers=auth_headers).get_json()[
            "location"
        ] is None
    assert first["series_id"] == body["series_id"]


def test_edit_all_following(client, auth_headers, seeded_db):
    first = _series(client, auth_headers)
    events = client.get(
        "/api/v1/events/?from=2030-01-01&to=2030-01-31", headers=auth_headers
    ).get_json()
    third = events[2]
    resp = client.patch(
        f"/api/v1/events/{third['id']}?scope=following",
        json={"time": "17:30-19:00", "location": "Halle A"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    after = client.get(
        "/api/v1/events/?from=2030-01-01&to=2030-01-31", headers=auth_headers
    ).get_json()
    assert [e["time"] for e in after] == [
        "18:00-19:30",
        "18:00-19:30",
        "17:30-19:00",
        "17:30-19:00",
        "17:30-19:00",
    ]
    assert first["series_id"] == after[-1]["series_id"]

    # Dates move one at a time, not for the whole series.
    resp = client.patch(
        f"/api/v1/events/{third['id']}?scope=following",
        json={"date": "2030-01-16"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    # A rule change needs the scope.
    resp = client.patch(
        f"/api/v1/events/{third['id']}",
        json={"recurrence": {"until": "2030-02-28"}},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_new_rule_from_a_date_splits_the_series(client, auth_headers, seeded_db):
    first = _series(client, auth_headers)
    events = client.get(
        "/api/v1/events/?from=2030-01-01&to=2030-01-31", headers=auth_headers
    ).get_json()
    third = events[2]  # 2030-01-15
    # Attendance was taken on the 22nd already; that date stays.
    member = add_member(client, auth_headers, email="kid@test.ch").get_json()
    db.session.add(EventAttendance(event_id=events[3]["id"], member_id=member["id"], status="present"))
    db.session.commit()

    resp = client.patch(
        f"/api/v1/events/{third['id']}?scope=following",
        # From now on Thursdays, until mid February.
        json={"recurrence": {"until": "2030-02-14", "weekdays": [3]}},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.get_json()
    old = db.session.get(EventSeries, first["series_id"])
    assert old.until == date(2030, 1, 14)
    assert [d for d, _ in _dates(old.id)] == ["2030-01-01", "2030-01-08"]

    new_id = (
        db.session.query(EventSeries.id)
        .filter(EventSeries.id != old.id)
        .scalar()
    )
    assert [d for d, _ in _dates(new_id)] == [
        "2030-01-17",
        "2030-01-24",
        "2030-01-31",
        "2030-02-07",
        "2030-02-14",
    ]
    # The 22nd had attendance: kept, outside the series.
    kept = db.session.get(ClubEvent, events[3]["id"])
    assert kept is not None and kept.series_id is None
    # The 15th and the 29th are gone.
    assert db.session.get(ClubEvent, third["id"]) is None
    assert db.session.get(ClubEvent, events[4]["id"]) is None


def test_delete_one_date_and_all_following(client, auth_headers, seeded_db):
    first = _series(client, auth_headers)
    events = client.get(
        "/api/v1/events/?from=2030-01-01&to=2030-01-31", headers=auth_headers
    ).get_json()
    assert client.delete(f"/api/v1/events/{events[1]['id']}", headers=auth_headers).status_code == 204
    series = db.session.get(EventSeries, first["series_id"])
    assert series.skip_dates == ["2030-01-08"]

    resp = client.delete(f"/api/v1/events/{events[3]['id']}?scope=following", headers=auth_headers)
    assert resp.status_code == 204
    db.session.expire_all()
    assert [d for d, _ in _dates(series.id)] == ["2030-01-01", "2030-01-15"]
    assert db.session.get(EventSeries, series.id).until == date(2030, 1, 21)

    # Deleting from the first date removes the series.
    resp = client.delete(f"/api/v1/events/{first['id']}?scope=following", headers=auth_headers)
    assert resp.status_code == 204
    assert db.session.get(EventSeries, series.id) is None


def test_series_change_tells_each_member_once(client, auth_headers, seeded_db):
    first = _series(client, auth_headers)
    events = client.get(
        "/api/v1/events/?from=2030-01-01&to=2030-01-31", headers=auth_headers
    ).get_json()
    member = add_member(client, auth_headers, email="parent@test.ch").get_json()
    for e in events:
        resp = client.post(f"/api/v1/events/{e['id']}/register/{member['id']}", json={}, headers=auth_headers)
        assert resp.status_code == 201
    resp = client.patch(
        f"/api/v1/events/{first['id']}?scope=following",
        json={"location": "Neue Halle"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    changed = (
        db.session.query(Notification)
        .filter_by(title="Event changed", member_id=member["id"])
        .count()
    )
    assert changed == 1
