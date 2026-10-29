"""Two checkouts of one item at the same moment: one gets it, one gets 409.

Needs real row locks, so it only runs on Postgres (TEST_DATABASE_URL).
"""

import threading
import time

import pytest

from hubra.api.inventory import services as inventory_services
from hubra.core.errors import ApiError
from hubra.core.models.inventory import InventoryCheckout, InventoryItem
from hubra.core.models.member import Member
from hubra.core.models.user import User


def test_one_item_one_checkout(app, db, seeded_db, monkeypatch):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("row locks need Postgres")

    member_ids = []
    for n in range(2):
        user = User(email=f"borrow{n}@test.ch", first_name="Borrow", last_name=str(n))
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()
        member = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
        db.session.add(member)
        db.session.flush()
        member_ids.append(member.id)
    item = InventoryItem(name="Bohrer", category="tools")
    db.session.add(item)
    db.session.commit()
    item_id = item.id

    # Widen the gap between the availability check and the commit.
    log_audit = inventory_services.log_audit

    def slow_log_audit(*args, **kwargs):
        time.sleep(0.3)
        return log_audit(*args, **kwargs)

    monkeypatch.setattr(inventory_services, "log_audit", slow_log_audit)

    outcomes = []

    def check_out(member_id):
        with app.app_context():
            try:
                inventory_services.InventoryService.checkout(item_id, member_id)
                db.session.commit()
                outcomes.append("ok")
            except ApiError as exc:
                db.session.rollback()
                outcomes.append(exc.status)

    threads = [threading.Thread(target=check_out, args=(m,)) for m in member_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes, key=str) == [409, "ok"]
    open_checkouts = (
        db.session.query(InventoryCheckout)
        .filter_by(item_id=item_id, returned_at=None)
        .count()
    )
    assert open_checkouts == 1
