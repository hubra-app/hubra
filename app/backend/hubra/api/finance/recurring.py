"""Recurring transactions: define an income or expense once, book it on
every due date."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from hubra.api.utils import id_from_body, log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.finance import (
    RECURRING_INTERVALS,
    RecurringTransaction,
    Transaction,
    TransactionCategory,
)

_MONTHS = {"monthly": 1, "quarterly": 3, "half_yearly": 6, "yearly": 12}
_METHODS = ("IBAN", "Card", "Twint", "Cash")
# At most this many missed dates are booked in one run (three years of a
# monthly item), so a wrong start date can't flood the transactions.
_MAX_CATCH_UP = 36


def add_months(day: date, months: int) -> date:
    """*day* moved by whole months, on the month's last day if it is shorter."""
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def occurrence_on_or_after(rule: RecurringTransaction, day: date) -> date | None:
    """The first due date of *rule* on or after *day*; None after its end."""
    step = _MONTHS[rule.interval]
    k = 0
    if day > rule.start_date:
        months = (day.year - rule.start_date.year) * 12 + (
            day.month - rule.start_date.month
        )
        k = max(months // step - 1, 0)
    due = add_months(rule.start_date, k * step)
    while due < day:
        k += 1
        due = add_months(rule.start_date, k * step)
    if rule.end_date is not None and due > rule.end_date:
        return None
    return due


def yearly_amount(rule: RecurringTransaction) -> Decimal:
    """What the rule comes to over a full year."""
    return Decimal(str(rule.amount)) * (12 // _MONTHS[rule.interval])


def recurring_to_dict(rule: RecurringTransaction) -> dict:
    return {
        "id": rule.id,
        "description": rule.description,
        "type": rule.type,
        "amount": float(rule.amount),
        "category_id": rule.category_id,
        "category_name": rule.category.name if rule.category else "",
        "payee_name": rule.payee_name,
        "method": rule.method,
        "interval": rule.interval,
        "start_date": rule.start_date.isoformat(),
        "end_date": rule.end_date.isoformat() if rule.end_date else None,
        "next_date": rule.next_date.isoformat() if rule.next_date else None,
        "book_completed": rule.book_completed,
        "counts_for_fees": rule.counts_for_fees,
        "active": rule.active,
        "yearly_amount": float(yearly_amount(rule)),
    }


def _date(value, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise_error(400, "VALIDATION_ERROR", f"{field} must be an ISO date")


def _text(value, field: str, required: bool) -> str | None:
    text = value.strip() if isinstance(value, str) else ""
    if value is not None and not isinstance(value, str):
        raise_error(400, "VALIDATION_ERROR", f"{field} must be text")
    if required and not text:
        raise_error(400, "VALIDATION_ERROR", f"{field} is required")
    if len(text) > 255:
        raise_error(400, "VALIDATION_ERROR", f"{field} is too long")
    return text or None


def _bool(value, field: str) -> bool:
    if not isinstance(value, bool):
        raise_error(400, "VALIDATION_ERROR", f"{field} must be true or false")
    return value


def _apply(rule: RecurringTransaction, data: dict, partial: bool) -> None:
    def given(field: str) -> bool:
        return field in data or not partial

    if given("description"):
        rule.description = _text(data.get("description"), "description", True)
    if given("type"):
        if data.get("type") not in ("income", "expense"):
            raise_error(400, "VALIDATION_ERROR", "type must be income or expense")
        rule.type = data["type"]
    if given("amount"):
        try:
            amount = Decimal(str(data.get("amount")))
        except (InvalidOperation, ValueError):
            raise_error(400, "VALIDATION_ERROR", "amount must be a number")
        if not amount.is_finite() or amount <= 0 or amount >= Decimal("1e10"):
            raise_error(400, "VALIDATION_ERROR", "amount must be above 0")
        rule.amount = amount.quantize(Decimal("0.01"))
    if given("interval"):
        if data.get("interval") not in RECURRING_INTERVALS:
            raise_error(
                400,
                "VALIDATION_ERROR",
                f"interval must be one of {RECURRING_INTERVALS}",
            )
        rule.interval = data["interval"]
    if given("start_date"):
        rule.start_date = _date(data.get("start_date"), "start_date")
    if "end_date" in data:
        end = data["end_date"]
        rule.end_date = None if end in (None, "") else _date(end, "end_date")
    if rule.end_date is not None and rule.end_date < rule.start_date:
        raise_error(400, "VALIDATION_ERROR", "end_date is before start_date")
    if "category_id" in data:
        category_id = id_from_body(data["category_id"], "category_id")
        if category_id is not None and not db.session.get(
            TransactionCategory, category_id
        ):
            raise_error(404, "NOT_FOUND", "Transaction category not found")
        rule.category_id = category_id
    if "payee_name" in data:
        rule.payee_name = _text(data["payee_name"], "payee_name", False)
    if "method" in data or rule.method is None:
        method = data.get("method", "IBAN")
        if method not in _METHODS:
            raise_error(400, "VALIDATION_ERROR", f"method must be one of {_METHODS}")
        rule.method = method
    for flag in ("book_completed", "counts_for_fees", "active"):
        if flag in data:
            setattr(rule, flag, _bool(data[flag], flag))


class RecurringTransactionService:
    @staticmethod
    def list() -> list[RecurringTransaction]:
        rules = db.session.scalars(
            select(RecurringTransaction).order_by(RecurringTransaction.description)
        ).all()
        # Running ones first, by their next date; ended and paused ones last.
        return sorted(
            rules,
            key=lambda r: (not (r.active and r.next_date), r.next_date or date.max),
        )

    @staticmethod
    def get(rule_id: int) -> RecurringTransaction:
        rule = db.session.get(RecurringTransaction, rule_id)
        if rule is None:
            raise_error(404, "NOT_FOUND", "Recurring transaction not found")
        return rule

    @staticmethod
    def create(data: dict, actor_id: int) -> RecurringTransaction:
        rule = RecurringTransaction(
            book_completed=False, counts_for_fees=True, active=True
        )
        _apply(rule, data, partial=False)
        # Dates before today are not booked: the club enters what already
        # runs, and its past payments are in the books (or the bank import).
        rule.next_date = occurrence_on_or_after(rule, date.today())
        db.session.add(rule)
        db.session.flush()
        log_audit(
            actor_id,
            "create_recurring_transaction",
            "RecurringTransaction",
            rule.id,
            rule.description,
        )
        return rule

    @staticmethod
    def update(rule_id: int, data: dict, actor_id: int) -> RecurringTransaction:
        rule = RecurringTransactionService.get(rule_id)
        _apply(rule, data, partial=True)
        if {"start_date", "end_date", "interval", "active"} & set(data):
            # Never book a date again that was booked already.
            last = db.session.scalar(
                select(Transaction.date)
                .where(Transaction.recurring_id == rule.id)
                .order_by(Transaction.date.desc())
                .limit(1)
            )
            start = date.today()
            if last is not None and last >= start:
                start = date.fromordinal(last.toordinal() + 1)
            rule.next_date = occurrence_on_or_after(rule, start)
        log_audit(
            actor_id,
            "update_recurring_transaction",
            "RecurringTransaction",
            rule.id,
            rule.description,
        )
        db.session.flush()
        return rule

    @staticmethod
    def delete(rule_id: int, actor_id: int) -> None:
        rule = RecurringTransactionService.get(rule_id)
        log_audit(
            actor_id,
            "delete_recurring_transaction",
            "RecurringTransaction",
            rule.id,
            rule.description,
        )
        # Its booked transactions stay; they only lose the link.
        db.session.query(Transaction).filter(
            Transaction.recurring_id == rule.id
        ).update({Transaction.recurring_id: None})
        db.session.delete(rule)
        db.session.flush()


def book_due(today: date | None = None) -> int:
    """Book every recurring transaction due on or before *today*."""
    today = today or date.today()
    rules = db.session.scalars(
        select(RecurringTransaction)
        .where(RecurringTransaction.active.is_(True))
        .where(RecurringTransaction.next_date.isnot(None))
        .where(RecurringTransaction.next_date <= today)
    ).all()
    booked = 0
    for rule in rules:
        for _ in range(_MAX_CATCH_UP):
            due = rule.next_date
            if due is None or due > today:
                break
            amount = Decimal(str(rule.amount))
            db.session.add(
                Transaction(
                    date=due,
                    description=rule.description,
                    category_id=rule.category_id,
                    payee_name=rule.payee_name,
                    amount=-amount if rule.type == "expense" else amount,
                    method=rule.method,
                    type=rule.type,
                    status="Completed" if rule.book_completed else "Pending",
                    recurring_id=rule.id,
                )
            )
            booked += 1
            rule.next_date = occurrence_on_or_after(
                rule, date.fromordinal(due.toordinal() + 1)
            )
        else:
            # Still behind after the cap: skip ahead instead of booking more.
            rule.next_date = occurrence_on_or_after(rule, today)
    db.session.flush()
    return booked
