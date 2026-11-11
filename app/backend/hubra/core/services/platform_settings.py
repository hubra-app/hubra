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
are stored (``backup.s3.*``) and how long they are kept (``backup.keep_*``,
see ``BackupService.run_retention_cleanup``) is the platform's to decide,
not a club's.

Files (``files.*``): where clubs' files (documents, attachments of plugins)
are kept, ``hubra.core.files``.  With ``files.s3.bucket`` set they go to
that S3 bucket, otherwise to the folder ``FILES_DIR`` on the server.

Browser push (``push.*``): the VAPID key pair every push is signed with.
Hubra makes one the first time a member turns push on; replacing it signs
every device out of push (they have to turn it on again).

Performance (``perf.*``): the thresholds of ``services.perf_monitor``.

Limits (``limits.warn_percent``): when clubs are warned about their
limits (``services.quotas``).  The limits and prices of each plan are on the
plan (``services.plans``); a club can have its own on top, set in manage.

Billing (``billing.*``): whether clubs pay Hubra through Stripe Billing,
monthly or yearly, its Stripe keys and the webhook secrets
(``hubra.core.billing``).

Stripe mode (``stripe.mode``): Online payments and billing each have a live
and a sandbox key (and billing a webhook secret per mode).  ``sandbox`` uses
the sandbox keys for every club; ``live`` the live keys, except for sandbox
clubs (``services.sandbox_clubs``), which always stay on the sandbox keys.
See ``stripe_mode``.

Translation (``translate.*``): the DeepL key that pre-fills the other
languages of a post (``services.machine_translation``); empty: none.

Legal (``legal.*``): where Hubra's privacy policy, terms of service and
imprint are (``legal_links``).  The sign-in pages, the footers and Stripe
Checkout link them; Stripe asks for the same addresses in its dashboard.

Google Wallet (``wallet.google.*``): the issuer account, generic class and
service account key the member badge's pass is issued with
(``services.google_wallet``).  Hubra is the one issuer for every club.

