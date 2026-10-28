"""A club's admins manage who else administers it (/system/tenants/<id>/admins).

SQLite has no schemas, so the "club" here shares the members table of the
seeded test club: admin@test.ch is its owner.
"""

from sqlalchemy import select

from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant

PASSWORD = "VeryStrongPass123!"


def _club(db, slug: str = "rowers") -> Tenant:
    tenant = Tenant(name="Rowers", slug=slug, plan="starter", status="active")
    db.session.add(tenant)
    db.session.commit()
    return tenant


def _login(client, email: str, password: str = PASSWORD) -> None:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.get_json()


def _account(client, db, email: str) -> User:
    client.post(
        "/api/v1/auth/signup",
        json={"name": "Some One", "email": email, "password": PASSWORD},
    )
    return db.session.scalar(select(User).where(User.email == email))


def _owner(client) -> None:
    _login(client, "admin@test.ch", "password123")


def _url(tenant: Tenant, suffix: str = "") -> str:
    return f"/api/v1/system/tenants/{tenant.id}/admins{suffix}"


def test_owner_sees_the_admins(client, seeded_db, db):
    club = _club(db, "rowers-list")
    _owner(client)

    body = client.get(_url(club)).get_json()
    assert body["access"] == "owner"
    assert body["canManageOwners"] is True
    assert [(a["email"], a["level"]) for a in body["admins"]] == [
        ("admin@test.ch", "owner")
    ]


def test_people_who_are_not_admins_are_refused(client, seeded_db, db):
    club = _club(db, "rowers-refused")
    _account(client, db, "plain@test.ch")
    _login(client, "plain@test.ch")

    assert client.get(_url(club)).status_code == 403
    assert client.post(_url(club), json={"email": "plain@test.ch"}).status_code == 403


def test_owner_makes_an_account_an_admin(client, seeded_db, db):
    club = _club(db, "rowers-add")
    user = _account(client, db, "helper@test.ch")
    _owner(client)

    resp = client.post(_url(club), json={"email": "Helper@test.ch"})
    assert resp.status_code == 201
    assert resp.get_json()["admin"]["level"] == "admin"

    member = db.session.scalar(select(Member).where(Member.user_id == user.id))
    assert any(r.is_admin and not r.is_owner for r in member.roles)
    assert db.session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == user.id, UserTenant.tenant_id == club.id
        )
    )

    emails = {a["email"] for a in client.get(_url(club)).get_json()["admins"]}
    assert emails == {"admin@test.ch", "helper@test.ch"}


def test_unknown_email_is_404(client, seeded_db, db):
    club = _club(db, "rowers-unknown")
    _owner(client)
    resp = client.post(_url(club), json={"email": "nobody@test.ch"})
    assert resp.status_code == 404


def test_an_admin_cannot_name_or_remove_owners(client, seeded_db, db):
    club = _club(db, "rowers-levels")
    _account(client, db, "second@test.ch")
    _account(client, db, "third@test.ch")
    _owner(client)
    assert client.post(_url(club), json={"email": "second@test.ch"}).status_code == 201

    _login(client, "second@test.ch")
    body = client.get(_url(club)).get_json()
    assert body["access"] == "admin" and body["canManageOwners"] is False

    resp = client.post(_url(club), json={"email": "third@test.ch", "level": "owner"})
    assert resp.status_code == 403
    assert client.post(_url(club), json={"email": "third@test.ch"}).status_code == 201

    owner_id = seeded_db["user"].id
    assert client.delete(_url(club, f"/{owner_id}")).status_code == 403


def test_removing_keeps_the_member_and_the_last_owner(client, seeded_db, db):
    club = _club(db, "rowers-remove")
    user = _account(client, db, "temp@test.ch")
    _owner(client)
    client.post(_url(club), json={"email": "temp@test.ch"})

    assert client.delete(_url(club, f"/{user.id}")).status_code == 204
    member = db.session.scalar(select(Member).where(Member.user_id == user.id))
    assert member is not None
    assert not any(r.is_admin or r.is_owner for r in member.roles)
    assert client.delete(_url(club, f"/{user.id}")).status_code == 404

    resp = client.delete(_url(club, f"/{seeded_db['user'].id}"))
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "LAST_OWNER"


def test_platform_managers_manage_any_club(client, seeded_db, db):
    club = _club(db, "rowers-platform")
    boss = _account(client, db, "boss@test.ch")
    boss.is_superadmin = True
    db.session.commit()
    _account(client, db, "newowner@test.ch")

    _login(client, "boss@test.ch")
    assert client.get(_url(club)).get_json()["access"] == "platform"
    resp = client.post(_url(club), json={"email": "newowner@test.ch", "level": "owner"})
    assert resp.status_code == 201
    assert resp.get_json()["admin"]["level"] == "owner"


def test_my_clubs_say_where_i_am_admin(client, seeded_db, db):
    club = _club(db, "rowers-mine")
    _account(client, db, "mine@test.ch")
    _owner(client)
    client.post(_url(club), json={"email": "mine@test.ch"})

    _login(client, "mine@test.ch")
    clubs = client.get("/api/v1/account/my-tenants").get_json()["tenants"]
    mine = next(c for c in clubs if c["tenant_slug"] == "rowers-mine")
    assert mine["admin_level"] == "admin"
