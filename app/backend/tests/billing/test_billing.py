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
        if path == "/v1/customers":
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


def test_sync_replaces_items_when_terms_change(stripe, club, db):
    service.apply_subscription(club, stripe.subscription)
    assert service.sync(club) is True
    update = stripe.made("POST", "/v1/subscriptions/sub_1")[-1]
    assert update["items[0][id]"] == "si_old"
    assert update["items[0][deleted]"] == "true"
    assert update["items[1][price_data][unit_amount]"] == "3000"
    assert update["proration_behavior"] == "none"
    # Nothing changed: no second update.
    assert service.sync(club) is False
    club_billing.update(club, {"discount_percent": 0})
    assert service.sync(club) is True
    assert (
        stripe.made("POST", "/v1/subscriptions/sub_1")[-1][
            "items[1][price_data][unit_amount]"
        ]
        == "4000"
    )


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
    client, stripe, club, db, auth_headers, plain_member_token, monkeypatch  # noqa: F811
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
