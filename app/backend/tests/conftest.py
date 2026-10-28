import os

os.environ.setdefault("FLASK_ENV", "testing")

from unittest.mock import patch

import pytest
from argon2 import PasswordHasher

from hubra import create_app
from hubra.core.extensions import db as _db
from hubra.core.models import *  # noqa: F401,F403 — import all models so SA knows them

_NOT_CONFIGURED = {"ok": False, "latency_ms": 0, "error": "not configured"}


def _set_cookie_value(resp, name: str) -> str | None:
    """Extract a cookie's value from the Set-Cookie response headers."""
    for header in resp.headers.getlist("Set-Cookie"):
        if header.startswith(f"{name}="):
            return header.split(";", 1)[0].split("=", 1)[1]
    return None


@pytest.fixture(autouse=True)
def _mock_health_checks():
    """Patch slow health-check services to avoid 2s network timeouts each.

    check_db is left real — SQLite in-memory is instant.  Tests that need
    specific mock values provide their own patches which override these.
    """
    from hubra.api.health.services import HealthService

    with (
        patch.object(HealthService, "check_redis", return_value=_NOT_CONFIGURED),
        patch.object(HealthService, "check_smtp", return_value=_NOT_CONFIGURED),
        patch.object(HealthService, "check_imap", return_value=_NOT_CONFIGURED),
    ):
        yield


@pytest.fixture(autouse=True)
def _fast_argon2():
    """Use low-cost argon2 parameters in tests for faster password hashing."""
    from hubra.core.models import user as user_module

    fast_ph = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    with patch.object(user_module, "_ph", fast_ph):
        yield


@pytest.fixture(autouse=True)
def _reset_redis_breaker():
    """Keep one test's simulated Redis outage from leaking into the next."""
    from hubra.core.redis_client import reset_redis_down

    reset_redis_down()
    yield
    reset_redis_down()


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        yield _db
        _db.session.rollback()
        # Truncate every table so the next test starts with a clean slate.
        # Disable FK checks while deleting to avoid constraint ordering issues.
        _db.session.execute(_db.text("PRAGMA foreign_keys = OFF"))
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.execute(_db.text("PRAGMA foreign_keys = ON"))
        _db.session.commit()


@pytest.fixture
def seeded_db(db):
    """Create minimal seed data: 1 role, 1 tier, 1 admin User + Member."""
    from hubra.core.models.role import Role
    from hubra.core.models.member import Member, MembershipTier
    from hubra.core.models.user import User

    role = Role(name="Admin", is_default=True, is_admin=True, is_system=True)
    owner_role = Role(name="Owner", is_admin=True, is_system=True, is_owner=True)
    tier = MembershipTier(name="Maker", price_chf=45, color="#2596be")
    db.session.add_all([role, owner_role, tier])
    db.session.flush()

    user = User(
        email="admin@test.ch",
        first_name="Test",
        last_name="Admin",
        private_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    admin = Member(
        user_id=user.id,
        status="active",
        tier_id=tier.id,
    )
    admin.roles = [owner_role]
    db.session.add(admin)

    db.session.commit()

    # Every module on, as before modules could be switched off.
    from tests.helpers import set_modules

    set_modules(True)

    return {
        "role": role,
        "owner_role": owner_role,
        "tier": tier,
        "admin": admin,
        "user": user,
    }


@pytest.fixture
def auth_headers(client, seeded_db):
    """Log in via cookie-based JWT. Cookies are stored on the test client automatically.
    Returns an empty dict so existing `headers=auth_headers` call sites keep working."""
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    return {}


# ── CSRF-enabled fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def csrf_client(app, client, seeded_db):
    """Test client with JWT_COOKIE_CSRF_PROTECT enabled.

    Logs in the seeded admin and extracts the CSRF access token so tests
    can attach it as the X-CSRF-TOKEN header. Returns a dict with
    ``client`` and ``csrf_token`` keys.
    """
    from unittest.mock import patch

    with patch.dict(app.config, {"JWT_COOKIE_CSRF_PROTECT": True}):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        csrf_token = _set_cookie_value(login_resp, "csrf_access_token")
        assert csrf_token, "csrf_access_token cookie must be set when CSRF is on"
        yield {"client": client, "csrf_token": csrf_token}


@pytest.fixture
def csrf_refresh_token(app, client, seeded_db):
    """Extract the CSRF refresh token after login (CSRF protection enabled)."""
    from unittest.mock import patch

    with patch.dict(app.config, {"JWT_COOKIE_CSRF_PROTECT": True}):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        token = _set_cookie_value(login_resp, "csrf_refresh_token")
        assert token, "csrf_refresh_token cookie must be set when CSRF is on"
        yield token


# ── Multi-tenant fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def tenant_pair(db, seeded_db):
    """Create two tenants (A and B) with a shared User, UserTenant links,
    and tenant-scoped Members. Returns a dict with all entities.

    Layout:
      - User: user@test.ch / password123 (global identity)
      - Tenant A (slug: tenant-a): Member admin-a@test.ch
      - Tenant B (slug: tenant-b): Member admin-b@test.ch
    """
    from hubra.core.models.tenant import Tenant
    from hubra.core.models.user import User
    from hubra.core.models.user_tenant import UserTenant
    from hubra.core.models.member import Member
    from hubra.core.models.role import Role

    tenant_a = Tenant(name="Tenant A", slug="tenant-a", plan="starter", status="active")
    tenant_b = Tenant(name="Tenant B", slug="tenant-b", plan="starter", status="active")
    db.session.add_all([tenant_a, tenant_b])
    db.session.flush()

    user = User(
        email="user@test.ch",
        first_name="Test",
        last_name="User",
        private_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    db.session.add_all(
        [
            UserTenant(user_id=user.id, tenant_id=tenant_a.id),
            UserTenant(user_id=user.id, tenant_id=tenant_b.id),
        ]
    )
    db.session.flush()

    role_a = Role(name="Admin A", is_default=True, is_admin=True)
    role_b = Role(name="Admin B", is_default=True, is_admin=True)
    db.session.add_all([role_a, role_b])
    db.session.flush()

    member_a = Member(
        user_id=user.id,
        status="active",
    )
    member_a.roles = [role_a]
    db.session.add(member_a)

    member_b = Member(
        user_id=user.id,
        status="active",
    )
    member_b.roles = [role_b]
    db.session.add(member_b)

    db.session.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user": user,
        "member_a": member_a,
        "member_b": member_b,
        "role_a": role_a,
        "role_b": role_b,
    }
