"""Attendance per event date and the overview per group and per member."""

from datetime import datetime, timezone

from hubra.core.extensions import db
from hubra.core.models.group import Group, GroupMembership
from hubra.core.models.member import Member, member_groups

from tests.authz.conftest import _create_member_with_role, _login_member
from tests.helpers import add_member


def _group(name, member_ids, joined=None):
    group = Group(name=name)
    db.session.add(group)
    db.session.flush()
    if member_ids:
        db.session.execute(
            member_groups.insert(),
            [{"member_id": m, "group_id": group.id} for m in member_ids],
        )
    for m, day in (joined or {}).items():
        db.session.add(
            GroupMembership(
                group_id=group.id,
                member_id=m,
                joined_at=datetime.fromisoformat(day).replace(tzinfo=timezone.utc),
            )
        )
    db.session.commit()
    return group


def _member(client, headers, first, last, **extra):
    return add_member(
        client,
        headers,
        email=f"{first.lower()}@test.ch",
        first_name=first,
        last_name=last,
        **extra,
    ).get_json()["id"]


def _training_series(client, headers, group_id):
    resp = client.post(
        "/api/v1/events/",
        json={
            "title": "Training U12",
            "date": "2030-01-01",
            "type": "Workshop",
            "group_id": group_id,
            "recurrence": {"until": "2030-01-22"},
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    return client.get(
        "/api/v1/events/?from=2030-01-01&to=2030-01-31", headers=headers
    ).get_json()


def _roll(client, headers, event_id, entries):
    return client.put(
        f"/api/v1/events/{event_id}/attendance",
        json={"entries": [{"member_id": m, "status": s} for m, s in entries]},
        headers=headers,
    )


def test_roll_lists_the_group_and_saves(client, auth_headers, seeded_db):
    anna = _member(client, auth_headers, "Anna", "Muster")
    ben = _member(client, auth_headers, "Ben", "Beispiel")
    group = _group("U12", [anna, ben])
    events = _training_series(client, auth_headers, group.id)
    assert [e["group_id"] for e in events] == [group.id] * 4

    roll = client.get(
        f"/api/v1/events/{events[0]['id']}/attendance", headers=auth_headers
    ).get_json()
    assert [(r["member_name"], r["status"]) for r in roll] == [
        ("Anna Muster", None),
        ("Ben Beispiel", None),
    ]

    resp = _roll(client, auth_headers, events[0]["id"], [(anna, "present"), (ben, "excused")])
    assert resp.status_code == 200
    assert {r["member_id"]: r["status"] for r in resp.get_json()} == {
        anna: "present",
        ben: "excused",
    }
    # Clearing one.
    resp = _roll(client, auth_headers, events[0]["id"], [(ben, None)])
    assert {r["member_id"]: r["status"] for r in resp.get_json()} == {
        anna: "present",
        ben: None,
    }
    assert _roll(client, auth_headers, events[0]["id"], [(anna, "late")]).status_code == 400


def test_present_marks_the_sign_up_attended(client, auth_headers, seeded_db):
    anna = _member(client, auth_headers, "Anna", "Muster")
    event = client.post(
        "/api/v1/events/",
        json={"title": "Match", "date": "2030-02-01", "type": "Social"},
        headers=auth_headers,
    ).get_json()
    client.post(f"/api/v1/events/{event['id']}/register/{anna}", json={}, headers=auth_headers)

    _roll(client, auth_headers, event["id"], [(anna, "present")])
    regs = client.get(f"/api/v1/events/{event['id']}/registrations", headers=auth_headers).get_json()
    assert regs[0]["status"] == "attended"
    _roll(client, auth_headers, event["id"], [(anna, "absent")])
    regs = client.get(f"/api/v1/events/{event['id']}/registrations", headers=auth_headers).get_json()
    assert regs[0]["status"] == "registered"

    # The older single endpoint records attendance too.
    resp = client.post(f"/api/v1/events/{event['id']}/attend/{anna}", headers=auth_headers)
    assert resp.status_code == 200
    roll = client.get(f"/api/v1/events/{event['id']}/attendance", headers=auth_headers).get_json()
    assert roll[0]["status"] == "present"


def test_overview_counts_and_csv(client, auth_headers, seeded_db):
    anna = _member(client, auth_headers, "Anna", "Muster", birthday="2018-05-04")
    ben = _member(client, auth_headers, "Ben", "Beispiel")
    # Ben joined the team for the third training.
    group = _group("U12", [anna, ben], joined={ben: "2030-01-15"})
    events = _training_series(client, auth_headers, group.id)
    ids = [e["id"] for e in events]
    _roll(client, auth_headers, ids[0], [(anna, "present")])
    _roll(client, auth_headers, ids[1], [(anna, "excused")])
    _roll(client, auth_headers, ids[2], [(anna, "present"), (ben, "present")])
    # Fourth: nobody recorded; both count as absent.

    data = client.get(
        f"/api/v1/events/attendance?from=2030-01-01&to=2030-01-31&group_id={group.id}",
        headers=auth_headers,
    ).get_json()
    assert [e["id"] for e in data["events"]] == ids
    rows = {r["member_id"]: r for r in data["members"]}
    assert (rows[anna]["present"], rows[anna]["excused"], rows[anna]["absent"], rows[anna]["expected"]) == (2, 1, 1, 4)
    assert rows[anna]["rate"] == 0.5
    # Not expected before he joined.
    assert (rows[ben]["present"], rows[ben]["expected"]) == (1, 2)
    assert set(rows[ben]["statuses"]) == {str(ids[2]), str(ids[3])}
    assert data["total"]["expected"] == 6

    resp = client.get(
        f"/api/v1/events/attendance?from=2030-01-01&to=2030-01-31&group_id={group.id}&format=csv",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    lines = resp.get_data(as_text=True).lstrip("﻿").splitlines()
    assert lines[0] == (
        "Nachname;Vorname;Geburtsdatum;01.01.2030;08.01.2030;15.01.2030;22.01.2030;"
        "Anwesend;Entschuldigt;Abwesend;Erwartet;Quote %"
    )
    assert lines[1] == "Beispiel;Ben;;;;1;0;1;0;1;2;50"
    assert lines[2] == "Muster;Anna;04.05.2018;1;E;1;0;2;1;1;4;50"


def test_member_history(client, auth_headers, seeded_db):
    anna = _member(client, auth_headers, "Anna", "Muster")
    group = _group("U12", [anna])
    events = _training_series(client, auth_headers, group.id)
    _roll(client, auth_headers, events[0]["id"], [(anna, "present")])
    data = client.get(
        f"/api/v1/events/attendance/members/{anna}?from=2030-01-01&to=2030-01-31",
        headers=auth_headers,
    ).get_json()
    assert [d["status"] for d in data["events"]] == ["present", "absent", "absent", "absent"]
    assert data["rate"] == 0.25


def test_own_history_and_rights(client, db, auth_headers, seeded_db):
    tier = seeded_db["tier"]
    kid, _ = _create_member_with_role(
        "kid@test.ch", "Kid", tier.id, permission_keys=["events.events.read"]
    )
    group = _group("U12", [kid.id])
    events = _training_series(client, auth_headers, group.id)
    _roll(client, auth_headers, events[0]["id"], [(kid.id, "present")])

    _login_member(client, "kid@test.ch")
    mine = client.get("/api/v1/events/attendance/me?from=2030-01-01&to=2030-01-31").get_json()
    assert mine["present"] == 1 and mine["expected"] == 4
    assert client.get("/api/v1/events/attendance").status_code == 403
    assert client.get(f"/api/v1/events/{events[0]['id']}/attendance").status_code == 403


def test_trainer_of_one_group(client, db, seeded_db):
    tier = seeded_db["tier"]
    _, trainer_role = _create_member_with_role(
        "someone@test.ch",
        "Trainer",
        tier.id,
        permission_keys=["events.events.read", "events.events.add_attendee"],
    )
    trainer, _ = _create_member_with_role("trainer@test.ch", "Plain", tier.id)
    u12 = _group("U12", [])
    u14 = _group("U14", [])

    _login_member(client, "admin@test.ch")
    resp = client.post(
        f"/api/v1/roles/{trainer_role.id}/scopes",
        json={"member_id": trainer.id, "group_id": u12.id},
    )
    assert resp.status_code == 201
    mine = _training_series(client, None, u12.id)
    other = client.post(
        "/api/v1/events/",
        json={"title": "U14", "date": "2030-01-02", "type": "Workshop", "group_id": u14.id},
    ).get_json()

    _login_member(client, "trainer@test.ch")
    assert client.get(f"/api/v1/events/{mine[0]['id']}/attendance").status_code == 200
    assert client.put(
        f"/api/v1/events/{mine[0]['id']}/attendance", json={"entries": []}
    ).status_code == 200
    assert client.get(f"/api/v1/events/attendance/groups/{u12.id}").status_code == 200
    assert client.get(f"/api/v1/events/{other['id']}/attendance").status_code == 403
    assert client.get(f"/api/v1/events/attendance/groups/{u14.id}").status_code == 403
    assert client.get("/api/v1/events/attendance").status_code == 403


def test_unknown_group_is_refused(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/events/",
        json={"title": "T", "date": "2030-01-01", "type": "Workshop", "group_id": 999},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert db.session.query(Member).count() >= 1
