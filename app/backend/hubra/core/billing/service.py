"""What a club pays Hubra, charged with Stripe Billing (docs/billing.md).

The terms stay where manage keeps them (``services.club_billing``: plan,
own price, discount, sponsor, add-ons). This module turns them into one
Stripe subscription per club and keeps the two in step:

* a club admin starts paying through Stripe Checkout (``checkout``) and
  manages the card and invoices in Stripe's customer portal (``portal``);
* Stripe tells Hubra what happened by webhook (``handle_event``), and an
  hourly job (``reconcile``) reads every subscription again, so a missed
  webhook only delays the status;
* when manage changes a club's terms, the subscription's items are replaced
  from the next invoice on (``sync``, no proration).

Stripe's side lives in ``tenant.settings["billing_stripe"]`` (customer,
subscription, its status and period, the last failed payment); the club's
status and period end in the terms follow it.  Products have fixed ids
(``hubra_plan_<plan>``, ``hubra_module_<code>``); prices are sent inline
(``price_data``), so a club's own price needs no Stripe price object.

Off until a platform admin turns ``billing.enabled`` on; the Stripe key is
the platform's (``payments.stripe.secret_key``).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from hubra.core.billing import stripe_api
from hubra.core.billing.stripe_api import StripeError
from hubra.core.errors import ApiError
from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant

logger = logging.getLogger(__name__)

STATE_KEY = "billing_stripe"
# Stripe statuses the terms know; the rest map onto them.
_STATUS_MAP = {"incomplete_expired": "canceled"}
# A subscription in one of these still runs (or may run again): no second one.
RUNNING = ("trialing", "active", "past_due", "unpaid", "incomplete", "paused")
TROUBLE = ("past_due", "unpaid", "incomplete")
# Checkout only takes a trial end at least this far ahead.
_MIN_TRIAL = timedelta(days=2, hours=1)
_PRODUCT_ID = re.compile(r"[^a-z0-9_]+")


# ── Settings ────────────────────────────────────────────────────────────────


def _key() -> str | None:
    from hubra.core.services import platform_settings

    stripe = platform_settings.stripe()
    return stripe.secret_key if stripe else None


def _setting(key: str) -> str:
    from hubra.core.services import platform_settings

    try:
        return platform_settings.get(key) or ""
    except Exception:  # noqa: BLE001
        return ""


def enabled() -> bool:
    """Billing is on and a Stripe key is set."""
    return _setting("billing.enabled") == "on" and bool(_key())


def yearly() -> bool:
    return _setting("billing.yearly") == "on"


def test_mode() -> bool:
    return "_test_" in (_key() or "")


def _need_key() -> str:
    key = _key()
    if not key or _setting("billing.enabled") != "on":
        raise ApiError(503, "BILLING_OFF", "Billing is not switched on")
    return key


# ── Stripe state on the club ────────────────────────────────────────────────


def state(tenant: Tenant) -> dict:
    return dict((tenant.settings or {}).get(STATE_KEY) or {})


def _save_state(tenant: Tenant, values: dict) -> dict:
    settings = dict(tenant.settings or {})
    merged = {**(settings.get(STATE_KEY) or {}), **values}
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()
    settings[STATE_KEY] = merged
    tenant.settings = settings
    flag_modified(tenant, "settings")
    return merged


def public_state(tenant: Tenant) -> dict:
    """Stripe's side, without ids a club has no use for."""
    s = state(tenant)
    return {
        "hasCustomer": bool(s.get("customer_id")),
        "hasSubscription": bool(s.get("subscription_id"))
        and s.get("status") in RUNNING,
        "status": s.get("status"),
        "currentPeriodEnd": s.get("current_period_end"),
        "cancelAtPeriodEnd": bool(s.get("cancel_at_period_end")),
        "paymentFailedAt": s.get("payment_failed_at"),
    }


# ── What the club pays, as subscription items ───────────────────────────────


