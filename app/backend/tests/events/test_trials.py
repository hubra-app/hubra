"""Trial trainings: the public trial page, the mail link, and the trainers' list."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent, TrialSignup
from tests.authz.conftest import permissioned_member_factory  # noqa: F401, F811

SLUG = "trial-club"
BASE = f"/api/v1/events/public/{SLUG}/trials"


@pytest.fixture
def club(db, seeded_db):
    from hubra.core.models.tenant import Tenant

    tenant = Tenant(name="Trial Club", slug=SLUG, plan="starter", status="active")
    db.session.add(tenant)
    db.session.commit()
    yield tenant
    db.session.delete(tenant)
    db.session.commit()


@pytest.fixture
def training(db, club):
    soon = date.today() + timedelta(days=4)
    event = ClubEvent(
        title="Training U14",
        date=soon,
        time="18:00-19:30",
        type="Workshop",
        location="Halle Nord",
        trial_spots=2,
    )
    db.session.add_all(
        [
            event,
            ClubEvent(title="Board meeting", date=soon, type="Meeting"),
            ClubEvent(
                title="Old training",
                date=date.today() - timedelta(days=3),
                type="Workshop",
                trial_spots=5,
            ),
        ]
    )
    db.session.commit()
    return event


@pytest.fixture
def anon(client):
    client.environ_base.pop("HTTP_AUTHORIZATION", None)
    return client


@pytest.fixture
def mails():
    sent = []
    with patch(
        "hubra.core.services.email._send",
        side_effect=lambda to, name, subject, html, text, *a, **k: (
            sent.append({"to": to, "subject": subject, "text": text}) or True
        ),
    ):
        yield sent


def _book(client, event_id, email="lea@example.ch", **extra):
    body = {
        "eventId": event_id,
        "firstName": "Lea",
        "lastName": "Muster",
        "email": email,
        "consent": True,
        **extra,
    }
    return client.post(BASE, json=body, headers={"Authorization": ""})


def _token(mail):
    return mail["text"].split("token=")[1].split()[0]


def test_trial_page_lists_open_trainings_only(anon, training):
    resp = anon.get(BASE, headers={"Authorization": ""})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["club"]["name"] == "Trial Club"
    assert [(e["title"], e["free"]) for e in body["events"]] == [("Training U14", 2)]
    assert "trial_spots" not in body["events"][0]


def test_book_confirm_and_cancel(anon, training, mails):
    resp = _book(anon, training.id, phone="079 123 45 67", birthDate="2012-03-04")
    assert resp.status_code == 201
    assert len(mails) == 1 and mails[0]["to"] == "lea@example.ch"
    assert f"/clubs/{SLUG}/trial?token=" in mails[0]["text"]
    signup = db.session.query(TrialSignup).one()
    assert signup.status == "pending" and signup.birth_date == date(2012, 3, 4)

    token = _token(mails[0])
    resp = anon.post(
        f"{BASE}/confirm", json={"token": token}, headers={"Authorization": ""}
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "confirmed"
    assert resp.get_json()["event"]["free"] == 1

    resp = anon.post(
        f"{BASE}/cancel", json={"token": token}, headers={"Authorization": ""}
    )
    assert resp.get_json()["status"] == "cancelled"
    assert resp.get_json()["event"]["free"] == 2
    assert (
        anon.post(
            f"{BASE}/confirm", json={"token": "nope"}, headers={"Authorization": ""}
        ).status_code
        == 404
    )


def test_validation_full_and_duplicates(anon, training, mails):
    assert _book(anon, training.id, consent=False).status_code == 400
    assert _book(anon, training.id, email="not-an-address").status_code == 400
    assert _book(anon, training.id, birthDate="2999-01-01").status_code == 400
    meeting = db.session.query(ClubEvent).filter_by(title="Board meeting").one()
    assert _book(anon, meeting.id).status_code == 404

    assert _book(anon, training.id).status_code == 201
    # The same address again: the mail goes out again, no second booking.
    assert _book(anon, training.id).status_code == 201
    assert db.session.query(TrialSignup).count() == 1 and len(mails) == 2
    assert _book(anon, training.id, email="tom@example.ch").status_code == 201
    resp = _book(anon, training.id, email="max@example.ch")
    assert resp.status_code == 409 and resp.get_json()["error"] == "EVENT_FULL"

    # An unconfirmed booking frees its place after a day.
    db.session.query(TrialSignup).update(
        {"created_at": datetime.now(timezone.utc) - timedelta(hours=25)}
    )
    db.session.commit()
    assert _book(anon, training.id, email="max@example.ch").status_code == 201


def test_booking_again_tells_nothing_about_the_address(anon, training, mails):
    """A second booking with a known address answers like a new one: the
    form can't be used to find out who booked a training."""
    assert _book(anon, training.id).status_code == 201
    token = _token(mails[0])
    anon.post(f"{BASE}/confirm", json={"token": token}, headers={"Authorization": ""})

    again = _book(anon, training.id)
    assert again.status_code == 201 and again.get_json() == {"status": "pending"}
    # The person gets their link again (it also cancels), no second booking.
    assert len(mails) == 2 and _token(mails[1]) == token
    assert db.session.query(TrialSignup).count() == 1

    db.session.query(TrialSignup).update({"status": "attended"})
    db.session.commit()
    again = _book(anon, training.id)
    assert again.status_code == 201 and again.get_json() == {"status": "pending"}
    assert len(mails) == 2


