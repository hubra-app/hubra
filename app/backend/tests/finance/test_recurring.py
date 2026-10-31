"""Recurring transactions: the API, the due dates and the daily booking."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from hubra.api.finance.recurring import add_months, book_due, occurrence_on_or_after
from hubra.core.models.finance import (
    RecurringTransaction,
    Transaction,
    TransactionCategory,
)

URL = "/api/v1/finance/recurring"


def _rule(**kw):
    values = dict(
        description="Rent",
        type="expense",
        amount=Decimal("1200"),
        method="IBAN",
        interval="monthly",
        start_date=date(2026, 1, 31),
        book_completed=False,
        counts_for_fees=True,
        active=True,
    )
    values.update(kw)
    return RecurringTransaction(**values)


@pytest.fixture
def rent_category(db):
    cat = TransactionCategory(name="Rent", color="#111111")
    db.session.add(cat)
    db.session.commit()
    return cat


# ── Due dates ─────────────────────────────────────────────────────────────────


def test_add_months_keeps_the_day_or_takes_the_last_one():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 1, 31), 2) == date(2026, 3, 31)
    assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)


@pytest.mark.parametrize(
    "interval, day, expected",
    [
        ("monthly", date(2026, 1, 1), date(2026, 1, 31)),
        ("monthly", date(2026, 2, 28), date(2026, 2, 28)),
        ("monthly", date(2026, 3, 1), date(2026, 3, 31)),
        ("quarterly", date(2026, 5, 1), date(2026, 7, 31)),
        ("half_yearly", date(2026, 8, 1), date(2027, 1, 31)),
        ("yearly", date(2029, 6, 1), date(2030, 1, 31)),
    ],
)
def test_next_due_date(interval, day, expected):
    assert occurrence_on_or_after(_rule(interval=interval), day) == expected


def test_no_due_date_after_the_end():
    rule = _rule(end_date=date(2026, 3, 15))
    assert occurrence_on_or_after(rule, date(2026, 3, 1)) is None


# ── Booking ───────────────────────────────────────────────────────────────────


def test_book_due_books_each_missed_date_once(db, rent_category):
    rule = _rule(category_id=rent_category.id, next_date=date(2026, 1, 31))
    db.session.add(rule)
    db.session.commit()

    assert book_due(date(2026, 3, 31)) == 3
    assert book_due(date(2026, 3, 31)) == 0
    rows = db.session.scalars(select(Transaction).order_by(Transaction.date)).all()
    assert [t.date for t in rows] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]
    assert all(t.amount == Decimal("-1200") for t in rows)
    assert all(t.status == "Pending" and t.recurring_id == rule.id for t in rows)
    assert all(t.category_id == rent_category.id for t in rows)
    assert rule.next_date == date(2026, 4, 30)


def test_book_due_standing_order_and_end_date(db):
    rule = _rule(
        type="income",
        amount=Decimal("50"),
        interval="quarterly",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        next_date=date(2026, 1, 1),
        book_completed=True,
    )
    db.session.add(rule)
    db.session.commit()

    assert book_due(date(2026, 12, 31)) == 2
    rows = db.session.scalars(select(Transaction)).all()
    assert {t.status for t in rows} == {"Completed"}
    assert {t.amount for t in rows} == {Decimal("50")}
    assert rule.next_date is None


def test_paused_rules_are_not_booked(db):
    db.session.add(_rule(next_date=date(2026, 1, 31), active=False))
    db.session.commit()
    assert book_due(date(2026, 3, 31)) == 0


def test_daily_task(app, db):
    from hubra.core.tasks.finance_tasks import book_recurring_transactions_task

    db.session.add(_rule(next_date=date.today()))
    db.session.commit()
    assert book_recurring_transactions_task.run() == {"booked": 1}


# ── API ───────────────────────────────────────────────────────────────────────


def test_create_starts_today_and_lists(client, auth_headers, db, rent_category):
    start = date.today() - timedelta(days=400)
    resp = client.post(
        URL,
        json={
            "description": "Hall rent",
            "type": "expense",
            "amount": "1200.50",
            "interval": "quarterly",
            "start_date": start.isoformat(),
            "category_id": rent_category.id,
            "payee_name": "Gemeinde",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["amount"] == 1200.5
    assert body["yearly_amount"] == 4802.0
    assert body["category_name"] == "Rent"
    assert body["method"] == "IBAN"
    assert body["counts_for_fees"] is True
    # Past dates are not booked: the next date is today or later.
    assert date.fromisoformat(body["next_date"]) >= date.today()

    listed = client.get(URL, headers=auth_headers).get_json()
    assert [r["id"] for r in listed] == [body["id"]]


def test_update_moves_the_next_date_but_never_books_twice(client, auth_headers, db):
    today = date.today()
    rule = _rule(start_date=today, next_date=today)
    db.session.add(rule)
    db.session.commit()
    book_due(today)
    db.session.commit()

    resp = client.patch(
        f"{URL}/{rule.id}",
        json={"interval": "yearly", "amount": 99},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["next_date"] == add_months(today, 12).isoformat()
    assert body["amount"] == 99


def test_delete_keeps_booked_transactions(client, auth_headers, db):
    rule = _rule(next_date=date(2026, 1, 31))
    db.session.add(rule)
    db.session.commit()
    book_due(date(2026, 1, 31))
    db.session.commit()

    assert client.delete(f"{URL}/{rule.id}", headers=auth_headers).status_code == 204
    tx = db.session.scalars(select(Transaction)).one()
    db.session.refresh(tx)
    assert tx.recurring_id is None


@pytest.mark.parametrize(
    "patch",
    [
        {"amount": 0},
        {"amount": "abc"},
        {"type": "gift"},
        {"interval": "weekly"},
        {"start_date": "soon"},
        {"end_date": "2000-01-01"},
        {"description": ""},
        {"method": "Cheque"},
        {"active": "yes"},
        {"category_id": 999},
    ],
)
def test_bad_input_is_refused(client, auth_headers, db, patch):
    payload = {
        "description": "Rent",
        "type": "expense",
        "amount": 10,
        "interval": "monthly",
        "start_date": "2026-01-01",
    }
    payload.update(patch)
    resp = client.post(URL, json=payload, headers=auth_headers)
    assert resp.status_code in (400, 404), patch
    assert db.session.scalars(select(RecurringTransaction)).all() == []
