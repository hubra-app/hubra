"""The club's finance settings: payment term, invoice emails and reminders."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select


def _config(**values):
    """Patch the finance module settings the way a club admin saves them."""
    return patch("hubra.core.modules.get_config", return_value=values)


def test_defaults_match_the_old_fixed_values(app):
    from hubra.api.finance.services import billing_settings

    with app.app_context(), _config():
        assert billing_settings() == {
            "payment_term_days": 30,
            "email_new_invoices": True,
            "reminders_enabled": True,
            "first_reminder_days": 7,
            "second_reminder_days": 14,
        }


def test_second_reminder_never_comes_before_the_first(app):
    from hubra.api.finance.services import billing_settings

    with app.app_context(), _config(first_reminder_days=20, second_reminder_days=5):
        s = billing_settings()
    assert s["first_reminder_days"] == 20
    assert s["second_reminder_days"] == 20


def test_generated_invoices_use_the_payment_term(app, billable_tier_db):
    from hubra.core.extensions import db
    from hubra.core.models.finance import Invoice
    from hubra.core.tasks.finance_tasks import generate_invoices_task

    with app.app_context(), _config(payment_term_days=10):
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            generate_invoices_task.run()
        inv = db.session.scalars(
            select(Invoice).where(
                Invoice.member_id == billable_tier_db["member_billed"].id
            )
        ).one()
        assert inv.due == inv.issued + timedelta(days=10)


def test_no_invoice_email_when_switched_off(app, billable_tier_db):
    from hubra.core.tasks.finance_tasks import generate_invoices_task

    with app.app_context(), _config(email_new_invoices=False):
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as send:
            result = generate_invoices_task.run()
    assert result["created"] >= 1
    send.assert_not_called()


@pytest.fixture
def overdue_invoice(db, billable_tier_db):
    from hubra.core.models.finance import Invoice

    # Reminders only go to a verified address.
    billable_tier_db["member_billed"].private_email_verified = True
    inv = Invoice(
        member_id=billable_tier_db["member_billed"].id,
        issued=date.today() - timedelta(days=40),
        due=date.today() - timedelta(days=10),
        amount=Decimal("99.00"),
        status="Open",
        purpose="membership",
    )
    db.session.add(inv)
    db.session.commit()
    return inv


def test_reminders_follow_the_configured_days(app, overdue_invoice):
    from hubra.core.tasks.finance_tasks import send_overdue_reminders_task

    # 10 days overdue: not yet with a first reminder after 12 days ...
    with app.app_context(), _config(first_reminder_days=12, second_reminder_days=20):
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            result = send_overdue_reminders_task.run()
    assert result["overdue_7d"] == 0 and result["overdue_14d"] == 0

    # ... and the second round already with a second reminder after 9.
    with app.app_context(), _config(first_reminder_days=3, second_reminder_days=9):
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            result = send_overdue_reminders_task.run()
    assert result["overdue_14d"] == 1


def test_no_reminders_when_switched_off(app, overdue_invoice):
    from hubra.core.tasks.finance_tasks import send_overdue_reminders_task

    with app.app_context(), _config(reminders_enabled=False):
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as send:
            result = send_overdue_reminders_task.run()
    assert result == {"overdue_7d": 0, "overdue_14d": 0, "skipped_no_email": 0}
    send.assert_not_called()


def test_bulk_invoices_without_a_date_use_the_term(app, billable_tier_db):
    from hubra.api.finance.services import InvoicesService

    with app.app_context(), _config(payment_term_days=21):
        created = InvoicesService.bulk_create({}, billable_tier_db["member_billed"].id)
    assert created
    assert all(inv.due == date.today() + timedelta(days=21) for inv in created)
