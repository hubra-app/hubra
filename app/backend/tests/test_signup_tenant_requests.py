"""Tests for login without Member, signup, and tenant request workflow."""

from sqlalchemy import select


# ── Login without Member ─────────────────────────────────────────────────────


def test_login_user_without_member_returns_no_tenant(client, db):
    """A User with valid credentials but no Member gets a JWT with noTenant=true."""
    from hubra.core.models.user import User

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
    from hubra.core.models.user import User

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

    from hubra.core.models.user import User

    user = db.session.scalar(select(User).where(User.email == "newuser@test.ch"))
    assert user is not None
    assert user.name == "New User"


def test_signup_duplicate_email_returns_409(client, db):
    """Duplicate email on signup returns 409, not 500."""
    from hubra.core.models.user import User

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
    from hubra.core.models.tenant import Tenant

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
    from hubra.core.models.user import User
    from hubra.core.models.user_tenant import UserTenant
    from hubra.core.models.tenant import Tenant

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
        patch("hubra.core.tenant.service.create_tenant_schema"),
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.core.tenant.context.reset_search_path"),
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
    from hubra.api.auth.services import AuthService

    tenants = AuthService.find_user_tenants(requester.id)
    assert any(t["tenant_slug"] == "link-me" for t in tenants)


# ── Add user to tenant ────────────────────────────────────────────────────────


def test_add_user_to_tenant_success(client, db):
    """A superadmin can add an existing User to a tenant via POST /tenants/<id>/members."""
    from unittest.mock import patch

    from hubra.core.models.user import User
    from hubra.core.models.user_tenant import UserTenant
    from hubra.core.models.tenant import Tenant

    # Create a tenant with mocked schema ops
    tenant = Tenant(name="Test Club", slug="test-club-add", plan="starter")
    db.session.add(tenant)
    db.session.flush()
    with (
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.core.tenant.context.reset_search_path"),
    ):
        from hubra.core.tenant.service import _seed_tenant

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
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.core.tenant.context.reset_search_path"),
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

    from hubra.core.models.user import User
    from hubra.core.models.user_tenant import UserTenant
    from hubra.core.models.tenant import Tenant

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
    from hubra.core.models.user import User
    from hubra.core.models.tenant import Tenant

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
    from hubra.core.models.user_tenant import UserTenant
    from hubra.core.models.tenant import Tenant

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
    from hubra.core.models.user import User

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


def test_a_request_needs_a_slug_the_club_can_use(client, db):
    """The slug is checked when the request comes in, not only on approval."""
    _signup_and_get_client(client, db)
    for slug in ("Mein Verein", "-abc", "api", "app", "assets"):
        resp = client.post(
            "/api/v1/system/tenant-requests",
            json={"name": "Club", "slug": slug},
        )
        assert resp.status_code == 400, slug


def test_tenant_request_and_global_role_refuse_wrong_types(client, db, staff_headers):
    for body in ({"name": 5, "slug": "acme"}, {"name": "Acme", "slug": ["acme"]}):
        resp = client.post("/api/v1/system/tenant-requests", json=body)
        assert resp.status_code == 400, body
    for body in ({"name": 5}, {"name": "Kasse", "permissions": 5}):
        resp = client.post("/api/v1/system/global-roles", json=body)
        assert resp.status_code == 400, body


