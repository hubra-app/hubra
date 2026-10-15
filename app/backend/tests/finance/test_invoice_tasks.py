"""Tests for invoice generation tasks (generate_invoices_task).

From test_s06_finance.py — task-level tests for automatic invoice creation.
"""

from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import select


def test_generate_invoices_creates_for_billable_member(app, billable_tier_db):
    """Task creates an Open invoice for an active member with a monthly billable tier."""
    from vollbuild.core.tasks.finance_tasks import generate_invoices_task
    from vollbuild.core.models.finance import Invoice
    from vollbuild.core.extensions import db

    with app.app_context():
        with patch("vollbuild.core.tasks.email_tasks.send_email_task.delay"):
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
    from vollbuild.core.tasks.finance_tasks import generate_invoices_task
    from vollbuild.core.models.finance import Invoice, Transaction, TransactionCategory
    from vollbuild.core.extensions import db

    with app.app_context():
        cat = TransactionCategory(name="Membership", color="#00aaff")
        db.session.add(cat)
        db.session.commit()

        with patch("vollbuild.core.tasks.email_tasks.send_email_task.delay"):
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
    from vollbuild.core.tasks.finance_tasks import generate_invoices_task
    from vollbuild.core.models.finance import Invoice
    from vollbuild.core.extensions import db

    with app.app_context():
        with patch("vollbuild.core.tasks.email_tasks.send_email_task.delay"):
            generate_invoices_task.run()
        invoices = db.session.scalars(
            select(Invoice).where(
                Invoice.member_id == billable_tier_db["member_free"].id
            )
        ).all()
        assert len(invoices) == 0


def test_generate_invoices_is_idempotent(app, billable_tier_db):
    """Running the task twice does not create duplicate invoices for the same period."""
    from vollbuild.core.tasks.finance_tasks import generate_invoices_task
    from vollbuild.core.models.finance import Invoice
    from vollbuild.core.extensions import db

    with app.app_context():
        with patch("vollbuild.core.tasks.email_tasks.send_email_task.delay"):
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
