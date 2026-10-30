"""Transactional email via SMTP.

All public send_* functions log errors and return silently on failure -- email
delivery issues must never block member creation or other core operations.

Each send_* function accepts a *lang* parameter (default ``"de-CH"``) used to
resolve translations from the Translation table with fallback chain:
    de-CH -> [de-CH, en-GB]
    en-GB -> [en-GB]
    other -> [de-CH, en-GB]

Every mail goes through the platform relay (``platform_settings.relay()``,
set in the manager portal, defaults from SMTP_* / MAIL_FROM in env):

* System mail (``system=True``: password reset, verification, password
  changed, new sign-in, account deleted) is sent from the platform sender.
* Club mail is sent from the platform sender with the club's
  ``club.notification_sender_email`` as Reply-To.  A club with its own sender
  mailbox (InternalKey ``mail.smtp.user`` / ``mail.smtp.password``, from the
  mail module) sends as that mailbox, through the mail module's own server
  (``ZONEMTA_SMTP_HOST``) or else the platform relay.
* With no platform sender configured, both fall back to the club sender, as
  before the platform relay existed.

A mail the platform relay refuses (send quota, outage, login) is sent again
through the fallback relay when one is set (``mail.fallback.*``).  After a
relay failure the fallback succeeded on, the relay is skipped for a while
(``_PRIMARY_DOWN_SECONDS``, kept in Redis), so a quota does not cost a failed
attempt per mail.  Club mailboxes never use the fallback.
"""

from __future__ import annotations

import base64
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from flask import current_app

from hubra.core.services import platform_settings

from hubra.core.services.mail_i18n import render_mail_template

logger = logging.getLogger(__name__)

DEFAULT_LANG = "de-CH"


class EmailDeliveryError(Exception):
    """Raised when a transactional email fails to send."""


def _get_setting(key: str, default: str = "") -> str:
    """Read a single value from the Setting KV store, returning *default* on miss or error."""
    try:
        from hubra.api.settings.services import SettingService

        return SettingService.get(key, default=default) or default
    except Exception as exc:
        logger.warning("Could not load setting %r: %s", key, exc)
        return default


def club_display_name(default: str = "Hubra") -> str:
    """The club's name for mail and invoices: the ``club.name`` setting when
    the club set one, otherwise its name on the platform."""
    name = _get_setting("club.name", "")
    if name:
        return name
    try:
        from hubra.core.tenant.context import current_tenant

        tenant = current_tenant()
    except Exception:
        tenant = None
    return (tenant.name if tenant is not None else "") or default


def _get_base_url() -> str:
    """Return the frontend's base URL for link generation (password-reset, etc.).

    The API lives on api.hubra.club and the frontend SPA on app.hubra.club,
    so request.url_root (which resolves to the API host) must NOT be used to build
    links that open the frontend. FRONTEND_BASE_URL is the canonical frontend
    origin (e.g. https://app.hubra.club).

    A request-context fallback to request.url_root is intentionally omitted —
    every link generated here must point at the frontend, never the API host.
    """
    base = current_app.config.get("FRONTEND_BASE_URL", "")
    return str(base).rstrip("/") if base else ""


def _get_sso_base_url() -> str:
    """Return the SSO portal's base URL for auth-related email links.

    Password-reset and email-verification links should point to the SSO portal
    (sso.hubra.club) so users land on the centralized login experience.
    Falls back to _get_base_url() for backward compatibility when SSO_BASE_URL
    is not configured.
    """
    sso_base = current_app.config.get("SSO_BASE_URL", "")
    if sso_base:
        return str(sso_base).rstrip("/")
    return _get_base_url()


@dataclass(frozen=True)
class _Route:
    host: str
    port: int
    user: str
    password: str


def _club_mailbox() -> tuple[str, str] | None:
    """The club's own sender mailbox login, if the mail module set one."""
    try:
        from hubra.core.services.key_service import KeyService

        user = str(KeyService.get("mail.smtp.user") or "")
        password = str(KeyService.get("mail.smtp.password") or "")
    except Exception:
        return None
    return (user, password) if user and password else None


def _mailbox_route(platform, mailbox: tuple[str, str]) -> _Route:
    """A club mailbox logs in to the mail module's server, not an outside relay."""
    cfg = current_app.config
    host = cfg.get("ZONEMTA_SMTP_HOST") or platform.host
    port = int(cfg.get("ZONEMTA_SMTP_PORT") or 0) or platform.port
    return _Route(host, port, *mailbox)


_SMTP_TIMEOUT = 30  # seconds

_PRIMARY_DOWN_KEY = "mail:relay:primary_down"
_PRIMARY_DOWN_SECONDS = 15 * 60


