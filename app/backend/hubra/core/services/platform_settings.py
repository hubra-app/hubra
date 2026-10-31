"""Platform settings: the outbound mail relay, backup storage and other
instance-wide values.

Each known key has a spec with a default taken from the deployment config
(env), so a fresh install works from ``.env`` alone.  A row in
``platform_settings`` overrides the default; deleting the row goes back to
it.  Platform managers edit them in the manager portal
(``/api/v1/manager/platform``).

Mail split:
  * system mail (sign-in, SSO, password and account notices, anything sent
    without a club) always goes through the platform relay, from the
    platform sender;
  * club mail goes through the platform relay too, from the platform sender
    with the club's address as Reply-To, unless the club has its own sender
    mailbox (``mail.smtp.user`` / ``mail.smtp.password`` from the mail
    module), which sends as that mailbox through the same relay.

Fallback relay: when ``mail.fallback.host`` is set, a mail the platform
relay refuses (a send quota, an outage, a login failure) is sent again
through the fallback, e.g. Brevo's SMTP relay, from the same sender.  See
``email._send_via_smtp``.

Backups (the global one and one per club) are the platform's, so where they
are stored (``backup.s3.*``) is the platform's to decide, not a club's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from flask import current_app

from hubra.core.crypto import PLATFORM, decrypt_code, encrypt_code
from hubra.core.extensions import db
from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.validators import validate_value


@dataclass(frozen=True)
class Spec:
    key: str
    label: str
    description: str
    default: Callable[[dict], object]
    validation: str | None = None
    secret: bool = False


def _relay_host(cfg) -> str:
    return cfg.get("SMTP_HOST") or cfg.get("ZONEMTA_SMTP_HOST") or ""


def _relay_port(cfg) -> str:
    return str(cfg.get("SMTP_PORT") or cfg.get("ZONEMTA_SMTP_PORT") or 587)


SPECS: tuple[Spec, ...] = (
    Spec(
        "mail.relay.host",
        "SMTP relay host",
        "Outgoing mail server for every mail Hubra sends",
        _relay_host,
        "host",
    ),
    Spec(
        "mail.relay.port",
        "SMTP relay port",
        "587 for STARTTLS, 25 for an internal relay without TLS",
        _relay_port,
        "port",
    ),
    Spec(
        "mail.relay.user",
        "SMTP user",
        "Leave empty if the relay needs no login",
        lambda cfg: cfg.get("SMTP_USER") or "",
    ),
    Spec(
        "mail.relay.password",
        "SMTP password",
        "Stored encrypted",
        lambda cfg: cfg.get("SMTP_PASSWORD") or "",
        secret=True,
    ),
    Spec(
        "mail.system.sender_email",
        "System sender address",
        "From address of sign-in, SSO and platform mail",
        lambda cfg: cfg.get("MAIL_FROM") or "",
        "email",
    ),
    Spec(
        "mail.system.sender_name",
        "System sender name",
        "Display name of the system sender",
        lambda cfg: "Hubra",
    ),
    Spec(
        "mail.fallback.host",
        "Fallback relay host",
        "Used when the relay refuses a mail, e.g. its send quota is reached "
        "(smtp-relay.brevo.com). Leave empty for no fallback",
        lambda cfg: cfg.get("SMTP_FALLBACK_HOST") or "",
        "host",
    ),
    Spec(
        "mail.fallback.port",
        "Fallback relay port",
        "587 for STARTTLS, 465 for TLS",
        lambda cfg: str(cfg.get("SMTP_FALLBACK_PORT") or 587),
        "port",
    ),
    Spec(
        "mail.fallback.user",
        "Fallback SMTP user",
        "Leave empty if the fallback needs no login",
        lambda cfg: cfg.get("SMTP_FALLBACK_USER") or "",
    ),
    Spec(
        "mail.fallback.password",
        "Fallback SMTP password",
        "Stored encrypted",
        lambda cfg: cfg.get("SMTP_FALLBACK_PASSWORD") or "",
        secret=True,
    ),
    Spec(
        "backup.public_key",
        "Backup public key",
        "age public key every backup is encrypted to (flask backups keygen). "
        "The private key stays off the server; restore asks for it",
        lambda cfg: cfg.get("BACKUP_PUBLIC_KEY") or "",
        "age_public_keys",
    ),
    Spec(
        "backup.s3.endpoint",
        "S3 endpoint",
        "S3-compatible endpoint URL, e.g. https://eu2.contabostorage.com",
        lambda cfg: cfg.get("BACKUP_S3_ENDPOINT") or "",
        "url",
    ),
    Spec(
        "backup.s3.bucket",
        "S3 bucket",
        "Bucket the encrypted backups go to",
        lambda cfg: cfg.get("BACKUP_S3_BUCKET") or "",
    ),
    Spec(
        "backup.s3.region",
        "S3 region",
        "Usually 'default' for Contabo",
        lambda cfg: cfg.get("BACKUP_S3_REGION") or "default",
    ),
    Spec(
        "backup.s3.access_key",
        "S3 access key",
        "Stored encrypted",
        lambda cfg: cfg.get("BACKUP_S3_ACCESS_KEY") or "",
        secret=True,
    ),
    Spec(
        "backup.s3.secret_key",
        "S3 secret key",
        "Stored encrypted",
        lambda cfg: cfg.get("BACKUP_S3_SECRET_KEY") or "",
        secret=True,
    ),
)

_BY_KEY = {s.key: s for s in SPECS}
_PURPOSE = "platform_settings.value"


class PlatformSettingError(ValueError):
    """An unknown key or an invalid value."""


def spec(key: str) -> Spec:
    try:
        return _BY_KEY[key]
    except KeyError:
        raise PlatformSettingError(f"Unknown platform setting: {key}") from None


def _row(key: str) -> PlatformSetting | None:
    return db.session.get(PlatformSetting, key)


def get(key: str) -> str:
    """The stored value, or the default from the deployment config."""
    s = spec(key)
    row = _row(key)
    if row is not None and row.value is not None:
        return decrypt_code(row.value, _PURPOSE, PLATFORM) if s.secret else row.value
    return str(s.default(current_app.config) or "")


def set_many(values: dict, actor_id: int | None = None) -> None:
    """Validate, then write.  ``None`` drops the row (back to the default).

    Does NOT commit.
    """
    errors: dict[str, str] = {}
    for key, value in values.items():
        if key not in _BY_KEY:
            errors[key] = "Unknown setting"
            continue
        if value is None:
            continue
        if not isinstance(value, (str, int)):
            errors[key] = "Must be a string"
            continue
        value = str(value).strip()
        if value and (err := validate_value(_BY_KEY[key].validation, value)):
            errors[key] = err
    if errors:
        raise PlatformSettingError(errors)

    for key, value in values.items():
        s = _BY_KEY[key]
        row = _row(key)
        if value is None:
            if row is not None:
                db.session.delete(row)
            continue
        value = str(value).strip()
        stored = encrypt_code(value, _PURPOSE, PLATFORM) if s.secret and value else value
        if row is None:
            row = PlatformSetting(key=key, secret=s.secret)
            db.session.add(row)
        row.value = stored
        row.updated_by = actor_id
    db.session.flush()


def as_list() -> list[dict]:
    """Every known setting for the manager portal.  Secrets are never returned."""
    out = []
    for s in SPECS:
        row = _row(s.key)
        stored = row is not None and row.value is not None
        value = get(s.key)
        out.append(
            {
                "key": s.key,
                "label": s.label,
                "description": s.description,
                "secret": s.secret,
                "validation": s.validation,
                "value": "" if s.secret else value,
                "isSet": bool(value),
                "source": "platform" if stored else "env",
            }
        )
    return out


@dataclass(frozen=True)
class Relay:
    host: str
    port: int
    user: str
    password: str
    sender_email: str
    sender_name: str


def relay() -> Relay:
    """The platform relay and system sender, as every send needs them."""
    try:
        port = int(get("mail.relay.port") or 587)
    except ValueError:
        port = 587
    return Relay(
        host=get("mail.relay.host"),
        port=port,
        user=get("mail.relay.user"),
        password=get("mail.relay.password"),
        sender_email=get("mail.system.sender_email"),
        sender_name=get("mail.system.sender_name") or "Hubra",
    )


@dataclass(frozen=True)
class FallbackRelay:
    host: str
    port: int
    user: str
    password: str


def fallback_relay() -> FallbackRelay | None:
    """The fallback relay, or None when no host is set."""
    host = get("mail.fallback.host")
    if not host:
        return None
    try:
        port = int(get("mail.fallback.port") or 587)
    except ValueError:
        port = 587
    return FallbackRelay(
        host=host,
        port=port,
        user=get("mail.fallback.user"),
        password=get("mail.fallback.password"),
    )
