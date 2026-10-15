"""
Application configuration classes.

All values are read from environment variables (or .env via python-dotenv).
Use config_map to look up a class by name:

    from vollbuild.core.config import config_map
    cfg = config_map[os.environ.get("FLASK_ENV", "development")]
"""

import logging as _logging
import os
import secrets as _secrets
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# In development, overlay .env.dev (if present) to override production values
# from .env with localhost-friendly defaults. .env.dev is gitignored.
if os.environ.get("FLASK_ENV", "development") == "development":
    from dotenv import find_dotenv

    _dev_env = find_dotenv(".env.dev")
    if _dev_env:
        load_dotenv(_dev_env, override=True)

_cfg_log = _logging.getLogger(__name__)


def _require_env(key: str) -> str:
    """Return the value of *key* from the environment, or raise RuntimeError."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"[Production] Required environment variable '{key}' is not set."
        )
    return value


def _dev_secret(env_key: str, length: int = 32) -> str:
    """Return env var value, or a random secret with a warning if unset."""
    val = os.environ.get(env_key)
    if val:
        return val
    generated = _secrets.token_hex(length)
    _cfg_log.warning(
        "%s is not set — using a random per-process secret. "
        "Set this env var to a stable value to keep sessions alive across restarts.",
        env_key,
    )
    return generated


class BaseConfig:
    # ── Flask core ──────────────────────────────────────────────────────────
    SECRET_KEY: str = _dev_secret("SECRET_KEY")

    # ── SQLAlchemy ──────────────────────────────────────────────────────────
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    # pool_pre_ping is safe for all dialects (SQLite + PostgreSQL).
    # Pool-sizing options (pool_size, max_overflow, pool_timeout) are set
    # separately in DevelopmentConfig and ProductionConfig because SQLite's
    # StaticPool does not accept them.
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,  # detect stale connections before use
    }

    # ── JWT ─────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = _dev_secret("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(
        minutes=int(os.environ.get("ACCESS_TOKEN_MINUTES", 15))
    )
    JWT_REFRESH_TOKEN_EXPIRES: timedelta = timedelta(
        days=int(os.environ.get("REFRESH_TOKEN_DAYS", 30))
    )
    JWT_TOKEN_LOCATION: list = ["cookies"]
    JWT_COOKIE_SECURE: bool = (
        os.environ.get("JWT_COOKIE_SECURE", "").lower() in ("true", "1", "yes")
        or os.environ.get("FLASK_ENV") == "production"
    )
    JWT_COOKIE_SAMESITE: str = os.environ.get("JWT_COOKIE_SAMESITE", "Lax")
    JWT_COOKIE_DOMAIN: str | None = os.environ.get("JWT_COOKIE_DOMAIN") or None
    JWT_COOKIE_CSRF_PROTECT: bool = True
    # Methods that require CSRF validation (double-submit cookie pattern).
    JWT_CSRF_METHODS: list[str] = ["POST", "PUT", "PATCH", "DELETE"]
    # Validate CSRF on refresh-token endpoints as well.
    JWT_CSRF_CHECK_REFRESH: bool = True
    # Paths exempt from CSRF protection (e.g. webhook endpoints that use
    # their own secret-based authentication). Populated per-deployment.
    CSRF_EXEMPT_PATHS: list[str] = []
    # Persistent cookies (with max_age) so set_refresh_cookies(max_age=...) works.
    # When True (default), cookies are session-only and max_age is ignored.
    JWT_SESSION_COOKIE: bool = False

    # ── CORS ────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.environ.get(
            "CORS_ORIGINS",
            os.environ.get("CORS_ORIGIN", "http://localhost:5173"),
        ).split(",")
        if o.strip()
    ]

    # ── Frontend origin (for email links & out-of-band URLs) ────────────────
    # The API and frontend now live on separate subdomains (api.vollbuild.ch vs
    # cos.vollbuild.ch), so request.url_root resolves to the API host and must
    # NOT be used to build links that open the SPA. Set this to the frontend's
    # canonical origin, e.g. https://cos.vollbuild.ch.
    FRONTEND_BASE_URL: str = os.environ.get("FRONTEND_BASE_URL", "")

    # ── SSO portal origin (for auth-related email links) ─────────────────────
    # Password-reset and email-verification links point to the SSO portal
    # (sso.vollbuild.ch) rather than the COS frontend. Falls back to
    # FRONTEND_BASE_URL for backward compatibility when not set.
    SSO_BASE_URL: str = os.environ.get("SSO_BASE_URL", "")

    # ── Integrations ────────────────────────────────────────────────────────
    WILDDUCK_API_URL: str = os.environ.get("WILDDUCK_API_URL", "")
    WILDDUCK_API_TOKEN: str = os.environ.get("WILDDUCK_API_TOKEN", "")
    SMTP_HOST: str = os.environ.get("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.environ.get("SMTP_PORT", 587))
    IMAP_HOST: str = os.environ.get("IMAP_HOST", "localhost")
    IMAP_PORT: int = int(os.environ.get("IMAP_PORT", 143))
    MAIL_FROM: str = os.environ.get("MAIL_FROM", "")
    MAIL_HOST: str = os.environ.get("MAIL_HOST", "")
    MAIL_DOMAIN: str = os.environ.get("MAIL_DOMAIN", "")

    # ── Fernet encryption key (codes at rest) ──────────────────────────────
    # If not set, derived from SECRET_KEY (legacy behavior, not recommended
    # for new deployments). Generate with:
    #   python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    FERNET_KEY: str = os.environ.get("FERNET_KEY", "")

    # ── Brevo transactional email ───────────────────────────────────────────
    BREVO_API_KEY: str = os.environ.get("BREVO_API_KEY", "")

    # ── ZoneMTA SMTP fallback (independent of member IMAP/SMTP) ────────────
    # When set, these override SMTP_HOST/SMTP_PORT for transactional email.
    ZONEMTA_SMTP_HOST: str = os.environ.get("ZONEMTA_SMTP_HOST", "")
    ZONEMTA_SMTP_PORT: int = int(os.environ.get("ZONEMTA_SMTP_PORT", 0))

    # ── Discord / bot ───────────────────────────────────────────────────────
    API_BOT_KEY: str = os.environ.get("API_BOT_KEY", "")
    DISCORD_CLIENT_ID: str = os.environ.get("DISCORD_CLIENT_ID", "")
    DISCORD_CLIENT_SECRET: str = os.environ.get("DISCORD_CLIENT_SECRET", "")
    DISCORD_WEBHOOK_URL: str = os.environ.get("DISCORD_WEBHOOK_URL", "")

    # ── Redis / rate limiting ───────────────────────────────────────────────
    REDIS_URL: str = os.environ.get("REDIS_URL", "")
    # flask-limiter 4.x reads RATELIMIT_STORAGE_URI (not RATE_LIMIT_STORAGE).
    # Accept both for backward compatibility.  Normalise to include "://"
    # since the limits library requires a scheme (e.g. "memory" → "memory://").
    _raw_storage = os.environ.get(
        "RATELIMIT_STORAGE_URI",
        os.environ.get("RATE_LIMIT_STORAGE", "memory://"),
    )
    RATELIMIT_STORAGE_URI: str = (
        _raw_storage if "://" in _raw_storage else f"{_raw_storage}://"
    )
    RATELIMIT_HEADERS_ENABLED: bool = True

    # ── Backups (Contabo S3) ─────────────────────────────────────────────────
    # S3 connection — also editable via Settings UI (backup namespace).
    # Env vars serve as fallback when KV settings are not populated.
    BACKUP_S3_ENDPOINT: str = os.environ.get("BACKUP_S3_ENDPOINT", "")
    BACKUP_S3_BUCKET: str = os.environ.get("BACKUP_S3_BUCKET", "")
    BACKUP_S3_ACCESS_KEY: str = os.environ.get("BACKUP_S3_ACCESS_KEY", "")
    BACKUP_S3_SECRET_KEY: str = os.environ.get("BACKUP_S3_SECRET_KEY", "")
    BACKUP_S3_REGION: str = os.environ.get("BACKUP_S3_REGION", "default")
    # GPG encryption passphrase — .env ONLY, never stored in DB (DR safety).
    BACKUP_ENCRYPTION_KEY: str = os.environ.get("BACKUP_ENCRYPTION_KEY", "")

    # ── Structured logging ──────────────────────────────────────────────────
    JSON_LOGGING: bool = os.environ.get("JSON_LOGGING", "true").lower() == "true"


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "sqlite:///dev.db")
    # Echo SQL to stdout in development for debugging
    SQLALCHEMY_ECHO: bool = False
    # Pool sizing for PostgreSQL (not used when falling back to SQLite)
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        "pool_recycle": 300,
        "pool_timeout": 10,
        "pool_size": 5,
        "max_overflow": 10,
    }


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
    SQLALCHEMY_ECHO: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        "pool_recycle": 300,
        "pool_timeout": 10,
        "pool_size": 5,
        "max_overflow": 10,
    }

    @classmethod
    def validate(cls) -> None:
        """Raise RuntimeError if any required production env var is missing.

        Called by create_app() after selecting this config class so that
        the error surfaces at app startup, not at module import time
        (which would break test collection).
        """
        _require_env("SECRET_KEY")
        _require_env("JWT_SECRET_KEY")
        _require_env("DATABASE_URL")
        if not os.environ.get("FERNET_KEY"):
            _cfg_log.warning(
                "FERNET_KEY is not set in production — falling back to "
                "SECRET_KEY-derived key (legacy, not recommended). "
                "Set FERNET_KEY independently for proper key separation "
                "and rotation support."
            )

    # Override insecure BaseConfig fallbacks with env vars (no default).
    # Missing vars produce an empty string here; validate() catches them.
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "")


class TestingConfig(BaseConfig):
    TESTING: bool = True
    DEBUG: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SQLALCHEMY_ECHO: bool = False
    # Long-lived tokens so tests don't expire mid-run
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(hours=1)
    # Fixed 32+ byte key to satisfy RFC 7518 §3.2 minimum HMAC key length.
    # Overrides the env-var fallback in BaseConfig so tests never trigger
    # InsecureKeyLengthWarning regardless of the JWT_SECRET_KEY env var.
    JWT_SECRET_KEY: str = "test-jwt-secret-key-at-least-32-bytes!"
    WTF_CSRF_ENABLED: bool = False
    JWT_COOKIE_CSRF_PROTECT: bool = False
    # Reset cookie attrs that may bleed in from .env via load_dotenv()
    JWT_COOKIE_DOMAIN: str | None = None
    JWT_COOKIE_SAMESITE: str = "Lax"
    JWT_COOKIE_SECURE: bool = False
    # Faster password hashing in tests
    BCRYPT_LOG_ROUNDS: int = 4
    # Disable JSON logging in tests for readable output
    JSON_LOGGING: bool = False
    # Force in-memory rate limiting so tests don't need a Redis instance
    RATELIMIT_STORAGE_URI: str = "memory://"
    # Disable rate limiting globally in tests to prevent spurious 429s;
    # override RATELIMIT_ENABLED=True in specific fixtures that test rate limits.
    RATELIMIT_ENABLED: bool = False
    # Isolate tests from .env values that would trigger live-service calls
    MAIL_DOMAIN: str = ""
    WILDDUCK_API_URL: str = ""
    WILDDUCK_API_TOKEN: str = ""
    BREVO_API_KEY: str = ""
    REDIS_URL: str = ""
    BACKUP_S3_ENDPOINT: str = ""
    BACKUP_S3_BUCKET: str = ""
    BACKUP_S3_ACCESS_KEY: str = ""
    BACKUP_S3_SECRET_KEY: str = ""
    BACKUP_ENCRYPTION_KEY: str = ""
    FERNET_KEY: str = ""
    # Run Celery tasks synchronously so tests don't need a Redis broker
    CELERY_TASK_ALWAYS_EAGER: bool = True
    CELERY_ALWAYS_EAGER: bool = True


config_map: dict = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
