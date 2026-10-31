"""Reminders before an event starts and before a poll closes (reminder_tasks)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from hubra.core.models.event import ClubEvent, EventRegistration
from hubra.core.models.member import Member
from hubra.core.models.notification import Notification
from hubra.core.models.poll import Poll, PollOption, PollProxy, PollVote
from hubra.core.models.user import User
from hubra.core.tasks import reminder_tasks

ZURICH = ZoneInfo("Europe/Zurich")
# A fixed "now" in UTC: Monday 2 November 2026, 10:00 in Zurich.
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
LONG_AGO = NOW - timedelta(days=7)


@pytest.fixture(autouse=True)
def mail_texts(db):
    """The shipped mail texts (tests start with an empty translation table)."""
    import json
    from pathlib import Path

    from hubra.core.models.translation import Translation

    seed = Path(reminder_tasks.__file__).parents[1] / "seed_data" / "translations"
    for locale in ("de-CH", "en-GB"):
        texts = json.loads((seed / f"{locale}.json").read_text())
        for key, value in texts.items():
            if key.startswith("mail.email."):
                db.session.add(Translation(locale=locale, key=key, value=value))
    db.session.commit()


@pytest.fixture
def run(db):
    def _run(job, config=None):
        with patch(
            "hubra.core.tasks.email_tasks.send_email_task.delay"
        ) as mail, patch.object(reminder_tasks, "emit") as emit, patch.object(
            reminder_tasks, "get_config", return_value=config or {}
        ):
            result = job(now=NOW)
            db.session.commit()
        return result, mail, emit

    return _run


def _member(db, email, *, verified=True, **fields):
    user = User(
        email=email, first_name=email.split("@")[0], last_name="Test",
        private_email_verified=verified,
    )
    user.set_password("Member-Pass-123!")
    db.session.add(user)
    db.session.flush()
    member = Member(user_id=user.id, status=fields.pop("status", "active"), **fields)
    db.session.add(member)
    db.session.flush()
    return member


def _event(db, start_local: datetime, *, created=LONG_AGO, **fields):
    event = ClubEvent(
        title=fields.pop("title", "Trainingsabend"),
        date=start_local.date(),
        time=fields.pop("time", f"{start_local:%H:%M}-22:00"),
        type="Meeting",
        created_at=created,
        **fields,
    )
    db.session.add(event)
    db.session.flush()
    return event


def _sign_up(db, event, member, status="registered"):
    db.session.add(EventRegistration(event_id=event.id, member_id=member.id, status=status))
    db.session.flush()


def _poll(db, closes_at: datetime, *, created=LONG_AGO, **fields):
    poll = Poll(question=fields.pop("question", "Neues Vereinslokal?"),
                closes_at=closes_at, created_at=created, **fields)
    db.session.add(poll)
    db.session.flush()
    db.session.add_all([PollOption(poll_id=poll.id, label="Ja"), PollOption(poll_id=poll.id, label="Nein")])
    db.session.flush()
    return poll


def _mailed_to(mail):
    return sorted(c.kwargs["to_email"] for c in mail.call_args_list)


def _bell(db, member):
    return [n.title for n in db.session.query(Notification).filter_by(member_id=member.id)]


# ── Events ────────────────────────────────────────────────────────────────────


def test_event_reminder_goes_to_those_signed_up_once(db, seeded_db, run):
    tomorrow = datetime(2026, 11, 3, 19, 0, tzinfo=ZURICH)  # 33 h ahead
    soon = datetime(2026, 11, 3, 8, 0, tzinfo=ZURICH)  # 22 h ahead
    later = _event(db, tomorrow)
    event = _event(db, soon, title="Arbeitstag")
    going = _member(db, "going@test.ch")
    approved = _member(db, "approved@test.ch")
    waiting = _member(db, "waiting@test.ch")
    cancelled = _member(db, "cancelled@test.ch")
    _sign_up(db, event, going)
    _sign_up(db, event, approved, "approved")
    _sign_up(db, event, waiting, "waitlisted")
    _sign_up(db, event, cancelled, "cancelled")
    _sign_up(db, later, going)
    db.session.commit()

    result, mail, emit = run(reminder_tasks._send_event_reminders)

    assert result == {"events": 1, "notified": 2, "mailed": 2}
    assert _mailed_to(mail) == ["approved@test.ch", "going@test.ch"]
    sent = mail.call_args_list[0].kwargs
    assert "Arbeitstag" in sent["subject"]
    assert "03.11.2026, 08:00-22:00" in sent["body_text"]
    assert _bell(db, going) == ["Event reminder"]
    note = db.session.query(Notification).filter_by(member_id=going.id).one()
    assert note.link == f"/app/operations/events?event={event.id}"
    assert _bell(db, waiting) == []
    assert [c.kwargs for c in emit.call_args_list] == [{"event_id": event.id}]
    assert event.reminder_sent_at is not None and later.reminder_sent_at is None

    result, mail, _ = run(reminder_tasks._send_event_reminders)
    assert result["events"] == 0 and mail.call_count == 0


def test_event_reminder_respects_mail_choice_and_verified_address(db, seeded_db, run):
    event = _event(db, datetime(2026, 11, 3, 8, 0, tzinfo=ZURICH))
    opted_out = _member(db, "quiet@test.ch", event_reminder_mail=False)
    unverified = _member(db, "new@test.ch", verified=False)
    archived = _member(db, "gone@test.ch", archived_at=LONG_AGO)
    for m in (opted_out, unverified, archived):
        _sign_up(db, event, m)
    db.session.commit()

    result, mail, _ = run(reminder_tasks._send_event_reminders)

    # The bell for both who can get it, mail for none of them.
    assert result == {"events": 1, "notified": 2, "mailed": 0}
    assert _bell(db, opted_out) == ["Event reminder"]
    assert _bell(db, unverified) == ["Event reminder"]
    assert _bell(db, archived) == []


def test_event_created_inside_the_window_gets_no_reminder(db, seeded_db, run):
    event = _event(db, datetime(2026, 11, 3, 8, 0, tzinfo=ZURICH), created=NOW - timedelta(hours=1))
    _sign_up(db, event, _member(db, "a@test.ch"))
    db.session.commit()

    result, mail, emit = run(reminder_tasks._send_event_reminders)

    assert result["events"] == 0 and mail.call_count == 0 and emit.call_count == 0
    # Marked, so it is not looked at again.
    assert event.reminder_sent_at is not None


def test_all_day_event_counts_as_starting_at_nine(db, seeded_db, run):
    # 9:00 Zurich tomorrow is 23 h ahead; one the day after is not due yet.
    tomorrow = _event(db, datetime(2026, 11, 3, 0, 0, tzinfo=ZURICH), all_day=True, time=None)
    after = _event(db, datetime(2026, 11, 4, 0, 0, tzinfo=ZURICH), all_day=True, time=None)
    member = _member(db, "a@test.ch")
    _sign_up(db, tomorrow, member)
    _sign_up(db, after, member)
    db.session.commit()

    result, mail, _ = run(reminder_tasks._send_event_reminders)

    assert result["events"] == 1
    assert "03.11.2026" in mail.call_args_list[0].kwargs["body_text"]
    assert after.reminder_sent_at is None


def test_event_reminder_hours_setting(db, seeded_db, run):
    event = _event(db, datetime(2026, 11, 4, 8, 0, tzinfo=ZURICH))  # 46 h ahead
    _sign_up(db, event, _member(db, "a@test.ch"))
    db.session.commit()

    assert run(reminder_tasks._send_event_reminders)[0]["events"] == 0
    assert run(reminder_tasks._send_event_reminders, {"reminder_hours": 0})[0]["events"] == 0
    assert run(reminder_tasks._send_event_reminders, {"reminder_hours": 48})[0]["events"] == 1


def test_moving_an_event_resets_its_reminder(client, auth_headers, db, seeded_db):
    event = _event(db, datetime(2026, 11, 3, 8, 0, tzinfo=ZURICH), reminder_sent_at=NOW)
    db.session.commit()

    client.patch(f"/api/v1/events/{event.id}", json={"title": "Neuer Titel"})
    db.session.refresh(event)
    assert event.reminder_sent_at is not None

    resp = client.patch(f"/api/v1/events/{event.id}", json={"time": "10:00-12:00"})
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(event)
    assert event.reminder_sent_at is None


# ── Polls ─────────────────────────────────────────────────────────────────────


def test_poll_reminder_goes_to_those_who_have_not_voted(db, seeded_db, run):
    poll = _poll(db, NOW + timedelta(hours=20))
    voted = _member(db, "voted@test.ch")
    proxy = _member(db, "proxy@test.ch")
    holder = _member(db, "holder@test.ch")
    _member(db, "trial@test.ch", status="trial")
    db.session.add(PollVote(poll_id=poll.id, option_id=poll.options[0].id, member_id=voted.id))
    db.session.add(PollProxy(poll_id=poll.id, grantor_id=proxy.id, holder_id=holder.id))
    db.session.commit()

    result, mail, emit = run(reminder_tasks._send_poll_reminders)

    # The seeded admin and the proxy holder; not who voted, gave a proxy
    # or is no active member.
    assert result == {"polls": 1, "notified": 2, "mailed": 2}
    assert _mailed_to(mail) == ["admin@test.ch", "holder@test.ch"]
    body = mail.call_args_list[0].kwargs["body_text"]
    assert "Neues Vereinslokal?" in body and "03.11.2026, 06:00" in body
    assert _bell(db, voted) == []
    assert [c.kwargs for c in emit.call_args_list] == [{"poll_id": poll.id}]

    result, mail, _ = run(reminder_tasks._send_poll_reminders)
    assert result["polls"] == 0 and mail.call_count == 0


def test_poll_reminder_skips_closed_far_and_fresh_polls(db, seeded_db, run):
    _poll(db, NOW + timedelta(hours=20), status="closed")
    _poll(db, NOW + timedelta(hours=30))
    _poll(db, NOW + timedelta(hours=20), created=NOW - timedelta(hours=1))
    _poll(db, None)
    db.session.commit()

    result, mail, _ = run(reminder_tasks._send_poll_reminders)

    assert result["polls"] == 0 and mail.call_count == 0


def test_poll_with_required_groups_reminds_only_them(db, seeded_db, run):
    from hubra.core.models.group import Group

    asked = _member(db, "board@test.ch")
    _member(db, "other@test.ch", poll_reminder_mail=False)
    group = Group(name="Vorstand")
    group.members = [asked]
    db.session.add(group)
    db.session.flush()
    _poll(db, NOW + timedelta(hours=20), required_group_ids=[group.id])
    db.session.commit()

    result, mail, _ = run(reminder_tasks._send_poll_reminders)

    assert result["notified"] == 1
    assert _mailed_to(mail) == ["board@test.ch"]


def test_changing_the_closing_time_resets_the_reminder(client, auth_headers, db, seeded_db):
    poll = _poll(db, NOW + timedelta(hours=20), reminder_sent_at=NOW)
    db.session.commit()

    client.patch(f"/api/v1/polls/{poll.id}", json={"question": "Anders gefragt?"})
    db.session.refresh(poll)
    assert poll.reminder_sent_at is not None

    resp = client.patch(
        f"/api/v1/polls/{poll.id}", json={"closes_at": "2026-11-10T18:00:00+00:00"}
    )
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(poll)
    assert poll.reminder_sent_at is None


# ── The member's choice ───────────────────────────────────────────────────────


def test_member_switches_reminder_mails(client, auth_headers):
    assert client.get("/api/v1/members/me/reminders").get_json() == {
        "events": True,
        "polls": True,
    }
    resp = client.put("/api/v1/members/me/reminders", json={"polls": False})
    assert resp.get_json() == {"events": True, "polls": False}
    assert client.put("/api/v1/members/me/reminders", json={"polls": "no"}).status_code == 422
    assert client.put("/api/v1/members/me/reminders", json={"other": True}).status_code == 422
    assert client.get("/api/v1/members/me/reminders").get_json()["polls"] is False


def test_reminder_mails_render_in_both_languages(app, db, seeded_db):
    from hubra.core.services.mail_i18n import render_mail_template

    for locale, word in (("de-CH", "abstimmen"), ("en-GB", "vote")):
        html, text, subject = render_mail_template(
            "poll_reminder", locale=locale, name="Anna", club_name="FC Test",
            question="Q?", when="03.11.2026, 06:00", portal_url="https://x/y",
        )
        assert word in subject.lower() and "https://x/y" in html and "Q?" in text
        html, text, subject = render_mail_template(
            "event_reminder", locale=locale, name="Anna", club_name="FC Test",
            event_title="Fest", when="03.11.2026", location="Halle", portal_url="",
        )
        assert "Fest" in subject and "Halle" in text and "mail.email" not in html
