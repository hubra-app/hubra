"""Inventory checkout rules (club settings of the inventory module)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from hubra.core.models.inventory import InventoryItem
from hubra.core.models.member import Member


@pytest.fixture
def other_member(db, seeded_db):
    from hubra.core.models.user import User

    user = User(email="holder@test.ch", first_name="Hanna", last_name="Holder")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    m = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    db.session.add(m)
    db.session.commit()
    return m


@pytest.fixture
def item(db, seeded_db):
    it = InventoryItem(name="Laser cutter", category="Tool", status="available")
    db.session.add(it)
    db.session.commit()
    return it


# ── Checkout rules ───────────────────────────────────────────────────────────


def test_checkout_requires_induction(db, seeded_db, item, other_member):
    from hubra.api.inventory.services import InventoryService
    from hubra.core.errors import ApiError

    item.instruction_required = True
    db.session.commit()
    with pytest.raises(ApiError) as exc:
        InventoryService.checkout(item.id, other_member.id)
    assert exc.value.code == "NOT_INSTRUCTED"

    item.instructed_members.append(other_member)
    db.session.commit()
    assert (
        InventoryService.checkout(item.id, other_member.id).member_id == other_member.id
    )


def test_checkout_blocked_when_overdue_if_configured(db, seeded_db, item, other_member):
    from hubra.api.inventory.services import InventoryService
    from hubra.core.errors import ApiError
    from hubra.core.models.feature import Feature
    from hubra.core.models.finance import Invoice
    from hubra.core.modules.state import invalidate

    db.session.add(
        Invoice(
            member_id=other_member.id,
            issued=date.today() - timedelta(days=40),
            due=date.today() - timedelta(days=10),
            amount=Decimal("50"),
            status="Open",
        )
    )
    db.session.commit()
    # Off by default: checkout works.
    assert InventoryService.checkout(item.id, other_member.id)

    item.status = "available"
    # Single-club install: settings live on a tenant grant, so emulate one by
    # patching the config read.
    from unittest.mock import patch

    with patch(
        "hubra.core.modules.get_config",
        return_value={"block_when_overdue": True, "require_induction": True},
    ):
        with pytest.raises(ApiError) as exc:
            InventoryService.checkout(item.id, other_member.id)
    assert exc.value.code == "PAYMENT_OVERDUE"
    assert db.session.get(Feature, "finance") is not None
    invalidate()
