"""Outgoing webhooks (docs/webhooks.md).

A club admin adds an https address and picks events. When one of them
happens, ``emit`` (hubra.core.modules.events) queues :func:`dispatch` for
after the commit, in the worker. It writes one :class:`WebhookDelivery` per
webhook and POSTs it, signed with the webhook's secret::

    X-Hubra-Event: member.joined
    X-Hubra-Delivery: <uuid, the same on every retry>
    X-Hubra-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<body>">

A failed delivery (no answer, or not 2xx) is tried again after 1 minute,
10 minutes and 1 hour. After ``MAX_FAILURES`` failed deliveries in a row
the webhook switches itself off and says why.

Only public https addresses are called: the host must resolve to public
addresses only, the connection goes to the address that was checked (no
second lookup a DNS answer could change), and redirects aren't followed.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import json
import logging
import secrets
import socket
import ssl
import time
import urllib.parse
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

# The events a webhook can listen to, in the order the settings show them.
EVENTS: tuple[str, ...] = (
    "member.joined",
    "member.left",
    "invoice.created",
    "invoice.paid",
    "invoice.overdue",
    "invoice.deleted",
    "event.published",
    "event.changed",
    "post.published",
    "poll.published",
    "poll.closed",
    "group.membership_changed",
)
PING = "ping"
MAX_WEBHOOKS = 10
MAX_FAILURES = 20
RETRY_DELAYS = (60, 600, 3600)
TIMEOUT = 5
KEEP_DELIVERIES = 50
SECRET_PURPOSE = "webhooks.secret"
USER_AGENT = "Hubra-Webhooks/1"


class WebhookUrlError(ValueError):
    """The address can't be called (not https, not public, malformed)."""


# ── Addresses ────────────────────────────────────────────────────────────────


