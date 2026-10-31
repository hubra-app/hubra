"""The yearly expenses behind percentage and formula tiers: where the sum
comes from, its lines per category, and what the tiers cost with it."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from hubra.api.finance import fee_basis as fb
from hubra.api.finance.fee_basis import fee_basis, yearly_expenses
from hubra.core.models.finance import (
    RecurringTransaction,
    Transaction,
    TransactionCategory,
)
from hubra.core.models.setting import Setting

URL = "/api/v1/finance/fee-basis"


def _config(**values):
    return patch("hubra.core.modules.get_config", return_value=values)


@pytest.fixture
def books(db):
    rent = TransactionCategory(name="Miete", color="#e8590c")
    power = TransactionCategory(name="Strom", color="#1c7ed6")
    db.session.add_all([rent, power])
    db.session.flush()
    rules = [
        ("Miete", "monthly", "1000", rent, True, True),
        ("Strom", "quarterly", "150", power, True, True),
        ("Spende", "yearly", "500", None, False, True),  # does not count
        ("Alte Miete", "monthly", "800", rent, True, False),  # stopped
    ]
    for text, interval, amount, category, counts, active in rules:
        db.session.add(
            RecurringTransaction(
                description=text,
                type="expense",
                amount=Decimal(amount),
                category_id=category.id if category else None,
                method="IBAN",
                interval=interval,
                start_date=date(2026, 1, 1),
                next_date=date(2026, 11, 1),
                book_completed=False,
                counts_for_fees=counts,
                active=active,
            )
        )
    for day, amount, category, status in [
        (date(2025, 3, 1), -6000, rent, "Completed"),
        (date(2025, 6, 1), -400, power, "Completed"),
        (date(2025, 7, 1), -99, power, "Pending"),  # not confirmed
        (date(2025, 8, 1), 3000, None, "Completed"),  # income
        (date(2026, 2, 1), -1000, rent, "Completed"),  # this year
    ]:
        db.session.add(
            Transaction(
                date=day,
                description="x",
                category_id=category.id if category else None,
                amount=Decimal(amount),
                method="IBAN",
                type="income" if amount > 0 else "expense",
                status=status,
            )
        )
    db.session.add(Setting(key=fb.LEGACY_SETTING, value="7000"))
    db.session.commit()


def test_manual_keeps_the_old_setting(app, db, books):
    with _config():
        basis = fee_basis(today=date(2026, 10, 31))
    assert basis["source"] == "manual"
    assert basis["total"] == 7000
    assert basis["lines"] == []
    with _config(fee_basis_manual=8000, fee_basis_extra=500):
        assert fee_basis()["total"] == 8000  # extra is for the other sources


def test_recurring_expenses_per_year(app, db, books):
    with _config(fee_basis_source="recurring", fee_basis_extra=400):
        basis = fee_basis(today=date(2026, 10, 31))
    assert basis["total"] == 12000 + 600 + 400
    assert [(line["name"], line["amount"]) for line in basis["lines"]] == [
        ("Miete", 12000),
        ("Strom", 600),
    ]
    rent = basis["lines"][0]
    assert rent["share"] == pytest.approx(12000 / 13000)
    assert [item["description"] for item in rent["items"]] == ["Miete"]


def test_last_years_confirmed_expenses(app, db, books):
    with _config(fee_basis_source="last_year"):
        basis = fee_basis(today=date(2026, 10, 31))
    assert basis["period"] == {"from": "2025-01-01", "to": "2025-12-31"}
    assert basis["total"] == 6400
    assert {line["name"]: line["amount"] for line in basis["lines"]} == {
        "Miete": 6000,
        "Strom": 400,
    }


def test_last_year_follows_the_billing_season(app, db, books):
    season = {"fee_anchor_month": 7, "fee_anchor_day": 1}
    with _config(fee_basis_source="last_year", **season):
        basis = fee_basis(today=date(2026, 10, 31))
    # This season runs from 1 July 2026, so last season is 2025/26.
    assert basis["period"] == {"from": "2025-07-01", "to": "2026-06-30"}
    assert basis["total"] == 1000


def test_budget_needs_the_plugin(app, db, books):
    with _config(fee_basis_source="budget", fee_basis_extra=100):
        basis = fee_basis(today=date(2026, 10, 31))
    assert "budget" not in basis["sources"]
    assert basis["note"] == "NO_BUDGET"
    assert basis["total"] == 100


def test_budget_from_a_registered_plugin(app, db, books, monkeypatch):
    monkeypatch.setattr(fb, "_PLUGIN_SOURCES", {})
    lines = [{"category_id": None, "name": "Anlässe", "amount": 2500, "items": []}]
    fb.register_source("budget", "finance.budgets", lambda year: lines)
    with (
        _config(fee_basis_source="budget"),
        patch("hubra.core.modules.is_enabled", return_value=True),
    ):
        basis = fee_basis(today=date(2026, 10, 31))
    assert "budget" in basis["sources"]
    assert basis["period"] == {"year": 2026}
    assert basis["total"] == 2500


def test_pricing_uses_the_chosen_source(app, db, books):
    from hubra.core.pricing import _get_yearly_expenses

    with _config(fee_basis_source="recurring"):
        assert _get_yearly_expenses() == Decimal("12600")


def test_a_broken_source_falls_back_to_the_old_setting(app, db, books):
    with (
        _config(fee_basis_source="recurring"),
        patch.object(fb, "_recurring_lines", side_effect=RuntimeError("boom")),
    ):
        assert yearly_expenses() == Decimal("7000")


@pytest.fixture
def share_tier(db):
    from hubra.core.models.member import MembershipTier

    tier = MembershipTier(
        name="Anteil",
        billing_cycle="yearly",
        price_type="percentage",
        percentage_value=Decimal("1"),
    )
    db.session.add(tier)
    db.session.commit()
    return tier


def test_route_previews_a_choice_with_tier_effects(
    client, auth_headers, db, books, share_tier
):
    with _config():
        resp = client.get(f"{URL}?source=recurring&extra=400", headers=auth_headers)
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["source"] == "recurring"
    assert body["total"] == 13000
    assert body["sources"] == ["manual", "recurring", "last_year"]
    (tier,) = body["tiers"]
    assert tier["name"] == "Anteil"
    assert tier["yearly_now"] == 70  # 1 % of the saved 7000
    assert tier["yearly"] == 130  # 1 % of the previewed 13000