def test_platform_routes_refuse_wrong_types(client, db, seeded_db, staff_headers):
    from hubra.core.models.tenant import Tenant

    tenant = Tenant(name="Typed", slug="typed-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()
    user_id = seeded_db["user"].id
    for method, path, body in (
        ("patch", f"/api/v1/system/tenants/{tenant.id}", {"name": ["x"]}),
        ("patch", f"/api/v1/system/tenants/{tenant.id}", {"name": ""}),
        ("patch", f"/api/v1/system/tenants/{tenant.id}", {"settings": [1]}),
        ("post", f"/api/v1/system/tenants/{tenant.id}/members", {"user_id": {"a": 1}}),
        ("post", f"/api/v1/system/tenants/{tenant.id}/members", {"email": 5}),
        ("post", f"/api/v1/system/users/{user_id}/roles", {"role_id": [1]}),
    ):
        resp = getattr(client, method)(path, json=body)
        assert resp.status_code == 400, (path, body, resp.get_json())
    db.session.refresh(tenant)
    assert tenant.name == "Typed"


def test_club_picker_leaves_out_clubs_where_archived(db, seeded_db):
    from datetime import datetime, timezone

    from hubra.api.auth.services import AuthService
    from hubra.core.models.tenant import Tenant
    from hubra.core.models.user_tenant import UserTenant

    user = seeded_db["user"]
    t2 = Tenant(name="Club Two", slug="club-two", plan="growth")
    db.session.add(t2)
    db.session.flush()
    db.session.add(UserTenant(user_id=user.id, tenant_id=t2.id))
    db.session.commit()
    assert AuthService.find_user_tenants(user.id)

    seeded_db["admin"].archived_at = datetime.now(timezone.utc)
    db.session.commit()
    assert AuthService.find_user_tenants(user.id) == []


def test_suspended_club_is_not_offered_or_opened(client, db, seeded_db):
    from hubra.api.auth.services import AuthService
    from hubra.core.models.tenant import Tenant
    from hubra.core.models.user_tenant import UserTenant

    user = seeded_db["user"]
    t2 = Tenant(name="Club Two", slug="club-two", plan="growth", status="suspended")
    db.session.add(t2)
    db.session.flush()
    db.session.add(UserTenant(user_id=user.id, tenant_id=t2.id))
    db.session.commit()
    assert AuthService.find_user_tenants(user.id) == []

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    resp = client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "club-two"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "CLUB_INACTIVE"


# ── Requester is mailed the decision ─────────────────────────────────────────


def _request_and_sign_in_staff(client, db, slug):
    """A user's pending request for *slug*, then a superadmin signed in."""
    import json
    from pathlib import Path

    import hubra
    from hubra.core.models.translation import Translation
    from hubra.core.models.user import User

    seed = Path(hubra.__file__).parent / "core/seed_data/translations/de-CH.json"
    for key, value in json.loads(seed.read_text()).items():
        if key.startswith("mail.email."):
            db.session.add(Translation(locale="de-CH", key=key, value=value))

    _signup_and_get_client(client, db, email=f"{slug}@test.ch")
    resp = client.post(
        "/api/v1/system/tenant-requests",
        json={"name": "Chor <Nord>", "slug": slug},
    )
    req_id = resp.get_json()["request"]["id"]

    admin = User(
        email=f"staff-{slug}@test.ch",
        first_name="Staff",
        last_name="Admin",
        is_superadmin=True,
    )
    admin.set_password("VeryStrongPass123!")
    db.session.add(admin)
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": f"staff-{slug}@test.ch", "password": "VeryStrongPass123!"},
    )
    return req_id


def test_approving_a_request_mails_the_requester(client, db, app):
    from unittest.mock import patch

    app.config["SSO_BASE_URL"] = "https://sso.example.ch"
    req_id = _request_and_sign_in_staff(client, db, "mail-ok")

    with (
        patch("hubra.core.tenant.service.create_tenant_schema"),
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.core.tenant.context.reset_search_path"),
        patch("hubra.core.services.email._send", return_value=True) as send,
    ):
        resp = client.post(f"/api/v1/system/tenant-requests/{req_id}/approve")

    assert resp.status_code == 200
    assert resp.get_json()["notified"] is True
    send.assert_called_once()
    to, _name, subject, html, text = send.call_args.args
    assert to == "mail-ok@test.ch"
    assert send.call_args.kwargs["system"] is True
    assert "Chor <Nord>" in subject
    assert "Chor &lt;Nord&gt;" in html and "<Nord>" not in html
    assert 'href="https://sso.example.ch/clubs"' in html
    assert "https://sso.example.ch/clubs" in text


def test_rejecting_a_request_mails_the_note(client, db, app):
    from unittest.mock import patch

    app.config["SSO_BASE_URL"] = "https://sso.example.ch"
    req_id = _request_and_sign_in_staff(client, db, "mail-no")

    with patch("hubra.core.services.email._send", return_value=True) as send:
        resp = client.post(
            f"/api/v1/system/tenant-requests/{req_id}/reject",
            json={"note": "Name <b>schon vergeben</b>"},
        )

    assert resp.status_code == 200
    assert resp.get_json()["notified"] is True
    _to, _name, _subject, html, text = send.call_args.args
    assert "mail-no" in html
    assert "Name &lt;b&gt;schon vergeben&lt;/b&gt;" in html
    assert "Name <b>schon vergeben</b>" in text
    assert 'href="https://sso.example.ch/start"' in html


def test_a_mail_failure_does_not_undo_the_decision(client, db):
    from unittest.mock import patch

    from hubra.core.models.tenant_request import TenantRequest

    req_id = _request_and_sign_in_staff(client, db, "mail-down")

    with patch(
        "hubra.core.services.email.render_mail_template",
        side_effect=RuntimeError("template broke"),
    ):
        resp = client.post(f"/api/v1/system/tenant-requests/{req_id}/reject")

    assert resp.status_code == 200
    assert resp.get_json()["notified"] is False
    assert db.session.get(TenantRequest, req_id).status == "rejected"
