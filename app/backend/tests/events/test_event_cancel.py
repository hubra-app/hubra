"""Calling an event off with a reason, and on again (roadmap idea 12)."""

from unittest.mock import patch

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.notification import Notification
from tests.events.test_m5_events import _create_event, _create_member


def _titles(member_id):
    return db.session.scalars(
        select(Notification.title).where(Notification.member_id == member_id)
    ).all()


def test_cancel_tells_signed_up_and_group_and_keeps_the_event(
    client, auth_headers, seeded_db
):
    from hubra.core.models.group import Group, GroupMembership

    signed = _create_member(client, auth_headers, email="anna@test.ch").get_json()["id"]
    in_group = _create_member(client, auth_headers, email="ben@test.ch").get_json()[
        "id"
    ]
    outsider = _create_member(client, auth_headers, email="cleo@test.ch").get_json()[
        "id"
    ]
    group = Group(name="Juniors")
    db.session.add(group)
    db.session.flush()
    db.session.add(GroupMembership(group_id=group.id, member_id=in_group))
    db.session.commit()

    event_id = _create_event(
        client, auth_headers, title="Training", group_id=group.id
    ).get_json()["id"]
    client.post(
        f"/api/v1/events/{event_id}/register/{signed}", json={}, headers=auth_headers
    )

    with (
        patch("hubra.core.tasks.reminder_tasks._mail", return_value=True) as mail,
        patch("hubra.api.events.services.emit") as emit,
    ):
        resp = client.post(
            f"/api/v1/events/{event_id}/cancel",
            json={"reason": "Platz gesperrt"},
            headers=auth_headers,
        )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["cancelled_at"] is not None
    assert body["cancel_reason"] == "Platz gesperrt"

    assert "Event cancelled" in _titles(signed)
    assert "Event cancelled" in _titles(in_group)
    assert "Event cancelled" not in _titles(outsider)
    # Only those signed up get the mail.
    assert [c.args[0].id for c in mail.call_args_list] == [signed]
    assert mail.call_args.kwargs["reason"] == "Platz gesperrt"
    emit.assert_any_call(
        "event.changed", event_id=event_id, cancelled=True, reason="Platz gesperrt"
    )

    # Still in the calendar, but nobody can sign up any more.
    assert (
        client.get(f"/api/v1/events/{event_id}", headers=auth_headers).status_code
        == 200
    )
    resp = client.post(
        f"/api/v1/events/{event_id}/register/{outsider}", json={}, headers=auth_headers
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "EVENT_CANCELLED"


def test_cancel_needs_a_reason_and_only_once(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers).get_json()["id"]
    url = f"/api/v1/events/{event_id}/cancel"
    assert (
        client.post(url, json={"reason": "  "}, headers=auth_headers).status_code == 400
    )
    assert (
        client.post(url, json={"reason": "x" * 501}, headers=auth_headers).status_code
        == 400
    )
    assert (
        client.post(url, json={"reason": "Regen"}, headers=auth_headers).status_code
        == 200
    )
    assert (
        client.post(url, json={"reason": "Regen"}, headers=auth_headers).status_code
        == 409
    )


def test_reinstate_tells_those_signed_up(client, auth_headers, seeded_db):
    signed = _create_member(client, auth_headers, email="anna@test.ch").get_json()["id"]
    event_id = _create_event(client, auth_headers).get_json()["id"]
    client.post(
        f"/api/v1/events/{event_id}/register/{signed}", json={}, headers=auth_headers
    )
    url = f"/api/v1/events/{event_id}/cancel"
    assert client.delete(url, headers=auth_headers).status_code == 409
    with patch("hubra.core.tasks.reminder_tasks._mail", return_value=True):
        client.post(url, json={"reason": "Regen"}, headers=auth_headers)
    resp = client.delete(url, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["cancelled_at"] is None
    assert resp.get_json()["cancel_reason"] is None
    assert "Event takes place" in _titles(signed)


def test_cancel_needs_sign_in(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers).get_json()["id"]
    client.post("/api/v1/auth/logout")
    client.delete_cookie("access_token_cookie")
    resp = client.post(f"/api/v1/events/{event_id}/cancel", json={"reason": "x"})
    assert resp.status_code == 401


def test_cancel_needs_the_update_right(client, auth_headers, seeded_db):
    _create_member(client, auth_headers, email="anna@test.ch")
    event_id = _create_event(client, auth_headers).get_json()["id"]
    client.post(
        "/api/v1/auth/login",
        json={"email": "anna@test.ch", "password": "Member-Pass-123!"},
    )
    resp = client.post(f"/api/v1/events/{event_id}/cancel", json={"reason": "x"})
    assert resp.status_code == 403
    assert client.delete(f"/api/v1/events/{event_id}/cancel").status_code == 403


def test_cancel_mail_renders_in_both_languages(app, db):
    from pathlib import Path

    import hubra
    from hubra.core.models.translation import Translation
    from hubra.core.seeds import load_shipped_translations
    from hubra.core.services.mail_i18n import render_mail_template

    seeds = Path(hubra.__file__).parent / "core" / "seed_data" / "translations"
    for locale in ("de-CH", "en-GB"):
        texts = load_shipped_translations(seeds, locale)
        for key, value in texts.items():
            if "event_cancelled" in key or "event_reminder" in key:
                db.session.add(Translation(locale=locale, key=key, value=value))
    db.session.commit()

    with app.test_request_context():
        for locale, word in (("de-CH", "Abgesagt"), ("en-GB", "Cancelled")):
            html, text, subject = render_mail_template(
                "event_cancelled",
                locale=locale,
                name="Anna",
                club_name="FC Test",
                event_title="Training",
                when="12.11.2030 18:30",
                location="Halle",
                reason="Platz gesperrt",
                portal_url="https://example.test/app",
            )
            assert word in subject and "Training" in subject
            assert "Platz gesperrt" in html and "Platz gesperrt" in text
