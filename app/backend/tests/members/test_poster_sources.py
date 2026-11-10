"""Join and trial posters: the QR link carries a source tag, the request to
join or trial booking keeps it, and the club sees sign-ups per tag."""

from __future__ import annotations

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.application import Application, SignupSource
from hubra.core.models.event import TrialSignup
from hubra.core.services.signup_source import clean, summary
from tests.events.test_trials import _book, anon, club, mails, training  # noqa: F401
from tests.tenant.test_join_club import _club, _signup


def test_tags_are_cleaned():
    assert clean(" Plakat Bahnhof! ") == "plakat-bahnhof"
    assert clean("x" * 60) == "x" * 40
    assert clean("") is None and clean(None) is None and clean("!!!") is None


def test_a_join_request_keeps_its_poster(client, db):
    _club(db, "chess-zug", "Chess Zug")
    _signup(client, "asker@test.ch", name="Ada Asker")
    resp = client.post(
        "/api/v1/system/clubs/chess-zug/join", json={"source": "Plakat Migros"}
    )
    assert resp.status_code == 201
    app = db.session.scalar(
        select(Application).where(Application.email == "asker@test.ch")
    )
    assert app.source == "plakat-migros"
    assert db.session.scalar(select(SignupSource.kind)) == "join"


def test_a_trial_booking_keeps_its_poster(anon, training, mails):  # noqa: F811
    resp = _book(anon, training.id, source="flyer-schule")
    assert resp.status_code == 201
    signup = db.session.scalar(select(TrialSignup))
    assert signup.source == "flyer-schule"
    assert summary() == [{"source": "flyer-schule", "join": 0, "trial": 1}]


def test_the_poster_link_and_the_counts(client, auth_headers, seeded_db):
    db.session.add_all(
        [
            SignupSource(kind="join", source="a4-bahnhof"),
            SignupSource(kind="trial", source="a4-bahnhof"),
            SignupSource(kind="join", source="a6-flyer"),
        ]
    )
    db.session.commit()
    from unittest.mock import patch

    from hubra.core.models.tenant import Tenant

    tenant = Tenant(
        name="Poster Club", slug="poster-club", plan="starter", status="active"
    )
    db.session.add(tenant)
    db.session.commit()
    with patch("hubra.core.tenant.context.current_tenant", return_value=tenant):
        resp = client.get(
            "/api/v1/applications/poster?kind=trial&source=A4 Bahnhof",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["url"].endswith("/clubs/poster-club/trial?src=a4-bahnhof")
    assert "<svg" in body["qrSvg"]
    assert body["club"]["name"] == "Poster Club"
    assert (
        client.get(
            "/api/v1/applications/poster?kind=nope", headers=auth_headers
        ).status_code
        == 400
    )
    rows = client.get("/api/v1/applications/sources", headers=auth_headers).get_json()
    assert rows[0] == {"source": "a4-bahnhof", "join": 1, "trial": 1}
    assert rows[1]["source"] == "a6-flyer"


def test_posters_need_sign_in(client, seeded_db):
    assert client.get("/api/v1/applications/poster").status_code == 401
    assert client.get("/api/v1/applications/sources").status_code == 401
