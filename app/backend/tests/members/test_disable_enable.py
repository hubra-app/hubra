"""Tests for member disable/enable lifecycle and self-delete prevention."""


# ── Self-delete returns 403 ────────────────────────────────────────────────────


def test_self_delete_returns_403(client, seeded_db, auth_headers):
    """Admin attempting to DELETE their own account must get 403 SELF_DELETE."""
    admin_id = seeded_db["admin"].id
    resp = client.delete(f"/api/v1/members/{admin_id}", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.get_json().get("error") == "SELF_DELETE"


# ── Disable/Enable Member ─────────────────────────────────────────────────────


def test_disabled_member_login_blocked(client, seeded_db, auth_headers):
    """Disable member then login returns 403 account_disabled."""
    # Create a regular member (no role)
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User
    from vollbuild.extensions import db

    regular_user = User(
        email="regular@test.ch",
        first_name="Regular",
        last_name="User",
    )
    regular_user.set_password("password123")
    db.session.add(regular_user)
    db.session.flush()

    regular = Member(
        user_id=regular_user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
    )
    db.session.add(regular)
    db.session.commit()

    # Disable the member
    resp = client.post(
        f"/api/v1/members/{regular.id}/disable",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["is_disabled"] is True

    # Try to login with disabled account
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "regular@test.ch",
            "password": "password123",
        },
    )
    assert resp.status_code == 403
    body = resp.get_json()
    assert body["error"] == "ACCOUNT_DISABLED"


def test_enable_restores_login(client, seeded_db, auth_headers):
    """Disable then enable then login succeeds."""
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User
    from vollbuild.extensions import db

    regular_user = User(
        email="regular@test.ch",
        first_name="Regular",
        last_name="User",
    )
    regular_user.set_password("password123")
    db.session.add(regular_user)
    db.session.flush()

    regular = Member(
        user_id=regular_user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
    )
    db.session.add(regular)
    db.session.commit()

    # Disable the member
    resp = client.post(
        f"/api/v1/members/{regular.id}/disable",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Try to login — should fail
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "regular@test.ch",
            "password": "password123",
        },
    )
    assert resp.status_code == 403

    # Enable the member
    resp = client.post(
        f"/api/v1/members/{regular.id}/enable",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["is_disabled"] is False

    # Try to login again — should succeed
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "regular@test.ch",
            "password": "password123",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "member" in body
    assert body["member"]["email"] == "regular@test.ch"


def test_disable_requires_permission(client, seeded_db):
    """Non-admin cannot disable returns 403."""
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User
    from vollbuild.extensions import db

    # Create a non-admin member (no role)
    regular_user = User(
        email="regular@test.ch",
        first_name="Regular",
        last_name="User",
    )
    regular_user.set_password("password123")
    db.session.add(regular_user)
    db.session.flush()

    regular = Member(
        user_id=regular_user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
    )
    db.session.add(regular)
    db.session.commit()

    # Login as regular member
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "regular@test.ch",
            "password": "password123",
        },
    )
    assert login_resp.status_code == 200

    # Try to disable another member — should fail with 403
    resp = client.post(
        f"/api/v1/members/{seeded_db['admin'].id}/disable",
    )
    assert resp.status_code == 403


def test_cannot_disable_self(client, seeded_db, auth_headers):
    """Admin cannot disable own account returns 409."""
    # Try to disable self
    resp = client.post(
        f"/api/v1/members/{seeded_db['admin'].id}/disable",
        headers=auth_headers,
    )
    assert resp.status_code == 409
    body = resp.get_json()
    assert body["error"] == "CONFLICT"


def test_cannot_disable_admin_role(client, seeded_db, auth_headers):
    """Cannot disable an Admin role member returns 409."""
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User
    from vollbuild.extensions import db

    # Create another admin member
    admin2_user = User(
        email="admin2@test.ch",
        first_name="Admin",
        last_name="Two",
    )
    admin2_user.set_password("password123")
    db.session.add(admin2_user)
    db.session.flush()

    admin2 = Member(
        user_id=admin2_user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
    )
    admin2.roles = [seeded_db["role"]]
    db.session.add(admin2)
    db.session.commit()

    # Try to disable admin2 — should fail with 409
    resp = client.post(
        f"/api/v1/members/{admin2.id}/disable",
        headers=auth_headers,
    )
    assert resp.status_code == 409
    body = resp.get_json()
    assert body["error"] == "CONFLICT"


def test_disable_member_returns_json(client, seeded_db, auth_headers):
    """POST /members/<id>/disable returns member JSON with is_disabled=true."""
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User
    from vollbuild.extensions import db

    regular_user = User(
        email="regular@test.ch",
        first_name="Regular",
        last_name="User",
    )
    regular_user.set_password("password123")
    db.session.add(regular_user)
    db.session.flush()

    regular = Member(
        user_id=regular_user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
    )
    db.session.add(regular)
    db.session.commit()

    resp = client.post(
        f"/api/v1/members/{regular.id}/disable",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == regular.id
    assert body["email"] == "regular@test.ch"
    assert body["is_disabled"] is True
    assert "password_hash" not in body  # Should not expose password hash


def test_enable_member_returns_json(client, seeded_db, auth_headers):
    """POST /members/<id>/enable returns member JSON with is_disabled=false."""
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User
    from vollbuild.extensions import db

    regular_user = User(
        email="regular@test.ch",
        first_name="Regular",
        last_name="User",
        is_disabled=True,
    )
    regular_user.set_password("password123")
    db.session.add(regular_user)
    db.session.flush()

    regular = Member(
        user_id=regular_user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
    )
    db.session.add(regular)
    db.session.commit()

    resp = client.post(
        f"/api/v1/members/{regular.id}/enable",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == regular.id
    assert body["email"] == "regular@test.ch"
    assert body["is_disabled"] is False
    assert "password_hash" not in body


# ── Mail lifecycle hooks ─────────────────────────────────────────────────────


def test_disable_calls_disable_member_mail(client, seeded_db, auth_headers):
    """POST /members/<id>/disable calls disable_member_mail."""
    from unittest.mock import patch

    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User
    from vollbuild.extensions import db

    regular_user = User(
        email="mailhook@test.ch",
        first_name="Regular",
        last_name="User",
    )
    regular_user.set_password("password123")
    db.session.add(regular_user)
    db.session.flush()

    regular = Member(
        user_id=regular_user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
    )
    db.session.add(regular)
    db.session.commit()

    with patch(
        "vollbuild.core.services.managed_mail.disable_member_mail"
    ) as mock_disable:
        resp = client.post(
            f"/api/v1/members/{regular.id}/disable",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    mock_disable.assert_called_once_with(regular.id)


def test_enable_calls_enable_member_mail(client, seeded_db, auth_headers):
    """POST /members/<id>/enable calls enable_member_mail."""
    from unittest.mock import patch

    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User
    from vollbuild.extensions import db

    regular_user = User(
        email="mailhook2@test.ch",
        first_name="Regular",
        last_name="User",
        is_disabled=True,
    )
    regular_user.set_password("password123")
    db.session.add(regular_user)
    db.session.flush()

    regular = Member(
        user_id=regular_user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
    )
    db.session.add(regular)
    db.session.commit()

    with patch(
        "vollbuild.core.services.managed_mail.enable_member_mail"
    ) as mock_enable:
        resp = client.post(
            f"/api/v1/members/{regular.id}/enable",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    mock_enable.assert_called_once_with(regular.id, regular.password_hash)
