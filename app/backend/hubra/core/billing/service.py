"""What a club pays Hubra, charged with Stripe Billing (docs/billing.md).

The terms stay where manage keeps them (``services.club_billing``: plan,
own price, discount, sponsor, add-ons). This module turns them into one
Stripe subscription per club and keeps the two in step:

* a club admin starts paying through Stripe Checkout (``checkout``) and
  manages the card and invoices in Stripe's customer portal (``portal``);
* Stripe tells Hubra what happened by webhook (``handle_event``), and an
  hourly job (``reconcile``) reads every subscription again, so a missed
  webhook only delays the status;
* when the club's terms change (manage, the club itself, the member count),
  the changed items are updated with ``create_prorations``: the rest of the
  period is charged or credited pro rata on the next invoice (``sync``).

Stripe's side lives in ``tenant.settings["billing_stripe"]`` (customer,
subscription, its status and period, the last failed payment), or in
``billing_stripe_sandbox`` while the club runs on the sandbox keys, so
switching ``stripe.mode`` never mixes test and live ids; the club's
status and period end in the terms follow it.  Products have fixed ids
(``hubra_plan_<plan>``, ``hubra_module_<code>``); prices are sent inline
(``price_data``), so a club's own price needs no Stripe price object.

Off until a platform admin turns ``billing.enabled`` on.  The Stripe key is
the billing key of the club's mode (``platform_settings.stripe_mode``:
sandbox clubs and sandbox mode use the sandbox key).
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
SANDBOX_STATE_KEY = "billing_stripe_sandbox"
# Stripe statuses the terms know; the rest map onto them.
_STATUS_MAP = {"incomplete_expired": "canceled"}
# A subscription in one of these still runs (or may run again): no second one.
RUNNING = ("trialing", "active", "past_due", "unpaid", "incomplete", "paused")
TROUBLE = ("past_due", "unpaid", "incomplete")
# Checkout only takes a trial end at least this far ahead.
_MIN_TRIAL = timedelta(days=2, hours=1)
_PRODUCT_ID = re.compile(r"[^a-z0-9_]+")


# ── Settings ────────────────────────────────────────────────────────────────


def mode(tenant: Tenant | None = None) -> str:
    """``sandbox`` or ``live`` for *tenant* (default: this request's club)."""
    from hubra.core.services import platform_settings

    return platform_settings.stripe_mode(tenant)


def _key(tenant: Tenant | None = None) -> str | None:
    """The billing key of *tenant*'s mode; without one, the Online payments
    key of that mode."""
    from hubra.core.services import platform_settings

    return platform_settings.billing_stripe_key(mode(tenant)) or None


def _setting(key: str) -> str:
    from hubra.core.services import platform_settings

    try:
        return platform_settings.get(key) or ""
    except Exception:  # noqa: BLE001
        return ""


def enabled(tenant: Tenant | None = None) -> bool:
    """Billing is on and *tenant*'s mode has a Stripe key."""
    return _setting("billing.enabled") == "on" and bool(_key(tenant))


def yearly() -> bool:
    return _setting("billing.yearly") == "on"


def test_mode(tenant: Tenant | None = None) -> bool:
    from hubra.core.services import platform_settings

    return mode(tenant) == platform_settings.SANDBOX


def _need_key(tenant: Tenant) -> str:
    key = _key(tenant)
    if not key or _setting("billing.enabled") != "on":
        raise ApiError(503, "BILLING_OFF", "Billing is not switched on")
    return key


# ── Stripe state on the club ────────────────────────────────────────────────


def _state_key(tenant: Tenant) -> str:
    from hubra.core.services import platform_settings

    return SANDBOX_STATE_KEY if mode(tenant) == platform_settings.SANDBOX else STATE_KEY


def state(tenant: Tenant, live: bool | None = None) -> dict:
    """Stripe's side in *tenant*'s current mode (or the live one with
    ``live=True``)."""
    key = STATE_KEY if live else _state_key(tenant)
    return dict((tenant.settings or {}).get(key) or {})


def _save_state(tenant: Tenant, values: dict) -> dict:
    settings = dict(tenant.settings or {})
    key = _state_key(tenant)
    merged = {**(settings.get(key) or {}), **values}
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()
    settings[key] = merged
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


def _club_setting(key: str) -> str:
    """One of the club's own settings (current tenant), empty if unset."""
    try:
        from hubra.core.services.settings import SettingService

        return (SettingService.get(key, default="") or "").strip()
    except Exception:  # noqa: BLE001
        return ""


CONTACT_KEY = "billing_contact"
CONTACT_FIELDS = ("email", "street", "houseNo", "postalCode", "city", "country")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def contact(tenant: Tenant) -> dict:
    """Where Hubra's invoices go: the club's billing email and address.

    Set by the club on its subscription tab (``tenant.settings
    ["billing_contact"]``). Until then it is taken from the club's settings:
    the finance email and the address of its QR bills."""
    own = (tenant.settings or {}).get(CONTACT_KEY)
    if isinstance(own, dict):
        out = {f: str(own.get(f) or "") for f in CONTACT_FIELDS}
        out["country"] = out["country"] or "CH"
        return {**out, "own": True}
    return {
        "email": _club_setting("Club.Contact.FinanceEmail"),
        "street": _club_setting("Club.Banking.Street"),
        "houseNo": _club_setting("Club.Banking.HouseNo"),
        "postalCode": _club_setting("Club.Banking.PostalCode"),
        "city": _club_setting("Club.Banking.City"),
        "country": _club_setting("Club.Banking.Country") or "CH",
        "own": False,
    }


def _stripe_address(c: dict) -> dict | None:
    """A Stripe address, or None without postal code and city."""
    if not c.get("postalCode") or not c.get("city"):
        return None
    street = " ".join(x for x in (c.get("street"), c.get("houseNo")) if x)
    return {
        "line1": street or None,
        "postal_code": c["postalCode"],
        "city": c["city"],
        "country": (c.get("country") or "CH").upper()[:2],
    }


def _invalid(field: str, message: str):
    raise ApiError(400, "VALIDATION_ERROR", message, {field: message})


def set_contact(tenant: Tenant, body: dict) -> dict:
    """Store the club's billing email and address, and copy them to its
    Stripe customer if it has one.  Does NOT commit."""
    clean: dict[str, str] = {}
    for f in CONTACT_FIELDS:
        value = body.get(f, "")
        if value is None:
            value = ""
        if not isinstance(value, str) or len(value) > 200:
            _invalid(f, f"{f} must be text of up to 200 characters")
        clean[f] = value.strip()
    if not clean["email"] or not _EMAIL.match(clean["email"]):
        _invalid("email", "A valid email is needed")
    clean["country"] = (clean["country"] or "CH").upper()
    if not re.fullmatch(r"[A-Z]{2}", clean["country"]):
        _invalid("country", "Country is a two-letter code")
    if bool(clean["postalCode"]) != bool(clean["city"]):
        _invalid(
            "city" if clean["postalCode"] else "postalCode",
            "Postal code and city go together",
        )
    settings = dict(tenant.settings or {})
    settings[CONTACT_KEY] = clean
    tenant.settings = settings
    flag_modified(tenant, "settings")
    customer = state(tenant).get("customer_id")
    key = _key(tenant)
    if customer and key:
        update: dict = {"email": clean["email"]}
        address = _stripe_address(clean)
        if address:
            update["address"] = address
        stripe_api.call(key, "POST", f"/v1/customers/{customer}", update)
    return contact(tenant)


def _ensure_customer(key: str, tenant: Tenant, email: str | None) -> str:
    """The club's Stripe customer: named after the club, with the club's
    billing email (else the paying admin's) and address."""
    s = state(tenant)
    if s.get("customer_id"):
        return s["customer_id"]
    c = contact(tenant)
    body: dict = {
        "name": tenant.name,
        "email": c["email"] or email or None,
        "metadata": {"tenant_id": tenant.id, "slug": tenant.slug},
        "preferred_locales": [tenant.locale or "de-CH"],
    }
    address = _stripe_address(c)
    if address:
        body["address"] = address
    customer = stripe_api.call(
        key,
        "POST",
        "/v1/customers",
        body,
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

    key = _need_key(tenant)
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
            # The invoice goes to the club: Checkout asks for its billing
            # address (prefilled when the club has one) and stores it on the
            # customer, so every invoice shows it.
            "billing_address_collection": "required",
            "customer_update": {"address": "auto"},
            "metadata": {"tenant_id": tenant.id},
            "locale": "de" if (tenant.locale or "de").startswith("de") else "auto",
            "success_url": success_url,
            "cancel_url": cancel_url,
        },
    )
    return session["url"]


