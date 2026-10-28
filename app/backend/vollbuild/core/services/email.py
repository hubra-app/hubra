"""Transactional email via SMTP (local Maddy sender with Infomaniak fallback).

All public send_* functions log errors and return silently on failure -- email
delivery issues must never block member creation or other core operations.

Each send_* function accepts a *lang* parameter (default ``"de-CH"``) used to
resolve translations from the Translation table with fallback chain:
    de-CH -> [de-CH, en-GB]
    en-GB -> [en-GB]
    other -> [de-CH, en-GB]

SMTP credentials are read from the encrypted InternalKey table:
    mail.smtp.user
    mail.smtp.password

SMTP host/port are read from the Setting KV store:
    mail.smtp_host  -- defaults to ``localhost``
    mail.smtp_port  -- defaults to ``587``
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

from vollbuild.core.services.mail_i18n import render_mail_template

logger = logging.getLogger(__name__)

DEFAULT_LANG = "de-CH"


class EmailDeliveryError(Exception):
    """Raised when a transactional email fails to send."""


def _get_setting(key: str, default: str = "") -> str:
    """Read a single value from the Setting KV store, returning *default* on miss or error."""
    try:
        from vollbuild.api.settings.services import SettingService

        return SettingService.get(key, default=default) or default
    except Exception as exc:
        logger.warning("Could not load setting %r: %s", key, exc)
        return default


def _get_base_url() -> str:
    """Return the frontend's base URL for link generation (password-reset, etc.).

    The API lives on api.vollbuild.ch and the frontend SPA on cos.vollbuild.ch,
    so request.url_root (which resolves to the API host) must NOT be used to build
    links that open the frontend. FRONTEND_BASE_URL is the canonical frontend
    origin (e.g. https://cos.vollbuild.ch).

    A request-context fallback to request.url_root is intentionally omitted —
    every link generated here must point at the frontend, never the API host.
    """
    base = current_app.config.get("FRONTEND_BASE_URL", "")
    return str(base).rstrip("/") if base else ""


def _get_sso_base_url() -> str:
    """Return the SSO portal's base URL for auth-related email links.

    Password-reset and email-verification links should point to the SSO portal
    (sso.vollbuild.ch) so users land on the centralized login experience.
    Falls back to _get_base_url() for backward compatibility when SSO_BASE_URL
    is not configured.
    """
    sso_base = current_app.config.get("SSO_BASE_URL", "")
    if sso_base:
        return str(sso_base).rstrip("/")
    return _get_base_url()


def _send_via_smtp(
    to_email: str,
    to_name: str,
    sender_email: str,
    sender_name: str,
    subject: str,
    body_html: str,
    body_text: str,
    attachments: list[dict] | None = None,
) -> bool:
    """Send a transactional email via SMTP (Maddy with Infomaniak fallback).

    Reads SMTP host/port from the ``mail.smtp_host`` / ``mail.smtp_port``
    Setting KV rows, and credentials from ``mail.smtp.user`` / ``mail.smtp.password``
    InternalKey records.
    Returns True on success, raises EmailDeliveryError on failure.
    """
    smtp_host = _get_setting("mail.smtp_host") or "localhost"
    smtp_port = int(_get_setting("mail.smtp_port") or 587)
    try:
        from vollbuild.core.services.key_service import KeyService

        smtp_user = str(KeyService.get("mail.smtp.user") or "")
        smtp_password = str(KeyService.get("mail.smtp.password") or "")
    except Exception:
        smtp_user = ""
        smtp_password = ""

    if attachments:
        msg = MIMEMultipart("mixed")
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text, "plain"))
        alt.attach(MIMEText(body_html, "html"))
        msg.attach(alt)
        for att in attachments:
            part = MIMEApplication(att["content"], _subtype="octet-stream")
            part.add_header("Content-Disposition", "attachment", filename=att["name"])
            msg.attach(part)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = f"{to_name} <{to_email}>"

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            if smtp_port != 25:
                _smtp_context = ssl.create_default_context()
                if current_app.config.get("SMTP_TLS_VERIFY", True) is False:
                    _smtp_context.check_hostname = False
                    _smtp_context.verify_mode = ssl.CERT_NONE
                server.starttls(context=_smtp_context)
                server.ehlo()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(sender_email, [to_email], msg.as_string())
        logger.info("smtp_fallback_sent to_email=%s subject=%s", to_email, subject)
        return True
    except Exception as exc:
        logger.error(
            "smtp_fallback_error to_email=%s subject=%s error=%s",
            to_email,
            subject,
            exc,
        )
        raise EmailDeliveryError(str(exc)) from exc


def _send(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    body_text: str,
    attachments: list[dict] | None = None,
) -> bool:
    """Send a single transactional email via SMTP (Maddy with Infomaniak fallback).

    Returns True on success, False on failure (delivery failures must not block callers).

    For callers that need retry, catch EmailDeliveryError from _send_via_smtp.
    """
    sender_email = _get_setting("club.notification_sender_email")
    sender_name = _get_setting("club.notification_sender_name", "Club Notifications")

    if not sender_email:
        logger.warning(
            "club.notification_sender_email not set in settings -- skipping email to %s",
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
    club_name = _get_setting("club.name", "Your Club")
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


def send_password_reset(
    to_address: str,
    name: str,
    reset_url: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Send a password reset link. Token expires in 1 hour."""
    club_name = _get_setting("club.name", "Your Club")

    body_html, body_text, subject = render_mail_template(
        "password_reset",
        locale=lang,
        name=name,
        club_name=club_name,
        reset_url=reset_url,
    )
    _send(to_address, name, subject, body_html, body_text)


def send_email_verification(
    to_address: str,
    name: str,
    verify_url: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Send a private email verification link. Token expires in 24 hours."""
    club_name = _get_setting("club.name", "Your Club")

    body_html, body_text, subject = render_mail_template(
        "verify_email",
        locale=lang,
        name=name,
        club_name=club_name,
        verify_url=verify_url,
    )
    _send(to_address, name, subject, body_html, body_text)


def send_password_changed(
    to_address: str, name: str, *, lang: str = DEFAULT_LANG
) -> None:
    """Notify a member that their password was successfully changed."""
    club_name = _get_setting("club.name", "Your Club")
    base = _get_base_url()
    support_url = f"{base}/contact" if base else ""

    body_html, body_text, subject = render_mail_template(
        "password_changed",
        locale=lang,
        name=name,
        club_name=club_name,
        support_url=support_url,
    )
    _send(to_address, name, subject, body_html, body_text)


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
    club_name = _get_setting("club.name", "Your Club")
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
    _send(to_address, name, subject, body_html, body_text)


def send_account_deleted(
    to_address: str, name: str, *, lang: str = DEFAULT_LANG
) -> None:
    """Notify a member that their account has been deactivated."""
    club_name = _get_setting("club.name", "Your Club")
    base = _get_base_url()
    support_url = f"{base}/contact" if base else ""

    body_html, body_text, subject = render_mail_template(
        "account_deleted",
        locale=lang,
        name=name,
        club_name=club_name,
        support_url=support_url,
    )
    _send(to_address, name, subject, body_html, body_text)


def send_invoice_generated(
    to_address: str,
    name: str,
    invoice_id: int,
    amount: float,
    due_date: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Send a notification that a new invoice has been generated."""
    club_name = _get_setting("club.name", "Your Club")
    base = _get_base_url()
    portal_url = f"{base}/invoices" if base else ""

    body_html, body_text, subject = render_mail_template(
        "invoice_generated",
        locale=lang,
        name=name,
        club_name=club_name,
        invoice_id=invoice_id,
        amount_formatted=f"CHF {amount:.2f}",
        due_date=due_date,
        portal_url=portal_url,
    )

    attachments = None
    try:
        from vollbuild.core.models.finance import Invoice
        from vollbuild.core.services.qr_bill import generate_invoice_pdf

        invoice = Invoice.query.get(invoice_id)
        if invoice is not None:
            pdf_bytes = generate_invoice_pdf(invoice)
            attachments = [{"name": f"invoice-{invoice_id}.pdf", "content": pdf_bytes}]
    except Exception:
        logger.warning("Failed to generate QR-bill PDF for invoice %s", invoice_id)

    _send(to_address, name, subject, body_html, body_text, attachments=attachments)


def send_invoice_reminder(
    to_address: str,
    name: str,
    invoice_id: int,
    amount: float,
    due_date: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Send a payment reminder email for an unpaid invoice."""
    club_name = _get_setting("club.name", "Your Club")
    base = _get_base_url()
    portal_url = f"{base}/invoices" if base else ""

    body_html, body_text, subject = render_mail_template(
        "invoice_reminder",
        locale=lang,
        name=name,
        club_name=club_name,
        invoice_id=invoice_id,
        amount_formatted=f"CHF {amount:.2f}",
        due_date=due_date,
        portal_url=portal_url,
    )
    _send(to_address, name, subject, body_html, body_text)


def send_notification(
    to_address: str,
    name: str,
    title: str,
    message: str,
    *,
    lang: str = DEFAULT_LANG,
) -> None:
    """Send a single notification email to a member."""
    club_name = _get_setting("club.name", "Your Club")
    base = _get_base_url()
    portal_url = base if base else ""

    subject = f"[{club_name}] {title}"

    body_html, body_text, _ = render_mail_template(
        "notification",
        locale=lang,
        name=name,
        club_name=club_name,
        message=message,
        portal_url=portal_url,
        subject=subject,
    )
    _send(to_address, name, subject, body_html, body_text)
