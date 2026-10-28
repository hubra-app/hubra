"""Tests for login without Member, signup, and tenant request workflow."""

from sqlalchemy import select


# ── Login without Member ─────────────────────────────────────────────────────


def test_login_user_without_member_returns_no_tenant(client, db):
    """A User with valid credentials but no Member gets a JWT with noTenant=true."""
    from vollbuild.core.models.user import User

    user = User(email="lonely@test.ch", first_name="Lonely", last_name="User")
    user.set_password("StrongPassword123!")
    db.session.add(user)
    db.session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "lonely@test.ch", "password": "StrongPassword123!"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("noTenant") is True
    assert body["user"]["email"] == "lonely@test.ch"
    assert "access_token_cookie" in resp.headers.get("Set-Cookie", "")


def test_login_user_without_member_permissions_endpoint_works(client, db):
    """A user logged in via the noTenant path can call /account/permissions."""
    from vollbuild.core.models.user import User

    user = User(email="perm@test.ch", first_name="Perm", last_name="User")
    user.set_password("StrongPassword123!")
    db.session.add(user)
    db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "perm@test.ch", "password": "StrongPassword123!"},
    )

    resp = client.get("/api/v1/account/permissions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["is_superadmin"] is False
    assert body["permissions"] == []


# ── Signup ───────────────────────────────────────────────────────────────────


def test_signup_creates_user_and_returns_jwt(client, db):
    """POST /auth/signup creates a new User and sets JWT cookies."""
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "New User",
            "email": "newuser@test.ch",
            "password": "VeryStrongPass123!",
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body.get("noTenant") is True
    assert body["user"]["email"] == "newuser@test.ch"
    assert "access_token_cookie" in resp.headers.get("Set-Cookie", "")

    from vollbuild.core.models.user import User

    user = db.session.scalar(select(User).where(User.email == "newuser@test.ch"))
    assert user is not None
    assert user.name == "New User"


def test_signup_duplicate_email_returns_409(client, db):
    """Duplicate email on signup returns 409, not 500."""
    from vollbuild.core.models.user import User

    user = User(email="existing@test.ch", first_name="Existing", last_name="User")
    user.set_password("VeryStrongPass123!")
    db.session.add(user)
    db.session.commit()

    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Duplicate",
            "email": "existing@test.ch",
            "password": "VeryStrongPass123!",
        },
    )
    assert resp.status_code == 409


def test_signup_weak_password_returns_400(client, db):
    """Weak password is rejected by zxcvbn strength check."""
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Weak User",
            "email": "weak@test.ch",
            "password": "password123",
        },
    )
    assert resp.status_code == 400


def test_signup_missing_fields_returns_400(client, db):
    """Missing required fields returns 400."""
    resp = client.post(
        "/api/v1/auth/signup",
        json={"name": "", "email": "", "password": ""},
    )
    assert resp.status_code == 400


# ── Tenant Requests ──────────────────────────────────────────────────────────


def _signup_and_get_client(client, db, email="requester@test.ch"):
    """Helper: signup a user and return the client with auth cookies set."""
    client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Requester",
            "email": email,
            "password": "VeryStrongPass123!",
        },
    )
    return client


def test_submit_tenant_request_success(client, db):
    """An authenticated user can submit a tenant request."""
    _signup_and_get_client(client, db)

    resp = client.post(
        "/api/v1/system/tenant-requests",
        json={
            "name": "Acme Club",
            "slug": "acme-club",
            "plan": "starter",
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["request"]["name"] == "Acme Club"
    assert body["request"]["slug"] == "acme-club"
    assert body["request"]["status"] == "pending"


def test_submit_tenant_request_unauthenticated_rejected(client, db):
    """Unauthenticated requests are rejected with 401."""
    resp = client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "Acme Club", "slug": "acme-club"},
    )
    assert resp.status_code == 401


def test_submit_tenant_request_duplicate_slug_with_existing_tenant(client, db):
    """Slug conflicting with an existing tenant returns 409."""
    from vollbuild.core.models.tenant import Tenant

    tenant = Tenant(
        name="Existing", slug="existing-club", plan="starter", status="active"
    )
    db.session.add(tenant)
    db.session.commit()

    _signup_and_get_client(client, db)
    resp = client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "New Club", "slug": "existing-club"},
    )
    assert resp.status_code == 409


def test_submit_tenant_request_duplicate_pending_slug(client, db):
    """Slug conflicting with a pending request returns 409."""
    _signup_and_get_client(client, db)
    client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "First Club", "slug": "dup-slug"},
    )

    _signup_and_get_client(client, db, email="second@test.ch")
    resp = client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "Second Club", "slug": "dup-slug"},
    )
    assert resp.status_code == 409


