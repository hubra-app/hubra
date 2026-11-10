"""One calendar feed for every club of an account (sso › My account)."""

from __future__ import annotations

from datetime import date, timedelta

from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent, EventRegistration
from tests.members.test_leave_club import H, _login, club  # noqa: F401

URL = "/api/v1/global/account/calendar"


def _events(anna_id: int) -> None:
    soon = date.today() + timedelta(days=7)
    mine = ClubEvent(title="Training", date=soon, type="Workshop")
    other = ClubEvent(title="Vorstandssitzung", date=soon, type="Workshop")
    db.session.add_all([mine, other])
    db.session.flush()
    db.session.add(EventRegistration(event_id=mine.id, member_id=anna_id))
    db.session.commit()


def _path(url: str) -> str:
    return "/" + url.split("://", 1)[1].split("/", 1)[1]


def test_the_feed_has_every_club_and_only_mine_on_request(client, club):  # noqa: F811
    _events(club["anna"].id)
    _login(client, "anna@test.ch")
    urls = client.get(URL).get_json()
    assert set(urls) == {"all", "mine"}

    everything = client.get(_path(urls["all"]))
    assert everything.status_code == 200
    assert everything.mimetype == "text/calendar"
    body = everything.get_data(as_text=True)
    assert "SUMMARY:Training · Club A" in body
    assert "Vorstandssitzung" in body
    assert "@club-a.hubra" in body

    mine = client.get(_path(urls["mine"])).get_data(as_text=True)
    assert "Training" in mine and "Vorstandssitzung" not in mine


def test_renewing_stops_the_old_url(client, club):  # noqa: F811
    _login(client, "anna@test.ch")
    old = client.get(URL).get_json()["all"]
    new = client.post(f"{URL}/renew").get_json()["all"]
    assert old != new
    assert client.get(_path(old)).status_code == 404
    assert client.get(_path(new)).status_code == 200


def test_a_forged_token_is_unknown(client, club):  # noqa: F811
    assert client.get(f"{URL}/nonsense.ics").status_code == 404


def test_the_urls_need_sign_in(client, club):  # noqa: F811
    assert client.get(URL).status_code == 401
    assert client.post(f"{URL}/renew").status_code == 401
