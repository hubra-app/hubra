"""Finance Celery tasks — periodic invoice generation and overdue reminders."""

from __future__ import annotations

import base64
import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING


from hubra.core.extensions import db
from hubra.core.modules import emit, per_tenant_job
from hubra.core.modules.events import INVOICE_OVERDUE
from hubra.core.tasks import celery_app
from hubra.core.pricing import (
    billing_cycle_for,
    calculate_invoice_amount,
    period_window,
    deductions_by_tier,
)
from hubra.core.services.email import DEFAULT_LANG
from hubra.core.services.mail_i18n import render_mail_template

if TYPE_CHECKING:
    from hubra.core.models.finance import Invoice

logger = logging.getLogger(__name__)


def _render_invoice_generated(
    name: str,
    invoice_id: int,
    amount: float,
    due_date: date,
    portal_url: str,
    *,
    lang: str = DEFAULT_LANG,
) -> tuple[str, str, str]:
    """Render invoice_generated email templates, returning (subject, html, text)."""
    from hubra.core.services.email import club_display_name

    club_name = club_display_name()
    # render_mail_template returns (html, text, subject).
    body_html, body_text, subject = render_mail_template(
        "invoice_generated",
        locale=lang,
        name=name,
        club_name=club_name,
        invoice_id=invoice_id,
        amount_formatted=f"CHF {amount:.2f}",
        due_date=due_date.isoformat(),
        portal_url=portal_url,
    )
    return subject, body_html, body_text


def _render_invoice_reminder(
    name: str,
    invoice_id: int,
    amount: float,
    due_date: date,
    portal_url: str,
    *,
    lang: str = DEFAULT_LANG,
) -> tuple[str, str, str]:
    """Render invoice_reminder email templates, returning (subject, html, text)."""
    from hubra.core.services.email import club_display_name

    club_name = club_display_name()
    # render_mail_template returns (html, text, subject).
    body_html, body_text, subject = render_mail_template(
        "invoice_reminder",
        locale=lang,
        name=name,
        club_name=club_name,
        invoice_id=invoice_id,
        amount_formatted=f"CHF {amount:.2f}",
        due_date=due_date.isoformat(),
        portal_url=portal_url,
    )
    return subject, body_html, body_text


def _dispatch_invoice_email(
    invoice: Invoice,
    member: object,
    subject: str,
    body_html: str,
    body_text: str,
    reminder_type: str,
    attachments: list | None = None,
) -> None:
    """Dispatch invoice email via Celery and record in InvoiceReminderHistory.

    Must be called *after* the invoice has been flushed so it has an ID.

    Email dispatch failures are caught and logged — the InvoiceReminderHistory
    entry is still recorded so the audit trail is complete.
    """
    if not member.email:  # type: ignore[attr-defined]
        _record_reminder_history(
            invoice, member, reminder_type, False, "no email address"
        )
        return

    from hubra.core.tasks.email_tasks import send_email_task

    try:
        send_email_task.delay(
            to_email=member.email,  # type: ignore[attr-defined]
            to_name=member.name,  # type: ignore[attr-defined]
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachments=attachments,
        )
        success = True
        error_message = None
    except Exception as exc:
        logger.warning(
            "invoice_email_dispatch_failed invoice_id=%s error=%s",
            invoice.id,
            exc,
        )
        success = False
        error_message = str(exc)

    _record_reminder_history(invoice, member, reminder_type, success, error_message)


def _record_reminder_history(
    invoice: Invoice,
    member: object,
    reminder_type: str,
    success: bool,
    error_message: str | None,
) -> None:
    """Insert an InvoiceReminderHistory row."""
    from hubra.core.models.invoice_reminder import InvoiceReminderHistory

    history = InvoiceReminderHistory(
        invoice_id=invoice.id,
        reminder_type=reminder_type,
        recipient_email=member.email or "",  # type: ignore[attr-defined]
        recipient_name=member.name,  # type: ignore[attr-defined]
        success=success,
        error_message=error_message,
    )
    db.session.add(history)