def test_booking_mails_are_limited_per_address(app):
    from hubra.api.events.trials import _address_key

    with app.test_request_context(json={"email": " Lea@Example.CH "}):
        assert _address_key() == "trial-mail:lea@example.ch"
    with app.test_request_context(data="not json"):
        assert _address_key() == "trial-mail:"


def test_honeypot_stores_nothing(anon, training, mails):
    assert _book(anon, training.id, website="http://spam").status_code == 201
    assert db.session.query(TrialSignup).count() == 0 and mails == []


def _confirmed(anon, training, mails, email="lea@example.ch"):
    _book(anon, training.id, email=email)
    anon.post(
        f"{BASE}/confirm",
        json={"token": _token(mails[-1])},
        headers={"Authorization": ""},
    )
    return db.session.query(TrialSignup).filter_by(email=email).one()


def test_trainer_list_attended_and_invite(client, auth_headers, training, mails, club):
    signup = _confirmed(client, training, mails)
    _book(client, training.id, email="ghost@example.ch")  # never confirmed

    resp = client.get("/api/v1/events/trials", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert [t["email"] for t in body["trials"]] == ["lea@example.ch"]
    assert body["events"][0]["spots"] == 2 and body["events"][0]["taken"] == 2

    resp = client.patch(
        f"/api/v1/events/trials/{signup.id}",
        json={"status": "attended"},
        headers=auth_headers,
    )
    assert resp.status_code == 200 and resp.get_json()["status"] == "attended"

    with (
        patch("hubra.core.tenant.context.current_tenant", return_value=club),
        patch("hubra.core.tenant.invites.send_invite") as send,
    ):
        send.return_value.id = 1
        resp = client.post(
            f"/api/v1/events/trials/{signup.id}/invite", headers=auth_headers
        )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "invited"
    member_data = send.call_args.kwargs["member_data"]
    assert (
        member_data["status"] == "trial" and member_data["membership_type"] == "trial"
    )
    again = client.post(
        f"/api/v1/events/trials/{signup.id}/invite", headers=auth_headers
    )
    assert again.status_code == 409

    assert (
        client.delete(
            f"/api/v1/events/trials/{signup.id}", headers=auth_headers
        ).status_code
        == 204
    )
    assert db.session.get(TrialSignup, signup.id) is None


def test_trainers_need_the_permission(
    client,
    training,
    mails,
    permissioned_member_factory,  # noqa: F811
):
    signup = _confirmed(client, training, mails)
    plain = permissioned_member_factory(["events.events.read"])
    assert client.get("/api/v1/events/trials", headers=plain).status_code == 403
    reader = permissioned_member_factory(["events.trials.read"])
    assert client.get("/api/v1/events/trials", headers=reader).status_code == 200
    assert (
        client.patch(
            f"/api/v1/events/trials/{signup.id}",
            json={"status": "no_show"},
            headers=reader,
        ).status_code
        == 403
    )


def test_inviting_needs_the_members_right(
    client,
    training,
    mails,
    club,
    permissioned_member_factory,  # noqa: F811
):
    signup = _confirmed(client, training, mails)
    trainer = permissioned_member_factory(
        ["events.trials.read", "events.trials.manage"]
    )
    url = f"/api/v1/events/trials/{signup.id}/invite"
    with patch("hubra.core.tenant.invites.send_invite") as send:
        resp = client.post(url, headers=trainer)
        assert resp.status_code == 403
        send.assert_not_called()
    assert db.session.get(TrialSignup, signup.id).status != "invited"

    both = permissioned_member_factory(
        ["events.trials.read", "events.trials.manage", "members.members.create"]
    )
    with (
        patch("hubra.core.tenant.context.current_tenant", return_value=club),
        patch("hubra.core.tenant.invites.send_invite") as send,
    ):
        send.return_value.id = 1
        resp = client.post(url, headers=both)
    assert resp.status_code == 200 and resp.get_json()["status"] == "invited"


def test_staff_get_a_notification(client, auth_headers, training, mails):
    from hubra.core.models.notification import Notification

    _confirmed(client, training, mails)
    titles = [n.title for n in db.session.query(Notification).all()]
    assert "Trial training: Lea Muster" in titles


def test_trial_spots_on_events(client, auth_headers):
    resp = client.post(
        "/api/v1/events/",
        json={
            "title": "Probetraining",
            "date": "2030-02-01",
            "type": "Workshop",
            "trial_spots": 3,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201 and resp.get_json()["trial_spots"] == 3
    event_id = resp.get_json()["id"]
    resp = client.patch(
        f"/api/v1/events/{event_id}", json={"trial_spots": None}, headers=auth_headers
    )
    assert resp.status_code == 200 and resp.get_json()["trial_spots"] is None
    assert (
        client.patch(
            f"/api/v1/events/{event_id}", json={"trial_spots": 0}, headers=auth_headers
        ).status_code
        == 400
    )


def test_late_confirm_does_not_overbook(anon, training, mails):
    """A booking confirmed after its hold ran out only counts if a place is
    still free; the places others took in the meantime stay theirs."""
    _book(anon, training.id)
    late = _token(mails[-1])
    db.session.query(TrialSignup).update(
        {"created_at": datetime.now(timezone.utc) - timedelta(hours=25)}
    )
    db.session.commit()
    _confirmed(anon, training, mails, email="tom@example.ch")
    _confirmed(anon, training, mails, email="max@example.ch")

    resp = anon.post(
        f"{BASE}/confirm", json={"token": late}, headers={"Authorization": ""}
    )
    assert resp.status_code == 409 and resp.get_json()["error"] == "EVENT_FULL"
    signup = db.session.query(TrialSignup).filter_by(email="lea@example.ch").one()
    assert signup.status == "pending"


def test_late_confirm_with_a_free_place(anon, training, mails):
    _book(anon, training.id)
    db.session.query(TrialSignup).update(
        {"created_at": datetime.now(timezone.utc) - timedelta(hours=25)}
    )
    db.session.commit()
    resp = anon.post(
        f"{BASE}/confirm",
        json={"token": _token(mails[-1])},
        headers={"Authorization": ""},
    )
    assert resp.status_code == 200 and resp.get_json()["status"] == "confirmed"


def test_invited_keeps_the_place(anon, training, mails):
    from hubra.api.events.trials import places_taken

    signup = _confirmed(anon, training, mails)
    signup.status = "invited"
    db.session.commit()
    assert places_taken(training.id) == 1


def test_listing_deletes_nothing_the_daily_job_does(
    client, auth_headers, training, mails
):
    from hubra.core.tasks.reminder_tasks import purge_trial_signups

    old = db.session.query(ClubEvent).filter_by(title="Old training").one()
    old.date = date.today() - timedelta(days=200)
    db.session.add(
        TrialSignup(
            event_id=old.id,
            first_name="Ada",
            last_name="Alt",
            email="ada@example.ch",
            token="old-token",
            status="attended",
        )
    )
    db.session.commit()
    assert (
        client.get("/api/v1/events/trials?past=1", headers=auth_headers).status_code
        == 200
    )
    assert db.session.query(TrialSignup).filter_by(email="ada@example.ch").count() == 1
    assert purge_trial_signups() == 1
    db.session.commit()
    assert db.session.query(TrialSignup).filter_by(email="ada@example.ch").count() == 0
