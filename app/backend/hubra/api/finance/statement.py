"""The monthly account statement: balance, sums per category, every booking
and the open invoices of one month, as a PDF mailed to the club's finance
address."""

from __future__ import annotations

import base64
import logging
from datetime import date, timedelta

from flask import render_template
from sqlalchemy import func, select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.finance import Invoice, Transaction, TransactionCategory
from hubra.core.services.email import DEFAULT_LANG, club_display_name
from hubra.core.services.mail_format import mail_date

logger = logging.getLogger(__name__)


def statement_settings() -> dict:
    """Whether the club gets a statement each month, and where it goes."""
    from hubra.core.modules import get_config

    config = get_config("finance")
    email = (config.get("statement_email") or "").strip()
    return {
        "enabled": config.get("statement_enabled") is True and "@" in email,
        "email": email,
    }


def month_of(value: str | None) -> date:
    """The first day of a ``YYYY-MM`` month; last month when not given."""
    if not value:
        return (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
    try:
        year, month = (int(part) for part in value.split("-"))
        return date(year, month, 1)
    except (TypeError, ValueError):
        raise_error(400, "VALIDATION_ERROR", "month must be YYYY-MM")


def _month_end(start: date) -> date:
    return (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(
        days=1
    )


def _balance_before(day: date):
    return db.session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.status == "Completed")
        .where(Transaction.date < day)
    )


def statement_data(start: date) -> dict:
    """What the statement of the month from *start* shows."""
    from hubra.api.finance.services import FinanceSummaryService

    end = _month_end(start)
    summary = FinanceSummaryService.get(
        {"from": start.isoformat(), "to": end.isoformat()}
    )
    rows = db.session.execute(
        select(Transaction, TransactionCategory.name)
        .outerjoin(
            TransactionCategory, Transaction.category_id == TransactionCategory.id
        )
        .where(Transaction.status == "Completed")
        .where(Transaction.date >= start)
        .where(Transaction.date <= end)
        .order_by(Transaction.date, Transaction.id)
    ).all()
    pending = db.session.execute(
        select(
            func.count(Transaction.id), func.coalesce(func.sum(Transaction.amount), 0)
        )
        .where(Transaction.status == "Pending")
        .where(Transaction.date <= end)
        # An open invoice's own booking is counted with the invoices.
        .where(
            Transaction.id.not_in(
                select(Invoice.transaction_id).where(Invoice.transaction_id.isnot(None))
            )
        )
    ).one()
    open_invoices = db.session.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.amount), 0))
        .where(Invoice.status != "Paid")
        .where(Invoice.issued <= end)
    ).one()
    overdue = db.session.scalar(
        select(func.count(Invoice.id))
        .where(Invoice.status != "Paid")
        .where(Invoice.due < end + timedelta(days=1))
    )
    opening = float(_balance_before(start))
    closing = float(_balance_before(end + timedelta(days=1)))
    return {
        "club_name": club_display_name(),
        "start": start,
        "end": end,
        "opening": opening,
        "closing": closing,
        "income": summary["income"],
        "expense": summary["expense"],
        "net": summary["net"],
        "categories": summary["categories"],
        "transactions": [
            {
                "date": tx.date,
                "description": tx.description,
                "category": category or "",
                "payee": tx.payee_name or (tx.member.name if tx.member else ""),
                "amount": float(tx.amount),
            }
            for tx, category in rows
        ],
        "pending": {"count": pending[0] or 0, "amount": float(pending[1] or 0)},
        "open_invoices": {
            "count": open_invoices[0] or 0,
            "amount": float(open_invoices[1] or 0),
            "overdue": overdue or 0,
        },
    }


def chf(value: float) -> str:
    """1234.5 as 1’234.50, the Swiss way."""
    sign = "−" if value < 0 else ""
    return sign + f"{abs(value):,.2f}".replace(",", "’")


_MONTHS = {
    "de": (
        "Januar Februar März April Mai Juni Juli August September Oktober "
        "November Dezember"
    ).split(),
    "en": (
        "January February March April May June July August September October "
        "November December"
    ).split(),
}


def _month_label(start: date, lang: str) -> str:
    names = _MONTHS["en" if lang.lower().startswith("en") else "de"]
    return f"{names[start.month - 1]} {start.year}"


def statement_pdf(data: dict, lang: str = DEFAULT_LANG) -> bytes:
    from weasyprint import HTML

    from hubra.core.services.mail_i18n import get_mail_translator
    from hubra.core.services.qr_bill import _no_fetch

    html = render_template(
        "finance/statement.html",
        t=get_mail_translator(lang),
        lang=lang,
        d=data,
        month=_month_label(data["start"], lang),
        chf=chf,
        fmt_date=lambda day: mail_date(day, lang),
        created=mail_date(date.today(), lang),
    )
    return HTML(string=html, url_fetcher=_no_fetch()).write_pdf()


def send_statement(start: date, to_email: str, lang: str = DEFAULT_LANG) -> dict:
    """Mail the statement of the month from *start* to *to_email*, once the
    session commits."""
    from hubra.core.services.mail_i18n import render_mail_template
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.email_tasks import send_email_task

    data = statement_data(start)
    month = _month_label(start, lang)
    body_html, body_text, subject = render_mail_template(
        "account_statement",
        locale=lang,
        club_name=data["club_name"],
        month=month,
        opening=f"CHF {chf(data['opening'])}",
        income=f"CHF {chf(data['income'])}",
        expense=f"CHF {chf(-data['expense'])}",
        closing=f"CHF {chf(data['closing'])}",
        open_invoices=data["open_invoices"]["count"],
        open_amount=f"CHF {chf(data['open_invoices']['amount'])}",
    )
    attachments = [
        {
            "name": f"kontoauszug-{start:%Y-%m}.pdf",
            "content": base64.b64encode(statement_pdf(data, lang)).decode("ascii"),
        }
    ]
    delay_after_commit(
        send_email_task,
        to_email=to_email,
        to_name=data["club_name"],
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        attachments=attachments,
    )
    logger.info("account_statement_queued month=%s", f"{start:%Y-%m}")
    return {"month": f"{start:%Y-%m}", "to": to_email}
