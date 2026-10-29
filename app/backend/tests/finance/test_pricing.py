"""Tests for pricing calculations using the global Club.Finance.YearlyExpenses setting."""

from decimal import Decimal

import pytest

from hubra.core.pricing import (
    annual_fee_for_member,
    calculate_preview_cost,
)


@pytest.fixture
def yearly_expenses_setting(db):
    from hubra.core.models.setting import Setting

    db.session.add(
        Setting(
            key="Club.Finance.YearlyExpenses",
            value="10000",
            namespace="club",
            validation_type="number",
        )
    )
    db.session.commit()


@pytest.fixture
def percentage_tier(db):
    from hubra.core.models.member import MembershipTier

    tier = MembershipTier(
        name="Pct",
        price_chf=None,
        color="#0000ff",
        billing_cycle="yearly",
        price_type="percentage",
        percentage_value=Decimal("2.5"),
    )
    db.session.add(tier)
    db.session.commit()
    return tier


@pytest.fixture
def formula_tier(db):
    from hubra.core.models.member import MembershipTier

    tier = MembershipTier(
        name="Formula",
        price_chf=None,
        color="#00ff00",
        billing_cycle="yearly",
        price_type="formula",
        coefficient=Decimal("0.5"),
    )
    db.session.add(tier)
    db.session.commit()
    return tier


class TestAnnualFeePercentage:
    def test_percentage_uses_global_setting(
        self, yearly_expenses_setting, percentage_tier, db
    ):
        member = type("M", (), {"tier": percentage_tier})()
        fee = annual_fee_for_member(member, percentage_tier)
        assert fee == Decimal("250.00")

    def test_percentage_with_no_setting_returns_zero(self, percentage_tier, db):
        member = type("M", (), {"tier": percentage_tier})()
        fee = annual_fee_for_member(member, percentage_tier)
        assert fee == Decimal(0)


class TestCalculatePreviewCost:
    def test_percentage_preview_uses_global_setting(
        self, yearly_expenses_setting, percentage_tier, db
    ):
        result = calculate_preview_cost(
            {
                "price_type": "percentage",
                "billing_cycle": "yearly",
                "percentage_value": 2.5,
            },
            db_session=db.session,
        )
        assert result["amount_yearly"] == 250.0

    def test_percentage_preview_no_setting_returns_zero(self, percentage_tier, db):
        result = calculate_preview_cost(
            {
                "price_type": "percentage",
                "billing_cycle": "yearly",
                "percentage_value": 2.5,
            },
            db_session=db.session,
        )
        assert result["amount_yearly"] == 0.0

    def test_formula_preview_uses_global_setting(
        self, yearly_expenses_setting, formula_tier, db
    ):
        result = calculate_preview_cost(
            {
                "price_type": "formula",
                "billing_cycle": "yearly",
                "coefficient": 0.5,
                "round_to": None,
                "deduct_tier_ids": [],
            },
            db_session=db.session,
        )
        assert result["amount_yearly"] == 10000.0

    def test_formula_preview_no_setting_returns_zero(self, formula_tier, db):
        result = calculate_preview_cost(
            {
                "price_type": "formula",
                "billing_cycle": "yearly",
                "coefficient": 0.5,
                "round_to": None,
                "deduct_tier_ids": [],
            },
            db_session=db.session,
        )
        assert result["amount_yearly"] == 0.0

    def test_fixed_preview_unaffected_by_setting(self, yearly_expenses_setting, db):
        result = calculate_preview_cost(
            {
                "price_type": "fixed",
                "billing_cycle": "yearly",
                "price_chf": 80,
            },
            db_session=db.session,
        )
        assert result["amount_yearly"] == 80.0


def test_invoice_amount_is_in_whole_rappen(yearly_expenses_setting, percentage_tier, db):
    from hubra.core.pricing import calculate_invoice_amount

    percentage_tier.billing_cycle = "monthly"
    percentage_tier.percentage_value = Decimal("3.33")
    member = type("M", (), {"tier": percentage_tier, "payment_plan": None})()
    amount = calculate_invoice_amount(member, percentage_tier, Decimal(0))
    assert amount == Decimal("27.75")
    assert amount.as_tuple().exponent == -2