def test_list_my_tenant_requests(client, db):
    """A user can list their own tenant requests."""
    _signup_and_get_client(client, db)
    client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "My Club", "slug": "my-club"},
    )

    resp = client.get("/api/v1/system/tenant-requests/mine")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["requests"]) == 1
    assert body["requests"][0]["name"] == "My Club"


def test_list_tenant_requests_requires_superadmin(client, db):
    """Non-superadmin cannot list all tenant requests."""
    _signup_and_get_client(client, db)

    resp = client.get("/api/v1/system/tenant-requests")
    assert resp.status_code == 403


def test_approve_tenant_request_requires_superadmin(client, db):
    """Non-superadmin cannot approve tenant requests."""
    _signup_and_get_client(client, db)
    client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "Approve Me", "slug": "approve-me"},
    )

    resp = client.post("/api/v1/system/tenant-requests/1/approve")
    assert resp.status_code == 403


def test_reject_tenant_request_requires_superadmin(client, db):
    """Non-superadmin cannot reject tenant requests."""
    _signup_and_get_client(client, db)
    client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "Reject Me", "slug": "reject-me"},
    )

    resp = client.post("/api/v1/system/tenant-requests/1/reject")
    assert resp.status_code == 403


# ── Approval links requester ──────────────────────────────────────────────────


def test_approve_tenant_request_links_requester(client, db):
    """Approving a tenant request links the requesting user as admin.

    Before the fix, provision_tenant was called with admin_email=None,
    admin_password=None, so _seed_tenant never created a Member or
    UserTenant for the requester. Now admin_user_id=req.user_id is
    passed so the existing User is linked as the tenant admin.
    """
    from vollbuild.core.models.user import User
    from vollbuild.core.models.user_tenant import UserTenant
    from vollbuild.core.models.tenant import Tenant

    # 1. Signup a regular user (no tenant)
    _signup_and_get_client(client, db, email="requester2@test.ch")
    requester = db.session.scalar(
        select(User).where(User.email == "requester2@test.ch")
    )
    assert requester is not None

    # 2. Submit a tenant request
    resp = client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "Link Me Club", "slug": "link-me", "plan": "starter"},
    )
    assert resp.status_code == 201
    req_id = resp.get_json()["request"]["id"]

    # 3. Create a superadmin and login
    admin = User(
        email="superadmin@test.ch",
        first_name="Super",
        last_name="Admin",
        is_superadmin=True,
    )
    admin.set_password("VeryStrongPass123!")
    db.session.add(admin)
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@test.ch", "password": "VeryStrongPass123!"},
    )

    # 4. Approve the request — mock PostgreSQL-specific schema ops for SQLite
    from unittest.mock import patch

    with (
        patch("vollbuild.core.tenant.service.create_tenant_schema"),
        patch("vollbuild.core.tenant.context.set_search_path"),
        patch("vollbuild.core.tenant.context.reset_search_path"),
    ):
        resp = client.post(f"/api/v1/system/tenant-requests/{req_id}/approve")
    assert resp.status_code == 200
    assert resp.get_json()["request"]["status"] == "approved"

    # 5. Verify UserTenant link exists
    tenant = db.session.scalar(select(Tenant).where(Tenant.slug == "link-me"))
    assert tenant is not None
    link = db.session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == requester.id,
            UserTenant.tenant_id == tenant.id,
        )
    )
    assert link is not None, "Requesting user should be linked to the new tenant"

    # 6. Verify find_user_tenants returns the new tenant
    from vollbuild.api.auth.services import AuthService

    tenants = AuthService.find_user_tenants(requester.id)
    assert any(t["tenant_slug"] == "link-me" for t in tenants)


# ── Add user to tenant ────────────────────────────────────────────────────────


def test_add_user_to_tenant_success(client, db):
    """A superadmin can add an existing User to a tenant via POST /tenants/<id>/members."""
    from unittest.mock import patch

    from vollbuild.core.models.user import User
    from vollbuild.core.models.user_tenant import UserTenant
    from vollbuild.core.models.tenant import Tenant

    # Create a tenant with mocked schema ops
    tenant = Tenant(name="Test Club", slug="test-club-add", plan="starter")
    db.session.add(tenant)
    db.session.flush()
    with (
        patch("vollbuild.core.tenant.context.set_search_path"),
        patch("vollbuild.core.tenant.context.reset_search_path"),
    ):
        from vollbuild.core.tenant.service import _seed_tenant

        _seed_tenant(tenant.id, None, None)
    db.session.commit()

    # Create a no-tenant user
    user = User(email="addme@test.ch", first_name="Add", last_name="Me")
    user.set_password("VeryStrongPass123!")
    db.session.add(user)
    db.session.commit()

    # Create a superadmin and login
    admin = User(
        email="superadmin2@test.ch",
        first_name="Super",
        last_name="Admin",
        is_superadmin=True,
    )
    admin.set_password("VeryStrongPass123!")
    db.session.add(admin)
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin2@test.ch", "password": "VeryStrongPass123!"},
    )

    # Add the user to the tenant
    with (
        patch("vollbuild.core.tenant.context.set_search_path"),
        patch("vollbuild.core.tenant.context.reset_search_path"),
    ):
        resp = client.post(
            f"/api/v1/system/tenants/{tenant.id}/members",
            json={"email": "addme@test.ch"},
        )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["member"]["email"] == "addme@test.ch"

    # Verify UserTenant link
    link = db.session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == user.id,
            UserTenant.tenant_id == tenant.id,
        )
    )
    assert link is not None