def _primary_down() -> bool:
    """Whether a recent relay failure says to try the fallback first."""
    from hubra.core.redis_client import get_redis_client, mark_redis_down

    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.exists(_PRIMARY_DOWN_KEY))
    except Exception:
        mark_redis_down()
        return False


def _mark_primary_down() -> None:
    from hubra.core.redis_client import get_redis_client, mark_redis_down

    client = get_redis_client()
    if client is None:
        return
    try:
        client.set(_PRIMARY_DOWN_KEY, "1", ex=_PRIMARY_DOWN_SECONDS)
    except Exception:
        mark_redis_down()


def _fallback_route() -> _Route | None:
    fb = platform_settings.fallback_relay()
    return _Route(fb.host, fb.port, fb.user, fb.password) if fb else None


def _deliver(route: _Route, sender_email: str, to_email: str, message: str) -> None:
    """Hand one message to *route*; raises whatever smtplib raises."""
    smtp_host = route.host or "localhost"
    smtp_port = route.port
    _smtp_context = ssl.create_default_context()
    if current_app.config.get("SMTP_TLS_VERIFY", True) is False:
        _smtp_context.check_hostname = False
        _smtp_context.verify_mode = ssl.CERT_NONE
    # A timeout, so a relay that stops answering fails the send (and
    # the task's retry) instead of holding a worker forever. Port 465
    # is TLS from the first byte; the others upgrade with STARTTLS.
    if smtp_port == 465:
        connection = smtplib.SMTP_SSL(
            smtp_host, smtp_port, timeout=_SMTP_TIMEOUT, context=_smtp_context
        )
    else:
        connection = smtplib.SMTP(smtp_host, smtp_port, timeout=_SMTP_TIMEOUT)
    with connection as server:
        server.ehlo()
        if smtp_port not in (25, 465):
            server.starttls(context=_smtp_context)
            server.ehlo()
        if route.user and route.password:
            server.login(route.user, route.password)
        server.sendmail(sender_email, [to_email], message)


def _send_via_smtp(
    to_email: str,
    to_name: str,
    sender_email: str,
    sender_name: str,
    subject: str,
    body_html: str,
    body_text: str,
    attachments: list[dict] | None = None,
    *,
    reply_to: str | None = None,
    route: _Route | None = None,
    via: str | None = None,
) -> bool:
    """Send one email over SMTP.  *route* defaults to the platform relay,
    with the fallback relay behind it.  ``via="relay"`` or ``"fallback"``
    uses only that one (the manager portal's test mail).

    Returns True on success, raises EmailDeliveryError on failure.
    """
    fallback: _Route | None = None
    if route is None:
        r = platform_settings.relay()
        primary = _Route(r.host, r.port, r.user, r.password)
        if via == "fallback":
            route = _fallback_route()
            if route is None:
                raise EmailDeliveryError("No fallback relay is set")
        else:
            route = primary
            if via != "relay":
                fallback = _fallback_route()

    if attachments:
        msg = MIMEMultipart("mixed")
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text, "plain"))
        alt.attach(MIMEText(body_html, "html"))
        msg.attach(alt)
        for att in attachments:
            content = att["content"]
            if isinstance(content, str):  # base64, as sent through Celery
                content = base64.b64decode(content)
            part = MIMEApplication(content, _subtype="octet-stream")
            part.add_header("Content-Disposition", "attachment", filename=att["name"])
            msg.attach(part)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))
    msg["Subject"] = subject
    # formataddr quotes and encodes names, so "Müller & Co." or a name
    # with <, > or a comma stays one display name.
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = formataddr((to_name, to_email))
    if reply_to:
        msg["Reply-To"] = reply_to
    message = msg.as_string()

    routes = [route]
    if fallback is not None:
        routes = [fallback, route] if _primary_down() else [route, fallback]

    primary_error: Exception | None = None
    last_error: Exception | None = None
    for current in routes:
        is_fallback = current is fallback
        try:
            _deliver(current, sender_email, to_email, message)
        except Exception as exc:
            last_error = exc
            if not is_fallback:
                primary_error = exc
            logger.error(
                "smtp_fallback_error to_email=%s subject=%s relay=%s error=%s",
                to_email,
                subject,
                current.host,
                exc,
            )
            continue
        if is_fallback:
            # One refused recipient says nothing about the relay; a quota,
            # an outage or a failed login does.
            if primary_error is not None and not isinstance(
                primary_error, smtplib.SMTPRecipientsRefused
            ):
                _mark_primary_down()
            logger.warning(
                "smtp_relay_fallback_used to_email=%s subject=%s relay=%s",
                to_email,
                subject,
                current.host,
            )
        logger.info("smtp_fallback_sent to_email=%s subject=%s", to_email, subject)
        return True
    raise EmailDeliveryError(str(last_error)) from last_error


