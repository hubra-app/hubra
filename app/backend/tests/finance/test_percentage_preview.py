"""A percentage tier's preview shows what each member is invoiced: the full
percentage, however many members the tier has."""

from decimal import Decimal

from hubra.core.pricing import annual_fee_for_member, calculate_preview_cost
from tests.finance.test_pricing import (  # noqa: F401  (fixtures)
    percentage_tier,
    yearly_expenses_setting,
)


def test_preview_matches_the_invoice_with_several_members(
    yearly_expenses_setting,  # noqa: F811
    percentage_tier,  # noqa: F811
    db,
):
    from hubra.core.models.member import Member

    db.session.add_all(
        [Member(status="active", tier_id=percentage_tier.id) for _ in range(4)]
    )
    db.session.commit()

    result = calculate_preview_cost(
        {
            "tier_id": percentage_tier.id,
            "price_type": "percentage",
            "billing_cycle": "yearly",
            "percentage_value": 2.5,
        },
        db_session=db.session,
    )
    member = type("M", (), {"tier": percentage_tier})()
    invoiced = annual_fee_for_member(member, percentage_tier)

    assert result["members"] == 4
    assert result["amount_yearly"] == 250.0
    assert Decimal(str(result["amount_yearly"])) == invoiced