def _rappen(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1"), ROUND_HALF_UP))


def _product_id(kind: str, code: str) -> str:
    slug = _PRODUCT_ID.sub("_", (code or "").lower()).strip("_")[:50] or "x"
    return f"hubra_{kind}_{slug}"


def items(tenant: Tenant, today: date | None = None) -> list[dict]:
    """The subscription's lines: the plan (own price less discount) and each
    module or add-on with a price, per month or per year (``billing.yearly``).
    Empty while a sponsorship runs or the club is not billed."""
    from hubra.core.services import club_billing

    summary = club_billing.summary(tenant, today)
    if summary["sponsorship_running"]:
        return []
    months = 12 if yearly() else 1
    out: list[dict] = []
    base = Decimal(summary["base_chf"]) - Decimal(summary["discount_chf"])
    if base > 0:
        out.append(
            {
                "product": _product_id("plan", tenant.plan),
                "name": f"Hubra {tenant.plan}",
                "unit_amount": _rappen(base * months),
                "quantity": 1,
            }
        )
    for line in summary["module_lines"]:
        each = Decimal(line["unit_price_chf"])
        if line["included"] or each <= 0 or line["quantity"] <= 0:
            continue
        out.append(
            {
                "product": _product_id("module", line["code"]),
                "name": f"Hubra {line['label'] or line['code']}",
                "unit_amount": _rappen(each * months),
                "quantity": int(line["quantity"]),
            }
        )
    return out


def _signature(lines: list[dict]) -> str:
    return json.dumps(
        sorted((x["product"], x["unit_amount"], x["quantity"]) for x in lines),
        separators=(",", ":"),
    )


def _price_data(line: dict) -> dict:
    return {
        "currency": "chf",
        "product": line["product"],
        "unit_amount": line["unit_amount"],
        "recurring": {"interval": "year" if yearly() else "month"},
    }


_known_products: set[str] = set()


def _ensure_products(key: str, lines: list[dict]) -> None:
    """Products have fixed ids, so each is made once, on first use."""
    for line in lines:
        pid = line["product"]
        if pid in _known_products:
            continue
        try:
            stripe_api.call(key, "GET", f"/v1/products/{pid}")
        except StripeError as exc:
            if exc.status != 404:
                raise
            stripe_api.call(
                key,
                "POST",
                "/v1/products",
                {"id": pid, "name": line["name"]},
                idempotency_key=f"hubra-product-{pid}",
            )
        _known_products.add(pid)


# ── Club admin: start paying, manage payment ────────────────────────────────


def _ensure_customer(key: str, tenant: Tenant, email: str | None) -> str:
    s = state(tenant)
    if s.get("customer_id"):
        return s["customer_id"]
    customer = stripe_api.call(
        key,
        "POST",
        "/v1/customers",
        {
            "name": tenant.name,
            "email": email or None,
            "metadata": {"tenant_id": tenant.id, "slug": tenant.slug},
            "preferred_locales": [tenant.locale or "de-CH"],
        },
        idempotency_key=f"hubra-customer-{tenant.id}",
    )
    _save_state(tenant, {"customer_id": customer["id"]})
    return customer["id"]


def checkout(
    tenant: Tenant, email: str | None, success_url: str, cancel_url: str
) -> str:
    """A Stripe Checkout page that starts the club's subscription.  Commits
    the new customer id.  Returns the page's address."""
    from hubra.core.services import club_billing

    key = _need_key()
    if public_state(tenant)["hasSubscription"]:
        raise ApiError(409, "ALREADY_SUBSCRIBED", "The club already pays by Stripe")
    lines = items(tenant)
    if not lines:
        raise ApiError(400, "NOTHING_TO_PAY", "The club has nothing to pay")
    _ensure_products(key, lines)
    customer = _ensure_customer(key, tenant, email)
    db.session.commit()
    sub: dict = {"metadata": {"tenant_id": tenant.id}}
    terms = club_billing.stored(tenant)
    if terms["status"] == "trialing" and terms["trial_ends"]:
        end = datetime.combine(
            date.fromisoformat(terms["trial_ends"]),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ) + timedelta(hours=12)
        if end - datetime.now(timezone.utc) >= _MIN_TRIAL:
            sub["trial_end"] = int(end.timestamp())
    session = stripe_api.call(
        key,
        "POST",
        "/v1/checkout/sessions",
        {
            "mode": "subscription",
            "customer": customer,
            "client_reference_id": str(tenant.id),
            "line_items": [
                {"price_data": _price_data(x), "quantity": x["quantity"]} for x in lines
            ],
            "subscription_data": sub,
            "metadata": {"tenant_id": tenant.id},
            "locale": "de" if (tenant.locale or "de").startswith("de") else "auto",
            "success_url": success_url,
            "cancel_url": cancel_url,
        },
    )
    return session["url"]


def portal(tenant: Tenant, return_url: str) -> str:
    """Stripe's customer portal: card, invoices, cancel."""
    key = _need_key()
    customer = state(tenant).get("customer_id")
    if not customer:
        raise ApiError(409, "NO_CUSTOMER", "The club doesn't pay by Stripe yet")
    session = stripe_api.call(
        key,
        "POST",
        "/v1/billing_portal/sessions",
        {"customer": customer, "return_url": return_url},
    )
    return session["url"]


def invoices(tenant: Tenant, limit: int = 12) -> list[dict]:
    key = _key()
    customer = state(tenant).get("customer_id")
    if not key or not customer:
        return []
    found = stripe_api.call(
        key, "GET", "/v1/invoices", {"customer": customer, "limit": limit}
    )
    out = []
    for inv in found.get("data") or []:
        out.append(
            {
                "id": inv.get("id"),
                "number": inv.get("number"),
                "created": _iso(inv.get("created")),
                "status": inv.get("status"),
                "totalChf": f"{Decimal(inv.get('total') or 0) / 100:.2f}",
                "paid": bool(inv.get("paid")) or inv.get("status") == "paid",
                "url": inv.get("hosted_invoice_url"),
                "pdf": inv.get("invoice_pdf"),
            }
        )
    return out


# ── Stripe → Hubra ──────────────────────────────────────────────────────────


def _iso(stamp) -> str | None:
    if not stamp:
        return None
    return datetime.fromtimestamp(int(stamp), tz=timezone.utc).isoformat()


def apply_subscription(tenant: Tenant, sub: dict) -> None:
    """Store a subscription Stripe sent or returned, and let the club's
    status and period end follow it.  Does NOT commit."""
    from hubra.core.services import club_billing

    before = state(tenant).get("status")
    status = sub.get("status") or "incomplete"
    _save_state(
        tenant,
        {
            "subscription_id": sub.get("id"),
            "customer_id": sub.get("customer") or state(tenant).get("customer_id"),
            "status": status,
            "current_period_end": _iso(sub.get("current_period_end")),
            "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        },
    )
    terms_status = _STATUS_MAP.get(status, status)
    change = {}
    if terms_status in club_billing.STATUSES:
        change["status"] = terms_status
    end = sub.get("current_period_end")
    if end:
        change["period_end"] = (
            datetime.fromtimestamp(int(end), tz=timezone.utc).date().isoformat()
        )
    trial_end = sub.get("trial_end")
    if status == "trialing" and trial_end:
        change["trial_ends"] = (
            datetime.fromtimestamp(int(trial_end), tz=timezone.utc).date().isoformat()
        )
    if change:
        club_billing.update(tenant, change)
    if status in TROUBLE and before not in TROUBLE:
        _alert(tenant, status)


def _alert(tenant: Tenant, status: str) -> None:
    from hubra.core.services import platform_monitor

    label = {
        "past_due": "Zahlung überfällig",
        "unpaid": "Unbezahlt",
        "incomplete": "Zahlung nicht abgeschlossen",
        "payment_failed": "Zahlung fehlgeschlagen",
    }.get(status, status)
    platform_monitor.alert(
        "billing",
        f"{tenant.name}: {label}",
        [
            f"Verein: {tenant.name} ({tenant.slug})",
            f"Stripe: {status}",
        ],
        level="warning",
        throttle=False,
        link=f"/app/tenants/{tenant.id}",
    )


def _tenant_for(obj: dict) -> Tenant | None:
    meta = obj.get("metadata") or {}
    tid = meta.get("tenant_id") or obj.get("client_reference_id")
    if tid and str(tid).isdigit():
        tenant = db.session.get(Tenant, int(tid))
        if tenant is not None:
            return tenant
    customer = obj.get("customer")
    if not customer:
        return None
    for tenant in db.session.scalars(select(Tenant)).all():
        if state(tenant).get("customer_id") == customer:
            return tenant
    return None


def handle_event(event: dict) -> str:
    """One verified webhook event.  Commits.  Returns what was done."""
    kind = event.get("type") or ""
    obj = (event.get("data") or {}).get("object") or {}
    tenant = _tenant_for(obj)
    if tenant is None:
        return "ignored"
    key = _key()
    if kind == "checkout.session.completed":
        sub_id = obj.get("subscription")
        if obj.get("customer"):
            _save_state(tenant, {"customer_id": obj["customer"]})
        if sub_id and key:
            apply_subscription(
                tenant, stripe_api.call(key, "GET", f"/v1/subscriptions/{sub_id}")
            )
            _save_state(tenant, {"synced": _signature(items(tenant))})
    elif kind.startswith("customer.subscription."):
        apply_subscription(tenant, obj)
    elif kind == "invoice.payment_failed":
        _save_state(
            tenant, {"payment_failed_at": datetime.now(timezone.utc).isoformat()}
        )
        _alert(tenant, "payment_failed")
    elif kind == "invoice.paid":
        _save_state(tenant, {"payment_failed_at": None})
    else:
        return "ignored"
    db.session.commit()
    return kind


# ── Keeping Stripe in step ──────────────────────────────────────────────────


def sync(tenant: Tenant, force: bool = False) -> bool:
    """Replace the subscription's items when the club's terms changed.  The
    new amounts apply from the next invoice (no proration).  Does NOT commit.
    Returns True when Stripe was changed."""
    key = _key()
    s = state(tenant)
    if not key or not s.get("subscription_id") or s.get("status") not in RUNNING:
        return False
    lines = items(tenant)
    signature = _signature(lines)
    if not force and s.get("synced") == signature:
        return False
    if not lines:
        # Nothing to charge any more (say a sponsor took over): leave the
        # subscription to manage, which cancels it in Stripe.
        return False
    _ensure_products(key, lines)
    sub = stripe_api.call(key, "GET", f"/v1/subscriptions/{s['subscription_id']}")
    old = [
        {"id": it["id"], "deleted": True}
        for it in (sub.get("items") or {}).get("data") or []
    ]
    new = [{"price_data": _price_data(x), "quantity": x["quantity"]} for x in lines]
    updated = stripe_api.call(
        key,
        "POST",
        f"/v1/subscriptions/{s['subscription_id']}",
        {"items": old + new, "proration_behavior": "none"},
    )
    apply_subscription(tenant, updated)
    _save_state(tenant, {"synced": signature})
    return True


def refresh(tenant: Tenant) -> None:
    """Read the club's subscription from Stripe again and sync the terms.
    Does NOT commit."""
    key = _key()
    sub_id = state(tenant).get("subscription_id")
    if not key or not sub_id:
        return
    apply_subscription(
        tenant, stripe_api.call(key, "GET", f"/v1/subscriptions/{sub_id}")
    )
    sync(tenant)


def reconcile() -> dict:
    """Every club with a subscription, read again (the hourly job)."""
    done = failed = 0
    if not enabled():
        return {"done": 0, "failed": 0}
    for tenant in db.session.scalars(
        select(Tenant).where(Tenant.deleted_at.is_(None))
    ).all():
        if not state(tenant).get("subscription_id"):
            continue
        try:
            refresh(tenant)
            db.session.commit()
            done += 1
        except Exception:  # noqa: BLE001
            db.session.rollback()
            failed += 1
            logger.warning(
                "billing_reconcile_failed tenant=%s", tenant.id, exc_info=True
            )
    return {"done": done, "failed": failed}


# ── Manage: the whole picture ───────────────────────────────────────────────


def overview(today: date | None = None) -> dict:
    """Monthly revenue, clubs per status and the clubs with a payment problem."""
    from hubra.core.services import club_billing

    per_status: dict[str, int] = {}
    mrr = Decimal("0")
    trouble = []
    paying = 0
    for tenant in db.session.scalars(
        select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.name)
    ).all():
        terms = club_billing.stored(tenant)
        status = terms["status"]
        per_status[status] = per_status.get(status, 0) + 1
        s = state(tenant)
        if status in ("active", "past_due", "unpaid") or s.get("status") in TROUBLE:
            summary = club_billing.summary(tenant, today)
            due = Decimal(summary["due_chf"])
            if status in ("active", "past_due"):
                mrr += due
                paying += 1 if due > 0 else 0
            if status in TROUBLE or s.get("payment_failed_at"):
                trouble.append(
                    {
                        "id": tenant.id,
                        "name": tenant.name,
                        "slug": tenant.slug,
                        "status": status,
                        "dueChf": summary["due_chf"],
                        "paymentFailedAt": s.get("payment_failed_at"),
                        "periodEnd": terms["period_end"],
                    }
                )
    return {
        "enabled": enabled(),
        "testMode": test_mode(),
        "yearly": yearly(),
        "mrrChf": f"{mrr.quantize(Decimal('0.01'))}",
        "arrChf": f"{(mrr * 12).quantize(Decimal('0.01'))}",
        "payingClubs": paying,
        "perStatus": per_status,
        "trouble": trouble,
    }