def _send(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    body_text: str,
    attachments: list[dict] | None = None,
    *,
    system: bool = False,
) -> bool:
    """Send a single transactional email (see the module docstring for who sends).

    Returns True on success, False on failure (delivery failures must not block callers).

    For callers that need retry, catch EmailDeliveryError from _send_via_smtp.
    """
    platform = platform_settings.relay()
    club_sender = _get_setting("club.notification_sender_email")
    club_name = _get_setting("club.notification_sender_name")

    route: _Route | None = None
    reply_to: str | None = None
    mailbox = None if system else _club_mailbox()
    if club_sender and mailbox:
        sender_email, sender_name = club_sender, club_name or "Club Notifications"
        route = _mailbox_route(platform, mailbox)
    elif platform.sender_email:
        sender_email = platform.sender_email
        sender_name = (
            platform.sender_name if system else club_name or platform.sender_name
        )
        reply_to = None if system else club_sender or None
    elif club_sender:
        sender_email, sender_name = club_sender, club_name or "Club Notifications"
    else:
        logger.warning(
            "No sender configured (platform mail.system.sender_email or "
            "club.notification_sender_email) -- skipping email to %s",
            to_email,
        )
        return False

    try:
        return _send_via_smtp(
            to_email,
            to_name,
            sender_email,
            sender_name,
            subject,
            body_html,
            body_text,
            attachments=attachments,
            reply_to=reply_to,
            route=route,
        )
    except EmailDeliveryError:
        return False


def send_welcome(
    to_address: str,
    name: str,
    login_email: str,
    temp_password: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Send new-member welcome email with temporary credentials."""
    club_name = club_display_name()
    base = _get_base_url()
    login_url = f"{base}/login" if base else "the member portal"

    body_html, body_text, subject = render_mail_template(
        "welcome",
        locale=lang,
        name=name,
        club_name=club_name,
        login_email=login_email,
        temp_password=temp_password,
        login_url=login_url,
    )
    _send(to_address, name, subject, body_html, body_text)


def send_club_invite(
    to_address: str,
    name: str,
    invite_url: str,
    invited_by: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Send a personal link to join the club. Valid for 14 days."""
    club_name = club_display_name()

    body_html, body_text, subject = render_mail_template(
        "club_invite",
        locale=lang,
        name=name,
        club_name=club_name,
        invited_by=invited_by,
        invite_url=invite_url,
    )
    _send(to_address, name, subject, body_html, body_text)


def send_password_reset(
    to_address: str,
    name: str,
    reset_url: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Send a password reset link. Token expires in 1 hour."""
    club_name = club_display_name()

    body_html, body_text, subject = render_mail_template(
        "password_reset",
        locale=lang,
        name=name,
        club_name=club_name,
        reset_url=reset_url,
    )
    _send(to_address, name, subject, body_html, body_text, system=True)


def send_email_verification(
    to_address: str,
    name: str,
    verify_url: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Send a private email verification link. Token expires in 24 hours."""
    club_name = club_display_name()

    body_html, body_text, subject = render_mail_template(
        "verify_email",
        locale=lang,
        name=name,
        club_name=club_name,
        verify_url=verify_url,
    )
    _send(to_address, name, subject, body_html, body_text, system=True)


def send_password_changed(
    to_address: str, name: str, *, lang: str = DEFAULT_LANG
) -> None:
    """Notify a member that their password was successfully changed."""
    club_name = club_display_name()
    base = _get_base_url()
    support_url = f"{base}/contact" if base else ""

    body_html, body_text, subject = render_mail_template(
        "password_changed",
        locale=lang,
        name=name,
        club_name=club_name,
        support_url=support_url,
    )
    _send(to_address, name, subject, body_html, body_text, system=True)


def send_new_device_login(
    to_address: str,
    name: str,
    ip: str,
    user_agent: str,
    timestamp: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Alert a member that their account was accessed from a new IP address."""
    club_name = club_display_name()
    base = _get_base_url()
    support_url = f"{base}/contact" if base else ""

    body_html, body_text, subject = render_mail_template(
        "new_device_login",
        locale=lang,
        name=name,
        club_name=club_name,
        timestamp=timestamp,
        ip=ip,
        user_agent=user_agent,
        support_url=support_url,
    )
    _send(to_address, name, subject, body_html, body_text, system=True)


def send_account_deleted(
    to_address: str, name: str, *, lang: str = DEFAULT_LANG
) -> None:
    """Notify a member that their account has been deactivated."""
    club_name = club_display_name()
    base = _get_base_url()
    support_url = f"{base}/contact" if base else ""

    body_html, body_text, subject = render_mail_template(
        "account_deleted",
        locale=lang,
        name=name,
        club_name=club_name,
        support_url=support_url,
    )
    _send(to_address, name, subject, body_html, body_text, system=True)
