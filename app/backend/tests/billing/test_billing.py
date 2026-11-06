"""Billing clubs for Hubra with Stripe Billing (hubra.core.billing)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse

import pytest

from hubra.core.billing import service, stripe_api
from hubra.core.errors import ApiError
from hubra.core.models.tenant import Tenant
from hubra.core.services import club_billing, plans, platform_settings
from tests.authz.conftest import (  # noqa: F401
    _login_member,
    plain_member_token,
)

WEBHOOK_SECRET = "whsec_test"


class FakeStripe:
    """Stripe's API in memory: records each call and answers it."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.products: set[str] = set()
        self.subscription = {
            "id": "sub_1",
            "customer": "cus_1",
            "status": "active",
            "current_period_end": 1798761600,  # 2027-01-01
            "cancel_at_period_end": False,
            "items": {"data": [{"id": "si_old"}]},
        }

    def __call__(self, method, url, headers, body):
        path = urllib.parse.urlparse(url).path
        form = dict(urllib.parse.parse_qsl((body or b"").decode()))
        if method == "GET" and "?" in url:
            form = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        self.calls.append((method, path, form))
        if path.startswith("/v1/products/"):
            pid = path.rsplit("/", 1)[1]
            if pid in self.products:
                return 200, json.dumps({"id": pid}).encode()
            return 404, json.dumps({"error": {"message": "No such product"}}).encode()
        if path == "/v1/products":
            self.products.add(form["id"])
            return 200, json.dumps({"id": form["id"]}).encode()
        if path in ("/v1/customers", "/v1/customers/cus_1"):
            return 200, b'{"id": "cus_1"}'
        if path == "/v1/checkout/sessions":
            return 200, b'{"id": "cs_1", "url": "https://checkout.stripe.test/cs_1"}'
        if path == "/v1/billing_portal/sessions":
            return 200, b'{"url": "https://billing.stripe.test/p"}'
        if path == "/v1/subscriptions/sub_1":
            return 200, json.dumps(self.subscription).encode()
        if path == "/v1/invoices":
            return 200, json.dumps(
                {
                    "data": [
                        {
                            "id": "in_1",
                            "number": "HUB-0001",
                            "created": 1767225600,
                            "status": "paid",
                            "total": 4000,
                            "paid": True,
                            "hosted_invoice_url": "https://invoice.stripe.test/1",
                            "invoice_pdf": "https://invoice.stripe.test/1.pdf",
                        }
                    ]
                }
            ).encode()
        return 404, b'{"error": {"message": "unexpected"}}'

    def made(self, method, path):
        return [form for m, p, form in self.calls if m == method and p == path]


@pytest.fixture
def stripe(monkeypatch, db):
    fake = FakeStripe()
    monkeypatch.setattr(stripe_api, "_send", fake)
    service._known_products.clear()
    platform_settings.set_many(
        {
            "billing.enabled": "on",
            "payments.stripe.secret_key": "sk_test_" + "a" * 24,
            "billing.stripe.webhook_secret": WEBHOOK_SECRET,
        }
    )
    db.session.commit()
    return fake


@pytest.fixture
def club(db):
    tenant = Tenant(name="Club A", slug="club-a", status="active", settings={})
    db.session.add(tenant)
    plans.update(plans.get("starter"), {"price_month_chf": "40"})
    db.session.commit()
    club_billing.update(tenant, {"status": "trialing", "discount_percent": 25})
    db.session.commit()
    return tenant


def test_items_follow_the_terms(stripe, club, db):
    club_billing.update(
        club, {"addons": [{"code": "discord", "label": "Discord", "price_chf": 5}]}
    )
    lines = service.items(club)
    assert lines == [
        {
            "product": "hubra_plan_starter",
            "name": "Hubra starter",
            "unit_amount": 3000,
            "quantity": 1,
        },
        {
            "product": "hubra_module_discord",
            "name": "Hubra Discord",
            "unit_amount": 500,
            "quantity": 1,
        },
    ]
    platform_settings.set_many({"billing.yearly": "on"})
    assert service.items(club)[0]["unit_amount"] == 36000
    # A running sponsorship: nothing to charge.
    club_billing.update(club, {"sponsored": True, "sponsor_name": "Bank"})
    assert service.items(club) == []


