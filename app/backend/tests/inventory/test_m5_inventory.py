"""Tests for M5 Inventory module — new fields, checkout/checkin, overdue."""

from tests.helpers import add_member


def _create_item(client, auth_headers, **overrides):
    payload = {
        "name": "Test Item",
        "category": "Tool",
    }
    payload.update(overrides)
    return client.post("/api/v1/inventory/", json=payload, headers=auth_headers)


def _create_member(client, auth_headers, **overrides):
    """Helper: a member with sensible defaults (they accepted an invite)."""
    payload = {
        "first_name": "Test",
        "last_name": "Member",
        "email": "member@test.ch",
    }
    payload.update(overrides)
    return add_member(client, auth_headers, **payload)


# ── New fields ───────────────────────────────────────────────────────────────


def test_create_item_with_new_fields(client, auth_headers, seeded_db):
    resp = _create_item(
        client,
        auth_headers,
        name="Cordless Drill",
        category="Tool",
        purchase_date="2024-01-15",
        purchase_cost="299.90",
        current_value="250.00",
        location="Workshop A",
        serial_number="BOSCH-12345",
        barcode_id="BC-001",
        documents=[
            {"name": "Manual", "url": "https://example.com/manual.pdf", "type": "pdf"}
        ],
        image_url="https://example.com/drill.jpg",
        notes="Heavy duty drill",
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["purchase_date"] == "2024-01-15"
    assert body["location"] == "Workshop A"
    assert body["serial_number"] == "BOSCH-12345"
    assert body["barcode_id"] == "BC-001"
    assert body["image_url"] == "https://example.com/drill.jpg"
    assert body["notes"] == "Heavy duty drill"
    assert len(body["documents"]) == 1


def test_update_item_new_fields(client, auth_headers, seeded_db):
    created = _create_item(client, auth_headers, name="Update Me")
    item_id = created.get_json()["id"]

    resp = client.patch(
        f"/api/v1/inventory/{item_id}",
        json={
            "location": "Storage B",
            "serial_number": "SN-999",
            "notes": "Updated notes",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["location"] == "Storage B"
    assert body["serial_number"] == "SN-999"
    assert body["notes"] == "Updated notes"


# ── Checkout / Check-in ──────────────────────────────────────────────────────


def test_checkout_item(client, auth_headers, seeded_db):
    item = _create_item(client, auth_headers, name="Checkout Test")
    item_id = item.get_json()["id"]

    member = _create_member(
        client,
        auth_headers,
        email="checkout@test.ch",
        first_name="Checkout",
        last_name="User",
    )
    member_id = member.get_json()["id"]

    resp = client.post(
        f"/api/v1/inventory/{item_id}/checkout",
        json={"member_id": member_id, "condition_notes": "Good condition"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["item_id"] == item_id
    assert body["member_id"] == member_id
    assert body["condition_notes"] == "Good condition"
    assert body["returned_at"] is None

    # Item status should be checked_out
    resp = client.get(f"/api/v1/inventory/{item_id}", headers=auth_headers)
    assert resp.get_json()["status"] == "checked_out"


def test_checkout_unavailable_item(client, auth_headers, seeded_db):
    item = _create_item(client, auth_headers, name="Broken Item", status="broken")
    item_id = item.get_json()["id"]

    member = _create_member(
        client,
        auth_headers,
        email="checkout2@test.ch",
        first_name="Checkout2",
        last_name="User",
    )
    member_id = member.get_json()["id"]

    resp = client.post(
        f"/api/v1/inventory/{item_id}/checkout",
        json={"member_id": member_id},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_checkin_item(client, auth_headers, seeded_db):
    item = _create_item(client, auth_headers, name="Checkin Test")
    item_id = item.get_json()["id"]

    member = _create_member(
        client,
        auth_headers,
        email="checkin@test.ch",
        first_name="Checkin",
        last_name="User",
    )
    member_id = member.get_json()["id"]

    # Checkout first
    client.post(
        f"/api/v1/inventory/{item_id}/checkout",
        json={"member_id": member_id},
        headers=auth_headers,
    )

    # Now check in
    resp = client.post(
        f"/api/v1/inventory/{item_id}/checkin",
        json={"condition_notes": "Returned in good condition"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["returned_at"] is not None
    assert body["condition_notes"] == "Returned in good condition"

    # Item status should be available again
    resp = client.get(f"/api/v1/inventory/{item_id}", headers=auth_headers)
    assert resp.get_json()["status"] == "available"


def test_checkin_not_checked_out(client, auth_headers, seeded_db):
    item = _create_item(client, auth_headers, name="Not Checked Out")
    item_id = item.get_json()["id"]

    resp = client.post(
        f"/api/v1/inventory/{item_id}/checkin",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 409


# ── Overdue ──────────────────────────────────────────────────────────────────


def test_overdue_returns_late_items(client, auth_headers, seeded_db, db):
    from datetime import datetime, timedelta, timezone

    from hubra.core.models.inventory import InventoryCheckout, InventoryItem

    item = _create_item(client, auth_headers, name="Overdue Item")
    item_id = item.get_json()["id"]

    member = _create_member(
        client,
        auth_headers,
        email="overdue@test.ch",
        first_name="Overdue",
        last_name="User",
    )
    member_id = member.get_json()["id"]

    # Checkout with expected return in the past
    past = datetime.now(timezone.utc) - timedelta(days=5)
    checkout = InventoryCheckout(
        item_id=item_id,
        member_id=member_id,
        expected_return_at=past,
    )
    db.session.add(checkout)
    item_obj = db.session.get(InventoryItem, item_id)
    item_obj.status = "checked_out"
    db.session.commit()

    resp = client.get("/api/v1/inventory/overdue", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) >= 1
    assert any(o["item_id"] == item_id for o in body)


def test_overdue_empty(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/inventory/overdue", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == []
