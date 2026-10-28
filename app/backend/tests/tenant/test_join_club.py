"""Finding a club and asking to join it (/system/clubs), and what approval does.

SQLite has no schemas, so every "club" here shares one members table; each
test uses its own users and club slugs.
"""

from unittest.mock import patch

from flask import g
from sqlalchemy import select

from hubra.core.models.application import Application
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant

PASSWORD = "VeryStrongPass123!"


def _signup(client, email: str, name: str = "Jo Joiner") -> None:
    resp = client.post(
        "/api/v1/auth/signup",
        json={"name": name, "email": email, "password": PASSWORD},
    )
    assert resp.status_code == 201


def _club(db, slug: str, name: str, status: str = "active") -> Tenant:
    tenant = Tenant(name=name, slug=slug, plan="starter", status=status)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def _user(db, email: str) -> User:
    return db.session.scalar(select(User).where(User.email == email))


def test_directory_needs_a_search_for_ordinary_users(client, db):
    _club(db, "rowing-zug", "Rowing Zug")
    _club(db, "rowing-old", "Rowing Old", status="suspended")
    _signup(client, "dir@test.ch")

    assert client.get("/api/v1/system/clubs").get_json() == {
        "clubs": [],
        "canJoinDirectly": False,
    }

    body = client.get("/api/v1/system/clubs?search=rowing").get_json()
    assert [c["slug"] for c in body["clubs"]] == ["rowing-zug"]
    assert body["clubs"][0]["membership"] is None


def test_directory_requires_sign_in(client, db):
    assert client.get("/api/v1/system/clubs?search=rowing").status_code == 401
    assert client.post("/api/v1/system/clubs/rowing-zug/join").status_code == 401


def test_join_request_files_an_application(client, db):
    _club(db, "chess-luzern", "Chess Luzern")
    _signup(client, "asker@test.ch", name="Ada Asker")

    resp = client.post("/api/v1/system/clubs/chess-luzern/join")
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "requested"

    application = db.session.scalar(
        select(Application).where(Application.email == "asker@test.ch")
    )
    assert application is not None
    assert application.name == "Ada Asker"

    # No membership yet, and a second request is refused.
    assert db.session.scalar(
        select(UserTenant).where(UserTenant.user_id == _user(db, "asker@test.ch").id)
    ) is None
    again = client.post("/api/v1/system/clubs/chess-luzern/join")
    assert again.status_code == 409
    assert again.get_json()["error"] == "REQUEST_PENDING"

    body = client.get("/api/v1/system/clubs?search=chess").get_json()
    assert body["clubs"][0]["membership"] == "pending"


def test_join_unknown_or_inactive_club_is_404(client, db):
    _club(db, "gone-club", "Gone Club", status="archived")
    _signup(client, "lost@test.ch")

    assert client.post("/api/v1/system/clubs/no-such-club/join").status_code == 404
    assert client.post("/api/v1/system/clubs/gone-club/join").status_code == 404


def test_superadmin_joins_directly(client, db):
    tenant = _club(db, "sailing-thun", "Sailing Thun")
    _signup(client, "boss@test.ch")
    boss = _user(db, "boss@test.ch")
    boss.is_superadmin = True
    db.session.commit()

    # Managers see every club without searching.
    body = client.get("/api/v1/system/clubs").get_json()
    assert body["canJoinDirectly"] is True
    assert "sailing-thun" in [c["slug"] for c in body["clubs"]]

    resp = client.post("/api/v1/system/clubs/sailing-thun/join")
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "joined"
    assert db.session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == boss.id, UserTenant.tenant_id == tenant.id
        )
    ) is not None

    again = client.post("/api/v1/system/clubs/sailing-thun/join")
    assert again.status_code == 409
    assert again.get_json()["error"] == "ALREADY_MEMBER"

    tenants = client.get("/api/v1/account/my-tenants").get_json()["tenants"]
    assert "sailing-thun" in [t["tenant_slug"] for t in tenants]


def test_approving_links_the_existing_account(app, db):
    """Approval must add user_tenants, or sign-in and switch-tenant refuse the club."""
    from hubra.api.members.services import MembersService

    tenant = _club(db, "hiking-bern", "Hiking Bern")
    user = User(email="hiker@test.ch", first_name="Hanna", last_name="Hiker")
    user.set_password(PASSWORD)
    db.session.add(user)
    application = Application(name="Hanna Hiker", email="hiker@test.ch")
    db.session.add(application)
    db.session.commit()

    with app.test_request_context():
        g.tenant = tenant
        member = MembersService.create_from_application(application)
        db.session.commit()

    assert member.user_id == user.id
    # The account keeps its own password.
    assert user.check_password(PASSWORD)
    assert db.session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == user.id, UserTenant.tenant_id == tenant.id
        )
    ) is not None


def test_approve_skips_the_temp_password_mail_for_existing_accounts(
    client, db, seeded_db
):
    """The welcome mail carries a temporary password that a join request doesn't have."""
    user = User(email="known@test.ch", first_name="Kim", last_name="Known")
    user.set_password(PASSWORD)
    db.session.add(user)
    application = Application(name="Kim Known", email="known@test.ch")
    db.session.add(application)
    db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    with patch("hubra.core.services.email.send_welcome") as send_welcome:
        resp = client.post(f"/api/v1/applications/{application.id}/approve")
    assert resp.status_code == 201, resp.get_json()
    send_welcome.assert_not_called()


# ── The club's join page on SSO (replaces the club app's /apply form) ─────────


def _tier(db, name: str):
    from hubra.core.models.member import MembershipTier

    tier = MembershipTier(name=name)
    db.session.add(tier)
    db.session.commit()
    return tier


def test_club_page_shows_name_status_and_tiers(client, db):
    _club(db, "tennis-chur", "Tennis Chur")
    tier = _tier(db, "Aktiv Chur")
    _signup(client, "page@test.ch")

    body = client.get("/api/v1/system/clubs/tennis-chur").get_json()
    assert body["name"] == "Tennis Chur"
    assert body["membership"] is None
    assert body["canJoinDirectly"] is False
    assert {"id": tier.id, "name": "Aktiv Chur"} in body["tiers"]


def test_club_page_needs_sign_in_and_an_active_club(client, db):
    _club(db, "tennis-old", "Tennis Old", status="archived")
    assert client.get("/api/v1/system/clubs/tennis-old").status_code == 401
    _signup(client, "page2@test.ch")
    assert client.get("/api/v1/system/clubs/tennis-old").status_code == 404


def test_join_request_with_a_tier(client, db):
    _club(db, "golf-sion", "Golf Sion")
    tier = _tier(db, "Junior Sion")
    _signup(client, "tier@test.ch")

    resp = client.post(
        "/api/v1/system/clubs/golf-sion/join", json={"wantsTierId": tier.id}
    )
    assert resp.status_code == 201
    application = db.session.scalar(
        select(Application).where(Application.email == "tier@test.ch")
    )
    assert application.wants_tier_id == tier.id


def test_join_request_with_an_unknown_tier(client, db):
    _club(db, "golf-brig", "Golf Brig")
    _signup(client, "tier2@test.ch")
    resp = client.post("/api/v1/system/clubs/golf-brig/join", json={"wantsTierId": 99999})
    assert resp.status_code == 400


def test_the_anonymous_application_form_is_gone(client, db):
    resp = client.post(
        "/api/v1/applications/",
        json={"first_name": "A", "last_name": "B", "email": "anon@test.ch"},
    )
    assert resp.status_code in (401, 403, 404, 405)
