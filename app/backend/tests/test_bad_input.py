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


# ── Wrong field types (found by sending each body field as text, list,
# object, bool and odd numbers) ───────────────────────────────────────────────


def _function(db, name="Kasse"):
    from hubra.core.models.function import Function

    fn = Function(name=name, max_holders=1)
    db.session.add(fn)
    db.session.commit()
    return fn.id


@pytest.mark.parametrize("member_id", ["abc", [1], {"a": 1}, True, 1.5])
def test_function_holder_needs_a_member_id(client, auth_headers, db, member_id):
    url = f"/api/v1/functions/{_function(db)}/holders"
    resp = client.post(url, json={"memberId": member_id}, headers=auth_headers)
    assert resp.status_code == 400


def test_function_update_ignores_unknown_keys(client, auth_headers, db):
    fn_id = _function(db)
    resp = client.patch(
        f"/api/v1/functions/{fn_id}",
        json={"function_id": 5, "description": "Kasse"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["id"] == fn_id


def test_member_update_with_unknown_tier(client, auth_headers, seeded_db):
    resp = client.patch(
        f"/api/v1/members/{seeded_db['admin'].id}",
        json={"tier_id": 999999},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.parametrize("plan_id", ["", "abc", [1], {"a": 1}, True])
def test_payment_plan_id_must_be_an_id(client, auth_headers, seeded_db, plan_id):
    for url in ("/api/v1/tiers/my-plan", f"/api/v1/tiers/members/{seeded_db['admin'].id}/plan"):
        resp = client.put(url, json={"plan_id": plan_id}, headers=auth_headers)
        assert resp.status_code == 400, url


@pytest.mark.parametrize(
    "body",
    [{"tier_id": True}, {"tier_id": [1]}, {"tier_id": "abc"}, {"price_chf": "abc"}],
)
def test_tier_cost_preview_with_bad_values(client, auth_headers, body):
    resp = client.post("/api/v1/tiers/calculate-cost", json=body, headers=auth_headers)
    assert resp.status_code == 400


def test_payment_plan_name_must_be_text(client, auth_headers, seeded_db):
    resp = client.post(
        f"/api/v1/tiers/{seeded_db['tier'].id}/plans",
        json={"name": 5, "interval": "monthly"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "body", [{"due": 5}, {"due": "2030-01-01", "tier_id": "x"}, {"due": "2030-01-01", "description": [1]}]
)
def test_bulk_invoices_with_bad_values(client, auth_headers, body):
    resp = client.post("/api/v1/finance/invoices/bulk", json=body, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "url, body",
    [
        ("/api/v1/mail/aliases", {"address": 5}),
        ("/api/v1/mail/system-addresses", {"address": ["a"]}),
        ("/api/v1/mail/mailboxes", {"username": "anna", "quotaGb": "lots"}),
        ("/api/v1/mail/mailboxes", {"username": {"a": 1}}),
        ("/api/v1/mail/test", {"to": True}),
    ],
)
def test_mail_forms_with_bad_values(client, auth_headers, url, body):
    resp = client.post(url, json=body, headers=auth_headers)
    assert resp.status_code == 400, resp.get_data(as_text=True)[:200]
