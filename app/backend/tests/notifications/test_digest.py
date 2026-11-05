"""The weekly digest mail (digest_tasks)."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from hubra.core.models.post import Post
from hubra.core.models.poll import PollVote
from hubra.core.tasks import digest_tasks
from tests.notifications.test_reminders import (  # noqa: F401  (mail_texts: autouse)
    NOW,
    ZURICH,
    _event,
    _member,
    _poll,
    _sign_up,
    mail_texts,
)


@pytest.fixture
def run(db):
    def _run(now=NOW):
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as mail:
            result = digest_tasks._send_weekly_digests(now=now)
            db.session.commit()
        return result, mail

    return _run


def _mails(mail):
    return {c.kwargs["to_email"]: c.kwargs for c in mail.call_args_list}


def _week(db):
    """An event tomorrow, one next month, a post from yesterday, one from
    last month, and an open poll."""
    local = NOW.astimezone(ZURICH)
    soon = _event(db, local + timedelta(days=1), title="Trainingsabend")
    _event(db, local + timedelta(days=30), title="Generalversammlung")
    author = _member(db, "author@example.com")
    db.session.add_all(
        [
            Post(
                author_id=author.id,
                title="Neue Trikots",
                body="x",
                summary="Ab sofort im Clubhaus",
                created_at=NOW - timedelta(days=1),
            ),
            Post(
                author_id=author.id,
                title="Alter Beitrag",
                body="x",
                created_at=NOW - timedelta(days=30),
            ),
        ]
    )
    poll = _poll(db, NOW + timedelta(days=3), question="Neues Vereinslokal?")
    db.session.flush()
    return soon, poll


def test_digest_goes_to_those_who_turned_it_on_once_a_week(db, seeded_db, run):
    soon, poll = _week(db)
    anna = _member(db, "anna@example.com", weekly_digest_mail=True)
    _member(db, "ben@example.com")  # did not turn it on
    _member(db, "cleo@example.com", weekly_digest_mail=True, verified=False)
    _sign_up(db, soon, anna)
    db.session.commit()

    result, mail = run()
    mails = _mails(mail)
    assert list(mails) == ["anna@example.com"]
    text = mails["anna@example.com"]["body_text"]
    assert "Trainingsabend" in text and "du bist angemeldet" in text
    assert "Generalversammlung" not in text  # more than a week away
    assert "Neue Trikots" in text and "Ab sofort im Clubhaus" in text
    assert "Alter Beitrag" not in text
    assert "Neues Vereinslokal?" in text
    assert "Deine Woche" in mails["anna@example.com"]["subject"]
    assert result["mailed"] == 1

    # The next hourly run the same Monday sends nothing again.
    _result, mail = run(NOW + timedelta(hours=1))
    assert mail.call_count == 0
    # A week later it goes out again (with that week's news).
    db.session.add(
        Post(
            author_id=anna.id,
            title="Saisonstart",
            body="x",
            created_at=NOW + timedelta(days=6),
        )
    )
    db.session.commit()
    _result, mail = run(NOW + timedelta(days=7))
    assert list(_mails(mail)) == ["anna@example.com"]


def test_digest_only_on_monday_morning_club_time(db, seeded_db, run):
    _week(db)
    _member(db, "anna@example.com", weekly_digest_mail=True)
    db.session.commit()
    # Monday 06:30 in Zurich: too early.
    early = NOW.replace(hour=5, minute=30)
    _result, mail = run(early)
    assert mail.call_count == 0
    # Tuesday: not the day (the member has never had one, but it waits).
    _result, mail = run(NOW + timedelta(days=1))
    assert mail.call_count == 0
    _result, mail = run()
    assert mail.call_count == 1


def test_digest_lists_only_polls_the_member_can_still_vote_in(db, seeded_db, run):
    _soon, poll = _week(db)
    anna = _member(db, "anna@example.com", weekly_digest_mail=True)
    db.session.add(
        PollVote(poll_id=poll.id, member_id=anna.id, option_id=poll.options[0].id)
    )
    db.session.commit()
    _result, mail = run()
    assert "Neues Vereinslokal?" not in _mails(mail)["anna@example.com"]["body_text"]


def test_nothing_to_tell_no_mail(db, seeded_db, run):
    _member(db, "anna@example.com", weekly_digest_mail=True)
    db.session.commit()
    result, mail = run()
    assert mail.call_count == 0 and result["empty"] == 1


def test_digest_in_english(db, seeded_db, run):
    _week(db)
    anna = _member(db, "anna@example.com", weekly_digest_mail=True)
    db.session.get(type(anna), anna.id).user.language = "en-GB"
    db.session.commit()
    _result, mail = run()
    sent = _mails(mail)["anna@example.com"]
    assert "Your week" in sent["subject"]
    assert "Events in the next 7 days" in sent["body_text"]
    assert "mail.email" not in sent["body_html"]


def test_member_turns_the_digest_on(client, auth_headers):
    assert client.get("/api/v1/members/me/notifications").get_json()["digest"] is False
    resp = client.put("/api/v1/members/me/notifications", json={"digest": True})
    assert resp.status_code == 200 and resp.get_json()["digest"] is True
    resp = client.put(
        "/api/v1/members/me/notifications",
        json={"digest": False, "posts": {"push": False}},
    )
    body = resp.get_json()
    assert body["digest"] is False and body["topics"]["posts"]["push"] is False
    assert (
        client.put(
            "/api/v1/members/me/notifications", json={"digest": "yes"}
        ).status_code
        == 422
    )