def portal(tenant: Tenant, return_url: str) -> str:
    """Stripe's customer portal: card, invoices, cancel."""
    key = _need_key(tenant)
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
    key = _key(tenant)
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
            "current_period_end": _iso(_period_end(sub)),
            "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        },
    )
    terms_status = _STATUS_MAP.get(status, status)
    change = {}
    if terms_status in club_billing.STATUSES:
        change["status"] = terms_status
    end = _period_end(sub)
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


def _period_end(sub: dict):
    """On the subscription, or (newer API versions) on its items."""
    if sub.get("current_period_end"):
        return sub["current_period_end"]
    ends = [
        i.get("current_period_end")
        for i in ((sub.get("items") or {}).get("data") or [])
        if i.get("current_period_end")
    ]
    return min(ends) if ends else None


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
    """One verified webhook event.  Commits.  Returns what was done.  An
    event from the other mode than the club's (``livemode``: a sandbox event
    naming a live club, or the other way round) is ignored."""
    from hubra.core.services import platform_settings

    kind = event.get("type") or ""
    obj = (event.get("data") or {}).get("object") or {}
    tenant = _tenant_for(obj)
    if tenant is None:
        return "ignored"
    if "livemode" in event:
        sent_from = (
            platform_settings.LIVE if event["livemode"] else platform_settings.SANDBOX
        )
        if sent_from != mode(tenant):
            return "ignored"
    key = _key(tenant)
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
        # The payload follows the webhook's API version, which may be newer
        # than ours (from 2025-03-31 the period end sits on the items): read
        # the subscription again with our pinned version.
        if key and obj.get("id"):
            obj = stripe_api.call(key, "GET", f"/v1/subscriptions/{obj['id']}")
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


