"""Tell an account when it is signed into from a new device or browser.

Only sign-ins to the account itself (the SSO portal) count; signing in to a
club neither alerts nor teaches a device.

Each browser keeps a random token in the ``hubra_device`` cookie, which
outlives sign-out.  The token decides: a known token is a known device.  A
browser without the cookie (cleared, private window) is checked against a
softer signature: browser, system, language, time zone and IP network
(``soft_signature``).  When the account saw that signature in the last
``SOFT_DAYS`` days it is "probably you": no alert, and the browser gets a new
token.  Otherwise it is a new device: the account gets a mail (and, when it
asked for it, a Discord direct message) with the time, IP address, browser
and system with versions, how it signed in, the active sessions, and links
to its sessions and to "This wasn't me", which ends every session.

The first device an account is seen with (a new account, or every account
right after this feature shipped) is learnt without a mail.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app
from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.known_device import KnownDevice
from hubra.core.models.user import User

_log = logging.getLogger(__name__)

DEVICE_COOKIE = "hubra_device"
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{32,128}")
# Chrome caps cookie lifetimes at 400 days.
_COOKIE_MAX_AGE = 400 * 24 * 3600
# A matching soft signature seen this recently counts as a known device.
SOFT_DAYS = 30
# "This wasn't me" links stay valid this long.
NOT_ME_MAX_AGE = 7 * 24 * 3600
_NOT_ME_SALT = "hubra-not-me"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def ip_network(ip: str) -> str:
    """The network an address belongs to: /24 for IPv4, /48 for IPv6 (a
    home or office line keeps it while the last part changes)."""
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return ""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{addr}/{prefix}", strict=False))


def soft_signature(
    browser_family: str, platform: str, language: str, time_zone: str, ip: str
) -> str | None:
    """Hash of what a browser shows without its cookie, or None when too
    little is known to tell browsers apart."""
    network = ip_network(ip)
    if not network or not browser_family or browser_family == "Unknown":
        return None
    lang = (language or "").split(",")[0].split(";")[0].strip().lower()
    raw = "|".join(
        (browser_family, platform or "", lang, (time_zone or "")[:64], network)
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def remember(
    user: User,
    token: str | None,
    browser_family: str = "",
    platform: str = "",
    soft: str | None = None,
) -> tuple[str | None, bool]:
    """Note this sign-in's browser for *user*.  Does NOT commit.

    *soft*: the browser's ``soft_signature``.  Returns ``(token, alert)``: a
    freshly made token to set as the cookie (None when the browser is known
    already and keeps its cookie), and whether the account should hear about
    a sign-in from a new device.
    """
    now = datetime.now(timezone.utc)
    if token and _TOKEN_RE.fullmatch(token):
        # The browser keeps the cookie it has; it is only looked up here and
        # never written back, so the cookie value is always one of ours.
        token_hash = _hash(token)
        known = db.session.scalar(
            select(KnownDevice).where(
                KnownDevice.user_id == user.id, KnownDevice.token_hash == token_hash
            )
        )
        if known is not None:
            known.last_seen_at = now
            if soft:
                known.soft_hash = soft
            return None, False
        new_token = None
    else:
        new_token = secrets.token_urlsafe(32)
        token_hash = _hash(new_token)

    first = (
        db.session.scalar(
            select(KnownDevice.id).where(KnownDevice.user_id == user.id).limit(1)
        )
        is None
    )
    # No cookie we know: a recent browser with the same signature is
    # probably this one after its cookies were cleared.
    probably_known = soft is not None and (
        db.session.scalar(
            select(KnownDevice.id)
            .where(
                KnownDevice.user_id == user.id,
                KnownDevice.soft_hash == soft,
                KnownDevice.last_seen_at >= now - timedelta(days=SOFT_DAYS),
            )
            .limit(1)
        )
        is not None
    )
    db.session.add(
        KnownDevice(
            user_id=user.id,
            token_hash=token_hash,
            soft_hash=soft,
            browser_family=browser_family or None,
            platform=platform or None,
            created_at=now,
            last_seen_at=now,
        )
    )
    db.session.flush()
    return new_token, not first and not probably_known


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


_BROWSER_VERSION = (
    ("Edge", re.compile(r"Edg(?:e|A|iOS)?/(\d+)")),
    ("Opera", re.compile(r"OPR/(\d+)")),
    ("Firefox", re.compile(r"(?:Firefox|FxiOS)/(\d+)")),
    ("Chrome", re.compile(r"(?:Chrome|CriOS)/(\d+)")),
    ("Safari", re.compile(r"Version/(\d+(?:\.\d+)?)")),
)
_OS_VERSION = (
    ("iOS", re.compile(r"(?:iPhone|CPU) OS (\d+(?:_\d+)?)")),
    ("Android", re.compile(r"Android (\d+(?:\.\d+)?)")),
    ("macOS", re.compile(r"Mac OS X (\d+[_.]\d+)")),
)


def describe_device(user_agent: str, browser_family: str, platform: str) -> str:
    """"Chrome 141 on Android 14": the browser and system with their main
    versions where the user agent says them (Windows and macOS freeze
    theirs, so those stay plain)."""
    ua = user_agent or ""
    browser = browser_family if browser_family and browser_family != "Unknown" else ""
    for family, pattern in _BROWSER_VERSION:
        if family == browser and (m := pattern.search(ua)):
            browser = f"{browser} {m.group(1)}"
            break
    system = platform if platform and platform != "Unknown" else ""
    for family, pattern in _OS_VERSION:
        if family == system and family != "macOS" and (m := pattern.search(ua)):
            system = f"{system} {m.group(1).replace('_', '.')}"
            break
    if browser and system:
        return f"{browser} · {system}"
    return browser or system or ua[:120] or "?"


def not_me_token(user: User) -> str:
    """A signed token for "This wasn't me": it ends every session of the
    account, once (it stops working when the sessions were ended since)."""
    from itsdangerous import URLSafeTimedSerializer

    cutoff = user.tokens_valid_after
    stamp = int(cutoff.timestamp()) if cutoff else 0
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt=_NOT_ME_SALT
    )
    return serializer.dumps({"u": user.id, "c": stamp})


def read_not_me_token(token: str) -> User | None:
    """The account a "This wasn't me" token is for, while it is valid."""
    from itsdangerous import BadSignature, URLSafeTimedSerializer

    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt=_NOT_ME_SALT
    )
    try:
        data = serializer.loads(token, max_age=NOT_ME_MAX_AGE)
    except (BadSignature, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    user = db.session.get(User, data.get("u"))
    if user is None:
        return None
    cutoff = user.tokens_valid_after
    stamp = int(cutoff.timestamp()) if cutoff else 0
    return user if stamp == data.get("c") else None


def sign_in_info(
    user: User,
    *,
    ip: str,
    browser_family: str,
    platform: str,
    user_agent: str,
    method: str = "password",
    second_step: str = "",
) -> dict:
    """What the alert says about a sign-in (the mail and the Discord message).

    *method*: ``password`` or ``passkey``; *second_step*: ``totp``,
    ``recovery``, ``passkey`` or "" (none).
    """
    from hubra.core.auth import session_service
    from hubra.core.services.email import _get_sso_base_url

    sso = _get_sso_base_url()
    try:
        sessions = len(session_service.list_account_sessions(user))
    except Exception:  # noqa: BLE001
        sessions = None
    return {
        "time": sign_in_time(),
        "ip": ip or "?",
        "device": describe_device(user_agent, browser_family, platform),
        "method": method,
        "second_step": second_step,
        "sessions": sessions,
        "sessions_url": f"{sso}/account/sitzungen" if sso else "",
        "not_me_url": f"{sso}/not-me#token={not_me_token(user)}" if sso else "",
    }


_METHOD = {
    "password": ("Passwort", "Password"),
    "passkey": ("Passkey", "Passkey"),
}
_SECOND = {
    "totp": ("Code aus der App", "Code from the app"),
    "recovery": ("Wiederherstellungscode", "Recovery code"),
    "passkey": ("Passkey", "Passkey"),
    "": ("Keiner", "None"),
}


def _label(table: dict, key: str, lang: str) -> str:
    de, en = table.get(key, (key, key))
    return en if str(lang).startswith("en") else de


def send_alert(
    user: User,
    ip: str,
    browser_family: str,
    platform: str,
    user_agent: str,
    *,
    method: str = "password",
    second_step: str = "",
) -> None:
    """Tell the account about a sign-in from a new device, once the sign-in
    is committed (queued: the SMTP hand-off must not slow the sign-in): by
    mail to a confirmed address (an unconfirmed one may not be theirs), and
    as a Discord direct message when the account asked for it."""
    info = sign_in_info(
        user,
        ip=ip,
        browser_family=browser_family,
        platform=platform,
        user_agent=user_agent,
        method=method,
        second_step=second_step,
    )
    lang = user.language or "de-CH"
    shown = {
        **info,
        "method": _label(_METHOD, method, lang),
        "second_step": _label(_SECOND, second_step, lang),
    }
    try:
        from hubra.core.notifications import account_dm

        embed, components = account_dm.sign_in_embed(user, shown)
        account_dm.send(user, "sign_in", embed, components)
    except Exception:  # noqa: BLE001
        _log.warning("new_device_login dm not queued", exc_info=True)
    if not user.private_email_verified:
        _log.info("skip_new_device_login user_id=%s — email not verified", user.id)
        return
    queue_mail(
        user.email,
        user.name,
        ip=ip,
        browser_family=browser_family,
        platform=platform,
        user_agent=user_agent,
        lang=lang,
        details={
            k: shown[k]
            for k in ("device", "method", "second_step", "sessions", "not_me_url")
        },
    )


def queue_mail(
    address: str,
    name: str,
    *,
    ip: str,
    browser_family: str,
    platform: str,
    user_agent: str,
    lang: str,
    details: dict | None = None,
) -> None:
    """Queue the new-device mail to *address*, sent after the commit."""
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.email_tasks import send_new_device_login_task

    try:
        delay_after_commit(
            send_new_device_login_task,
            address,
            name,
            ip,
            browser_family,
            platform,
            user_agent,
            sign_in_time(),
            lang,
            details,
        )
    except Exception:
        # A mail problem never stops the sign-in.
        _log.exception("new_device_login mail not queued")
