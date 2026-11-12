"""Hubra's own billing of clubs (docs/billing.md, ``hubra.core.billing``).

Club app, ``/api/v1/app/billing`` (needs ``billing.billing.manage``):

* ``GET  /``          what the club pays, the status, Stripe's side
* ``POST /checkout``  a Stripe Checkout page that starts paying
* ``POST /portal``    Stripe's customer portal (card, invoices, cancel)
* ``POST /cancel``    cancel: runs to the end of the paid period, then ends
* ``POST /resume``    take the cancellation back before the period ends
* ``GET  /invoices``  the last Stripe invoices
* ``GET  /catalog``   plans and paid modules with prices (any member: the
  modules page shows the prices)
* ``PUT  /plan``      switch to another plan the club may pick
* ``PUT  /addons/<code>``  take or drop a paid module, set its licences
* ``PUT  /licenses/<code>``  give the module's licences to members

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
from hubra.core.permissions import permission_required, require_member
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
            "enabled": service.enabled(tenant),
            "testMode": service.test_mode(tenant),
            "yearly": service.yearly(),
            "canPay": service.enabled(tenant) and bool(service.items(tenant)),
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


@billing_bp.get("/limits")
@permission_required(*PERM)
def get_limits():
    """Members, mails and storage against the club's limits, the grace period
    at the member limit and the cheapest plan that fits (``LIMIT_NEAR`` in
    ``code`` when a limit is close or reached)."""
    from hubra.core.services import quotas

    view = quotas.club_view(current_tenant())
    tight = any(r["level"] != "ok" for r in view["limits"].values())
    return jsonify({**view, "code": "LIMIT_NEAR" if tight else None}), 200


@billing_bp.get("/catalog")
@require_member
def get_catalog():
    """Plans and paid modules with their prices. Prices are public
    (``/api/v1/public/pricing``); every member may see them."""
    from hubra.core.billing import self_service

    return jsonify(self_service.catalog(current_tenant())), 200


def _after_terms_change(tenant, action: str, details: dict):
    """Audit, commit and push the new terms to a running subscription."""
    from hubra.core.models.tenant import GlobalAuditEntry
    from hubra.core.services import club_billing

    member = get_current_member()
    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant.id,
            action=action,
            target_type="Tenant",
            target_id=str(tenant.id),
            details={**details, "member_id": getattr(member, "id", None)},
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    stripe_error = None
    try:
        if service.sync(tenant):
            db.session.commit()
    except StripeError as exc:
        db.session.rollback()
        logger.warning("billing_sync_failed tenant=%s error=%s", tenant.id, exc)
        stripe_error = exc.public_message()
    summary = club_billing.summary(tenant)
    return jsonify(
        {
            **{k: summary.get(k) for k in _CLUB_FIELDS},
            "stripeError": stripe_error,
        }
    ), 200


@billing_bp.put("/plan")
@permission_required(*PERM)
def put_plan():
    """Switch to another plan the club may pick; the next invoice has the new price."""
    from hubra.core.billing import self_service

    tenant = current_tenant()
    before = tenant.plan
    key = (request.get_json(silent=True) or {}).get("plan")
    if not self_service.choose_plan(tenant, key):
        return get_billing()
    return _after_terms_change(
        tenant, "tenant.plan.self", {"before": before, "after": tenant.plan}
    )


@billing_bp.put("/addons/<string:code>")
@permission_required(*PERM)
def put_addon(code: str):
    """``{"on": bool?, "licenses": int?}``: take or drop a paid module."""
    from hubra.core.billing import self_service
    from hubra.core.utils import log_audit

    tenant = current_tenant()
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not ({"on", "licenses"} & set(body)):
        return api_error("VALIDATION_ERROR", "Send on and/or licenses", 400)
    self_service.set_addon(tenant, code, body)
    member = get_current_member()
    if "on" in body:
        log_audit(
            getattr(member, "id", None),
            "enable_module" if body["on"] else "disable_module",
            "module",
            None,
            code,
        )
    return _after_terms_change(
        tenant,
        "tenant.addon.self",
        {"code": code, **{k: body[k] for k in ("on", "licenses") if k in body}},
    )


@billing_bp.put("/licenses/<string:code>")
@permission_required(*PERM)
def put_license_holders(code: str):
    """``{"memberIds": [..]}``: the members who may use a licensed module."""
    from hubra.core.models.tenant import GlobalAuditEntry
    from hubra.core.services import licenses

    tenant = current_tenant()
    ids = licenses.set_holders(
        tenant, code, (request.get_json(silent=True) or {}).get("memberIds")
    )
    member = get_current_member()
    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant.id,
            action="tenant.licenses",
            target_type="Tenant",
            target_id=str(tenant.id),
            details={
                "code": code,
                "member_ids": ids,
                "member_id": getattr(member, "id", None),
            },
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    return jsonify(
        {"code": code, "holders": licenses.holder_rows(tenant).get(code, [])}
    ), 200


@billing_bp.post("/portal")
@permission_required(*PERM)
def open_portal():
    tenant = current_tenant()
    try:
        url = service.portal(tenant, _settings_url(tenant))
    except StripeError as exc:
        return _stripe_failed(exc)
    return jsonify({"url": url}), 200


def _change_subscription(action: str, change):
    from hubra.core.models.tenant import GlobalAuditEntry

    tenant = current_tenant()
    member = get_current_member()
    try:
        change(tenant)
    except StripeError as exc:
        db.session.rollback()
        return _stripe_failed(exc)
    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant.id,
            action=action,
            target_type="Tenant",
            target_id=str(tenant.id),
            details={"member_id": getattr(member, "id", None)},
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    return get_billing()


@billing_bp.post("/cancel")
@permission_required(*PERM)
def cancel_subscription():
    """Cancel the club's subscription: it runs to the end of the period
    already paid (or of the trial), then ends. Nothing more is charged."""
    return _change_subscription("tenant.billing.cancel", service.cancel)


@billing_bp.post("/resume")
@permission_required(*PERM)
def resume_subscription():
    """Take a cancellation back while the period still runs."""
    return _change_subscription("tenant.billing.resume", service.resume)


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

    secrets = platform_settings.billing_webhook_secrets()
    if not secrets:
        return api_error("BILLING_OFF", "No webhook secret is set", 503)
    payload = request.get_data(cache=False)
    header = request.headers.get("Stripe-Signature", "")
    # The live and the sandbox webhook both point here; the event's own
    # livemode tells which one it comes from (service.handle_event).
    if not any(
        stripe_api.verify_signature(payload, header, secret)
        for secret in secrets.values()
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