Discord (``discord.*``): the one Hubra application every club's server and
every linked account goes through (see docs/discord.md). Set here only, with
no env fallback.  ``discord.log_*`` is the platform log: the bot posts
platform events to a channel on the platform's own server
(``services.platform_discord``); ``discord.audit_channel_id`` is an optional
channel that takes the audit entries off the log, and
``discord.changelog_channel_id`` one for the release notes of Hubra and its
plugins (``services.changelogs``).  ``discord.support_*``:
one private thread per support case (``services.support_discord``).
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from flask import current_app
from sqlalchemy import event, select, text

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
        "backup.keep_daily",
        "Daily backups kept",
        "Newest daily backups kept per set (the global one and each club's), "
        "1 to 365",
        lambda cfg: "7",
        "backup_keep",
    ),
    Spec(
        "backup.keep_weekly",
        "Weekly backups kept",
        "Newest weekly backups (Sunday) kept per set, 1 to 365",
        lambda cfg: "4",
        "backup_keep",
    ),
    Spec(
        "backup.keep_monthly",
        "Monthly backups kept",
        "Newest monthly backups (the 1st) kept per set, 1 to 365",
        lambda cfg: "12",
        "backup_keep",
    ),
    Spec(
        "backup.keep_manual_days",
        "Manual backups kept for",
        "Days a backup made by hand is kept; 0 keeps it until someone deletes it",
        lambda cfg: "0",
        "keep_days",
    ),
    Spec(
        "backup.keep_deleted_club_days",
        "Backups of deleted clubs kept for",
        "Days each backup of a club deleted for good is kept, counted from "
        "the day it was made; 0 keeps them like any other club's",
        lambda cfg: "0",
        "keep_days",
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
        "files.s3.endpoint",
        "Files S3 endpoint",
        "S3-compatible endpoint URL for club files, e.g. "
        "https://eu2.contabostorage.com. Empty: files stay on the server",
        lambda cfg: cfg.get("FILES_S3_ENDPOINT") or "",
        "url",
    ),
    Spec(
        "files.s3.bucket",
        "Files S3 bucket",
        "Bucket for club files (not the backup bucket). Each file is "
        "encrypted with its club's key before it leaves the server",
        lambda cfg: cfg.get("FILES_S3_BUCKET") or "",
    ),
    Spec(
        "files.s3.region",
        "Files S3 region",
        "Usually 'default' for Contabo",
        lambda cfg: cfg.get("FILES_S3_REGION") or "default",
    ),
    Spec(
        "files.s3.access_key",
        "Files S3 access key",
        "Stored encrypted",
        lambda cfg: cfg.get("FILES_S3_ACCESS_KEY") or "",
        secret=True,
    ),
    Spec(
        "files.s3.secret_key",
        "Files S3 secret key",
        "Stored encrypted",
        lambda cfg: cfg.get("FILES_S3_SECRET_KEY") or "",
        secret=True,
    ),
    Spec(
        "files.max_mb",
        "Largest file (default)",
        "Largest file a club can upload, in MB, when its plan sets none "
        "(plans and clubs can have their own under All clubs)",
        lambda cfg: str(cfg.get("FILES_MAX_MB") or 25),
        "count",
    ),
    Spec(
        "domains.serving",
        "Serve club domains",
        "on: every verified club domain gets a certificate and its own "
        "Ingress (Kubernetes with cert-manager), and visitors are sent on to the "
        "club. off: their Ingresses are removed (the kill switch)",
        lambda cfg: "off",
        "on_off",
    ),
    Spec(
        "domains.cname_target",
        "Club domains point to",
        "The host clubs point their domain to (CNAME), shown in the club's "
        "domain settings, e.g. clubs.hubra.club",
        lambda cfg: cfg.get("CUSTOM_DOMAIN_TARGET") or "",
        "host",
    ),
    Spec(
        "domains.cluster_issuer",
        "Certificate issuer",
        "The cert-manager ClusterIssuer for club domains",
        lambda cfg: "letsencrypt",
        "k8s_name",
    ),
    Spec(
        "domains.ingress_class",
        "Ingress class",
        "The ingress class of club domains",
        lambda cfg: "traefik",
        "k8s_name",
    ),
    Spec(
        "domains.service",
        "Service for club domains",
        "The Service (port 'http') club domains are routed to; it sends "
        "visitors on to the club",
        lambda cfg: "global-backend",
        "k8s_name",
    ),
    Spec(
        "stripe.mode",
        "Stripe mode",
        "sandbox: every club uses the sandbox keys (sk_test_), no real money "
        "moves. live: clubs use the live keys; sandbox clubs (manage › club › "
        "Sandbox club) stay on the sandbox keys",
        lambda cfg: "sandbox",
        "stripe_mode",
    ),
    Spec(
        "payments.stripe.secret_key",
        "Stripe live key",
        "The platform's live Stripe key (Connect, sk_live_). Clubs connect "
        "their own Stripe account to it and members pay invoices online. "
        "Stored encrypted",
        lambda cfg: cfg.get("STRIPE_SECRET_KEY") or "",
        "stripe_live_key",
        secret=True,
    ),
    Spec(
        "payments.stripe.sandbox_secret_key",
        "Stripe sandbox key",
        "The platform's sandbox Stripe key (Connect, sk_test_), used in "
        "sandbox mode and always by sandbox clubs. Stored encrypted",
        lambda cfg: "",
        "stripe_test_key",
        secret=True,
    ),
    Spec(
        "payments.fee_percent",
        "Hubra fee",
        "Share of each online payment that goes to Hubra (%), on top of "
        "Stripe's own fees. The club pays both or passes them on to members "
        "as a surcharge. 0: none",
        lambda cfg: "0",
        "fee_percent",
    ),
    Spec(
        "billing.enabled",
        "Bill clubs with Stripe",
        "on: club admins see Einstellungen › Hubra-Abo and pay their plan "
        "through Stripe Checkout with the billing Stripe key; Stripe's "
        "state is read every hour. off: terms are only stored (docs/billing.md)",
        lambda cfg: "off",
        "on_off",
    ),
    Spec(
        "billing.yearly",
        "Bill yearly",
        "on: new subscriptions are charged once a year (12 × the monthly "
        "price). off: monthly. Running subscriptions change at their next sync",
        lambda cfg: "off",
        "on_off",
    ),
    Spec(
        "billing.stripe.secret_key",
        "Stripe billing live key",
        "Live secret or restricted key (sk_live_/rk_live_) of the Stripe "
        "account that bills clubs for Hubra. Empty: the Online payments live "
        "key. Stored encrypted",
        lambda cfg: cfg.get("STRIPE_BILLING_SECRET_KEY") or "",
        "stripe_live_key",
        secret=True,
    ),
    Spec(
        "billing.stripe.webhook_secret",
        "Stripe billing live webhook secret",
        "Signing secret (whsec_…) of the live Stripe webhook pointing at "
        "/api/v1/global/billing/stripe/webhook. Without it the status follows "
        "Stripe only through the hourly check. Stored encrypted",
        lambda cfg: cfg.get("STRIPE_BILLING_WEBHOOK_SECRET") or "",
        secret=True,
    ),
    Spec(
        "billing.stripe.sandbox_secret_key",
        "Stripe billing sandbox key",
        "Sandbox key (sk_test_/rk_test_) of the billing Stripe account, used "
        "in sandbox mode and always by sandbox clubs. Empty: the Online "
        "payments sandbox key. Stored encrypted",
        lambda cfg: "",
        "stripe_test_key",
        secret=True,
    ),
    Spec(
        "billing.stripe.sandbox_webhook_secret",
        "Stripe billing sandbox webhook secret",
        "Signing secret (whsec_…) of the same webhook in the Stripe sandbox. "
        "Stored encrypted",
        lambda cfg: "",
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
        "discord.audit_channel_id",
        "Audit channel",
        "Channel ID on the same server for the audit entries. Set: they go "
        "there instead of the platform log, which keeps the alerts. Empty: off",
        lambda cfg: "",
        "number",
    ),
    Spec(
        "discord.changelog_channel_id",
        "Changelog channel",
        "Channel ID on the same server for the release notes of Hubra and of "
        "every plugin update. Set: Hubra's release notes go there instead of "
        "the platform log. Empty: off",
        lambda cfg: "",
        "number",
    ),
    Spec(
        "discord.language",
        "Platform bot language",
        "Language of everything the bot posts on the platform's Discord server "
        "(log, audit, alerts, digest, buttons, command replies, support threads): "
        "de or en. Club servers follow each club's language",
        lambda cfg: "de",
        "discord_language",
    ),
    Spec(
        "discord.support_channel_id",
        "Support channel",
        "Channel ID on the platform's Discord server: every support case gets "
        "a private thread there, and what is written in it becomes a comment "
        "on the case. Empty: off",
        lambda cfg: "",
        "number",
    ),
    Spec(
        "discord.support_add_reporters",
        "Add reporters to the thread",
        "on: whoever sent a case is added to its Discord thread when their "
        "Discord is linked (people not on the platform server get an invite "
        "as a direct message). off: staff add people by hand",
        lambda cfg: "on",
        "on_off",
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
        "discord.platform_roles",
        "Roles on the platform server",
        "on: the bot gives everyone who linked Discord the roles Plattform-Admin, "
        "Vereinsinhaber, Vereinsadmin and Vereinsmitglied on the platform server. "
        "off deletes these roles again",
        lambda cfg: "off",
        "on_off",
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
        "notify.mail_events",
        "Platform events by mail",
        "Comma-separated platform event categories mailed to platform admins "
        "(clubs, requests, access, members, plugins, backups, platform). "
        "Empty: none",
        lambda cfg: "",
        "discord_log_events",
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
        "alerts.manage_url",
        "Manage address",
        "Address of the manage portal, for the button in alert mails "
        "(https://manage.hubra.club). Empty: no button",
        lambda cfg: cfg.get("MANAGE_BASE_URL") or "",
        "url",
    ),
    Spec(
        "mcp.url",
        "Claude connector address",
        "Address of the MCP server (app/mcp), shown with the setup command "
        "on the API tokens page (https://mcp.hubra.club). Empty: not set up",
        lambda cfg: cfg.get("MCP_PUBLIC_URL") or "",
        "url",
    ),
    Spec(
        "oauth.dynamic_clients",
        "Self-registered apps",
        "on: apps such as Claude may register themselves (OAuth dynamic client "
        "registration) to use the Claude connector; they can only read, and "
        "the person sees them as not checked by Hubra. off: only apps "
        "registered in manage",
        lambda cfg: "on",
        "on_off",
    ),
    Spec(
        "oauth.dynamic_redirect_hosts",
        "Return addresses for self-registered apps",
        "Hosts a self-registered app may send people back to, comma-separated "
        "(subdomains count). Empty: any https host",
        lambda cfg: "claude.ai,claude.com,localhost,127.0.0.1",
    ),
    Spec(
        "oauth.signing_keys",
        "Sign-in signing keys",
        "RSA keys that sign the ID tokens of Sign in with Hubra (OpenID "
        "Connect), newest first. Made automatically, stored encrypted",
        lambda cfg: "",
        secret=True,
    ),
    Spec(
        "oauth.subject_salt",
        "Sign-in subject key",
        "Makes the per-app person id (sub) of Sign in with Hubra. Made "
        "automatically, stored encrypted; changing it gives every person a "
        "new id in every app",
        lambda cfg: "",
        secret=True,
    ),
    Spec(
        "support.url",
        "Support site address",
        "Address of the support site (app/support-frontend): help, roadmap, "
        "status and problem reports (https://support.hubra.club). Links in "
        "mails to reporters point there. Empty: the club app's feedback page",
        lambda cfg: cfg.get("SUPPORT_BASE_URL") or "",
        "url",
    ),
    Spec(
        "legal.privacy_url",
        "Privacy policy URL",
        "Hubra's privacy policy. Linked on sign-up, in the footers and in "
        "Stripe Checkout; enter the same address in Stripe (Settings › "
        "Public details, Connect › Platform profile). Empty: no link",
        lambda cfg: cfg.get("LEGAL_PRIVACY_URL") or "https://hubra.club/datenschutz/",
        "url",
    ),
    Spec(
        "legal.terms_url",
        "Terms of service URL",
        "Hubra's terms of service. Linked on sign-up, in the footers and in "
        "Stripe Checkout; enter the same address in Stripe (Settings › "
        "Public details, Connect › Platform profile). Empty: no link",
        lambda cfg: cfg.get("LEGAL_TERMS_URL")
        or "https://hubra.club/nutzungsbedingungen/",
        "url",
    ),
    Spec(
        "legal.imprint_url",
        "Imprint URL",
        "Hubra's imprint (Impressum), linked in the footers. Empty: no link",
        lambda cfg: cfg.get("LEGAL_IMPRINT_URL") or "https://hubra.club/impressum/",
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
    Spec(
        "errors.auto_resolve",
        "Mark errors fixed on upgrade",
        "on: when every backend process runs a new build, open errors that "
        "have not happened on it are marked fixed in that build "
        "(services.error_tracker). They open again if they come back",
        lambda cfg: "on",
        "on_off",
    ),
    Spec(
        "upgrades.post_deploy_steps",
        "Post-deploy steps",
        "on: once every backend process runs a new build, a worker runs "
        "flask db upgrade, sync-tenant-schemas, sync-permissions, seed and "
        "plugins sync (services.post_deploy) and reports on System health. "
        "off: run them yourself, or start them in manage",
        lambda cfg: "on",
        "on_off",
    ),
    Spec(
        "limits.warn_percent",
        "Limit warning",
        "Club owners and the platform are warned when a club reaches this "
        "share of a limit (%). The second warning comes at 100 %",
        lambda cfg: "80",
        "percent",
    ),
    Spec(
        "translate.deepl_key",
        "DeepL API key",
        "Machine translation for posts in several languages "
        "(services.machine_translation). Empty: no machine translation, "
        "clubs write each language by hand. Stored encrypted",
        lambda cfg: "",
        secret=True,
    ),
    Spec(
        "translate.deepl_url",
        "DeepL API address",
        "https://api-free.deepl.com for a free key, https://api.deepl.com "
        "for a paid one",
        lambda cfg: "https://api-free.deepl.com",
    ),
    Spec(
        "wallet.google.issuer_id",
        "Google Wallet issuer id",
        "The long number on the Google Pay & Wallet Console. Empty: no "
        "\"Add to Google Wallet\" button",
        lambda cfg: "",
        "google_issuer_id",
    ),
    Spec(
        "wallet.google.class_id",
        "Google Wallet class id",
        "Id of the generic class created in the console (with or without the "
        "issuer id in front)",
        lambda cfg: "",
        "google_wallet_class",
    ),
    Spec(
        "wallet.google.service_account",
        "Google Wallet service account key",
        "The JSON key of a Google Cloud service account with the Developer "
        "role on the issuer account. Stored encrypted",
        lambda cfg: "",
        "google_service_account",
        secret=True,
    ),
    Spec(
        "wallet.google.logo_url",
        "Google Wallet pass logo",
        "Public https address of a square PNG (660 px recommended). Default: "
        "the sign-in site's app icon",
        lambda cfg: (
            f"{cfg['SSO_BASE_URL'].rstrip('/')}/icon-512.png"
            if cfg.get("SSO_BASE_URL")
            else ""
        ),
        "url",
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


_ROWS = "hubra_platform_settings_rows"


def _forget(session, *_args) -> None:
    session.info.pop(_ROWS, None)


def _row(key: str) -> PlatformSetting | None:
    """The stored row for *key*, or None.

    Most keys have no row (they use the deployment default), and
    ``session.get`` asks the database again for every missing key, so a
    single ``relay()`` used to cost six queries.  The first lookup in a
    transaction loads every row at once and keeps them (the session's
    identity map alone would let them go); the next commit or rollback
    forgets them, so another process's change is seen in the next
    transaction.
    """
    session = db.session()
    rows = session.info.get(_ROWS)
    if rows is None:
        rows = {r.key: r for r in session.scalars(select(PlatformSetting)).all()}
        session.info[_ROWS] = rows
        if not event.contains(session, "after_commit", _forget):
            event.listen(session, "after_commit", _forget)
            event.listen(session, "after_soft_rollback", _forget)
    return rows.get(key)


def get(key: str) -> str:
    """The stored value, or the default from the deployment config."""
    s = spec(key)
    row = _row(key)
    if row is not None and row.value is not None:
        # A cleared secret is stored as "" (not encrypted).
        if s.secret and row.value:
            return decrypt_code(row.value, _PURPOSE, PLATFORM)
        return row.value
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

    _forget(db.session())
    for key, value in values.items():
        s = _BY_KEY[key]
        row = db.session.get(PlatformSetting, key)
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
    _forget(db.session())


def legal_links() -> dict[str, str | None]:
    """Hubra's legal pages for the SPAs and Stripe Checkout (None: not set)."""
    out: dict[str, str | None] = {}
    for name, key in (
        ("privacyUrl", "legal.privacy_url"),
        ("termsUrl", "legal.terms_url"),
        ("imprintUrl", "legal.imprint_url"),
    ):
        try:
            out[name] = get(key).strip() or None
        except Exception:  # noqa: BLE001 - no database yet: the public page still loads
            current_app.logger.debug("platform setting %s not readable", key, exc_info=True)
            out[name] = None
    return out


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


SANDBOX = "sandbox"
LIVE = "live"


def _is_test_key(key: str) -> bool:
    return key.startswith(("sk_test_", "rk_test_"))


def stripe_mode(tenant=None) -> str:
    """``sandbox`` or ``live``: the Stripe keys *tenant* (default: the club
    of this request) uses.  A sandbox club is always in sandbox mode; any
    other club, and the platform itself, follows ``stripe.mode``."""
    from hubra.core.services import sandbox_clubs

    if tenant is None:
        tenant = sandbox_clubs.current()
    if tenant is not None and sandbox_clubs.is_sandbox(tenant):
        return SANDBOX
    return LIVE if get("stripe.mode") == LIVE else SANDBOX


def _pick(live: str, sandbox: str, mode: str) -> str:
    """The key for *mode*.  A test key in the live slot (stored before
    there were two) counts as the sandbox key and is never used live."""
    if mode == LIVE:
        return "" if _is_test_key(live) else live
    return sandbox or (live if _is_test_key(live) else "")


def stripe_key(mode: str) -> str:
    """The Online payments (Connect) key for *mode*; empty when not set."""
    return _pick(
        get("payments.stripe.secret_key"),
        get("payments.stripe.sandbox_secret_key"),
        mode,
    )


def billing_stripe_key(mode: str) -> str:
    """The billing account's key for *mode*; without one, the Online
    payments key of the same mode."""
    own = _pick(
        get("billing.stripe.secret_key"),
        get("billing.stripe.sandbox_secret_key"),
        mode,
    )
    return own or stripe_key(mode)


def billing_webhook_secrets() -> dict[str, str]:
    """``{mode: whsec}`` for each mode that has a webhook secret."""
    found = {
        LIVE: get("billing.stripe.webhook_secret"),
        SANDBOX: get("billing.stripe.sandbox_webhook_secret"),
    }
    return {mode: secret for mode, secret in found.items() if secret}


@dataclass(frozen=True)
class StripePlatform:
    secret_key: str
    fee_percent: float
    mode: str = ""  # sandbox or live (stripe_mode); the key always matches it

    @property
    def test_mode(self) -> bool:
        return _is_test_key(self.secret_key)


def stripe(tenant=None) -> StripePlatform | None:
    """The platform's Stripe Connect account in the mode of *tenant*
    (default: the club of this request), or None when that mode has no key."""
    mode = stripe_mode(tenant)
    key = stripe_key(mode)
    if not key:
        return None
    try:
        fee = float((get("payments.fee_percent") or "0").replace(",", "."))
    except ValueError:
        fee = 0.0
    own = _club_fee_percent(tenant)
    if own is not None:
        fee = own
    return StripePlatform(
        secret_key=key, fee_percent=max(0.0, min(fee, 10.0)), mode=mode
    )


def _club_fee_percent(tenant=None) -> float | None:
    """The club's own Hubra fee (manage › club › Billing), or None outside a
    club or when the club uses the default.  *tenant* defaults to the club
    of this request."""
    from hubra.core.services import sandbox_clubs

    if tenant is None:
        tenant = sandbox_clubs.current()
    if tenant is None:
        return None
    from hubra.core.services import club_billing

    own = club_billing.stored(tenant).get("payments_fee_percent")
    return None if own is None else float(own)


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
            _forget(db.session())  # the other process may have stored them
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
