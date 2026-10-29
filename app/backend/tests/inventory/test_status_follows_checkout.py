"""Whether an item is out follows its checkout record, not the edit form.

Setting "available" by hand on a checked-out item left the checkout open,
so it showed as overdue for ever and the next borrower's check-in closed
the wrong one; setting "checked_out" by hand made an item nobody had.
"""

from tests.inventory.test_m5_inventory import _create_item, _create_member


def test_out_and_back_only_through_checkout(client, auth_headers, seeded_db):
    item_id = _create_item(client, auth_headers, name="Drill").get_json()["id"]
    member_id = _create_member(client, auth_headers).get_json()["id"]

    resp = client.patch(
        f"/api/v1/inventory/{item_id}", json={"status": "checked_out"}, headers=auth_headers
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "USE_CHECKOUT"

    client.post(
        f"/api/v1/inventory/{item_id}/checkout",
        json={"member_id": member_id},
        headers=auth_headers,
    )
    resp = client.patch(
        f"/api/v1/inventory/{item_id}", json={"status": "available"}, headers=auth_headers
    )
    assert resp.status_code == 409

    # The edit form sends the status it shows; that is fine.
    resp = client.patch(
        f"/api/v1/inventory/{item_id}",
        json={"status": "checked_out", "location": "Shelf 2"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert client.post(
        f"/api/v1/inventory/{item_id}/checkin", json={}, headers=auth_headers
    ).status_code == 200
    resp = client.patch(
        f"/api/v1/inventory/{item_id}", json={"status": "maintenance"}, headers=auth_headers
    )
    assert resp.status_code == 200
