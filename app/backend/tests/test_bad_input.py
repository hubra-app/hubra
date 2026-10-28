"""Malformed requests get a 4xx, not a 500 (found by calling every route
with odd bodies)."""

from datetime import date

import pytest


def test_scalar_json_body_is_a_400(client, auth_headers):
    for body in ("text", 5, True):
        resp = client.post("/api/v1/functions/", json=body, headers=auth_headers)
        assert resp.status_code == 400, body
        assert resp.get_json()["error"] == "VALIDATION_ERROR"


def test_list_body_still_reaches_the_route(client, auth_headers):
    # i18n imports take a list; only bare strings and numbers are refused.
    resp = client.post("/api/v1/functions/", json=[], headers=auth_headers)
    assert resp.status_code == 400
    assert "name" in resp.get_json()["message"].lower()


@pytest.mark.parametrize(
    "body", [{"name": None}, {"name": 5}, {"name": "Kasse", "maxHolders": "two"}]
)
def test_function_create_checks_its_fields(client, auth_headers, body):
    resp = client.post("/api/v1/functions/", json=body, headers=auth_headers)
    assert resp.status_code == 400


def test_event_registration_with_bad_fields(client, auth_headers, db, seeded_db):
    from hubra.core.models.event import ClubEvent

    event = ClubEvent(title="Fest", date=date(2030, 1, 1), type="Social")
    db.session.add(event)
    db.session.commit()
    admin_id = seeded_db["admin"].id

    for url in (
        f"/api/v1/events/{event.id}/register",
        f"/api/v1/events/{event.id}/register/{admin_id}",
    ):
        resp = client.post(url, json={"unknown": 1}, headers=auth_headers)
        assert resp.status_code == 400, url


def test_inventory_checkout_without_member(client, auth_headers, db):
    from hubra.core.models.inventory import InventoryItem

    item = InventoryItem(name="Bohrer", category="tools")
    db.session.add(item)
    db.session.commit()

    resp = client.post(f"/api/v1/inventory/{item.id}/checkout", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_revert_unknown_setting_is_404(client, auth_headers):
    resp = client.post("/api/v1/settings/no.such.key/revert", headers=auth_headers)
    assert resp.status_code == 404


def test_qr_bill_without_banking_details_is_409(client, auth_headers, db, seeded_db):
    from hubra.core.models.finance import Invoice

    invoice = Invoice(
        member_id=seeded_db["admin"].id,
        issued=date(2026, 1, 1),
        due=date(2026, 2, 1),
        amount=5,
        status="Open",
    )
    db.session.add(invoice)
    db.session.commit()

    resp = client.get(f"/api/v1/finance/invoices/{invoice.id}/qr-bill.pdf", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "QR_BILL_NOT_CONFIGURED"