def _resolve(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise WebhookUrlError(f"{host} could not be resolved") from exc
    addrs = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise WebhookUrlError(f"{host} is not a public address")
        addrs.append(str(ip))
    if not addrs:
        raise WebhookUrlError(f"{host} could not be resolved")
    return addrs


def parse_url(url: str) -> urllib.parse.SplitResult:
    """A plain https address with a host name; raises WebhookUrlError."""
    url = (url or "").strip()
    if len(url) > 500:
        raise WebhookUrlError("The address is too long")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        raise WebhookUrlError("Only https:// addresses")
    if not parts.hostname or parts.username or parts.password:
        raise WebhookUrlError("A plain https:// address without user or password")
    if any(c.isspace() for c in url):
        raise WebhookUrlError("No spaces in the address")
    try:
        parts.port  # noqa: B018  (raises on a bad port)
    except ValueError as exc:
        raise WebhookUrlError("The port is not valid") from exc
    return parts


def check_url(url: str) -> str:
    """Raise WebhookUrlError unless *url* is a public https address."""
    parts = parse_url(url)
    _resolve(parts.hostname, parts.port or 443)
    return url.strip()


class _PinnedHTTPS(http.client.HTTPSConnection):
    """Connects to an address checked beforehand, with SNI and the
    certificate check for the host name."""

    def __init__(self, host: str, ip: str, port: int, timeout: float):
        super().__init__(
            host, port, timeout=timeout, context=ssl.create_default_context()
        )
        self._ip = ip

    def connect(self) -> None:
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def post(url: str, body: bytes, headers: dict[str, str]) -> int:
    """POST *body*; returns the status code. Raises OSError or WebhookUrlError."""
    parts = parse_url(url)
    port = parts.port or 443
    ip = _resolve(parts.hostname, port)[0]
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    conn = _PinnedHTTPS(parts.hostname, ip, port, TIMEOUT)
    try:
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        resp.read(4096)
        return resp.status
    finally:
        conn.close()


# ── Signing ──────────────────────────────────────────────────────────────────


def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def signature(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return f"t={timestamp},v1={mac.hexdigest()}"


def seal(secret: str) -> str:
    from hubra.core.crypto import encrypt_code

    return encrypt_code(secret, SECRET_PURPOSE)


def unseal(stored: str) -> str:
    from hubra.core.crypto import decrypt_code

    return decrypt_code(stored, SECRET_PURPOSE)


# ── What the receiver gets ───────────────────────────────────────────────────


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _member(member_id) -> dict | None:
    from hubra.core.models.member import Member

    member = db.session.get(Member, member_id) if member_id else None
    if member is None:
        return None
    return {
        "id": member.id,
        "firstName": member.first_name,
        "lastName": member.last_name,
        "email": member.email or None,
        "status": member.status,
        "membershipType": member.membership_type,
        "tier": member.tier.name if member.tier else None,
        "joined": _plain(member.joined),
        "left": _plain(member.archived_at),
    }


def _object(event: str, data: dict) -> dict | None:
    """The thing the event is about, as the receiver needs it (or None)."""
    kind = event.split(".")[0]
    if kind == "member":
        return _member(data.get("member_id"))
    if kind == "invoice" and event != "invoice.deleted":
        from hubra.core.models.finance import Invoice

        inv = db.session.get(Invoice, data.get("invoice_id") or 0)
        if inv is None:
            return None
        return {
            "id": inv.id,
            "memberId": inv.member_id,
            "amount": _plain(inv.amount),
            "status": inv.status,
            "issued": _plain(inv.issued),
            "due": _plain(inv.due),
            "description": inv.description,
        }
    if kind == "event" and not data.get("deleted"):
        from hubra.core.models.event import ClubEvent

        ev = db.session.get(ClubEvent, data.get("event_id") or 0)
        if ev is None:
            return None
        return {
            "id": ev.id,
            "title": ev.title,
            "date": _plain(ev.date),
            "time": ev.time,
            "location": ev.location,
            "public": ev.is_public,
        }
    if kind == "post":
        from hubra.core.models.post import Post

        post_ = db.session.get(Post, data.get("post_id") or 0)
        return {"id": post_.id, "title": post_.title} if post_ else None
    if kind == "poll":
        from hubra.core.models.poll import Poll

        poll = db.session.get(Poll, data.get("poll_id") or 0)
        return (
            {"id": poll.id, "question": poll.question, "status": poll.status}
            if poll
            else None
        )
    return None


def build_body(event: str, data: dict, uid: str) -> str:
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    return json.dumps(
        {
            "id": uid,
            "event": event,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "club": {"slug": tenant.slug, "name": tenant.name} if tenant else None,
            "data": {k: _plain(v) for k, v in data.items()},
            "object": _object(event, data) if event != PING else None,
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ── Sending ──────────────────────────────────────────────────────────────────


def _trim(webhook_id: int) -> None:
    from hubra.core.models.webhook import WebhookDelivery

    old = db.session.scalars(
        select(WebhookDelivery.id)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.id.desc())
        .offset(KEEP_DELIVERIES)
    ).all()
    if old:
        db.session.query(WebhookDelivery).filter(WebhookDelivery.id.in_(old)).delete(
            synchronize_session=False
        )


def attempt(delivery) -> bool:
    """Send *delivery* once and record the outcome. True when delivered."""
    from hubra.core.models.webhook import Webhook

    hook = db.session.get(Webhook, delivery.webhook_id)
    if hook is None:
        return False
    body = delivery.body.encode()
    ts = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "X-Hubra-Event": delivery.event,
        "X-Hubra-Delivery": delivery.uid,
        "X-Hubra-Signature": signature(unseal(hook.secret), ts, body),
    }
    started = time.monotonic()
    delivery.attempts += 1
    delivery.last_attempt_at = datetime.now(timezone.utc)
    try:
        status = post(hook.url, body, headers)
        ok = 200 <= status < 300
        delivery.response_status = status
        delivery.error = None if ok else f"HTTP {status}"
    except (OSError, WebhookUrlError, http.client.HTTPException) as exc:
        ok = False
        delivery.response_status = None
        delivery.error = (str(exc) or exc.__class__.__name__)[:500]
    delivery.duration_ms = int((time.monotonic() - started) * 1000)
    hook.last_delivery_at = delivery.last_attempt_at
    if ok:
        delivery.status = "delivered"
        hook.failures = 0
    elif delivery.attempts > len(RETRY_DELAYS) or delivery.event == PING:
        delivery.status = "failed"
    if not ok:
        hook.failures += 1
        if hook.failures >= MAX_FAILURES and hook.active:
            hook.active = False
            hook.disabled_reason = (
                f"Switched off after {MAX_FAILURES} failed deliveries in a row"
            )
    return ok


def _schedule_retry(delivery) -> None:
    if delivery.status != "pending":
        return
    from hubra.core.tasks.webhook_tasks import retry_delivery

    delay = RETRY_DELAYS[min(delivery.attempts, len(RETRY_DELAYS)) - 1]
    if retry_delivery.app.conf.task_always_eager:
        return  # tests retry by hand
    retry_delivery.apply_async(args=(delivery.id,), countdown=delay)


def send(hook, event: str, data: dict):
    """Create a delivery of *event* for *hook* and try it now."""
    from hubra.core.models.webhook import WebhookDelivery

    uid = str(uuid.uuid4())
    delivery = WebhookDelivery(
        webhook_id=hook.id, uid=uid, event=event, body=build_body(event, data, uid)
    )
    db.session.add(delivery)
    db.session.flush()
    attempt(delivery)
    _trim(hook.id)
    db.session.commit()
    _schedule_retry(delivery)
    return delivery


def dispatch(tenant_id=None, *, event: str, data: dict) -> None:
    """Send *event* to every active webhook of the club that listens to it.

    Runs in the worker after the commit (the ``webhooks`` module's handler,
    see ``emit``).
    """
    from hubra.core.models.webhook import Webhook

    hooks = [
        h
        for h in db.session.scalars(select(Webhook).where(Webhook.active.is_(True)))
        if event in (h.events or [])
    ]
    for hook in hooks:
        try:
            send(hook, event, data)
        except Exception:
            db.session.rollback()
            _log.exception("Webhook %s: couldn't deliver %s", hook.id, event)
