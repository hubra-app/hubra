"""A member's own fee: exempt, own yearly amount or a reduction, with a
reason, an optional end date, a reminder before it and the standard fee
again after it."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.fee_adjustment import MemberFeeAdjustment
from hubra.core.models.finance import Invoice
from hubra.core.models.member import Member
from hubra.core.models.notification import Notification
from hubra.core.pricing import apply_fee_adjustment
from tests.helpers import add_member


def _adj(kind, amount=None, percent=None, until=None):
    return SimpleNamespace(
        kind=kind,
        amount_chf=amount,
        percent=percent,
        valid_until=until,
        active_on=lambda day: until is None or day <= until,
    )


def _member(adj, interval=None):
    plan = SimpleNamespace(tier_id=1, interval=interval) if interval else None
    return SimpleNamespace(fee_adjustment=adj, payment_plan=plan)


TIER = SimpleNamespace(id=1, billing_cycle="yearly")
TODAY = date(2026, 11, 9)


def test_no_adjustment_keeps_the_amount():
    assert apply_fee_adjustment(_member(None), TIER, Decimal("120"), TODAY) == 120


def test_exempt_pays_nothing():
    member = _member(_adj("exempt"))
    assert apply_fee_adjustment(member, TIER, Decimal("120"), TODAY) == 0


def test_own_yearly_amount_is_split_into_the_members_periods():
    member = _member(_adj("amount", amount=Decimal("50")), interval="quarterly")
    assert apply_fee_adjustment(member, TIER, Decimal("30"), TODAY) == Decimal("12.5")


def test_reduction_in_percent_rounds_to_5_rappen():
    member = _member(_adj("percent", percent=Decimal("33")))
    # 45 * 0.67 = 30.15
    assert apply_fee_adjustment(member, TIER, Decimal("45"), TODAY) == Decimal("30.15")


def test_ended_adjustment_gives_the_standard_fee():
    member = _member(_adj("exempt", until=TODAY - timedelta(days=1)))
    assert apply_fee_adjustment(member, TIER, Decimal("120"), TODAY) == 120
    # A period that starts on the end date is still covered.
    member = _member(_adj("exempt", until=TODAY))
    assert apply_fee_adjustment(member, TIER, Decimal("120"), TODAY) == 0


# ── API ───────────────────────────────────────────────────────────────────────


@pytest.fixture
def anna(client, db, auth_headers, seeded_db):
    tier = seeded_db["tier"]
    tier.price_chf = Decimal("120")
    tier.price_type = "fixed"
    tier.billing_cycle = "yearly"
    db.session.commit()
    created = add_member(
        client,
        auth_headers,
        email="anna@test.ch",
        first_name="Anna",
        last_name="Student",
        status="active",
        tier=tier.name,
    )
    assert created.status_code == 200, created.get_json()
    member = db.session.get(Member, int(created.get_json()["id"]))
    member.tier_id = tier.id
    # A member for years: billed the whole period, not pro rata.
    member.joined = date(2020, 1, 1)
    member.status = "active"
    db.session.commit()
    return member.id


def _url(member_id):
    return f"/api/v1/tiers/members/{member_id}/fee"


def test_board_sets_reads_and_removes_an_own_fee(client, db, auth_headers, anna):
    assert client.get(_url(anna)).get_json() == {
        "adjustment": None,
        "billing_cycle": "yearly",
        "standard_amount": 120.0,
        "amount": 120.0,
    }

    resp = client.put(
        _url(anna),
        json={
            "kind": "percent",
            "percent": 50,
            "reason": "Studentin",
            "valid_until": "2027-07-31",
        },
    )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["amount"] == 60.0
    assert body["standard_amount"] == 120.0
    assert body["adjustment"]["reason"] == "Studentin"
    assert body["adjustment"]["remind_days"] == 30
    assert body["adjustment"]["active"] is True

    listed = client.get("/api/v1/tiers/fee-adjustments").get_json()
    assert [(a["member_id"], a["member_name"]) for a in listed] == [
        (anna, "Anna Student")
    ]

    resp = client.delete(_url(anna))
    assert resp.status_code == 200
    assert resp.get_json()["adjustment"] is None
    assert client.delete(_url(anna)).status_code == 404


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"kind": "exempt", "reason": "  "}, "reason"),
        ({"kind": "free", "reason": "x"}, "kind"),
        ({"kind": "amount", "reason": "x"}, "amount_chf"),
        ({"kind": "amount", "amount_chf": -1, "reason": "x"}, "amount_chf"),
        ({"kind": "percent", "percent": 120, "reason": "x"}, "percent"),
        ({"kind": "exempt", "reason": "x", "valid_until": "soon"}, "valid_until"),
        ({"kind": "exempt", "reason": "x", "remind_days": -2}, "remind_days"),
    ],
)
def test_bad_input_names_the_field(client, auth_headers, anna, payload, field):
    resp = client.put(_url(anna), json=payload)
    assert resp.status_code == 400
    assert field in (resp.get_json().get("fields") or {})


def test_reason_stays_out_of_the_audit_log(client, db, auth_headers, anna):
    from hubra.core.models.audit import AuditEntry

    client.put(_url(anna), json={"kind": "exempt", "reason": "Arbeitslos"})
    labels = db.session.scalars(select(AuditEntry.target_label)).all()
    assert labels and not any("Arbeitslos" in (label or "") for label in labels)


def _login(client, email):
    client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Member-Pass-123!"}
    )


def test_member_sees_and_confirms_their_own_fee(
    client, db, auth_headers, anna, seeded_db
):
    until = (date.today() + timedelta(days=20)).isoformat()
    client.put(
        _url(anna),
        json={
            "kind": "amount",
            "amount_chf": 40,
            "reason": "Lehrling",
            "valid_until": until,
        },
    )
    _login(client, "anna@test.ch")
    mine = client.get("/api/v1/tiers/my-fee").get_json()
    assert mine["amount"] == 40.0
    assert mine["adjustment"]["reason"] == "Lehrling"
    # Members can't set their own fee.
    assert (
        client.put(_url(anna), json={"kind": "exempt", "reason": "x"}).status_code
        == 403
    )
    assert client.get("/api/v1/tiers/fee-adjustments").status_code == 403

    assert client.post("/api/v1/tiers/my-fee/confirm", json={}).status_code == 400
    resp = client.post("/api/v1/tiers/my-fee/confirm", json={"note": "Lehre bis 2028"})
    assert resp.status_code == 200
    adj = resp.get_json()["adjustment"]
    assert adj["confirmed_at"] and adj["confirmation_note"] == "Lehre bis 2028"
    told = db.session.scalars(
        select(Notification.member_id).where(
            Notification.title == "Fee reason confirmed"
        )
    ).all()
    assert told == [seeded_db["admin"].id]


def test_new_end_date_asks_again(client, db, auth_headers, anna):
    client.put(
        _url(anna),
        json={"kind": "exempt", "reason": "x", "valid_until": "2026-12-31"},
    )
    adj = db.session.scalar(select(MemberFeeAdjustment))
    adj.reminder_sent_at = adj.confirmed_at = adj.created_at
    adj.confirmation_note = "still"
    db.session.commit()
    client.put(
        _url(anna),
        json={"kind": "exempt", "reason": "x", "valid_until": "2027-12-31"},
    )
    db.session.refresh(adj)
    assert adj.reminder_sent_at is None
    assert adj.confirmed_at is None and adj.confirmation_note is None


# ── Invoices ─────────────────────────────────────────────────────────────────


def _invoices(db, member_id):
    return db.session.scalars(
        select(Invoice).where(Invoice.member_id == member_id)
    ).all()


def _run_invoices(app):
    from hubra.core.tasks.finance_tasks import generate_invoices_task

    with patch("hubra.core.tasks.email_tasks.send_email_task.delay"):
        return generate_invoices_task.run()


def test_exempt_member_gets_no_invoice(app, client, db, auth_headers, anna):
    client.put(_url(anna), json={"kind": "exempt", "reason": "Ehrenhalber"})
    _run_invoices(app)
    assert _invoices(db, anna) == []


def test_reduced_member_is_billed_the_reduced_fee(app, client, db, auth_headers, anna):
    client.put(_url(anna), json={"kind": "percent", "percent": 25, "reason": "IV"})
    _run_invoices(app)
    assert [float(i.amount) for i in _invoices(db, anna)] == [90.0]


def test_after_the_end_date_the_standard_fee_applies(
    app, client, db, auth_headers, anna
):
    client.put(_url(anna), json={"kind": "exempt", "reason": "x"})
    adj = db.session.scalar(select(MemberFeeAdjustment))
    # Ended before this year's billing period started.
    adj.valid_until = date(date.today().year - 1, 12, 31)
    db.session.commit()
    _run_invoices(app)
    assert [float(i.amount) for i in _invoices(db, anna)] == [120.0]


# ── Reminders ────────────────────────────────────────────────────────────────


def _remind(today=None):
    from hubra.core.tasks.finance_tasks import _fee_adjustment_reminders

    with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as sent:
        result = _fee_adjustment_reminders(today=today)
    return result, sent


def _titles(db, member_id):
    return db.session.scalars(
        select(Notification.title).where(Notification.member_id == member_id)
    ).all()


def test_member_is_asked_once_before_the_end_date(app, client, db, auth_headers, anna):
    today = date.today()
    client.put(
        _url(anna),
        json={
            "kind": "exempt",
            "reason": "x",
            "valid_until": (today + timedelta(days=40)).isoformat(),
            "remind_days": 30,
        },
    )
    # Too early.
    assert _remind(today)[0] == {"reminded": 0, "ended": 0}
    result, sent = _remind(today + timedelta(days=10))
    assert result == {"reminded": 1, "ended": 0}
    assert sent.call_count == 1
    assert "anna@test.ch" == sent.call_args.kwargs["to_email"]
    assert _titles(db, anna) == ["Fee arrangement ends soon"]
    # Not again.
    assert _remind(today + timedelta(days=11))[0] == {"reminded": 0, "ended": 0}


def test_member_and_board_hear_when_it_ended(
    app, client, db, auth_headers, anna, seeded_db
):
    today = date.today()
    client.put(
        _url(anna),
        json={
            "kind": "exempt",
            "reason": "x",
            "valid_until": (today + timedelta(days=5)).isoformat(),
            "remind_days": 0,
        },
    )
    assert _remind(today)[0] == {"reminded": 0, "ended": 0}
    assert _remind(today + timedelta(days=6))[0] == {"reminded": 0, "ended": 1}
    assert _titles(db, anna) == ["Fee arrangement ended"]
    assert "A member fee arrangement ended" in _titles(db, seeded_db["admin"].id)
    assert _remind(today + timedelta(days=7))[0] == {"reminded": 0, "ended": 0}