def test_checkout_makes_customer_products_and_session(stripe, club, db):
    url = service.checkout(club, "kassier@club.test", "https://s", "https://c")
    assert url == "https://checkout.stripe.test/cs_1"
    assert service.state(club)["customer_id"] == "cus_1"
    assert stripe.made("POST", "/v1/products")[0]["id"] == "hubra_plan_starter"
    session = stripe.made("POST", "/v1/checkout/sessions")[0]
    assert session["mode"] == "subscription"
    assert session["line_items[0][price_data][unit_amount]"] == "3000"
    assert session["line_items[0][price_data][recurring][interval]"] == "month"
    assert session["subscription_data[metadata][tenant_id]"] == str(club.id)
    # The product isn't made again.
    service.checkout(club, None, "https://s", "https://c")
    assert len(stripe.made("POST", "/v1/products")) == 1
    assert len(stripe.made("POST", "/v1/customers")) == 1


def test_checkout_bills_the_club_with_its_address(stripe, club, db):
    from hubra.core.models.setting import Setting

    for key, value in {
        "Club.Banking.Street": "Seeweg",
        "Club.Banking.HouseNo": "3",
        "Club.Banking.PostalCode": "8000",
        "Club.Banking.City": "Zürich",
        "Club.Contact.FinanceEmail": "finanzen@club.test",
    }.items():
        db.session.add(Setting(key=key, value=value))
    db.session.commit()
    service.checkout(club, "kassier@club.test", "https://s", "https://c")
    customer = stripe.made("POST", "/v1/customers")[0]
    assert customer["name"] == "Club A"
    assert customer["email"] == "finanzen@club.test"
    assert customer["address[line1]"] == "Seeweg 3"
    assert customer["address[postal_code]"] == "8000"
    assert customer["address[city]"] == "Zürich"
    assert customer["address[country]"] == "CH"
    session = stripe.made("POST", "/v1/checkout/sessions")[0]
    assert session["billing_address_collection"] == "required"
    assert session["customer_update[address]"] == "auto"
    assert "customer_update[name]" not in session


def test_checkout_without_club_address(stripe, club, db):
    service.checkout(club, "kassier@club.test", "https://s", "https://c")
    customer = stripe.made("POST", "/v1/customers")[0]
    assert customer["email"] == "kassier@club.test"
    assert not any(k.startswith("address") for k in customer)


def test_checkout_refuses_when_off_paid_or_nothing_due(stripe, club, db):
    platform_settings.set_many({"billing.enabled": "off"})
    with pytest.raises(ApiError) as off:
        service.checkout(club, None, "s", "c")
    assert off.value.status == 503
    platform_settings.set_many({"billing.enabled": "on"})
    service.apply_subscription(club, stripe.subscription)
    with pytest.raises(ApiError) as twice:
        service.checkout(club, None, "s", "c")
    assert twice.value.status == 409
    other = Tenant(name="Free", slug="free", status="active", plan="free", settings={})
    db.session.add(other)
    db.session.commit()
    with pytest.raises(ApiError) as nothing:
        service.checkout(other, None, "s", "c")
    assert nothing.value.status == 400


def test_subscription_sets_the_clubs_status(stripe, club, db):
    service.apply_subscription(club, {**stripe.subscription, "status": "past_due"})
    terms = club_billing.stored(club)
    assert terms["status"] == "past_due"
    assert terms["period_end"] == "2027-01-01"
    assert service.public_state(club)["hasSubscription"] is True
    service.apply_subscription(
        club, {**stripe.subscription, "status": "incomplete_expired"}
    )
    assert club_billing.stored(club)["status"] == "canceled"
    assert service.public_state(club)["hasSubscription"] is False


def test_sync_updates_changed_items_pro_rata(stripe, club, db):
    service.apply_subscription(club, stripe.subscription)
    assert service.sync(club) is True
    update = stripe.made("POST", "/v1/subscriptions/sub_1")[-1]
    # An item Hubra doesn't know goes, the plan comes in.
    assert update["items[0][price_data][unit_amount]"] == "3000"
    assert update["items[1][id]"] == "si_old"
    assert update["items[1][deleted]"] == "true"
    assert update["proration_behavior"] == "create_prorations"
    # Nothing changed: no second update.
    assert service.sync(club) is False

    # Stripe now holds the plan item; a price change touches only it.
    stripe.subscription["items"] = {
        "data": [
            {
                "id": "si_plan",
                "quantity": 1,
                "price": {
                    "product": "hubra_plan_starter",
                    "unit_amount": 3000,
                    "recurring": {"interval": "month"},
                },
            }
        ]
    }
    club_billing.update(club, {"discount_percent": 0})
    assert service.sync(club) is True
    update = stripe.made("POST", "/v1/subscriptions/sub_1")[-1]
    assert update["items[0][id]"] == "si_plan"
    assert update["items[0][price_data][unit_amount]"] == "4000"
    assert "items[1][id]" not in update


