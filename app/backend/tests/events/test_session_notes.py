"""Session notes on event dates, shown on the next date of the series
(hubra/api/events/session_notes.py, roadmap idea 13)."""

from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent
from tests.events.test_event_series import _series
from tests.settings.test_settings_kv import _login, _make_role_and_member


def _dates(series_id: int) -> list[int]:
    return [
        e.id
        for e in db.session.query(ClubEvent)
        .filter(ClubEvent.series_id == series_id)
        .order_by(ClubEvent.date)
    ]


def _url(event_id: int) -> str:
    return f"/api/v1/events/{event_id}/session-notes"


def test_the_next_date_shows_the_last_notes(client, auth_headers, seeded_db):
    first = _series(client, auth_headers)
    one, two, three, *_ = _dates(first["series_id"])
    body = {
        "trained": "Passen im Dreieck",
        "trainer_note": "Luca schont das Knie",
        "guide_url": "/app/guides/12",
    }
    resp = client.put(_url(one), json=body, headers=auth_headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["note"]["trained"] == "Passen im Dreieck"
    assert resp.get_json()["previous"] is None

    later = client.get(_url(three), headers=auth_headers).get_json()
    assert later["note"] is None
    assert later["previous"]["date"] == "2030-01-01"
    assert later["previous"]["trainer_note"] == "Luca schont das Knie"
    assert later["can_edit"] is True

    # The second date gets notes: the third shows those now.
    client.put(_url(two), json={"trained": "Torschuss"}, headers=auth_headers)
    later = client.get(_url(three), headers=auth_headers).get_json()
    assert later["previous"]["trained"] == "Torschuss"
    assert later["previous"]["date"] == "2030-01-08"

    # Everything empty removes them.
    client.put(_url(two), json={"trained": " "}, headers=auth_headers)
    assert (
        client.get(_url(three), headers=auth_headers).get_json()["previous"]["date"]
        == "2030-01-01"
    )


def test_bad_links_and_long_texts_are_refused(client, auth_headers, seeded_db):
    first = _series(client, auth_headers)
    url = _url(first["id"])
    for bad in (
        {"guide_url": "javascript:alert(1)"},
        {"guide_url": "//evil.example"},
        {"guide_url": "http://plain.example"},
        {"trained": "x" * 4001},
        {"trained": 5},
    ):
        assert client.put(url, json=bad, headers=auth_headers).status_code == 400
    ok = client.put(
        url, json={"guide_url": "https://example.org/drill"}, headers=auth_headers
    )
    assert ok.status_code == 200


def test_members_read_what_was_trained_not_the_trainer_note(
    client, app, db, auth_headers, seeded_db
):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    first = _series(client, auth_headers)
    one, two, *_ = _dates(first["series_id"])
    client.put(
        _url(one),
        json={"trained": "Passen", "trainer_note": "Privat"},
        headers=auth_headers,
    )
    _make_role_and_member(
        db, seeded_db["tier"], name="Reader", permission_keys=["events.events.read"]
    )
    _login(client, "reader@test.ch")
    seen = client.get(_url(two)).get_json()
    assert seen["previous"]["trained"] == "Passen"
    assert "trainer_note" not in seen["previous"]
    assert seen["can_edit"] is False
    assert client.put(_url(two), json={"trained": "x"}).status_code == 403
    assert app.test_client().get(_url(two)).status_code == 401
