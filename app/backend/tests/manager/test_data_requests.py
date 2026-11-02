"""Data protection requests per club: record, deadline, export, deletion,
done/rejected with who and when (services/data_requests.py)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from hubra.core.models.data_request import DataRequest
from hubra.core.models.finance import Invoice
from hubra.core.models.member import Member
from hubra.core.models.notification import Notification
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant


@pytest.fixture
def club(db, seeded_db):
    tenant = Tenant(name="Club A", slug="club-a", status="active", settings={})
    db.session.add(tenant)
    db.session.flush()
    db.session.add(
        UserTenant(user_id=seeded_db["user"].id, tenant_id=tenant.id, is_owner=True)
    )
    db.session.commit()
    return tenant


@pytest.fixture
def anna(db, club):
    user = User(
        email="anna@test.ch",
        first_name="Anna",
        last_name="Muster",
        phone="+41 79 000 00 00",
        private_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    member = Member(user_id=user.id, status="active", notes="Trainerin U12")
    db.session.add(member)
    db.session.flush()
    db.session.add(UserTenant(user_id=user.id, tenant_id=club.id))
    db.session.add(
        Invoice(
            member_id=member.id,
            issued=date(2026, 1, 1),
            due=date(2026, 1, 31),
            amount="80.00",
            status="Paid",
        )
    )
    db.session.add(Notification(member_id=member.id, kind="info", title="Hi", msg="x"))
    db.session.commit()
    return member


def _create(client, club, **body):
    resp = client.post(f"/api/v1/system/tenants/{club.id}/data-requests", json=body)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_request_is_recorded_with_deadline(client, staff_headers, db, club, anna):
    received = (date.today() - timedelta(days=25)).isoformat()
    req = _create(
        client,
        club,
        kind="export",
        subject_name="Anna Muster",
        subject_email="anna@test.ch",
        received_on=received,
        received_via="Mail an support@",
        member_id=anna.id,
    )
    assert req["status"] == "open" and req["tenant_name"] == "Club A"
    assert req["due_on"] == (date.fromisoformat(received) + timedelta(30)).isoformat()
    assert req["days_left"] == 5 and req["due_soon"] and not req["overdue"]

    listing = client.get("/api/v1/system/data-requests").get_json()
    assert [r["id"] for r in listing["requests"]] == [req["id"]]
    assert listing["counts"] == {"open": 1, "overdue": 0}
    entry = db.session.scalar(
        select(GlobalAuditEntry).where(
            GlobalAuditEntry.action == "privacy.request.created"
        )
    )
    assert entry.tenant_id == club.id


def test_overdue_and_filters(client, staff_headers, db, club):
    old = (date.today() - timedelta(days=40)).isoformat()
    _create(client, club, kind="deletion", subject_email="x@y.ch", received_on=old)
    body = client.get("/api/v1/system/data-requests").get_json()
    assert body["requests"][0]["overdue"] and body["counts"]["overdue"] == 1
    assert (
        client.get("/api/v1/system/data-requests?status=done").get_json()["requests"]
        == []
    )
    other = client.get(f"/api/v1/system/data-requests?tenant_id={club.id + 1}")
    assert other.get_json()["requests"] == []
    assert client.get("/api/v1/system/data-requests?status=x").status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "copy", "subject_email": "a@b.ch"},
        {"kind": "export"},  # nobody named
        {"kind": "export", "subject_email": "a@b.ch", "received_on": "2999-01-01"},
        {"kind": "export", "subject_email": "a@b.ch", "received_on": "gestern"},
        {"kind": "export", "member_id": 9999},
        {"kind": "export", "member_id": "1"},
        {"kind": "export", "subject_name": "x" * 201},
    ],
)
def test_bad_requests_are_refused(client, staff_headers, club, body):
    resp = client.post(f"/api/v1/system/tenants/{club.id}/data-requests", json=body)
    assert resp.status_code in (400, 404)


def test_export_has_the_members_data_without_secrets(
    client, staff_headers, db, club, anna
):
    req = _create(client, club, kind="export", member_id=anna.id)
    resp = client.post(f"/api/v1/system/data-requests/{req['id']}/export")
    assert resp.status_code == 200, resp.get_json()
    assert "attachment" in resp.headers["Content-Disposition"]
    data = resp.get_json()
    assert data["account"]["email"] == "anna@test.ch"
    assert data["account"]["phone"] == "+41 79 000 00 00"
    assert "password_hash" not in data["account"]
    assert data["member"]["notes"] == "Trainerin U12"
    assert data["related"]["invoices"][0]["amount"] in ("80.00", "80")
    assert len(data["related"]["notifications"]) == 1
    text = resp.get_data(as_text=True)
    assert "password" not in text and "totp" not in text

    db.session.expire_all()
    stored = db.session.get(DataRequest, req["id"])
    assert stored.result["rows"]["invoices"] == 1
    assert len(stored.exports) == 1
    assert stored.status == "open"  # done is a separate step

    done = client.post(
        f"/api/v1/system/data-requests/{req['id']}/done",
        json={"outcome": "Per Mail an anna@test.ch geschickt"},
    ).get_json()
    assert done["status"] == "done" and done["handled_at"]
    assert done["handled_by"] is not None
    again = client.post(f"/api/v1/system/data-requests/{req['id']}/rejected")
    assert again.status_code == 409


def test_export_needs_the_member_and_the_kind(client, staff_headers, club, anna):
    no_member = _create(client, club, kind="export", subject_email="a@b.ch")
    assert (
        client.post(f"/api/v1/system/data-requests/{no_member['id']}/export")
    ).status_code == 400
    deletion = _create(client, club, kind="deletion", member_id=anna.id)
    assert (
        client.post(f"/api/v1/system/data-requests/{deletion['id']}/export")
    ).status_code == 409


def test_deletion_removes_the_member_and_keeps_the_books(
    client, staff_headers, db, club, anna
):
    member_id, user_id = anna.id, anna.user_id
    req = _create(client, club, kind="deletion", member_id=member_id)
    url = f"/api/v1/system/data-requests/{req['id']}"
    # Done before anything was deleted is refused.
    assert client.post(f"{url}/done").status_code == 409
    assert client.post(f"{url}/delete-member", json={}).status_code == 400

    resp = client.post(f"{url}/delete-member", json={"confirm": "club-a"})
    assert resp.status_code == 200, resp.get_json()
    result = resp.get_json()["result"]
    assert result["deleted"] and result["kept_without_name"]["invoices"] == 1

    db.session.expire_all()
    assert db.session.get(Member, member_id) is None
    invoice = db.session.scalar(select(Invoice))
    assert invoice.member_id is None  # the club keeps its books
    assert db.session.scalar(select(Notification)) is None
    assert db.session.get(User, user_id) is not None  # the account is theirs
    assert (
        db.session.scalar(
            select(UserTenant).where(
                UserTenant.user_id == user_id, UserTenant.tenant_id == club.id
            )
        )
        is None
    )
    assert client.post(f"{url}/done", json={"outcome": "Bestätigt"}).status_code == 200
    actions = set(db.session.scalars(select(GlobalAuditEntry.action)).all())
    assert {"privacy.deletion", "privacy.request.done"} <= actions


def test_last_owner_cannot_be_deleted(client, staff_headers, db, club, seeded_db):
    req = _create(client, club, kind="deletion", member_id=seeded_db["admin"].id)
    resp = client.post(
        f"/api/v1/system/data-requests/{req['id']}/delete-member",
        json={"confirm": "club-a"},
    )
    assert resp.status_code == 409
    assert db.session.get(Member, seeded_db["admin"].id) is not None


def test_reject_needs_a_reason(client, staff_headers, club):
    req = _create(client, club, kind="deletion", subject_email="a@b.ch")
    url = f"/api/v1/system/data-requests/{req['id']}/rejected"
    assert client.post(url, json={}).status_code == 400
    resp = client.post(url, json={"outcome": "Keine Mitgliedschaft gefunden"})
    assert resp.get_json()["status"] == "rejected"


def test_update_while_open(client, staff_headers, club, anna):
    req = _create(client, club, kind="export", subject_email="a@b.ch")
    url = f"/api/v1/system/data-requests/{req['id']}"
    resp = client.patch(url, json={"member_id": anna.id, "note": "Gefunden"})
    assert resp.get_json()["member_id"] == anna.id
    assert client.patch(url, json={"status": "done"}).status_code == 400


def test_needs_the_privacy_right(client, auth_headers, club):
    assert client.get("/api/v1/system/data-requests").status_code in (401, 403)
    resp = client.post(
        f"/api/v1/system/tenants/{club.id}/data-requests",
        json={"kind": "export", "subject_email": "a@b.ch"},
    )
    assert resp.status_code in (401, 403)
