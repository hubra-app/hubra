"""A platform manager who left a club can join it again."""

from sqlalchemy import select

from hubra.core.models.user_tenant import UserTenant
from tests.tenant.test_join_club import _club, _signup, _user


def test_a_manager_who_left_can_join_again(client, db):
    """A platform manager who had left a club got "already a member" and a
    link to a club they could not enter, since their archived member row
    was taken for a current one."""
    from datetime import datetime, timezone

    from hubra.core.models.member import Member

    tenant = _club(db, "rowing-biel", "Rowing Biel")
    _signup(client, "returner@test.ch")
    boss = _user(db, "returner@test.ch")
    boss.is_superadmin = True
    db.session.commit()
    assert client.post("/api/v1/system/clubs/rowing-biel/join").status_code == 201

    member = db.session.scalar(select(Member).where(Member.user_id == boss.id))
    member.archived_at = datetime.now(timezone.utc)
    db.session.query(UserTenant).filter_by(user_id=boss.id, tenant_id=tenant.id).delete()
    db.session.commit()

    resp = client.post("/api/v1/system/clubs/rowing-biel/join")
    assert resp.status_code == 201, resp.get_json()
    db.session.refresh(member)
    assert member.archived_at is None
    assert db.session.scalars(select(Member.id).where(Member.user_id == boss.id)).all() == [
        member.id
    ]
    tenants = client.get("/api/v1/account/my-tenants").get_json()["tenants"]
    assert "rowing-biel" in [t["tenant_slug"] for t in tenants]
