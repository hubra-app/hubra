"""
Singleton extension instances.

These are created without an app object so they can be imported anywhere
without triggering circular imports.  Each is bound to the app inside
create_app() via its init_app() method.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_migrate import cli as _migrate_cli
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

# Parallel pull requests each add a migration on the head they saw, so main can
# have several heads at once (docs/migrations.md). "heads" is the same as "head"
# when there is one: `flask db upgrade` applies every head, and a new migration
# from `flask db migrate`/`revision` follows all of them.
for _command, _name in (
    (_migrate_cli.upgrade, "revision"),
    (_migrate_cli.migrate, "head"),
    (_migrate_cli.revision, "head"),
):
    for _param in _command.params:
        if _param.name == _name:
            _param.default = "heads"
jwt = JWTManager()
ma = Marshmallow()
cors = CORS()
limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["200 per minute"],
    headers_enabled=True,
    retry_after=None,  # don't add Retry-After to non-429 responses
)
