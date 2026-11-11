"""Notice periods from the statutes on requests to leave."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from hubra.core.services.notice_period import earliest_exit
from tests.members.test_leave_club import H, _login, club  # noqa: F401


@pytest.mark.parametrize(
    ("asked", "months", "at", "exit_on"),
    [
        (date(2026, 9, 15), 3, "year_end", date(2026, 12, 31)),
        (date(2026, 10, 1), 3, "year_end", date(2027, 12, 31)),
        (date(2026, 10, 1), 3, "quarter_end", date(2027, 3, 31)),
        (date(2026, 3, 31), 0, "quarter_end", date(2026, 3, 31)),
        (date(2026, 2, 10), 1, "month_end", date(2026, 3, 31)),
        (date(2026, 11, 30), 3, "any", date(2027, 2, 28)),
        (date(2026, 5, 1), 2, "half_year_end", date(2026, 12, 31)),
        (date(2026, 4, 1), 2, "half_year_end", date(2026, 6, 30)),
    ],
)
def test_earliest_exit(asked, months, at, exit_on):
    assert earliest_exit(asked, months, at) == exit_on


def test_a_request_shows_the_exit_date_and_open_invoices(client, db, club):  # noqa: F811
    from hubra.core.models.finance import Invoice

    club["tenant"].settings = {
        "branding": {
            "leave_requires_approval": True,
            "leave_notice_months": 3,
            "leave_at": "year_end",
        }
    }
    today = date.today()
    db.session.add(
        Invoice(
            member_id=club["anna"].id,
            issued=today - timedelta(days=40),
            due=today - timedelta(days=10),
            amount=Decimal("120.00"),
            status="Open",
            description="Jahresbeitrag",
        )
    )
    db.session.add(
        Invoice(
            member_id=club["anna"].id,
            issued=today,
            due=today,
            amount=Decimal("50"),
            status="Paid",
        )
    )
    db.session.commit()

    _login(client, "anna@test.ch")
    state = client.get("/api/v1/members/me/leave", headers=H).json
    assert state["notice"] == {"months": 3, "at": "year_end"}
    assert state["earliestExit"] == earliest_exit(today, 3, "year_end").isoformat()
    assert [i["amount"] for i in state["openInvoices"]] == ["120.00"]
    assert state["openInvoices"][0]["overdue"] is True
    assert (
        client.post("/api/v1/members/me/leave", headers=H).json["status"] == "requested"
    )

    _login(client, "admin@test.ch")
    rows = client.get("/api/v1/members/leave-requests", headers=H).json
    assert rows[0]["earliestExit"] == state["earliestExit"]
    assert len(rows[0]["openInvoices"]) == 1


def test_the_club_saves_its_notice_rule(client, db, club):  # noqa: F811
    _login(client, "admin@test.ch")
    url = "/api/v1/admin/club-settings"
    resp = client.patch(
        url, json={"leave_notice_months": 3, "leave_at": "year_end"}, headers=H
    )
    assert resp.status_code == 200
    assert resp.json["settings"]["leave_at"] == "year_end"
    assert (
        client.patch(url, json={"leave_at": "whenever"}, headers=H).status_code == 422
    )
    assert (
        client.patch(url, json={"leave_notice_months": 99}, headers=H).status_code
        == 422
    )


def test_leave_terms_need_sign_in(client, club):  # noqa: F811
    assert client.get("/api/v1/members/me/leave", headers=H).status_code == 401
