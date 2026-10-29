"""Tests for invoice generation tasks (generate_invoices_task).

From test_s06_finance.py — task-level tests for automatic invoice creation.
"""

from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import select


def test_generate_invoices_creates_for_billable_member(app, billable_tier_db):
    """Task creates an Open invoice for an active member with a monthly billable tier."""
    from hubra.core.tasks.finance_tasks import generate_invoices_task
    from hubra.core.models.finance import Invoice
    from hubra.core.extensions import db

    with app.app_context():
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            result = generate_invoices_task.run()
        assert result["created"] >= 1

        invoices = db.session.scalars(
            select(Invoice).where(
                Invoice.member_id == billable_tier_db["member_billed"].id
            )
        ).all()
        assert len(invoices) == 1
        inv = invoices[0]
        assert inv.status == "Open"
        assert float(inv.amount) == 99.0
        assert inv.due == inv.issued + timedelta(days=30)


def test_generate_invoices_creates_pending_transaction(app, billable_tier_db):
    """Task creates a Pending income transaction linked to the invoice."""
    from hubra.core.tasks.finance_tasks import generate_invoices_task
    from hubra.core.models.finance import Invoice, Transaction, TransactionCategory
    from hubra.core.extensions import db

    with app.app_context():
        cat = TransactionCategory(name="Membership", color="#00aaff")
        db.session.add(cat)
        db.session.commit()

        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            result = generate_invoices_task.run()
        assert result["created"] >= 1

        invoice = db.session.scalars(
            select(Invoice).where(
                Invoice.member_id == billable_tier_db["member_billed"].id
            )
        ).one()
        assert invoice.transaction_id is not None

        tx = db.session.get(Transaction, invoice.transaction_id)
        assert tx is not None
        assert tx.status == "Pending"
        assert tx.type == "income"
        assert tx.method == "IBAN"
        assert float(tx.amount) == 99.0
        assert tx.member_id == billable_tier_db["member_billed"].id
        assert tx.description == f"Invoice #{invoice.id}"
        assert tx.category_id == cat.id


def test_generate_invoices_skips_member_without_tier(app, billable_tier_db):
    """Task skips member with no tier."""
    from hubra.core.tasks.finance_tasks import generate_invoices_task
    from hubra.core.models.finance import Invoice
    from hubra.core.extensions import db

    with app.app_context():
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            generate_invoices_task.run()
        invoices = db.session.scalars(
            select(Invoice).where(
                Invoice.member_id == billable_tier_db["member_free"].id
            )
        ).all()
        assert len(invoices) == 0


def test_generate_invoices_is_idempotent(app, billable_tier_db):
    """Running the task twice does not create duplicate invoices for the same period."""
    from hubra.core.tasks.finance_tasks import generate_invoices_task
    from hubra.core.models.finance import Invoice
    from hubra.core.extensions import db

    with app.app_context():
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            generate_invoices_task.run()
            result2 = generate_invoices_task.run()
        assert result2["created"] == 0

        count = len(
            db.session.scalars(
                select(Invoice).where(
                    Invoice.member_id == billable_tier_db["member_billed"].id
                )
            ).all()
        )
        assert count == 1


def test_generate_invoices_skips_a_period_already_paid(app, billable_tier_db):
    """The task runs every day: a member who paid this period's invoice is
    not billed again the next morning."""
    from hubra.core.tasks.finance_tasks import generate_invoices_task
    from hubra.core.models.finance import Invoice
    from hubra.core.extensions import db

    member_id = billable_tier_db["member_billed"].id
    with app.app_context():
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            generate_invoices_task.run()
            invoice = db.session.scalars(
                select(Invoice).where(Invoice.member_id == member_id)
            ).one()
            for status in ("Paid", "Overdue"):
                invoice.status = status
                db.session.commit()
                assert generate_invoices_task.run()["created"] == 0

        assert (
            len(
                db.session.scalars(
                    select(Invoice).where(Invoice.member_id == member_id)
                ).all()
            )
            == 1
        )


def test_generate_invoices_ignores_other_open_invoices(app, billable_tier_db):
    """An open invoice for something else (an event, a key deposit) does not
    stand in for the membership fee."""
    from datetime import date

    from hubra.core.tasks.finance_tasks import generate_invoices_task
    from hubra.core.models.finance import Invoice
    from hubra.core.extensions import db

    member_id = billable_tier_db["member_billed"].id
    with app.app_context():
        db.session.add(
            Invoice(
                member_id=member_id,
                issued=date.today(),
                due=date.today() + timedelta(days=30),
                amount=20,
                status="Open",
                purpose="other",
                description="Workshop",
            )
        )
        db.session.commit()
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
            generate_invoices_task.run()
        purposes = sorted(
            db.session.scalars(
                select(Invoice.purpose).where(Invoice.member_id == member_id)
            ).all()
        )
        assert purposes == ["membership", "other"]


def test_generate_invoices_email_args_are_json_serialisable(app, billable_tier_db):
    """The QR-bill PDF travels through Celery's JSON serializer as base64."""
    import base64
    import json

    from hubra.core.tasks.finance_tasks import generate_invoices_task

    with app.app_context():
        with (
            patch(
                "hubra.core.services.qr_bill.generate_invoice_pdf",
                return_value=b"%PDF-1.7 test",
            ),
            patch("hubra.core.tasks.email_tasks.send_email_task.delay") as delay,
        ):
            generate_invoices_task.run()

        kwargs = delay.call_args.kwargs
        json.dumps(kwargs)
        assert base64.b64decode(kwargs["attachments"][0]["content"]) == b"%PDF-1.7 test"


def test_generated_invoice_mail_has_subject_and_bodies_in_place(app, billable_tier_db):
    from hubra.core.tasks.finance_tasks import generate_invoices_task

    with app.app_context():
        with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as delay:
            generate_invoices_task.run()

        kwargs = delay.call_args.kwargs
        assert "<" not in kwargs["subject"] and "\n" not in kwargs["subject"]
        assert "<html" in kwargs["body_html"].lower()
        assert "<html" not in kwargs["body_text"].lower()
        assert kwargs["body_text"] != kwargs["subject"]


def test_bulk_invoices_leave_out_inactive_members(app, billable_tier_db):
    from sqlalchemy import select

    from hubra.api.finance.services import InvoicesService
    from hubra.core.extensions import db
    from hubra.core.models.finance import Invoice

    with app.app_context():
        member = billable_tier_db["member_billed"]
        member.status = "inactive"
        db.session.commit()
        try:
            InvoicesService.bulk_create({"due": "2099-01-31"}, actor_id=member.id)
        except Exception:
            db.session.rollback()  # "no active members" is fine too
        billed = db.session.scalars(
            select(Invoice).where(Invoice.member_id == member.id)
        ).all()
        assert billed == []
