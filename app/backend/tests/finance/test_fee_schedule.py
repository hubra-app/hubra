"""Membership fees on a fixed billing date or on each member's join date,
with the first fee reduced by the months left for members who join during
the period."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.pricing import billing_period, first_fee_share, prorate

FIXED = {"fee_anchor": "fixed_date", "fee_anchor_month": 1, "fee_anchor_day": 1}


class _Member:
    def __init__(self, joined):
        self.joined = joined


# ── Periods ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "day, cycle, anchor, expected",
    [
        # Calendar year and its parts, as before
        (date(2026, 10, 31), "yearly", (1, 1), (date(2026, 1, 1), date(2026, 12, 31))),
        (
            date(2026, 10, 31),
            "quarterly",
            (1, 1),
            (date(2026, 10, 1), date(2026, 12, 31)),
        ),
        (date(2026, 2, 10), "monthly", (1, 1), (date(2026, 2, 1), date(2026, 2, 28))),
        # A season from 1 July
        (date(2026, 3, 1), "yearly", (7, 1), (date(2025, 7, 1), date(2026, 6, 30))),
        (date(2026, 7, 1), "yearly", (7, 1), (date(2026, 7, 1), date(2027, 6, 30))),
        (
            date(2026, 9, 1),
            "half_yearly",
            (7, 1),
            (date(2026, 7, 1), date(2026, 12, 31)),
        ),
        # A join date on the 15th
        (date(2026, 4, 14), "yearly", (4, 15), (date(2025, 4, 15), date(2026, 4, 14))),
        (date(2026, 5, 20), "monthly", (4, 15), (date(2026, 5, 15), date(2026, 6, 14))),
        # 29 February is the 28th in other years
        (date(2027, 3, 1), "yearly", (2, 29), (date(2027, 2, 28), date(2028, 2, 28))),
    ],
)
def test_billing_period(day, cycle, anchor, expected):
    assert billing_period(day, cycle, *anchor) == expected


# ── Reduced first fee ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "joined, expected",
    [
        (date(2026, 4, 15), (date(2026, 4, 1), (9, 12))),  # Mike's example
        (date(2026, 12, 31), (date(2026, 12, 1), (1, 12))),
        (date(2026, 1, 20), None),  # the first month counts in full
        (date(2025, 6, 1), None),  # joined before the period
        (None, None),
    ],
)
def test_first_fee_share(joined, expected):
    start, end = date(2026, 1, 1), date(2026, 12, 31)
    assert first_fee_share(_Member(joined), start, end, FIXED) == expected


def test_first_fee_share_can_be_switched_off():
    off = {**FIXED, "prorate_first_fee": False}
    member = _Member(date(2026, 4, 15))
    assert first_fee_share(member, date(2026, 1, 1), date(2026, 12, 31), off) is None


def test_half_year_share():
    member = _Member(date(2026, 9, 3))
    share = first_fee_share(member, date(2026, 7, 1), date(2026, 12, 31), FIXED)
    assert share == (date(2026, 9, 1), (4, 6))


def test_prorate_rounds_to_5_rappen():
    assert prorate(Decimal("120"), (9, 12)) == Decimal("90")
    assert prorate(Decimal("100"), (7, 12)) == Decimal("58.35")


# ── The invoice run ───────────────────────────────────────────────────────────


@pytest.fixture
def yearly_member(db):
    from hubra.core.models.member import Member, MembershipTier
    from hubra.core.models.user import User

    tier = MembershipTier(
        name="Aktiv",
        price_chf=Decimal("120"),
        billing_cycle="yearly",
        price_type="fixed",
    )
    user = User(email="new@test.ch", first_name="Neu", last_name="Mitglied")
    user.set_password("password123")
    db.session.add_all([tier, user])
    db.session.flush()
    member = Member(user_id=user.id, status="active", tier_id=tier.id)
    db.session.add(member)
    db.session.commit()
    return member


def _run(app, today, **config):
    from hubra.core.tasks.finance_tasks import _generate_invoices

    with (
        patch("hubra.core.modules.get_config", return_value=config),
        patch("hubra.core.tasks.email_tasks.send_email_task.delay"),
    ):
        return _generate_invoices(today=today)


def _invoices(db, member):
    from hubra.core.models.finance import Invoice

    return db.session.scalars(
        select(Invoice).where(Invoice.member_id == member.id).order_by(Invoice.issued)
    ).all()


def test_member_joining_in_april_pays_nine_months(app, db, yearly_member):
    yearly_member.joined = date(2026, 4, 15)
    db.session.commit()

    assert _run(app, date(2026, 4, 15))["created"] == 1
    assert _run(app, date(2026, 11, 1))["created"] == 0
    assert _run(app, date(2027, 1, 1))["created"] == 1

    first, second = _invoices(db, yearly_member)
    assert first.amount == Decimal("90.00")
    assert (first.period_start, first.period_end) == (
        date(2026, 4, 1),
        date(2026, 12, 31),
    )
    assert second.amount == Decimal("120.00")
    assert (second.period_start, second.period_end) == (
        date(2027, 1, 1),
        date(2027, 12, 31),
    )


def test_full_fee_without_proration(app, db, yearly_member):
    yearly_member.joined = date(2026, 4, 15)
    db.session.commit()

    _run(app, date(2026, 4, 15), prorate_first_fee=False)
    assert _invoices(db, yearly_member)[0].amount == Decimal("120.00")


def test_billed_on_the_join_date_every_year(app, db, yearly_member):
    yearly_member.joined = date(2026, 4, 15)
    db.session.commit()
    join = {"bill_on_join_date": True}

    assert _run(app, date(2026, 4, 15), **join)["created"] == 1
    assert _run(app, date(2027, 1, 1), **join)["created"] == 0
    assert _run(app, date(2027, 4, 14), **join)["created"] == 0
    assert _run(app, date(2027, 4, 15), **join)["created"] == 1

    first, second = _invoices(db, yearly_member)
    assert first.amount == second.amount == Decimal("120.00")
    assert (first.period_start, first.period_end) == (
        date(2026, 4, 15),
        date(2027, 4, 14),
    )
    assert second.period_start == date(2027, 4, 15)


def test_season_from_1_july(app, db, yearly_member):
    yearly_member.joined = date(2025, 1, 10)
    db.session.commit()
    season = {"fee_anchor_month": 7, "fee_anchor_day": 1}

    assert _run(app, date(2026, 6, 30), **season)["created"] == 1
    assert _run(app, date(2026, 7, 1), **season)["created"] == 1
    starts = [i.period_start for i in _invoices(db, yearly_member)]
    assert starts == [date(2025, 7, 1), date(2026, 7, 1)]


def test_moving_the_billing_date_bills_nobody_twice(app, db, yearly_member):
    """An invoice from before invoices kept their period covers its calendar
    year; switching to join dates later in that year bills nothing more."""
    from hubra.core.models.finance import Invoice

    yearly_member.joined = date(2020, 4, 15)
    db.session.add(
        Invoice(
            member_id=yearly_member.id,
            issued=date(2026, 1, 1),
            due=date(2026, 1, 31),
            amount=Decimal("120"),
            status="Paid",
            purpose="membership",
        )
    )
    db.session.commit()

    assert _run(app, date(2026, 6, 1), bill_on_join_date=True)["created"] == 0
    assert _run(app, date(2027, 4, 15), bill_on_join_date=True)["created"] == 1


def test_members_who_have_not_joined_yet_are_not_billed(app, db, yearly_member):
    yearly_member.joined = date(2026, 12, 1)
    db.session.commit()
    assert _run(app, date(2026, 11, 1))["created"] == 0


def test_bulk_invoices_use_the_same_reduction(client, auth_headers, db, yearly_member):
    yearly_member.joined = date.today().replace(day=1)
    db.session.commit()
    months_left = 13 - date.today().month

    resp = client.post(
        "/api/v1/finance/invoices/bulk",
        json={"tier_id": yearly_member.tier_id},
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201), resp.get_json()
    invoice = _invoices(db, yearly_member)[0]
    assert invoice.amount == prorate(Decimal("120"), (months_left, 12))
    assert invoice.period_start == date.today().replace(day=1)
    assert invoice.period_end == date(date.today().year, 12, 31)
