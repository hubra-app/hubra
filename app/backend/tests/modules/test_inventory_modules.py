"""Keys and guides modules, and the inventory checkout rules."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.helpers import set_modules
from vollbuild.core.models.inventory import InventoryItem
from vollbuild.core.models.member import Member
from vollbuild.core.models.notification import Notification
from vollbuild.modules.inventory_keys.models import Key


@pytest.fixture
def other_member(db, seeded_db):
    from vollbuild.core.models.user import User

    user = User(email="holder@test.ch", first_name="Hanna", last_name="Holder")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    m = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    db.session.add(m)
    db.session.commit()
    return m


@pytest.fixture
def key(db, seeded_db):
    k = Key(label="Front door", number="A-1", kind="key", opens="Main entrance")
    db.session.add(k)
    db.session.commit()
    return k


# ── Keys ─────────────────────────────────────────────────────────────────────


def test_create_and_list_keys(client, auth_headers):
    resp = client.post(
        "/api/v1/keys/",
        json={"label": "Workshop", "number": "W-7", "kind": "card", "deposit_chf": 20},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "available"
    assert body["depositChf"] == "20.00" or body["depositChf"] == "20"
    listed = client.get("/api/v1/keys/").get_json()
    assert [k["label"] for k in listed] == ["Workshop"]


def test_create_key_validates(client, auth_headers, key):
    assert client.post("/api/v1/keys/", json={}).status_code == 400
    assert (
        client.post("/api/v1/keys/", json={"label": "x", "kind": "laser"}).status_code
        == 400
    )
    dup = client.post("/api/v1/keys/", json={"label": "Copy", "number": "A-1"})
    assert dup.status_code == 409


def test_issue_and_return_key_logs_history(client, auth_headers, key, other_member):
    resp = client.post(
        f"/api/v1/keys/{key.id}/issue", json={"member_id": other_member.id}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "issued"
    assert body["holderName"] == "Hanna Holder"

    # Cannot issue twice or delete while issued.
    again = client.post(
        f"/api/v1/keys/{key.id}/issue", json={"member_id": other_member.id}
    )
    assert again.status_code == 409
    assert client.delete(f"/api/v1/keys/{key.id}").status_code == 409

    resp = client.post(f"/api/v1/keys/{key.id}/return", json={"note": "ok"})
    body = resp.get_json()
    assert body["status"] == "available" and body["holderId"] is None
    assert [h["action"] for h in body["history"]] == ["return", "issue"]


def test_lost_and_found(client, auth_headers, key):
    assert client.post(f"/api/v1/keys/{key.id}/lost").get_json()["status"] == "lost"
    assert client.post(f"/api/v1/keys/{key.id}/lost").status_code == 409
    assert (
        client.post(f"/api/v1/keys/{key.id}/found").get_json()["status"] == "available"
    )


def test_my_keys(client, db, auth_headers, key, seeded_db):
    key.status = "issued"
    key.holder_id = seeded_db["admin"].id
    db.session.commit()
    mine = client.get("/api/v1/keys/mine").get_json()
    assert [k["id"] for k in mine] == [key.id]


def test_keys_need_inventory(client, db, auth_headers):
    set_modules(False, "inventory")
    resp = client.get("/api/v1/keys/")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MODULE_DISABLED"


def test_overdue_invoice_notifies_key_managers(db, seeded_db, key, other_member):
    from vollbuild.core.modules import emit

    key.status = "issued"
    key.holder_id = other_member.id
    db.session.commit()
    called = emit(
        "invoice.overdue", tenant_id=None, member_id=other_member.id, invoice_id=1
    )
    assert "inventory.keys" in called
    notes = (
        db.session.query(Notification).filter_by(member_id=seeded_db["admin"].id).all()
    )
    assert any("Front door" in n.msg for n in notes)


# ── Guides ───────────────────────────────────────────────────────────────────


@pytest.fixture
def item(db, seeded_db):
    it = InventoryItem(name="Laser cutter", category="Tool", status="available")
    db.session.add(it)
    db.session.commit()
    return it


def test_save_and_read_guide(client, auth_headers, item):
    resp = client.put(
        f"/api/v1/guides/{item.id}",
        json={
            "guide": "# Safety\nWear goggles.",
            "guide_url": "https://drive.google.com/x",
        },
    )
    assert resp.status_code == 200
    got = client.get(f"/api/v1/guides/{item.id}").get_json()
    assert got["guide"].startswith("# Safety")
    assert got["guideUrl"] == "https://drive.google.com/x"
    assert [g["itemId"] for g in client.get("/api/v1/guides/").get_json()] == [item.id]


def test_guide_url_must_be_https(client, auth_headers, item):
    resp = client.put(f"/api/v1/guides/{item.id}", json={"guide_url": "http://x"})
    assert resp.status_code == 400


def test_item_api_does_not_leak_guide(client, auth_headers, item, db):
    item.guide = "secret steps"
    db.session.commit()
    body = client.get(f"/api/v1/inventory/{item.id}").get_json()
    assert "guide" not in str(body.keys())


# ── Checkout rules ───────────────────────────────────────────────────────────


def test_checkout_requires_induction(db, seeded_db, item, other_member):
    from vollbuild.api.inventory.services import InventoryService
    from vollbuild.core.errors import ApiError

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
    from vollbuild.api.inventory.services import InventoryService
    from vollbuild.core.errors import ApiError
    from vollbuild.core.models.feature import Feature
    from vollbuild.core.models.finance import Invoice
    from vollbuild.core.modules.state import invalidate

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
        "vollbuild.core.modules.get_config",
        return_value={"block_when_overdue": True, "require_induction": True},
    ):
        with pytest.raises(ApiError) as exc:
            InventoryService.checkout(item.id, other_member.id)
    assert exc.value.code == "PAYMENT_OVERDUE"
    assert db.session.get(Feature, "finance") is not None
    invalidate()