def _item_changes(current: list[dict], lines: list[dict]) -> list[dict]:
    """The subscription item updates that turn *current* into *lines*: only
    what differs. An unchanged line is left alone, so Stripe's prorations
    show just the real change (a new member, an add-on), not a credit and a
    new charge for every line."""
    by_product: dict[str, dict] = {}
    extra: list[dict] = []
    for it in current:
        price = it.get("price") or {}
        product = price.get("product")
        if isinstance(product, dict):
            product = product.get("id")
        if product and product not in by_product:
            by_product[product] = it
        else:
            extra.append(it)
    out: list[dict] = []
    for line in lines:
        it = by_product.pop(line["product"], None)
        if it is None:
            out.append({"price_data": _price_data(line), "quantity": line["quantity"]})
            continue
        price = it.get("price") or {}
        same_price = (
            price.get("unit_amount") == line["unit_amount"]
            and ((price.get("recurring") or {}).get("interval"))
            == _price_data(line)["recurring"]["interval"]
        )
        if not same_price:
            out.append(
                {
                    "id": it["id"],
                    "price_data": _price_data(line),
                    "quantity": line["quantity"],
                }
            )
        elif int(it.get("quantity") or 0) != line["quantity"]:
            out.append({"id": it["id"], "quantity": line["quantity"]})
    for it in [*by_product.values(), *extra]:
        out.append({"id": it["id"], "deleted": True})
    return out


def sync(tenant: Tenant, force: bool = False) -> bool:
    """Bring the subscription's items in step with the club's terms.

    Only lines that changed are touched, with ``create_prorations``: a
    member who joins, an add-on taken or a plan change mid-period is charged
    pro rata for the rest of the period on the next invoice (and a member
    who leaves or an add-on dropped is credited there), besides the full
    new amount for the next period (docs/billing.md). Does NOT commit.
    Returns True when Stripe was changed."""
    key = _key(tenant)
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
    changes = _item_changes((sub.get("items") or {}).get("data") or [], lines)
    if not changes:
        _save_state(tenant, {"synced": signature})
        return False
    # Stripe doesn't prorate while a trial runs: nothing is charged yet.
    updated = stripe_api.call(
        key,
        "POST",
        f"/v1/subscriptions/{s['subscription_id']}",
        {"items": changes, "proration_behavior": "create_prorations"},
    )
    apply_subscription(tenant, updated)
    _save_state(tenant, {"synced": signature})
    return True


def refresh(tenant: Tenant) -> None:
    """Read the club's subscription from Stripe again and sync the terms.
    Does NOT commit."""
    key = _key(tenant)
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
    if _setting("billing.enabled") != "on":
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
    """Monthly revenue, clubs per status and the clubs with a payment problem.
    Sandbox clubs are only counted (``sandboxClubs``): their money isn't real."""
    from hubra.core.services import club_billing, sandbox_clubs

    per_status: dict[str, int] = {}
    mrr = Decimal("0")
    trouble = []
    paying = sandbox = 0
    for tenant in db.session.scalars(
        select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.name)
    ).all():
        if sandbox_clubs.is_sandbox(tenant):
            sandbox += 1
            continue
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
        "sandboxClubs": sandbox,
        "perStatus": per_status,
        "trouble": trouble,
    }
