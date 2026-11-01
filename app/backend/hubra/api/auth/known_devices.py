"""Tell an account when it is signed into from a new device or browser.

Each browser keeps a random token in the ``hubra_device`` cookie, which
outlives sign-out.  A sign-in whose token this account has not seen before
is from a new device: the account gets a mail with the time, IP address and
browser, and a link to its sessions on the SSO portal.

The first device an account is seen with (a new account, or every account
right after this feature shipped) is learnt without a mail.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app
from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.known_device import KnownDevice
from hubra.core.models.user import User

_log = logging.getLogger(__name__)

DEVICE_COOKIE = "hubra_device"
# Chrome caps cookie lifetimes at 400 days.
_COOKIE_MAX_AGE = 400 * 24 * 3600


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def remember(
    user: User, token: str | None, browser_family: str = "", platform: str = ""
) -> tuple[str, bool]:
    """Note this sign-in's browser for *user*.  Does NOT commit.

    Returns ``(token, alert)``: the token to keep in the cookie, and whether
    the account should hear about a sign-in from a new device.
    """
    if not token or len(token) > 128:
        token = secrets.token_urlsafe(32)
    token_hash = _hash(token)
    now = datetime.now(timezone.utc)

    known = db.session.scalar(
        select(KnownDevice).where(
            KnownDevice.user_id == user.id, KnownDevice.token_hash == token_hash
        )
    )
    if known is not None:
        known.last_seen_at = now
        return token, False

    first = (
        db.session.scalar(
            select(KnownDevice.id).where(KnownDevice.user_id == user.id).limit(1)
        )
        is None
    )
    db.session.add(
        KnownDevice(
            user_id=user.id,
            token_hash=token_hash,
            browser_family=browser_family or None,
            platform=platform or None,
            created_at=now,
            last_seen_at=now,
        )
    )
    db.session.flush()
    return token, not first


def set_cookie(response, token: str) -> None:
    """Keep the device token on the shared domain; sign-out leaves it."""
    response.set_cookie(
        DEVICE_COOKIE,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=current_app.config.get("JWT_COOKIE_SECURE", False),
        domain=current_app.config.get("JWT_COOKIE_DOMAIN") or None,
    )


def sign_in_time(now: datetime | None = None) -> str:
    """The time for the mail, in the platform's time zone (MAIL_TIMEZONE)."""
    now = now or datetime.now(timezone.utc)
    try:
        zone = ZoneInfo(current_app.config.get("MAIL_TIMEZONE") or "Europe/Zurich")
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    local = now.astimezone(zone)
    return f"{local:%d.%m.%Y %H:%M} {local.tzname()}"


def send_alert(
    user: User, ip: str, browser_family: str, platform: str, user_agent: str
) -> None:
    """Mail the account about a sign-in from a new device.

    Only to a confirmed address: an unconfirmed one may not be theirs.
    """
    if not user.private_email_verified:
        _log.info("skip_new_device_login user_id=%s — email not verified", user.id)
        return
    from hubra.core.services import email as email_svc

    try:
        email_svc.send_new_device_login(
            user.email,
            user.name,
            ip=ip,
            browser_family=browser_family,
            platform=platform,
            user_agent=user_agent,
            timestamp=sign_in_time(),
            lang=user.language or "de-CH",
        )
    except Exception:
        # A mail problem never stops the sign-in.
        _log.exception("new_device_login mail failed user_id=%s", user.id)
