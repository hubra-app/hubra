"""Tests for /api/v1/account/ endpoints (profile, invoices, groups, mail-settings)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def member_headers(client, seeded_db):
    """Authenticate as the seeded admin member and return headers."""
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "password123",
        },
    )
    assert resp.status_code == 200
    return {}


# ── PATCH /account/ — avatar and profile_note ─────────────────────────────────


def test_patch_account_avatar_persists(client, member_headers):
    """PATCH /account/ with avatar persists the value and returns 200."""
    resp = client.patch(
        "/api/v1/account/",
        json={"avatar": "MK"},
        headers=member_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["avatar"] == "MK"


def test_patch_account_profile_note_persists(client, member_headers):
    """PATCH /account/ with profile_note persists the value and returns 200."""
    resp = client.patch(
        "/api/v1/account/",
        json={"profile_note": "Loves 3D printing"},
        headers=member_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["profile_note"] == "Loves 3D printing"


def test_patch_account_avatar_and_profile_note_together(client, member_headers):
    """PATCH /account/ with both avatar and profile_note updates both fields."""
    resp = client.patch(
        "/api/v1/account/",
        json={"avatar": "AB", "profile_note": "CNC enthusiast"},
        headers=member_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["avatar"] == "AB"
    assert data["profile_note"] == "CNC enthusiast"


def test_patch_account_profile_note_reflected_in_get(client, member_headers):
    """Value updated via PATCH /account/ is reflected in subsequent GET."""
    client.patch(
        "/api/v1/account/",
        json={"profile_note": "Woodworking"},
        headers=member_headers,
    )
    resp = client.get("/api/v1/account/", headers=member_headers)
    assert resp.status_code == 200
    assert resp.get_json()["profile_note"] == "Woodworking"


def test_patch_account_requires_auth(client, seeded_db):
    """PATCH /account/ returns 401 when unauthenticated."""
    resp = client.patch("/api/v1/account/", json={"avatar": "XX"})
    assert resp.status_code == 401


# ── GET /account/invoices ─────────────────────────────────────────────────────


def test_get_invoices_returns_list(client, db, member_headers, seeded_db):
    """GET /account/invoices returns a list (possibly empty)."""
    resp = client.get("/api/v1/account/invoices", headers=member_headers)
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_get_invoices_returns_own_invoices_only(client, db, member_headers, seeded_db):
    """GET /account/invoices returns only the authenticated member's invoices."""
    from hubra.core.models.finance import Invoice
    from hubra.core.models.member import Member

    # Create a second member
    role = seeded_db["role"]
    tier = seeded_db["tier"]
    from hubra.core.models.user import User

    other_user = User(
        email="other@test.ch",
        first_name="Other",
        last_name="User",
    )
    other_user.set_password("password123")
    db.session.add(other_user)
    db.session.flush()

    other = Member(
        user_id=other_user.id,
        status="active",
        tier_id=tier.id,
    )
    other.roles = [role]
    db.session.add(other)
    db.session.flush()

    admin = seeded_db["admin"]
    today = date.today()

    # One invoice for admin, one for other member
    inv_admin = Invoice(
        member_id=admin.id,
        issued=today,
        due=today,
        amount=Decimal("45.00"),
        status="Open",
    )
    inv_other = Invoice(
        member_id=other.id,
        issued=today,
        due=today,
        amount=Decimal("90.00"),
        status="Open",
    )
    db.session.add_all([inv_admin, inv_other])
    db.session.commit()

    resp = client.get("/api/v1/account/invoices", headers=member_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    ids = [inv["id"] for inv in data]
    assert inv_admin.id in ids
    assert inv_other.id not in ids


def test_get_invoices_requires_auth(client, seeded_db):
    """GET /account/invoices returns 401 when unauthenticated."""
    resp = client.get("/api/v1/account/invoices")
    assert resp.status_code == 401


# ── GET /account/groups ───────────────────────────────────────────────────────


def test_get_groups_returns_list(client, db, member_headers, seeded_db):
    """GET /account/groups returns a list (possibly empty) for authenticated member."""
    resp = client.get("/api/v1/account/groups", headers=member_headers)
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_get_groups_returns_member_groups(client, db, member_headers, seeded_db):
    """GET /account/groups returns groups the member belongs to."""
    from hubra.core.models.group import Group

    admin = seeded_db["admin"]
    grp = Group(name="Laser Crew", color="#ff0000")
    db.session.add(grp)
    db.session.flush()
    admin.groups.append(grp)
    db.session.commit()

    resp = client.get("/api/v1/account/groups", headers=member_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    names = [g["name"] for g in data]
    assert "Laser Crew" in names


def test_get_groups_excludes_non_member_groups(client, db, member_headers, seeded_db):
    """GET /account/groups does not return groups the member is not in."""
    from hubra.core.models.group import Group

    other_grp = Group(name="Secret Group", color="#000000")
    db.session.add(other_grp)
    db.session.commit()

    resp = client.get("/api/v1/account/groups", headers=member_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    names = [g["name"] for g in data]
    assert "Secret Group" not in names


def test_get_groups_requires_auth(client, seeded_db):
    """GET /account/groups returns 401 when unauthenticated."""
    resp = client.get("/api/v1/account/groups")
    assert resp.status_code == 401


# ── GET /account/mail-settings ────────────────────────────────────────────────


def test_get_mail_settings(client, member_headers):
    """Primary GET test: returns forwarding_enabled and mailbox_enabled."""
    resp = client.get("/api/v1/account/mail-settings", headers=member_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "forwarding_enabled" in data
    assert "mailbox_enabled" in data


def test_get_mail_settings_returns_defaults(client, member_headers):
    """GET /account/mail-settings returns forwarding_enabled and mailbox_enabled."""
    resp = client.get("/api/v1/account/mail-settings", headers=member_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "forwarding_enabled" in data
    assert "mailbox_enabled" in data
    assert data["forwarding_enabled"] is False
    assert data["mailbox_enabled"] is False


def test_get_mail_settings_requires_auth(client, seeded_db):
    """GET /account/mail-settings returns 401 when unauthenticated."""
    resp = client.get("/api/v1/account/mail-settings")
    assert resp.status_code == 401


def test_get_mail_settings_returns_private_email_verified(
    client, db, member_headers, seeded_db
):
    """GET /account/mail-settings returns private_email_verified in response."""
    admin = seeded_db["admin"]
    # Admin starts with private_email_verified=True from fixture
    resp = client.get("/api/v1/account/mail-settings", headers=member_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "private_email_verified" in data
    assert data["private_email_verified"] is True

    # Toggle to False and verify it's reflected
    admin.user.private_email_verified = False
    db.session.commit()

    resp = client.get("/api/v1/account/mail-settings", headers=member_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "private_email_verified" in data
    assert data["private_email_verified"] is False


# ── PATCH /account/mail-settings ─────────────────────────────────────────────


def test_patch_mail_settings(client, db, seeded_db, member_headers):
    """Primary PATCH test: returns 202 with updated settings and dispatches task."""
    from hubra.core.models.managed_mail import ManagedMailAddress

    admin = seeded_db["admin"]
    admin.user.private_email_verified = True
    db.session.commit()
    addr = ManagedMailAddress(
        address="admin@club.ch",
        address_type="mailbox",
        is_protected=False,
        owner_type="member",
        owner_id=admin.id,
        forwarding_enabled=False,
    )
    db.session.add(addr)
    db.session.commit()

    with patch("hubra.core.tasks.wildduck.provision_member_mail.delay") as mock_task:
        resp = client.patch(
            "/api/v1/account/mail-settings",
            json={"forwarding_enabled": True},
            headers=member_headers,
        )
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["forwarding_enabled"] is True
    assert "mailbox_enabled" in data
    mock_task.assert_called_once()


def test_patch_mail_settings_forwarding(client, db, seeded_db, member_headers):
    """PATCH /account/mail-settings with forwarding_enabled=True returns 202."""
    from hubra.core.models.managed_mail import ManagedMailAddress

    admin = seeded_db["admin"]
    admin.user.private_email_verified = True
    db.session.commit()
    addr = ManagedMailAddress(
        address="admin@club.ch",
        address_type="mailbox",
        is_protected=False,
        owner_type="member",
        owner_id=admin.id,
        forwarding_enabled=False,
    )
    db.session.add(addr)
    db.session.commit()

    with patch("hubra.core.tasks.wildduck.provision_member_mail.delay") as mock_task:
        resp = client.patch(
            "/api/v1/account/mail-settings",
            json={"forwarding_enabled": True},
            headers=member_headers,
        )
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["forwarding_enabled"] is True
    mock_task.assert_called_once()


def test_patch_mail_settings_multiple_fields(client, db, seeded_db, member_headers):
    """PATCH /account/mail-settings accepts forwarding_enabled."""
    from hubra.core.models.managed_mail import ManagedMailAddress

    admin = seeded_db["admin"]
    admin.user.private_email_verified = True
    db.session.commit()
    addr = ManagedMailAddress(
        address="admin@club.ch",
        address_type="mailbox",
        is_protected=False,
        owner_type="member",
        owner_id=admin.id,
        forwarding_enabled=False,
    )
    db.session.add(addr)
    db.session.commit()

    with patch("hubra.core.tasks.wildduck.provision_member_mail.delay"):
        resp = client.patch(
            "/api/v1/account/mail-settings",
            json={"forwarding_enabled": True},
            headers=member_headers,
        )
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["forwarding_enabled"] is True


def test_patch_mail_settings_persists(client, db, seeded_db, member_headers):
    """Values updated via PATCH are reflected in the subsequent GET."""
    from hubra.core.models.managed_mail import ManagedMailAddress

    admin = seeded_db["admin"]
    admin.user.private_email_verified = True
    db.session.commit()
    addr = ManagedMailAddress(
        address="admin@club.ch",
        address_type="mailbox",
        is_protected=False,
        owner_type="member",
        owner_id=admin.id,
        forwarding_enabled=False,
    )
    db.session.add(addr)
    db.session.commit()

    with patch("hubra.core.tasks.wildduck.provision_member_mail.delay"):
        client.patch(
            "/api/v1/account/mail-settings",
            json={"forwarding_enabled": True},
            headers=member_headers,
        )
    resp = client.get("/api/v1/account/mail-settings", headers=member_headers)
    assert resp.status_code == 200
    assert resp.get_json()["forwarding_enabled"] is True


def test_patch_mail_settings_forwarding_unverified_returns_422(
    client, seeded_db, db, member_headers
):
    """PATCH forwarding_enabled=True returns 422 when private_email is not verified."""
    seeded_db["admin"].user.private_email_verified = False
    db.session.commit()

    resp = client.patch(
        "/api/v1/account/mail-settings",
        json={"forwarding_enabled": True},
        headers=member_headers,
    )
    assert resp.status_code == 422
    data = resp.get_json()
    assert data["error"] == "VERIFICATION_REQUIRED"


# ── Negative tests ────────────────────────────────────────────────────────────


def test_patch_mail_settings_requires_auth(client, seeded_db):
    """PATCH /account/mail-settings returns 401 when unauthenticated."""
    resp = client.patch(
        "/api/v1/account/mail-settings",
        json={"forwarding_enabled": True},
    )
    assert resp.status_code == 401


def test_patch_mail_settings_empty_body(client, member_headers):
    """PATCH /account/mail-settings with empty body returns 400."""
    resp = client.patch(
        "/api/v1/account/mail-settings",
        json={},
        headers=member_headers,
    )
    assert resp.status_code == 400


def test_patch_mail_settings_no_valid_fields(client, member_headers):
    """PATCH /account/mail-settings with unrecognised keys returns 400."""
    resp = client.patch(
        "/api/v1/account/mail-settings",
        json={"unknown_field": True},
        headers=member_headers,
    )
    assert resp.status_code == 400


def test_patch_mail_settings_non_bool_value(client, member_headers):
    """PATCH /account/mail-settings with non-boolean value returns 400."""
    resp = client.patch(
        "/api/v1/account/mail-settings",
        json={"forwarding_enabled": "yes"},
        headers=member_headers,
    )
    assert resp.status_code == 400


def test_patch_mail_settings_dispatches_celery_task(
    client, db, seeded_db, member_headers
):
    """provision_member_mail.delay is called with the correct member_id."""
    from hubra.core.models.managed_mail import ManagedMailAddress

    admin = seeded_db["admin"]
    addr = ManagedMailAddress(
        address="admin@club.ch",
        address_type="mailbox",
        is_protected=False,
        owner_type="member",
        owner_id=admin.id,
        forwarding_enabled=True,
    )
    db.session.add(addr)
    db.session.commit()
    with patch("hubra.core.tasks.wildduck.provision_member_mail.delay") as mock_task:
        resp = client.patch(
            "/api/v1/account/mail-settings",
            json={"forwarding_enabled": False},
            headers=member_headers,
        )
    assert resp.status_code == 202
    mock_task.assert_called_once()
    call_args = mock_task.call_args[0]
    assert isinstance(call_args[0], int)  # member_id is an int


# ── POST /account/request-email-verification ──────────────────────────────────


def test_request_email_verification_returns_202(client, db, seeded_db, member_headers):
    """POST /account/request-email-verification returns 202 and sends email."""
    with patch("hubra.api.auth.routes.email_svc.send_email_verification") as mock_send:
        resp = client.post(
            "/api/v1/account/request-email-verification",
            headers=member_headers,
        )
    assert resp.status_code == 202
    assert resp.get_json()["ok"] is True
    mock_send.assert_called_once()


def test_request_email_verification_requires_auth(client, seeded_db):
    """POST /account/request-email-verification returns 401 when unauthenticated."""
    resp = client.post("/api/v1/account/request-email-verification")
    assert resp.status_code == 401


def test_request_email_verification_invalidates_prior_tokens(
    client, db, seeded_db, member_headers
):
    """A second verification request invalidates the first token."""
    from hubra.core.models.email_verification import EmailVerificationToken
    import hashlib
    import secrets
    from datetime import timedelta

    admin = seeded_db["admin"]
    # Insert a prior unused token
    raw = secrets.token_urlsafe(32)
    prior = EmailVerificationToken(
        user_id=admin.user_id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.session.add(prior)
    db.session.commit()

    with patch("hubra.api.auth.routes.email_svc.send_email_verification"):
        client.post(
            "/api/v1/account/request-email-verification", headers=member_headers
        )

    db.session.refresh(prior)
    assert prior.used is True


# ── POST /account/verify-email ───────────────────────────────────────────────────


def test_verify_email_valid_token(client, db, seeded_db, member_headers):
    """POST /account/verify-email sets private_email_verified=True and returns 200."""
    from hubra.core.models.email_verification import EmailVerificationToken
    import hashlib
    import secrets
    from datetime import timedelta

    admin = seeded_db["admin"]
    raw = secrets.token_urlsafe(32)
    evt = EmailVerificationToken(
        user_id=admin.user_id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.session.add(evt)
    db.session.commit()

    resp = client.post(
        "/api/v1/account/verify-email",
        json={"token": raw},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["verified"] is True

    db.session.refresh(admin)
    assert admin.private_email_verified is True
    db.session.refresh(evt)
    assert evt.used is True


def test_verify_email_invalid_token_returns_400(client, seeded_db):
    """POST /account/verify-email with bad token returns 400 with INVALID_TOKEN."""
    resp = client.post(
        "/api/v1/account/verify-email",
        json={"token": "notarealtoken"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "INVALID_TOKEN"


def test_verify_email_used_token_returns_400(client, db, seeded_db):
    """POST /account/verify-email with used token returns 400 with INVALID_TOKEN."""
    from hubra.core.models.email_verification import EmailVerificationToken
    import hashlib
    import secrets
    from datetime import timedelta

    admin = seeded_db["admin"]
    raw = secrets.token_urlsafe(32)
    evt = EmailVerificationToken(
        user_id=admin.user_id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        used=True,
    )
    db.session.add(evt)
    db.session.commit()

    resp = client.post(
        "/api/v1/account/verify-email",
        json={"token": raw},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "INVALID_TOKEN"


def test_verify_email_expired_token_returns_400(client, db, seeded_db):
    """POST /account/verify-email with expired token returns 400 with INVALID_TOKEN."""
    from hubra.core.models.email_verification import EmailVerificationToken
    import hashlib
    import secrets
    from datetime import timedelta

    admin = seeded_db["admin"]
    raw = secrets.token_urlsafe(32)
    evt = EmailVerificationToken(
        user_id=admin.user_id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # already expired
    )
    db.session.add(evt)
    db.session.commit()

    resp = client.post(
        "/api/v1/account/verify-email",
        json={"token": raw},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "INVALID_TOKEN"
