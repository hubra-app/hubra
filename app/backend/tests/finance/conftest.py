"""Shared fixtures for finance tests."""

import pytest
from decimal import Decimal


@pytest.fixture
def billable_tier_db(db):
    """Create seed data with a billable tier and two members."""
    from vollbuild.core.models.role import Role
    from vollbuild.core.models.member import Member, MembershipTier
    from vollbuild.core.models.user import User

    role = Role(name="Admin", is_default=True)
    billable_tier = MembershipTier(
        name="Premium",
        price_chf=Decimal("99.00"),
        color="#ff0000",
        billing_cycle="monthly",
        price_type="fixed",
    )
    free_tier = MembershipTier(
        name="Free",
        price_chf=None,
        color="#00ff00",
        billing_cycle=None,
        price_type=None,
    )
    db.session.add_all([role, billable_tier, free_tier])
    db.session.flush()

    user_billed = User(
        email="alice@test.ch",
        first_name="Alice",
        last_name="Billed",
    )
    user_billed.set_password("password123")
    db.session.add(user_billed)
    db.session.flush()

    member_billed = Member(
        user_id=user_billed.id,
        status="active",
    )
    member_billed.roles = [role]
    member_billed.tier_id = billable_tier.id

    user_free = User(
        email="bob@test.ch",
        first_name="Bob",
        last_name="Free",
    )
    user_free.set_password("password123")
    db.session.add(user_free)
    db.session.flush()

    member_free = Member(
        user_id=user_free.id,
        status="active",
    )
    member_free.roles = [role]
    member_free.tier_id = None

    db.session.add_all([member_billed, member_free])
    db.session.commit()

    return {
        "role": role,
        "billable_tier": billable_tier,
        "free_tier": free_tier,
        "member_billed": member_billed,
        "member_free": member_free,
    }