def test_a_new_member_changes_only_the_quantity(stripe, club, db, monkeypatch):
    from hubra.core.services import quotas

    club_billing.update(
        club,
        {
            "addons": [
                {"code": "polls", "label": "Polls", "price_chf": "1", "unit": "member"}
            ]
        },
    )
    service.apply_subscription(club, stripe.subscription)
    monkeypatch.setattr(quotas, "member_count", lambda t: 10)
    stripe.subscription["items"] = {
        "data": [
            {
                "id": "si_plan",
                "quantity": 1,
                "price": {
                    "product": "hubra_plan_starter",
                    "unit_amount": 3000,
                    "recurring": {"interval": "month"},
                },
            },
            {
                "id": "si_polls",
                "quantity": 10,
                "price": {
                    "product": {"id": "hubra_module_polls"},
                    "unit_amount": 100,
                    "recurring": {"interval": "month"},
                },
            },
        ]
    }
    assert service.sync(club) is False  # already in step
    monkeypatch.setattr(quotas, "member_count", lambda t: 11)
    assert service.sync(club) is True
    update = stripe.made("POST", "/v1/subscriptions/sub_1")[-1]
    assert update == {
        "items[0][id]": "si_polls",
        "items[0][quantity]": "11",
        "proration_behavior": "create_prorations",
    }


def _signed(body: dict, secret=WEBHOOK_SECRET, stamp=None):
    payload = json.dumps(body).encode()
    stamp = stamp or int(time.time())
    sig = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256)
    return payload, f"t={stamp},v1={sig.hexdigest()}"


def test_signature_check():
    payload, header = _signed({"a": 1})
    assert stripe_api.verify_signature(payload, header, WEBHOOK_SECRET)
    assert not stripe_api.verify_signature(payload + b" ", header, WEBHOOK_SECRET)
    assert not stripe_api.verify_signature(payload, header, "whsec_other")
    old_payload, old = _signed({"a": 1}, stamp=int(time.time()) - 3600)
    assert not stripe_api.verify_signature(old_payload, old, WEBHOOK_SECRET)


WEBHOOK = "/api/v1/global/billing/stripe/webhook"


