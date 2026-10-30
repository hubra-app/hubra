"""Every member has a join date, so "Member since" is never empty."""

from datetime import date

from sqlalchemy import select

from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User

PASSWORD = "VeryStrongPass123!"


def test_a_new_member_joined_today(db):
    """Club owners are made without a date; the model fills it in."""
    user = User(email="owner-joined@test.ch", name="Olga Owner", password_hash="x")
    db.session.add(user)
    db.session.flush()
    member = Member(user_id=user.id, status="active")
    db.session.add(member)
    db.session.flush()
    assert member.joined == date.today()


def test_joining_directly_sets_the_join_date(client, db):
    db.session.add(Tenant(name="Curling Bern", slug="curling-bern", plan="starter"))
    resp = client.post(
        "/api/v1/auth/signup",
        json={"name": "Max Manager", "email": "max-joined@test.ch", "password": PASSWORD},
    )
    assert resp.status_code == 201
    user = db.session.scalar(select(User).where(User.email == "max-joined@test.ch"))
    user.is_superadmin = True
    db.session.commit()

    assert client.post("/api/v1/system/clubs/curling-bern/join").status_code == 201

    member = db.session.scalar(select(Member).where(Member.user_id == user.id))
    assert member.joined == date.today()
