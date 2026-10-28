"""Private email verification of the global User, done on the SSO portal.

Verification is a step after sign-in, never a gate in front of it:

* A verified user goes straight on.
* Without working system mail nobody can receive a link, so nobody is held
  back; a warning is logged instead.
* With system mail configured, superadmins are marked verified on their next
  sign-in, so a fresh install's first admin is never stuck.
* Everyone else confirms the link mailed to them, or changes the address.

The club app does not check verification at all.  The SSO portal asks
``status()`` after every sign-in, and ``POST /auth/switch-tenant`` refuses to
open a club while ``required()`` is true, so the step cannot be skipped by
going to a club directly.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.email_verification import EmailVerificationToken
from hubra.core.models.user import User
from hubra.core.services import email as email_svc

_log = logging.getLogger(__name__)

TOKEN_TTL = timedelta(hours=24)

_EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def mail_configured() -> bool:
    """True when system mail (sign-in and account mail) can be sent.

    System mail needs a sender address; the relay host falls back to
    localhost and is always set.
    """
    return bool(email_svc._get_setting("club.notification_sender_email"))


_warned = False


def _warn_mail_missing(user: User) -> None:
    """Warn once per process, then only at debug level."""
    global _warned
    level = logging.DEBUG if _warned else logging.WARNING
    _warned = True
    _log.log(
        level,
        "email_verification_skipped user_id=%s: system mail is not configured "
        "(no sender address), so nobody is asked to verify their email. "
        "Set the system sender to turn verification on.",
        user.id,
    )


def auto_verify_superadmin(user: User) -> bool:
    """Mark a superadmin verified once system mail works.  Does NOT commit.

    Returns True when the flag changed.
    """
    if user.is_superadmin and not user.private_email_verified and mail_configured():
        user.private_email_verified = True
        _log.info("email_auto_verified_superadmin user_id=%s", user.id)
        return True
    return False


def required(user: User) -> bool:
    """Whether *user* must verify before going on.  May flag a superadmin."""
    if user.private_email_verified:
        return False
    if not mail_configured():
        _warn_mail_missing(user)
        return False
    if auto_verify_superadmin(user):
        return False
    return True


def _pending(user: User) -> EmailVerificationToken | None:
    """The newest unused link for the user's current address."""
    return db.session.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id)
        .where(EmailVerificationToken.email == user.email)
        .where(EmailVerificationToken.used.is_(False))
        .order_by(EmailVerificationToken.created_at.desc())
    )


def status(user: User) -> dict:
    """What the SSO portal shows after sign-in.  May flag a superadmin."""
    must = required(user)
    pending = _pending(user) if must else None
    return {
        "email": user.email,
        "verified": user.private_email_verified,
        "required": must,
        "mailConfigured": mail_configured(),
        "sentAt": (
            pending.created_at.isoformat()
            if pending is not None and pending.is_valid
            else None
        ),
    }


def send(user: User, verify_base_url: str) -> None:
    """Mail a fresh link to the user's address; older links stop working.

    Commits, so the link works as soon as the mail arrives.
    """
    for old in db.session.scalars(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id)
        .where(EmailVerificationToken.used.is_(False))
    ):
        old.used = True

    raw = secrets.token_urlsafe(32)
    db.session.add(
        EmailVerificationToken(
            user_id=user.id,
            email=user.email,
            token_hash=_hash(raw),
            expires_at=datetime.now(timezone.utc) + TOKEN_TTL,
        )
    )
    db.session.commit()

    email_svc.send_email_verification(
        user.email,
        user.name,
        f"{verify_base_url}/verify-email#token={raw}",
        lang=user.language or "de-CH",
    )
    _log.info("email_verification_sent user_id=%s", user.id)


def confirm(raw_token: str) -> User:
    """Mark the user of a valid link verified.  Does NOT commit."""
    token = db.session.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == _hash(raw_token)
        )
    )
    user = db.session.get(User, token.user_id) if token is not None else None
    if (
        token is None
        or not token.is_valid
        or user is None
        or token.email.lower() != user.email.lower()
    ):
        raise_error(400, "INVALID_TOKEN", "Verification link is invalid or has expired")
    token.used = True
    user.private_email_verified = True
    return user


def change_email(user: User, new_email: str, current_password: str) -> None:
    """Change the login and private address.  Does NOT commit.

    Asks for the current password, since the address is also where password
    reset links go.  The new address starts unverified.
    """
    new_email = (new_email or "").strip().lower()
    if not _EMAIL_RE.fullmatch(new_email):
        raise_error(400, "VALIDATION_ERROR", "Invalid email address")
    if not current_password or not user.check_password(current_password):
        raise_error(401, "UNAUTHORIZED", "Current password is incorrect")
    if new_email == user.email:
        return
    taken = db.session.scalar(
        select(User.id).where(User.email == new_email).where(User.id != user.id)
    )
    if taken is not None:
        raise_error(409, "CONFLICT", "Email already in use")
    _log.info("email_changed user_id=%s — verification reset", user.id)
    user.email = new_email
    user.private_email_verified = False
