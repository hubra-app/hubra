"""A member who left still counts in the months they were a member."""

from datetime import date, datetime, timedelta, timezone

from hubra.core.models.member import Member


def test_growth_keeps_members_who_left_later(client, auth_headers, db, seeded_db):
    long_ago = date.today() - timedelta(days=400)
    admin = db.session.get(Member, seeded_db["admin"].id)
    admin.joined = long_ago
    gone = Member(status="active", joined=long_ago)
    gone.archived_at = datetime.now(timezone.utc)
    db.session.add(gone)
    db.session.commit()

    growth = client.get("/api/v1/dashboard/summary", headers=auth_headers).get_json()[
        "growth"
    ]
    assert growth[0] == 2  # eleven months ago both were in
    assert growth[-1] == 1  # the one who left this month is gone at its end
