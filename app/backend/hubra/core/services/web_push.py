"""Web Push (RFC 8030/8291/8292): signed, encrypted messages to browsers.

A browser that allows notifications gives the club app a subscription (a
push service URL plus two keys). Hubra encrypts each message to those keys
(aes128gcm) and signs the request with the platform's VAPID key, so only that
browser can read it and the push service knows it comes from Hubra.

Only the big browsers' push services are called: the URL comes from the
browser, and the server must not post to any address someone sends it.
"""

from __future__ import annotations

import base64
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

_log = logging.getLogger(__name__)

# Chrome/Edge/Android (FCM), Firefox, Safari/iOS, legacy Edge (WNS).
_PUSH_HOSTS = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    ".push.services.mozilla.com",
    ".push.apple.com",
    ".notify.windows.com",
)
# The browser still shows a push that waited this long (seconds).
DEFAULT_TTL = 24 * 3600


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def generate_vapid_keys() -> tuple[str, str]:
    """A new P-256 key pair as (public, private), both base64url."""
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64(public), _b64(private)


def is_push_endpoint(url: str | None) -> bool:
    if not url or len(url) > 2000:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.port not in (None, 443):
        return False
    return any(
        host.endswith(h) if h.startswith(".") else host == h for h in _PUSH_HOSTS
    )


def valid_keys(p256dh: str | None, auth: str | None) -> bool:
    try:
        point = _unb64(p256dh or "")
        secret = _unb64(auth or "")
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
    except (ValueError, TypeError):
        return False
    return len(secret) == 16


@dataclass(frozen=True)
class PushResult:
    ok: bool
    # The subscription is gone for good (unsubscribed, expired): delete it.
    gone: bool = False
    status: int | None = None


def _vapid_header(endpoint: str, private_key: str, contact: str) -> str:
    from py_vapid import Vapid02

    parsed = urlparse(endpoint)
    vapid = Vapid02.from_raw(private_key.encode())
    claims = {
        "aud": f"{parsed.scheme}://{parsed.netloc}",
        "exp": int(time.time()) + 12 * 3600,
        "sub": contact,
    }
    return vapid.sign(claims)["Authorization"]


def encrypt(payload: bytes, p256dh: str, auth: str) -> bytes:
    import http_ece

    return http_ece.encrypt(
        payload,
        private_key=ec.generate_private_key(ec.SECP256R1()),
        dh=_unb64(p256dh),
        auth_secret=_unb64(auth),
        version="aes128gcm",
    )


def send(
    subscription,
    message: dict,
    keys,
    *,
    ttl: int = DEFAULT_TTL,
    topic: str | None = None,
    timeout: float = 10,
) -> PushResult:
    """Push *message* (JSON) to one subscription."""
    if not is_push_endpoint(subscription.endpoint):
        return PushResult(ok=False, gone=True)
    body = encrypt(
        json.dumps(message, ensure_ascii=False).encode(),
        subscription.p256dh,
        subscription.auth,
    )
    headers = {
        "Authorization": _vapid_header(
            subscription.endpoint, keys.private_key, keys.contact
        ),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Urgency": "normal",
    }
    if topic:
        headers["Topic"] = topic  # a newer push with the same topic replaces it
    request = urllib.request.Request(
        subscription.endpoint, data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            return PushResult(ok=True, status=resp.status)
    except urllib.error.HTTPError as exc:
        # 404/410: unsubscribed or expired. 400/403: keys no longer match.
        gone = exc.code in (400, 403, 404, 410)
        if not gone:
            _log.warning("web push failed: %s %s", exc.code, exc.reason)
        return PushResult(ok=False, gone=gone, status=exc.code)
    except (urllib.error.URLError, TimeoutError) as exc:
        _log.warning("web push service unreachable: %s", exc)
        return PushResult(ok=False)
