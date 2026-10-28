"""
Singleton extension instances.

These are created without an app object so they can be imported anywhere
without triggering circular imports.  Each is bound to the app inside
create_app() via its init_app() method.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _rate_limit_key() -> str:
    """Use JWT identity for authenticated requests, fall back to IP for unauthenticated ones.

    This prevents per-IP bypass by distributing clients with many IPs — an
    authenticated user is still capped regardless of how many addresses they rotate.
    """
    try:
        from flask_jwt_extended import get_jwt_identity

        identity = get_jwt_identity()
        if identity:
            return f"user:{identity}"
    except Exception:
        pass
    return get_remote_address()


db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
ma = Marshmallow()
cors = CORS()
limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["200 per minute"],
    headers_enabled=True,
    retry_after=None,  # don't add Retry-After to non-429 responses
)


@limiter.request_filter
def _exempt_options_preflight() -> bool:
    """Exempt CORS preflight (OPTIONS) from rate limiting.

    Preflight carries no credentials and must return 200/204 with CORS headers.
    A 429 on OPTIONS would break every cross-origin request before it starts.
    Auth and RBAC already bypass OPTIONS via Flask's automatic OPTIONS handler;
    this ensures the limiter does too. CrowdSec runs as a Traefik middleware
    (crowdsec@file) and must likewise pass OPTIONS through unchanged — see the
    operator note in docs/SUBDOMAIN_MIGRATION.md.
    """
    from flask import request

    return request.method == "OPTIONS"
