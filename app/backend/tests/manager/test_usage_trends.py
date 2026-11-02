"""Usage per club over time: GET /api/v1/system/tenants/<id>/trends."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from hubra.core.models.audit import AuditEntry
from hubra.core.models.event import ClubEvent
from hubra.core.models.finance import Invoice
from hubra.core.models.member import Member
from hubra.core.models.platform_event import PlatformEvent
from hubra.core.models.tenant import Tenant
from hubra.core.services import usage_trends

TODAY = date(2026, 11, 4)  # a Wednesday


def _at(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)


def test_buckets():
    assert usage_trends.buckets("week", 3, TODAY) == [
        date(2026, 10, 19),
        date(2026, 10, 26),
        date(2026, 11, 2),
    ]
    assert usage_trends.buckets("month", 3, date(2026, 1, 15)) == [
        date(2025, 11, 1),
        date(2025, 12, 1),
        date(2026, 1, 1),
    ]


@pytest.fixture
def club(db, seeded_db):
    tenant = Tenant(name="Club", slug="club", status="active", plan="starter")
    db.session.add(tenant)
    db.session.flush()
    admin = seeded_db["admin"]
    admin.joined = date(2026, 1, 1)
    other = Member(status="active", joined=date(2026, 10, 28))
    left = Member(
        status="active",
        joined=date(2026, 1, 1),
        archived_at=_at(date(2026, 10, 21)),
    )
    db.session.add_all([other, left])
    db.session.flush()

    def login(member, day):
        db.session.add(AuditEntry(actor_id=member.id, action="login", time=_at(day)))

    login(admin, date(2026, 11, 2))
    login(admin, date(2026, 11, 3))
    login(other, date(2026, 11, 3))
    login(admin, date(2026, 10, 20))
    login(admin, date(2026, 6, 1))  # outside 12 weeks
    db.session.add(
        AuditEntry(actor_id=admin.id, action="member.update", time=_at(TODAY))
    )
    db.session.add_all(
        [
            ClubEvent(title="Training", date=date(2026, 10, 27), type="training"),
            ClubEvent(title="GV", date=date(2026, 11, 6), type="meeting"),
            Invoice(
                member_id=admin.id,
                issued=date(2026, 10, 26),
                due=date(2026, 11, 26),
                amount=Decimal("50.00"),
                purpose="membership",
            ),
            Invoice(
                member_id=other.id,
                issued=date(2026, 10, 27),
                due=date(2026, 11, 27),
                amount=Decimal("25.50"),
                purpose="membership",
            ),
            PlatformEvent(
                created_at=_at(date(2026, 11, 3)),
                category="mail",
                kind="mail.sent",
                level="info",
                tenant_id=tenant.id,
                message="sent",
            ),
            PlatformEvent(
                created_at=_at(date(2026, 11, 3)),
                category="mail",
                kind="mail.failed",
                level="warning",
                tenant_id=tenant.id,
                message="failed",
            ),
        ]
    )
    db.session.commit()
    return tenant


def test_weekly_numbers(db, club):
    out = usage_trends.for_tenant(club, "12w", today=TODAY)
    assert out["unit"] == "week"
    assert len(out["buckets"]) == 12
    assert out["buckets"][-3:] == ["2026-10-19", "2026-10-26", "2026-11-02"]
    s = {k: v[-3:] for k, v in out["series"].items()}
    assert s["logins"] == [1, 0, 3]
    assert s["active_members"] == [1, 0, 2]
    assert s["new_members"] == [0, 1, 0]
    # The archived member counts until the week they left.
    assert s["members"] == [1, 2, 2]
    assert s["events"] == [0, 1, 1]
    assert s["invoices"] == [0, 2, 0]
    assert s["invoice_total"] == [0, 75.5, 0]
    assert s["mails"] == [0, 0, 1]


def test_monthly_numbers(db, club):
    out = usage_trends.for_tenant(club, "12m", today=TODAY)
    assert out["buckets"][-2:] == ["2026-10-01", "2026-11-01"]
    s = {k: v[-2:] for k, v in out["series"].items()}
    assert s["logins"] == [1, 2 + 1]
    assert s["active_members"] == [1, 2]
    assert s["invoices"] == [2, 0]
    assert out["series"]["logins"][-6] == 1  # June


def test_trends_api(client, staff_headers, club):
    resp = client.get(f"/api/v1/system/tenants/{club.id}/trends?range=26w")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["range"] == "26w" and len(body["buckets"]) == 26
    assert set(body["series"]) == set(usage_trends.METRICS)
    assert (
        client.get(f"/api/v1/system/tenants/{club.id}/trends?range=5y").status_code
        == 400
    )
    assert client.get("/api/v1/system/tenants/999/trends").status_code == 404


def test_trends_need_platform_rights(client, auth_headers, club):
    assert client.get(f"/api/v1/system/tenants/{club.id}/trends").status_code in (
        401,
        403,
    )