@celery_app.task(
    name="hubra.core.tasks.finance_tasks.generate_invoices_task",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def generate_invoices_task(self) -> dict:
    """Generate invoices for every club with finance on (see _generate_invoices)."""
    return _generate_invoices()


@per_tenant_job("finance")
def _generate_invoices() -> dict:
    """Generate invoices for all active members whose tier has a billing cycle.

    Handles three price types:
      - fixed:      price_chf per billing period
      - percentage: percentage_value/100 * baseline per member per year, divided into periods
      - formula:    (baseline - coefficient * sum(deducted_tier_annual_fees)) / members_in_tier
                    per year, divided into periods, rounded up to round_to

    Idempotency guard: skips a member if an Open invoice already exists for the
    current billing period (current month for 'monthly', current year for 'yearly').

    Sends an invoice_generated email for each created invoice and records the
    dispatch in InvoiceReminderHistory.

    Returns a summary dict with counts for created/skipped invoices.
    """
    from sqlalchemy import select
    from hubra.core.models.finance import Invoice
    from hubra.core.models.member import Member, MembershipTier
    from hubra.core.services.email import _get_base_url

    today = date.today()
    created = 0
    skipped = 0
    _base = _get_base_url()
    portal_url = f"{_base}/invoices" if _base else "the member portal"

    active_members: list[Member] = db.session.scalars(  # type: ignore[assignment]
        select(Member)
        .where(Member.status == "active")
        .where(Member.archived_at.is_(None))
        .where(Member.tier_id.isnot(None))
    ).all()

    # Each formula tier deducts the yearly fees of its own deduct_tier_ids.
    deducted_for = deductions_by_tier(db.session)

    # Generate invoices
    for member in active_members:
        tier: MembershipTier | None = member.tier

        if tier is None or not tier.billing_cycle:
            logger.info(
                "invoice_generation_skipped member_id=%s reason=no_billable_tier",
                member.id,
            )
            skipped += 1
            continue

        cycle = billing_cycle_for(member, tier)
        period_start, period_end = period_window(today, cycle)

        existing = db.session.scalar(
            select(Invoice.id)
            .where(Invoice.member_id == member.id)
            .where(Invoice.status == "Open")
            .where(Invoice.issued >= period_start)
            .where(Invoice.issued <= period_end)
        )

        if existing is not None:
            logger.info(
                "invoice_generation_skipped member_id=%s reason=open_invoice_exists_for_period invoice_id=%s",
                member.id,
                existing,
            )
            skipped += 1
            continue

        amount = calculate_invoice_amount(member, tier, deducted_for(tier))
        if amount <= 0:
            logger.info(
                "invoice_generation_skipped member_id=%s reason=amount_zero_or_negative",
                member.id,
            )
            skipped += 1
            continue

        due_date = today + timedelta(days=30)
        invoice = Invoice(
            member_id=member.id,
            issued=today,
            due=due_date,
            amount=amount,
            status="Open",
            purpose="membership",
        )
        db.session.add(invoice)
        db.session.flush()

        from hubra.api.finance.services import _link_pending_transaction

        _link_pending_transaction(invoice, member.id)

        logger.info(
            "invoice_generated member_id=%s tier=%s price_type=%s amount=%s billing_cycle=%s invoice_id=%s",
            member.id,
            tier.name,
            tier.price_type,
            amount,
            cycle,
            invoice.id,
        )
        created += 1

        # Generate QR-bill PDF attachment (best-effort)
        pdf_attachments = None
        try:
            from hubra.core.services.qr_bill import generate_invoice_pdf

            # Celery serialises task args as JSON, so ship the PDF as base64.
            pdf_b64 = base64.b64encode(generate_invoice_pdf(invoice)).decode("ascii")
            pdf_attachments = [
                {"name": f"invoice-{invoice.id}.pdf", "content": pdf_b64}
            ]
        except Exception:
            logger.warning("Failed to generate QR-bill PDF for invoice %s", invoice.id)

        # Dispatch email (async via Celery) and record history
        subject, body_html, body_text = _render_invoice_generated(
            name=member.name,
            invoice_id=invoice.id,
            amount=float(amount),
            due_date=due_date,
            portal_url=portal_url,
            lang=getattr(member, "language", DEFAULT_LANG) or DEFAULT_LANG,
        )
        _dispatch_invoice_email(
            invoice=invoice,
            member=member,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            reminder_type="generation",
            attachments=pdf_attachments,
        )

    db.session.commit()
    logger.info("invoice_generation_complete created=%s skipped=%s", created, skipped)
    return {"created": created, "skipped": skipped}


@celery_app.task(
    name="hubra.core.tasks.finance_tasks.send_overdue_reminders_task",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_overdue_reminders_task(self) -> dict:
    """Send overdue reminders in every club with finance on."""
    return _send_overdue_reminders()


@per_tenant_job("finance")
def _send_overdue_reminders() -> dict:
    """Send overdue reminders for unpaid invoices past their due date.

    Two reminder rounds:
      - overdue_7d:  sent when an invoice is 7+ days past due
      - overdue_14d: sent when an invoice is 14+ days past due (if still unpaid)

    Idempotency: each reminder_type is sent at most once per invoice, tracked
    via InvoiceReminderHistory.

    The first reminder for an invoice also emits ``invoice.overdue`` so other
    modules can react (for example keys tells the key managers).

    Returns a summary dict with counts per round.
    """
    from sqlalchemy import select
    from hubra.core.models.finance import Invoice
    from hubra.core.models.invoice_reminder import InvoiceReminderHistory
    from hubra.core.models.member import Member
    from hubra.core.services.email import _get_base_url

    today = date.today()
    _base = _get_base_url()
    portal_url = f"{_base}/invoices" if _base else "the member portal"

    overdue_7d = 0
    overdue_14d = 0
    skipped_no_email = 0

    # Fetch all open invoices that are past due
    overdue_invoices: list[Invoice] = db.session.scalars(  # type: ignore[assignment]
        select(Invoice)
        .where(Invoice.status == "Open")
        .where(Invoice.due < today)
        .order_by(Invoice.due.asc())
    ).all()

    # Pre-fetch all existing reminder history for these invoices
    invoice_ids = [inv.id for inv in overdue_invoices]
    if not invoice_ids:
        return {"overdue_7d": 0, "overdue_14d": 0, "skipped_no_email": 0}

    existing_history: list[InvoiceReminderHistory] = db.session.scalars(  # type: ignore[assignment]
        select(InvoiceReminderHistory).where(
            InvoiceReminderHistory.invoice_id.in_(invoice_ids)
        )
    ).all()

    # Build a lookup: invoice_id -> set of sent reminder_types
    sent_types: dict[int, set[str]] = {}
    for h in existing_history:
        sent_types.setdefault(h.invoice_id, set()).add(h.reminder_type)

    for invoice in overdue_invoices:
        member = db.session.get(Member, invoice.member_id)
        if not member or not member.email:
            skipped_no_email += 1
            logger.info(
                "overdue_reminder_skipped invoice_id=%s reason=no_member_or_email",
                invoice.id,
            )
            continue

        sent = sent_types.get(invoice.id, set())

        # Check for 14-day reminder first (higher priority round)
        if "overdue_14d" not in sent and invoice.due <= today - timedelta(days=14):
            subject, body_html, body_text = _render_invoice_reminder(
                name=member.name,
                invoice_id=invoice.id,
                amount=float(invoice.amount),
                due_date=invoice.due,
                portal_url=portal_url,
                lang=getattr(member, "language", DEFAULT_LANG) or DEFAULT_LANG,
            )
            _dispatch_invoice_email(
                invoice=invoice,
                member=member,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                reminder_type="overdue_14d",
            )
            overdue_14d += 1
            if not sent:
                emit(INVOICE_OVERDUE, member_id=member.id, invoice_id=invoice.id)
            logger.info(
                "overdue_reminder_sent invoice_id=%s member_id=%s round=14d",
                invoice.id,
                member.id,
            )

        elif "overdue_7d" not in sent and invoice.due <= today - timedelta(days=7):
            subject, body_html, body_text = _render_invoice_reminder(
                name=member.name,
                invoice_id=invoice.id,
                amount=float(invoice.amount),
                due_date=invoice.due,
                portal_url=portal_url,
                lang=getattr(member, "language", DEFAULT_LANG) or DEFAULT_LANG,
            )
            _dispatch_invoice_email(
                invoice=invoice,
                member=member,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                reminder_type="overdue_7d",
            )
            overdue_7d += 1
            emit(INVOICE_OVERDUE, member_id=member.id, invoice_id=invoice.id)
            logger.info(
                "overdue_reminder_sent invoice_id=%s member_id=%s round=7d",
                invoice.id,
                member.id,
            )

    db.session.commit()
    logger.info(
        "overdue_reminders_complete overdue_7d=%s overdue_14d=%s skipped=%s",
        overdue_7d,
        overdue_14d,
        skipped_no_email,
    )
    return {
        "overdue_7d": overdue_7d,
        "overdue_14d": overdue_14d,
        "skipped_no_email": skipped_no_email,
    }
