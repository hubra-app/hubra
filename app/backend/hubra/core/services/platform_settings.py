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

Browser push (``push.*``): the VAPID key pair every push is signed with.
Hubra makes one the first time a member turns push on; replacing it signs
every device out of push (they have to turn it on again).

Performance (``perf.*``): the thresholds of ``services.perf_monitor``.

Discord (``discord.*``): the one Hubra application every club's server and
every linked account goes through (see docs/discord.md). Set here only, with
no env fallback.  ``discord.log_*`` is the platform log: the bot posts
platform events to a channel on the platform's own server
(``services.platform_discord``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from flask import current_app
from sqlalchemy import text

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
    Spec(
        "push.vapid_public_key",
        "Push public key",
        "VAPID public key for browser notifications. Made automatically",
        lambda cfg: "",
    ),
    Spec(
        "push.vapid_private_key",
        "Push private key",
        "VAPID private key. Made automatically, stored encrypted",
        lambda cfg: "",
        secret=True,
    ),
    Spec(
        "discord.client_id",
        "Discord application ID",
        "Developer Portal › your app › General Information › Application ID",
        lambda cfg: "",
        "number",
    ),
    Spec(
        "discord.public_key",
        "Discord public key",
        "General Information › Public Key; checks that interactions come from Discord",
        lambda cfg: "",
        "discord_public_key",
    ),
    Spec(
        "discord.client_secret",
        "Discord client secret",
        "OAuth2 › Client Secret. Stored encrypted",
        lambda cfg: "",
        secret=True,
    ),
    Spec(
        "discord.bot_token",
        "Discord bot token",
        "Bot › Token. Stored encrypted",
        lambda cfg: "",
        secret=True,
    ),
    Spec(
        "discord.log_channel_id",
        "Platform log channel",
        "Channel ID on the platform's Discord server where the bot posts "
        "platform events. Empty: no posts",
        lambda cfg: "",
        "number",
    ),
    Spec(
        "discord.log_events",
        "Platform log events",
        "Comma-separated categories to post: clubs, requests, access, members, "
        "plugins, backups, platform, alerts, digest, releases, security",
        lambda cfg: (
            "clubs,requests,access,plugins,backups,platform,alerts,"
            "digest,releases,security"
        ),
        "discord_log_events",
    ),
    Spec(
        "alerts.cooldown_minutes",
        "Alert cooldown",
        "Minutes before the same kind of alert is mailed again. 0: every time. "
        "Outages and recoveries always go out",
        lambda cfg: "60",
        "minutes",
    ),
    Spec(
        "alerts.retention_days",
        "Event log retention",
        "Days the platform event log keeps sent and failed mails, outages and "
        "alerts (1 to 365)",
        lambda cfg: "30",
        "retention_days",
    ),
    Spec(
        "alerts.enabled",
        "Alerts on",
        "off: no alert goes out by mail or Discord; the event log still keeps them",
        lambda cfg: "on",
        "on_off",
    ),
    Spec(
        "alerts.mail_off",
        "Alert types not mailed",
        "Comma-separated alert types nobody gets by mail",
        lambda cfg: "",
        "alert_types",
    ),
    Spec(
        "alerts.discord_off",
        "Alert types not posted to Discord",
        "Comma-separated alert types the bot does not post",
        lambda cfg: "",
        "alert_types",
    ),
    Spec(
        "maintenance.enabled",
        "Maintenance mode",
        "on: club apps show a maintenance notice and their API answers 503; "
        "manage keeps working and alerts are paused",
        lambda cfg: "",
        "on_off",
    ),
    Spec(
        "maintenance.message",
        "Maintenance message",
        "Shown to members while the platform is in maintenance",
        lambda cfg: "",
    ),
    Spec(
        "maintenance.until",
        "Maintenance until",
        "When maintenance ends by itself (ISO time, UTC). Empty: until turned off",
        lambda cfg: "",
        "iso_datetime",
    ),
    Spec(
        "maintenance.planned_start",
        "Planned maintenance",
        "When announced maintenance starts by itself (ISO time, UTC). Club apps "
        "show a banner until then. Empty: none planned",
        lambda cfg: "",
        "iso_datetime",
    ),
    Spec(
        "maintenance.planned_minutes",
        "Planned maintenance length",
        "Expected minutes of the planned maintenance",
        lambda cfg: "",
        "minutes",
    ),
    Spec(
        "maintenance.planned_message",
        "Planned maintenance message",
        "Shown in the banner before and during the planned maintenance",
        lambda cfg: "",
    ),
    Spec(
        "alerts.manage_url",
        "Manage address",
        "Address of the manage portal, for the button in alert mails "
        "(https://manage.hubra.club). Empty: no button",
        lambda cfg: cfg.get("MANAGE_BASE_URL") or "",
        "url",
    ),
    Spec(
        "perf.slow_request_ms",
        "Slow request",
        "API requests at least this long (ms) are counted as slow and written "
        "to the log, with the route only. 0: off",
        lambda cfg: "1000",
        "milliseconds",
    ),
    Spec(
        "perf.slow_query_ms",
        "Slow database query",
        "Queries at least this long (ms) are counted and written to the log, "
        "without their values. 0: off",
        lambda cfg: "250",
        "milliseconds",
    ),
    Spec(
        "perf.p95_warning_ms",
        "Slow API warning",
        "An open problem on the alerts page when 95 % of the last hour's "
        "requests are not faster than this (ms). 0: off",
        lambda cfg: "1500",
        "milliseconds",
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
        stored = (
            encrypt_code(value, _PURPOSE, PLATFORM) if s.secret and value else value
        )
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


def int_setting(key: str, fallback: int) -> int:
    """A whole-number setting, or *fallback* when it is empty or unreadable
    (a database hiccup must not stop an alert)."""
    try:
        return int(get(key))
    except Exception:  # noqa: BLE001
        return fallback


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


@dataclass(frozen=True)
class DiscordApp:
    client_id: str
    client_secret: str
    bot_token: str
    public_key: str


def discord() -> DiscordApp:
    """The platform's Discord application (empty strings when not set up)."""
    return DiscordApp(
        client_id=get("discord.client_id"),
        client_secret=get("discord.client_secret"),
        bot_token=get("discord.bot_token"),
        public_key=get("discord.public_key"),
    )


_VAPID_LOCK_KEY = 0x6875627261766170  # "hubravap"


@dataclass(frozen=True)
class PushKeys:
    public_key: str  # base64url, uncompressed P-256 point (applicationServerKey)
    private_key: str  # base64url raw private value
    contact: str  # mailto: subject push services may write to


def web_push(create: bool = False) -> PushKeys | None:
    """The platform's VAPID keys; with *create*, made and stored (flushed,
    not committed) when there are none yet."""
    public, private = get("push.vapid_public_key"), get("push.vapid_private_key")
    if not (public and private):
        if not create:
            return None
        # Two API processes asking at once must not each store a key pair:
        # browsers that subscribed with the losing key would get no pushes.
        # Wait for the other, then look again (held until the commit).
        if db.session.get_bind().dialect.name == "postgresql":
            db.session.execute(
                text("SELECT pg_advisory_xact_lock(:k)"), {"k": _VAPID_LOCK_KEY}
            )
            public, private = (
                get("push.vapid_public_key"),
                get("push.vapid_private_key"),
            )
    if not (public and private):
        from hubra.core.services.web_push import generate_vapid_keys

        public, private = generate_vapid_keys()
        set_many({"push.vapid_public_key": public, "push.vapid_private_key": private})
    sender = get("mail.system.sender_email") or "admin@hubra.club"
    return PushKeys(public_key=public, private_key=private, contact=f"mailto:{sender}")