def test_add_user_to_tenant_duplicate_returns_409(client, db):
    """Adding a user who is already a member returns 409."""

    from vollbuild.core.models.user import User
    from vollbuild.core.models.user_tenant import UserTenant
    from vollbuild.core.models.tenant import Tenant

    # Create a tenant + user + existing UserTenant
    tenant = Tenant(name="Dup Club", slug="dup-club", plan="starter")
    db.session.add(tenant)
    db.session.flush()

    user = User(email="dup@test.ch", first_name="Dup", last_name="User")
    user.set_password("VeryStrongPass123!")
    db.session.add(user)
    db.session.flush()
    db.session.add(UserTenant(user_id=user.id, tenant_id=tenant.id))
    db.session.commit()

    # Create superadmin and login
    admin = User(
        email="superadmin3@test.ch",
        first_name="Super",
        last_name="Admin",
        is_superadmin=True,
    )
    admin.set_password("VeryStrongPass123!")
    db.session.add(admin)
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin3@test.ch", "password": "VeryStrongPass123!"},
    )

    resp = client.post(
        f"/api/v1/system/tenants/{tenant.id}/members",
        json={"email": "dup@test.ch"},
    )
    assert resp.status_code == 409


def test_add_user_to_tenant_user_not_found(client, db):
    """Adding a non-existent user returns 404."""
    from vollbuild.core.models.user import User
    from vollbuild.core.models.tenant import Tenant

    tenant = Tenant(name="NF Club", slug="nf-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()

    admin = User(
        email="superadmin4@test.ch",
        first_name="Super",
        last_name="Admin",
        is_superadmin=True,
    )
    admin.set_password("VeryStrongPass123!")
    db.session.add(admin)
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin4@test.ch", "password": "VeryStrongPass123!"},
    )

    resp = client.post(
        f"/api/v1/system/tenants/{tenant.id}/members",
        json={"email": "nonexistent@test.ch"},
    )
    assert resp.status_code == 404


# ── My tenants endpoint ───────────────────────────────────────────────────────


def test_my_tenants_returns_user_tenants(client, seeded_db, db):
    """GET /account/my-tenants returns the user's tenant memberships."""
    from vollbuild.core.models.user_tenant import UserTenant
    from vollbuild.core.models.tenant import Tenant

    # Use the existing seeded admin user
    user = seeded_db["user"]

    # Create a second tenant and link the user
    t2 = Tenant(name="Club Two", slug="club-two", plan="growth")
    db.session.add(t2)
    db.session.flush()
    db.session.add(UserTenant(user_id=user.id, tenant_id=t2.id))
    db.session.commit()

    # Login as the member (standard path, cookies set with user_id claim)
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    resp = client.get("/api/v1/account/my-tenants")
    assert resp.status_code == 200
    body = resp.get_json()
    slugs = {t["tenant_slug"] for t in body["tenants"]}
    assert "club-two" in slugs


def test_my_tenants_empty_for_single_tenant_member(client, seeded_db):
    """A single-tenant member (no UserTenant records) gets a fallback entry.

    With the User/Member split, the JWT includes a user_id claim. When no
    UserTenant records exist, find_user_tenants falls back to the Member
    and returns a single entry with tenant_slug=None (implicit tenant).
    """
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    resp = client.get("/api/v1/account/my-tenants")
    assert resp.status_code == 200
    body = resp.get_json()
    tenants = body["tenants"]
    # Single-tenant fallback: one entry with null tenant info
    assert len(tenants) == 1
    assert tenants[0]["tenant_slug"] is None
    assert tenants[0]["member_id"] is not None


# ── Refresh token for no-tenant users ─────────────────────────────────────────


def test_refresh_token_for_no_tenant_user(client, db):
    """A no-tenant user (identity 'user:<id>') can refresh without a 500.

    Regression test: check_locked did int(identity) which raised ValueError
    for 'user:1' identities, crashing /auth/refresh with a 500.
    """
    from vollbuild.core.models.user import User

    user = User(email="refresh@test.ch", first_name="Refresh", last_name="User")
    user.set_password("StrongPassword123!")
    db.session.add(user)
    db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@test.ch", "password": "StrongPassword123!"},
    )

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True
