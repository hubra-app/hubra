"""The guides plugin: one usage guide per inventory item."""

from __future__ import annotations

import pytest

from hubra.core.models.inventory import InventoryItem
from hubra_guides.models import ItemGuide


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
    db.session.add(ItemGuide(item_id=item.id, guide="secret steps"))
    db.session.commit()
    body = client.get(f"/api/v1/inventory/{item.id}").get_json()
    assert "guide" not in str(body.keys())
