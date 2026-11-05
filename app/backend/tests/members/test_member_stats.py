"""Member statistics for the board: members on a day, ages, joins and
leaves per month, open fees."""

from datetime import date, datetime, timedelta, timezone

import pytest

from hubra.core.models.finance import Invoice
from hubra.core.models.member import Member
from hubra.core.models.user import User


def _member(db, tier, email, *, born=None, joined=None, left=None, status="active"):
    user = User(email=email, first_name=email.split("@")[0], last_name="Test")
    user.set_password("password123")
    user.birthday = born
    db.session.add(user)
    db.session.flush()
    m = Member(user_id=user.id, status=status, tier_id=tier.id, joined=joined)
    m.archived_at = left
    db.session.add(m)
    db.session.flush()
    return m


@pytest.fixture
def club(db, seeded_db):
    tier = seeded_db["tier"]
    on = date(2026, 1, 1)
    _member(db, tier, "kid@test.ch", born=date(2018, 5, 1), joined=date(2024, 3, 1))
    _member(db, tier, "teen@test.ch", born=date(2010, 1, 1), joined=date(2025, 2, 10))
    _member(db, tier, "old@test.ch", born=date(1950, 1, 2), joined=date(2001, 1, 1))
    # Joined after the reference day: not counted on it, but a join in 2026.
    _member(db, tier, "new@test.ch", joined=date(2026, 3, 15))
    # Left during 2025: not counted, a leave in March 2025.
    _member(
        db,
        tier,
        "gone@test.ch",
        joined=date(2020, 1, 1),
        left=datetime(2025, 3, 5, 10, tzinfo=timezone.utc),
    )
    db.session.commit()
    return on


def test_members_on_a_day_by_age(client, auth_headers, club):
    resp = client.get(
        "/api/v1/members/stats?on=2026-01-01&year=2025", headers=auth_headers
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    data["ages"] = {a["bracket"]: a["count"] for a in data["ages"]}
    assert list(data["ages"])[:3] == ["0-4", "5-9", "10-14"]
    # Kid, teen and old; the seeded admin joined today, "new" in March.
    assert data["total"] == 3
    assert data["ages"]["5-9"] == 1  # 7 on 1 Jan 2026
    assert data["ages"]["15-19"] == 1  # 16 on 1 Jan 2026
    assert data["ages"]["65+"] == 1  # 75, birthday on 2 Jan not yet
    assert data["ageUnknown"] == 0
    months = {m["month"]: m for m in data["months"]}
    assert months["2025-02"]["joins"] == 1
    assert months["2025-03"]["leaves"] == 1
    assert sum(m["joins"] for m in data["months"]) == 1


def test_birthday_on_the_day_counts(client, auth_headers, club):
    data = client.get(
        "/api/v1/members/stats?on=2026-01-02", headers=auth_headers
    ).get_json()
    ages = {a["bracket"]: a["count"] for a in data["ages"]}
    assert ages["65+"] == 1
    assert data["total"] == 3


def test_fees_for_those_who_read_invoices(client, auth_headers, db, club, seeded_db):
    admin = seeded_db["admin"]
    today = date.today()
    db.session.add(
        Invoice(
            member_id=admin.id,
            issued=today - timedelta(days=35),
            due=today - timedelta(days=5),
            amount=50,
            status="Open",
        )
    )
    db.session.commit()
    fees = client.get("/api/v1/members/stats", headers=auth_headers).get_json()["fees"]
    assert fees["open"] == 1 and fees["overdue"] == 1 and fees["openAmount"] == "50.00"


def test_csv_and_validation(client, auth_headers, club):
    resp = client.get("/api/v1/members/stats.csv?on=2026-01-01", headers=auth_headers)
    assert resp.status_code == 200
    text = resp.data.decode("utf-8-sig")
    assert text.startswith("Stichtag;2026-01-01")
    assert "65+;1" in text
    assert (
        client.get("/api/v1/members/stats?on=gestern", headers=auth_headers).status_code
        == 400
    )
    assert (
        client.get("/api/v1/members/stats?year=1066", headers=auth_headers).status_code
        == 400
    )


def test_stats_need_members_read(client, db, seeded_db):
    from tests.settings.test_settings_kv import _login, _make_role_and_member

    _make_role_and_member(db, seeded_db["tier"], name="Ola")
    _login(client, "ola@test.ch")
    assert client.get("/api/v1/members/stats").status_code == 403
