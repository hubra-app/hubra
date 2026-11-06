"""Hubra's own billing of clubs (docs/billing.md, ``hubra.core.billing``).

Club app, ``/api/v1/app/billing`` (needs ``billing.billing.manage``):

* ``GET  /``          what the club pays, the status, Stripe's side
* ``POST /checkout``  a Stripe Checkout page that starts paying
* ``POST /portal``    Stripe's customer portal (card, invoices, cancel)
* ``GET  /invoices``  the last Stripe invoices

Sign-in area, ``/api/v1/global/billing`` (no sign-in, signed by Stripe):

* ``POST /stripe/webhook``
"""

from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, request

from hubra.core.auth.helpers import get_current_member
from hubra.core.billing import service, stripe_api
from hubra.core.billing.stripe_api import StripeError
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.permissions import permission_required
from hubra.core.tenant.context import current_tenant

logger = logging.getLogger(__name__)

billing_bp = Blueprint("billing_bp", __name__)
billing_webhook_bp = Blueprint("billing_webhook_bp", __name__)

PERM = ("billing", "manage", "Manage the club's Hubra subscription")
# Fields of the terms a club sees: not manage's notes or the sponsor's note.
_CLUB_FIELDS = (
    "plan",
    "status",
    "trial_ends",
    "period_end",
    "plan_price_chf",
    "base_chf",
    "discount_percent",
    "discount_chf",
    "addons_chf",
    "module_lines",
    "members",
    "total_chf",
    "due_chf",
    "sponsored",
    "sponsor_name",
    "sponsored_until",
    "sponsorship_running",
    "sponsorship_days_left",
    "sponsorship_ending_soon",
    "trial_days_left",
)


def _settings_url(tenant, query: str = "") -> str:
    from hubra.core.services.email import _get_base_url

    base = _get_base_url() or request.host_url.rstrip("/")
    return f"{base}/{tenant.slug}/app/settings/subscription{query}"


def _payments_fee() -> float | None:
    """The platform fee on the club's online member payments, if any."""
    from hubra.core.services import platform_settings

    stripe = platform_settings.stripe()
    return stripe.fee_percent if stripe else None


def _stripe_failed(exc: StripeError):
    logger.warning(
        "billing_stripe_error status=%s code=%s error=%s", exc.status, exc.code, exc
    )
    return api_error("STRIPE_ERROR", exc.public_message(), 502)


@billing_bp.get("/")
@permission_required(*PERM)
def get_billing():
    from hubra.core.services import club_billing

    tenant = current_tenant()
    summary = club_billing.summary(tenant)
    return jsonify(
        {
            **{k: summary.get(k) for k in _CLUB_FIELDS},
            "enabled": service.enabled(),
            "testMode": service.test_mode(),
            "yearly": service.yearly(),
            "canPay": service.enabled() and bool(service.items(tenant)),
            "stripe": service.public_state(tenant),
            "paymentsFeePercent": _payments_fee(),
        }
    ), 200


@billing_bp.post("/checkout")
@permission_required(*PERM)
def start_checkout():
    tenant = current_tenant()
    member = get_current_member()
    try:
        url = service.checkout(
            tenant,
            getattr(member, "email", None),
            success_url=_settings_url(tenant, "?checkout=done"),
            cancel_url=_settings_url(tenant, "?checkout=cancelled"),
        )
    except StripeError as exc:
        db.session.rollback()
        return _stripe_failed(exc)
    return jsonify({"url": url}), 200


@billing_bp.get("/contact")
@permission_required(*PERM)
def get_contact():
    """Where Hubra's invoices go: billing email and address."""
    return jsonify(service.contact(current_tenant())), 200


@billing_bp.put("/contact")
@permission_required(*PERM)
def put_contact():
    """Change the billing email and address; copied to Stripe at once."""
    tenant = current_tenant()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return api_error("VALIDATION_ERROR", "Send the billing details", 400)
    try:
        data = service.set_contact(tenant, body)
    except StripeError as exc:
        db.session.rollback()
        return _stripe_failed(exc)
    db.session.commit()
    return jsonify(data), 200


@billing_bp.post("/portal")
@permission_required(*PERM)
def open_portal():
    tenant = current_tenant()
    try:
        url = service.portal(tenant, _settings_url(tenant))
    except StripeError as exc:
        return _stripe_failed(exc)
    return jsonify({"url": url}), 200


@billing_bp.post("/refresh")
@permission_required(*PERM)
def refresh():
    """Read Stripe again (after coming back from Checkout)."""
    tenant = current_tenant()
    try:
        service.refresh(tenant)
        db.session.commit()
    except StripeError as exc:
        db.session.rollback()
        return _stripe_failed(exc)
    return jsonify({"stripe": service.public_state(tenant)}), 200


@billing_bp.get("/invoices")
@permission_required(*PERM)
def list_invoices():
    try:
        found = service.invoices(current_tenant())
    except StripeError as exc:
        return _stripe_failed(exc)
    return jsonify({"items": found}), 200


@billing_webhook_bp.post("/stripe/webhook")
def stripe_webhook():
    from hubra.core.services import platform_settings

    secret = platform_settings.get("billing.stripe.webhook_secret")
    if not secret:
        return api_error("BILLING_OFF", "No webhook secret is set", 503)
    payload = request.get_data(cache=False)
    if not stripe_api.verify_signature(
        payload, request.headers.get("Stripe-Signature", ""), secret
    ):
        return api_error("BAD_SIGNATURE", "Signature does not match", 400)
    try:
        event = json.loads(payload)
    except ValueError:
        return api_error("VALIDATION_ERROR", "Not JSON", 400)
    try:
        done = service.handle_event(event)
    except StripeError as exc:
        db.session.rollback()
        # Stripe sends it again later.
        return _stripe_failed(exc)
    return jsonify({"received": True, "handled": done}), 200