def test_webhook_updates_the_club(client, stripe, club, db):
    payload, header = _signed(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"tenant_id": str(club.id)},
                    "customer": "cus_1",
                    "subscription": "sub_1",
                }
            },
        }
    )
    resp = client.post(
        WEBHOOK,
        data=payload,
        headers={"Stripe-Signature": header},
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(club)
    assert service.state(club)["subscription_id"] == "sub_1"
    assert club_billing.stored(club)["status"] == "active"

    # A failed payment is found by the customer id alone.
    payload, header = _signed(
        {"type": "invoice.payment_failed", "data": {"object": {"customer": "cus_1"}}}
    )
    resp = client.post(
        WEBHOOK,
        data=payload,
        headers={"Stripe-Signature": header},
        content_type="application/json",
    )
    assert resp.status_code == 200
    db.session.refresh(club)
    assert service.state(club)["payment_failed_at"]

    bad = client.post(
        WEBHOOK,
        data=payload,
        headers={"Stripe-Signature": "t=1,v1=00"},
        content_type="application/json",
    )
    assert bad.status_code == 400


def test_reconcile_reads_every_subscription(stripe, club, db):
    service.apply_subscription(club, stripe.subscription)
    db.session.commit()
    stripe.subscription["status"] = "unpaid"
    assert service.reconcile() == {"done": 1, "failed": 0}
    db.session.refresh(club)
    assert club_billing.stored(club)["status"] == "unpaid"
    overview = service.overview()
    assert [t["slug"] for t in overview["trouble"]] == ["club-a"]


def test_club_routes_need_the_right(
    client,
    stripe,
    club,
    db,
    auth_headers,
    plain_member_token,  # noqa: F811
    monkeypatch,
):
    from hubra.api.billing import routes

    # Test requests have no club host; the routes read the club from g.tenant.
    monkeypatch.setattr(routes, "current_tenant", lambda: club)
    assert client.get("/api/v1/app/billing/").status_code == 403
    _login_member(client, "admin@test.ch")
    body = client.get("/api/v1/app/billing/").get_json()
    assert body["enabled"] is True and body["testMode"] is True
    assert "note" not in body and "sponsor_note" not in body
    assert body["stripe"]["hasSubscription"] is False
    assert body["canPay"] is True
    assert client.get("/api/v1/app/billing/invoices").get_json() == {"items": []}
    url = client.post("/api/v1/app/billing/checkout").get_json()["url"]
    assert url == "https://checkout.stripe.test/cs_1"
    contact = {
        "email": "rechnung@club.test",
        "street": "Seeweg",
        "houseNo": "3",
        "postalCode": "8000",
        "city": "Zürich",
        "country": "ch",
    }
    saved = client.put("/api/v1/app/billing/contact", json=contact).get_json()
    assert saved["own"] is True and saved["country"] == "CH"
    assert client.get("/api/v1/app/billing/contact").get_json() == saved
    bad = client.put("/api/v1/app/billing/contact", json={**contact, "email": "x"})
    assert bad.status_code == 400


def test_contact_falls_back_to_club_settings_and_reaches_stripe(stripe, club, db):
    from hubra.core.models.setting import Setting

    db.session.add(Setting(key="Club.Contact.FinanceEmail", value="kasse@club.test"))
    db.session.commit()
    c = service.contact(club)
    assert c["email"] == "kasse@club.test" and c["own"] is False
    # Without a Stripe customer only Hubra stores it.
    body = {"email": "rechnung@club.test", "postalCode": "3000", "city": "Bern"}
    assert service.set_contact(club, body)["email"] == "rechnung@club.test"
    assert stripe.made("POST", "/v1/customers/cus_1") == []
    # With one, the customer is updated at once.
    service.checkout(club, "admin@club.test", "https://s", "https://c")
    made = stripe.made("POST", "/v1/customers")[0]
    assert made["email"] == "rechnung@club.test"
    assert made["address[city]"] == "Bern"
    service.set_contact(club, {**body, "email": "neu@club.test", "street": "Gasse"})
    update = stripe.made("POST", "/v1/customers/cus_1")[0]
    assert update["email"] == "neu@club.test"
    assert update["address[line1]"] == "Gasse"
    assert update["address[country]"] == "CH"
    with pytest.raises(ApiError) as missing_city:
        service.set_contact(club, {"email": "a@b.ch", "postalCode": "3000"})
    assert missing_city.value.fields == {"city": "Postal code and city go together"}


def test_stripe_errors_keep_their_text_out_of_answers():
    down = stripe_api.StripeError("ProxyError: http://10.0.0.5:3128 refused")
    assert down.public_message() == "Stripe could not be reached"
    refused = stripe_api.StripeError("No such customer: cus_x", 404, "resource_missing")
    assert refused.public_message() == "Stripe refused the call (resource_missing)"
    odd = stripe_api.StripeError("x", 400, "<script>")
    assert odd.public_message() == "Stripe refused the call (400)"


def test_billing_can_use_its_own_stripe_account(stripe, db):
    assert service._key() == "sk_test_" + "a" * 24
    platform_settings.set_many({"billing.stripe.secret_key": "rk_live_" + "b" * 24})
    assert service._key() == "rk_live_" + "b" * 24
    assert service.test_mode() is False


def test_subscription_events_are_read_again_with_our_api_version(stripe, club, db):
    """A webhook on a newer API version carries the period end on the items
    only; Hubra reads the subscription itself and also copes with that shape."""
    service._save_state(club, {"customer_id": "cus_1"})
    db.session.commit()
    stripe.subscription["status"] = "past_due"
    newer = {
        "id": "sub_1",
        "customer": "cus_1",
        "status": "active",
        "items": {"data": [{"current_period_end": 1798761600}]},
    }
    assert (
        service.handle_event(
            {"type": "customer.subscription.updated", "data": {"object": newer}}
        )
        == "customer.subscription.updated"
    )
    db.session.refresh(club)
    assert club_billing.stored(club)["status"] == "past_due"
    assert service._period_end(newer) == 1798761600
    service.apply_subscription(club, newer)
    assert club_billing.stored(club)["period_end"] == "2027-01-01"


def test_club_platform_fee_overrides_the_default(stripe, club, db, app):
    from flask import g

    platform_settings.set_many({"payments.fee_percent": "1.5"})
    with app.test_request_context():
        assert platform_settings.stripe().fee_percent == 1.5
        g.tenant = club
        assert platform_settings.stripe().fee_percent == 1.5
        club_billing.update(club, {"payments_fee_percent": 3})
        assert platform_settings.stripe().fee_percent == 3.0
        club_billing.update(club, {"payments_fee_percent": 0})
        assert platform_settings.stripe().fee_percent == 0.0
        club_billing.update(club, {"payments_fee_percent": None})
        assert platform_settings.stripe().fee_percent == 1.5
    with pytest.raises(ApiError):
        club_billing.update(club, {"payments_fee_percent": 11})
    with pytest.raises(ApiError):
        club_billing.update(club, {"payments_fee_percent": True})


def test_club_changes_its_plan_and_add_ons(
    client,
    stripe,
    club,
    db,
    auth_headers,
    plain_member_token,
    monkeypatch,  # noqa: F811
):
    from hubra.api.billing import routes
    from hubra.core.services import quotas

    monkeypatch.setattr(routes, "current_tenant", lambda: club)
    monkeypatch.setattr(quotas, "member_count", lambda t: 12)
    plans.update(plans.get("starter"), {"public": True})
    plans.create(
        {"key": "club", "name_de": "Club", "price_month_chf": "60", "public": True}
    )
    plans.create(
        {"key": "tiny", "name_de": "Tiny", "public": True, "limit_members": 10}
    )
    plans.create({"key": "deal", "name_de": "Deal", "public": False})
    plans.set_addon(
        "polls", {"price_month_chf": "2", "price_unit": "member", "public": True}
    )
    plans.set_addon(
        "groups", {"price_month_chf": "5", "price_unit": "license", "public": True}
    )
    club.plan = "starter"
    db.session.commit()

    # Any member sees the prices; changing needs the billing right.
    _login_member(client, "admin@test.ch")
    cat = client.get("/api/v1/app/billing/catalog").get_json()
    assert [p["key"] for p in cat["plans"]] == ["starter", "club", "tiny"]
    offered = {a["code"]: a for a in cat["addons"]}
    assert offered["polls"]["source"] is None
    assert offered["polls"]["price_month_chf"] == "2.00"

    r = client.put("/api/v1/app/billing/plan", json={"plan": "deal"})
    assert r.status_code == 400
    r = client.put("/api/v1/app/billing/plan", json={"plan": "tiny"})
    assert r.status_code == 409 and r.get_json()["error"] == "PLAN_TOO_SMALL"
    r = client.put("/api/v1/app/billing/plan", json={"plan": "club"})
    assert r.status_code == 200 and r.get_json()["plan"] == "club"
    assert club.plan == "club"

    r = client.put("/api/v1/app/billing/addons/polls", json={"on": True})
    assert r.status_code == 200, r.get_json()
    line = next(x for x in r.get_json()["module_lines"] if x["code"] == "polls")
    assert line["quantity"] == 12 and line["total_chf"] == "24.00"
    r = client.put(
        "/api/v1/app/billing/addons/groups", json={"on": True, "licenses": 3}
    )
    line = next(x for x in r.get_json()["module_lines"] if x["code"] == "groups")
    assert line["quantity"] == 3 and line["total_chf"] == "15.00"
    bad = client.put("/api/v1/app/billing/addons/polls", json={"licenses": 3})
    assert bad.status_code == 400
    r = client.put("/api/v1/app/billing/addons/polls", json={"on": False})
    assert all(x["code"] != "polls" for x in r.get_json()["module_lines"])
    assert (
        client.put("/api/v1/app/billing/addons/nope", json={"on": True}).status_code
        == 404
    )

    _login_member(client, "plain@test.ch")
    assert client.get("/api/v1/app/billing/catalog").status_code == 200
    r = client.put("/api/v1/app/billing/plan", json={"plan": "starter"})
    assert r.status_code == 403
