"""Tests for S02: club_username uniqueness guard and admin set-password endpoint."""

from hubra.core.models.member import Member
from hubra.core.models.user import User


def _make_member(
    db_session, seeded_db, first="Jane", last="Doe", email="jane@test.ch", username=None
):
    """Helper: create a regular member directly in DB."""
    user = User(email=email, first_name=first, last_name=last)
    user.set_password("password123")
    db_session.session.add(user)
    db_session.session.flush()

    m = Member(
        user_id=user.id,
        status="active",
        tier_id=seeded_db["tier"].id,
        club_username=username,
    )
    db_session.session.add(m)
    db_session.session.commit()
    return m


# ── set-password endpoint ─────────────────────────────────────────────────────


def test_set_password_success(client, seeded_db, auth_headers, db):
    """POST /members/{id}/set-password with password sets it and returns 200 success."""
    member = _make_member(db, seeded_db, email="setpw@test.ch")

    resp = client.post(
        f"/api/v1/members/{member.id}/set-password",
        json={"password": "Tr0ub4dor&3-correct-horse"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "generated_password" not in body

    # Verify new password works
    resp2 = client.post(
        "/api/v1/auth/login",
        json={
            "email": "setpw@test.ch",
            "password": "Tr0ub4dor&3-correct-horse",
        },
    )
    assert resp2.status_code == 200


def test_set_password_generate(client, seeded_db, auth_headers, db):
    """POST /members/{id}/set-password with generate=true returns generated_password."""
    member = _make_member(db, seeded_db, email="genpw@test.ch")

    resp = client.post(
        f"/api/v1/members/{member.id}/set-password",
        json={"generate": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    # Password is emailed, not returned in the response body
    assert "generated_password" not in body


def test_set_password_not_found(client, seeded_db, auth_headers):
    """POST /members/99999/set-password returns 404."""
    resp = client.post(
        "/api/v1/members/99999/set-password",
        json={"password": "abc123"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_set_password_missing_password(client, seeded_db, auth_headers, db):
    """POST /members/{id}/set-password without password or generate returns 400."""
    member = _make_member(db, seeded_db, email="nopw@test.ch")

    resp = client.post(
        f"/api/v1/members/{member.id}/set-password",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_set_password_sets_must_change_flag(client, seeded_db, auth_headers, db):
    """POST /members/{id}/set-password with must_change_password=true sets the flag."""
    member = _make_member(db, seeded_db, email="mustchange@test.ch")

    resp = client.post(
        f"/api/v1/members/{member.id}/set-password",
        json={"password": "Tr0ub4dor&3-correct-horse", "must_change_password": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    db.session.refresh(member)
    assert member.must_change_password is True


# ── club_username PATCH ───────────────────────────────────────────────────────


def test_patch_club_username_conflict(client, seeded_db, auth_headers, db):
    """PATCH /members/{id} with a taken club_username returns 409 CONFLICT."""
    _make_member(db, seeded_db, email="user1@test.ch", username="taken.name")
    m2 = _make_member(db, seeded_db, first="Bob", last="Smith", email="user2@test.ch")

    resp = client.patch(
        f"/api/v1/members/{m2.id}",
        json={"club_username": "taken.name"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "CONFLICT"


def test_patch_club_username_unique_succeeds(client, seeded_db, auth_headers, db):
    """PATCH /members/{id} with a unique club_username updates it."""
    member = _make_member(db, seeded_db, email="uname@test.ch")

    resp = client.patch(
        f"/api/v1/members/{member.id}",
        json={"club_username": "new.username"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["club_username"] == "new.username"


def test_patch_must_change_password(client, seeded_db, auth_headers, db):
    """PATCH /members/{id} with must_change_password=True sets the flag."""
    member = _make_member(db, seeded_db, email="flagme@test.ch")

    resp = client.patch(
        f"/api/v1/members/{member.id}",
        json={"must_change_password": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    db.session.refresh(member)
    assert member.must_change_password is True
