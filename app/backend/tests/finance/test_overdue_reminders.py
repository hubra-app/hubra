"""Tests for the daily overdue reminder job (_send_overdue_reminders)."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from hubra.core.models.finance import Invoice
from hubra.core.models.invoice_reminder import InvoiceReminderHistory


@pytest.fixture
def run(db):
    from hubra.core.tasks import finance_tasks

    def _run():
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as mail, patch.object(
            finance_tasks, "emit"
        ) as emit:
            result = finance_tasks._send_overdue_reminders()
        return result, mail, emit

    return _run


def _invoice(db, member, days_overdue, status="Open", history=()):
    invoice = Invoice(
        member_id=member.id,
        issued=date.today() - timedelta(days=days_overdue + 30),
        due=date.today() - timedelta(days=days_overdue),
        amount=Decimal("50.00"),
        status=status,
    )
    db.session.add(invoice)
    db.session.flush()
    for reminder_type in history:
        db.session.add(
            InvoiceReminderHistory(
                invoice_id=invoice.id,
                reminder_type=reminder_type,
                recipient_email=member.email,
                recipient_name=member.name,
            )
        )
    db.session.commit()
    return invoice


def _types(db, invoice):
    return {
        h.reminder_type
        for h in db.session.query(InvoiceReminderHistory).filter_by(invoice_id=invoice.id)
    }


def test_rounds_are_sent_once(db, seeded_db, run):
    admin = seeded_db["admin"]
    week = _invoice(db, admin, 8, history=["generation"])
    fortnight = _invoice(db, admin, 15, history=["generation", "overdue_7d"])
    fresh = _invoice(db, admin, 3, history=["generation"])

    result, mail, emit = run()

    assert (result["overdue_7d"], result["overdue_14d"]) == (1, 1)
    assert "overdue_7d" in _types(db, week)
    assert "overdue_14d" in _types(db, fortnight)
    assert _types(db, fresh) == {"generation"}
    # Only the first overdue round tells other modules.
    assert [c.kwargs["invoice_id"] for c in emit.call_args_list] == [week.id]

    result, _, _ = run()
    assert (result["overdue_7d"], result["overdue_14d"]) == (0, 0)


def test_straight_to_14_days_still_emits_overdue(db, seeded_db, run):
    """An invoice first seen 14+ days late (job was down, or it was entered
    late) gets the 14-day mail and the overdue event, even though its send
    history already has the generation mail."""
    invoice = _invoice(db, seeded_db["admin"], 20, history=["generation"])

    _, _, emit = run()

    assert _types(db, invoice) == {"generation", "overdue_14d"}
    assert [c.kwargs["invoice_id"] for c in emit.call_args_list] == [invoice.id]


def test_invoices_marked_overdue_are_reminded_paid_are_not(db, seeded_db, run):
    admin = seeded_db["admin"]
    marked = _invoice(db, admin, 8, status="Overdue")
    paid = _invoice(db, admin, 8, status="Paid")

    run()

    assert "overdue_7d" in _types(db, marked)
    assert _types(db, paid) == set()
