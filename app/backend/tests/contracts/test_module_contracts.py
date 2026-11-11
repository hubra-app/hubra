"""What Events, Polls, Groups and Finance offer plugins through contracts, in
place of their services (hubra/api/*/contracts.py)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from hubra.core.contracts import SYSTEM, Refused, call, query
from hubra.core.errors import ApiError
from hubra.core.extensions import db as _db


def _event(**kw):
    from hubra.core.models.event import ClubEvent

    row = ClubEvent(
        title=kw.pop("title", "Training"),
        date=kw.pop("date", date.today() + timedelta(days=3)),
        time=kw.pop("time", "19:00-21:00"),
        type="Social",
        **kw,
    )
    _db.session.add(row)
    _db.session.commit()
    return row


def _poll(seeded_db):
    return call(
        "polls.poll.create",
        question="Grill?",
        options=[{"label": "Ja"}, {"label": "Nein"}],
        actor_id=seeded_db["admin"].id,
        actor=SYSTEM,
    )


def test_a_refused_call_is_an_api_error():
    exc = Refused("taken", code="KEY_TAKEN")
    assert isinstance(exc, ApiError)
    assert (exc.status, exc.code, exc.message) == (409, "KEY_TAKEN", "taken")


def test_event_get_has_times_and_places(app, seeded_db):
    event = _event(max_attendees=5)
    call(
        "events.registration.set",
        event_id=event.id,
        member_id=seeded_db["admin"].id,
        status="registered",
        actor=SYSTEM,
    )
    info = query("events.event.get", event_id=event.id, actor=SYSTEM)
    assert info["places_taken"] == 1 and info["maybe"] == 0
    assert info["starts_at"].endswith("19:00:00")
    assert info["ends_at"].endswith("21:00:00")


def test_registration_set_signs_up_maybe_and_off(app, seeded_db):
    event = _event()
    me = seeded_db["admin"].id
    args = {"event_id": event.id, "member_id": me, "actor": SYSTEM}
    assert call("events.registration.set", status="registered", **args)["status"] == (
        "registered"
    )
    with pytest.raises(Refused) as exc:
        call("events.registration.set", status="registered", **args)
    assert exc.value.code == "CONFLICT"
    assert call("events.registration.set", status="maybe", **args)["status"] == "maybe"
    assert call("events.registration.set", status="cancelled", **args)["status"] == (
        "cancelled"
    )


def test_registration_closes_with_the_deadline(app, seeded_db):
    event = _event(date=date.today() - timedelta(days=1))
    with pytest.raises(Refused) as exc:
        call(
            "events.registration.set",
            event_id=event.id,
            member_id=seeded_db["admin"].id,
            status="registered",
            actor=SYSTEM,
        )
    assert exc.value.code == "REGISTRATION_CLOSED"


def test_event_create_checks_like_the_form(app, seeded_db):
    made = call(
        "events.event.create",
        title="Grillabend",
        date=(date.today() + timedelta(days=7)).isoformat(),
        type="Social",
        time="18:00",
        actor_id=seeded_db["admin"].id,
        actor=SYSTEM,
    )
    assert made["title"] == "Grillabend"
    with pytest.raises(Refused) as exc:
        call(
            "events.event.create",
            title="",
            date=date.today().isoformat(),
            type="Social",
            actor=SYSTEM,
        )
    assert exc.value.code == "VALIDATION_ERROR" and exc.value.status == 400


def test_attendance_set(app, seeded_db):
    from hubra.core.models.event import EventAttendance

    event = _event()
    me = seeded_db["admin"].id
    call(
        "events.attendance.set",
        event_id=event.id,
        member_id=me,
        status="present",
        actor_id=me,
        actor=SYSTEM,
    )
    row = _db.session.query(EventAttendance).filter_by(event_id=event.id).one()
    assert row.status == "present" and row.marked_by == me


def test_poll_create_get_and_vote(app, seeded_db):
    poll = _poll(seeded_db)
    me = seeded_db["admin"].id
    info = query("polls.poll.get", poll_id=poll["id"], actor=SYSTEM)
    assert info["closed"] is False and info["question"] == "Grill?"
    call(
        "polls.poll.vote",
        poll_id=poll["id"],
        member_id=me,
        option_index=1,
        actor=SYSTEM,
    )
    assert (
        query("polls.proxies.held", poll_id=poll["id"], member_id=me, actor=SYSTEM)
        == []
    )


def test_voting_on_a_closed_poll_is_refused(app, seeded_db):
    from hubra.core.models.poll import Poll

    poll = _poll(seeded_db)
    _db.session.get(Poll, poll["id"]).status = "closed"
    _db.session.commit()
    assert query("polls.poll.get", poll_id=poll["id"], actor=SYSTEM)["closed"] is True
    with pytest.raises(Refused) as exc:
        call(
            "polls.poll.vote",
            poll_id=poll["id"],
            member_id=seeded_db["admin"].id,
            option_index=0,
            actor=SYSTEM,
        )
    assert exc.value.code == "CONFLICT"


def test_self_join_lists_joins_and_leaves(app, seeded_db):
    from hubra.core.models.group import Group

    group = Group(name="Lauftreff", visibility="open")
    _db.session.add(group)
    _db.session.commit()
    me = seeded_db["admin"].id
    listed = query("groups.self_join.list", member_id=me, actor=SYSTEM)
    assert [(g["name"], g["joined"]) for g in listed] == [("Lauftreff", False)]
    call(
        "groups.self_join.set",
        group_id=group.id,
        member_id=me,
        joined=True,
        actor=SYSTEM,
    )
    listed = query("groups.self_join.list", member_id=me, actor=SYSTEM)
    assert listed[0]["joined"] is True and listed[0]["member_count"] == 1
    call(
        "groups.self_join.set",
        group_id=group.id,
        member_id=me,
        joined=False,
        actor=SYSTEM,
    )


def test_invoice_create_and_delete(app, seeded_db):
    from hubra.core.models.finance import Invoice

    me = seeded_db["admin"].id
    made = call(
        "finance.invoice.create",
        member_id=me,
        issued=date.today(),
        due=date.today() + timedelta(days=30),
        amount=Decimal("25.50"),
        description="Buchung Werkstatt",
        actor_id=me,
        actor=SYSTEM,
    )
    invoice = _db.session.get(Invoice, made["id"])
    assert invoice.amount == Decimal("25.50") and invoice.purpose == "other"
    call("finance.invoice.delete", invoice_id=made["id"], actor_id=me, actor=SYSTEM)
    assert _db.session.get(Invoice, made["id"]) is None


def test_invoice_create_refuses_an_unknown_member(app, seeded_db):
    with pytest.raises(Refused) as exc:
        call(
            "finance.invoice.create",
            member_id=99999,
            issued=date.today(),
            due=date.today(),
            amount=Decimal("1"),
            actor=SYSTEM,
        )
    assert exc.value.code == "NOT_FOUND" and exc.value.status == 404


def test_external_party_save_creates_then_updates(app, seeded_db):
    from hubra.core.models.external_party import ExternalParty

    made = call(
        "finance.external_party.save", name="Bäckerei", email="b@x.ch", actor=SYSTEM
    )
    assert made["created"] is True
    party = _db.session.get(ExternalParty, made["id"])
    assert party.address_country == "CH"
    again = call(
        "finance.external_party.save",
        external_party_id=made["id"],
        name="Bäckerei Huber",
        email="b@x.ch",
        actor=SYSTEM,
    )
    assert again == {"id": made["id"], "name": "Bäckerei Huber", "created": False}


def test_set_status_with_book_announces_an_unbooked_invoice(app, seeded_db):
    from unittest.mock import patch

    me = seeded_db["admin"].id
    made = call(
        "finance.invoice.create",
        member_id=me,
        issued=date.today(),
        due=date.today(),
        amount=Decimal("10"),
        actor=SYSTEM,
    )
    with patch("hubra.api.finance.services._link_pending_transaction") as link:
        call(
            "finance.invoice.set_status",
            invoice_id=made["id"],
            status="Paid",
            book=True,
            actor=SYSTEM,
        )
    assert link.call_count == 1


def test_badge_lookup_finds_the_member_in_this_club(app, seeded_db):
    from hubra.core.services import member_badge

    admin = seeded_db["admin"]
    code = member_badge.ensure_code(admin.user)
    for typed in (
        code,
        code.lower(),
        code.replace("-", ""),
        code[3:].replace("-", " "),
    ):
        found = query("members.badge.lookup", code=typed, actor=SYSTEM)
        assert found == {"member_id": admin.id}


def test_badge_lookup_refuses_unknown_numbers(app, seeded_db):
    for code in ("HB-0000-0000", "nonsense", ""):
        with pytest.raises(Refused) as exc:
            query("members.badge.lookup", code=code, actor=SYSTEM)
        assert exc.value.code == "NOT_FOUND"


def test_transaction_create_books_an_expense(app, seeded_db):
    from sqlalchemy import select

    from hubra.core.models.audit import AuditEntry
    from hubra.core.models.finance import Transaction

    me = seeded_db["admin"].id
    made = call(
        "finance.transaction.create",
        date=date.today(),
        description="Spesen: Kreide",
        amount=Decimal("23.50"),
        type="expense",
        method="Cash",
        member_id=me,
        actor_id=me,
        actor=SYSTEM,
    )
    tx = _db.session.get(Transaction, made["id"])
    assert tx.amount == Decimal("-23.50") and tx.type == "expense"
    assert _db.session.scalar(
        select(AuditEntry).where(
            AuditEntry.action == "create_transaction", AuditEntry.target_id == tx.id
        )
    )


def test_transaction_create_refuses_bad_input(app, seeded_db):
    with pytest.raises(Refused):
        call(
            "finance.transaction.create",
            date=date.today(),
            description="x",
            amount=Decimal("5"),
            type="expense",
            method="Cash",
            member_id=99999,
            actor=SYSTEM,
        )
    with pytest.raises((Refused, ApiError, ValueError)):
        call(
            "finance.transaction.create",
            date=date.today(),
            description="x",
            amount=Decimal("-5"),
            type="expense",
            method="Cash",
            actor=SYSTEM,
        )
