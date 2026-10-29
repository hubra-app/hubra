"""An archived member gives up their place at upcoming events (the waiting
list moves up) and their proxies in open polls."""

from sqlalchemy import select

from tests.events.test_m5_events import _create_event, _create_member


def test_archive_frees_event_place_and_proxies(client, auth_headers, seeded_db):
    from hubra.core.extensions import db
    from hubra.core.models.event import EventRegistration
    from hubra.core.models.poll import PollProxy

    event_id = _create_event(
        client, auth_headers, title="Kurs", max_attendees=1
    ).get_json()["id"]
    leaving, waiting = (
        _create_member(client, auth_headers, email=f"a{i}@test.ch").get_json()["id"]
        for i in range(2)
    )
    for member_id in (leaving, waiting):
        client.post(
            f"/api/v1/events/{event_id}/register/{member_id}", json={}, headers=auth_headers
        )
    poll_id = client.post(
        "/api/v1/polls/",
        json={"question": "Q?", "options": [{"label": "A"}, {"label": "B"}], "allow_proxy": True},
        headers=auth_headers,
    ).get_json()["id"]
    db.session.add(PollProxy(poll_id=poll_id, grantor_id=waiting, holder_id=leaving))
    db.session.commit()

    resp = client.post(f"/api/v1/members/{leaving}/archive", json={}, headers=auth_headers)
    assert resp.status_code in (200, 204)

    statuses = dict(
        db.session.execute(
            select(EventRegistration.member_id, EventRegistration.status).where(
                EventRegistration.event_id == event_id
            )
        ).all()
    )
    assert statuses == {leaving: "cancelled", waiting: "registered"}
    assert db.session.scalars(select(PollProxy)).all() == []
