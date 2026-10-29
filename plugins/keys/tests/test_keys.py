"""The keys plugin: keys, handovers and the overdue-invoice hook."""

from __future__ import annotations

import pytest

from tests.helpers import set_modules
from hubra.core.models.member import Member
from hubra.core.models.notification import Notification
from hubra_keys.models import Key


@pytest.fixture
def other_member(db, seeded_db):
    from hubra.core.models.user import User

    user = User(email="holder@test.ch", first_name="Hanna", last_name="Holder")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    m = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    db.session.add(m)
    db.session.commit()
    return m


@pytest.fixture
def key(db, seeded_db):
    k = Key(label="Front door", number="A-1", kind="key", opens="Main entrance")
    db.session.add(k)
    db.session.commit()
    return k


# ── Keys ─────────────────────────────────────────────────────────────────────


def test_create_and_list_keys(client, auth_headers):
    resp = client.post(
        "/api/v1/keys/",
        json={"label": "Workshop", "number": "W-7", "kind": "card", "deposit_chf": 20},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "available"
    assert body["depositChf"] == "20.00" or body["depositChf"] == "20"
    listed = client.get("/api/v1/keys/").get_json()
    assert [k["label"] for k in listed] == ["Workshop"]


def test_create_key_validates(client, auth_headers, key):
    assert client.post("/api/v1/keys/", json={}).status_code == 400
    assert (
        client.post("/api/v1/keys/", json={"label": "x", "kind": "laser"}).status_code
        == 400
    )
    for body in (
        {"label": 5},
        {"label": "x", "notes": ["a"]},
        {"label": "x", "code_id": "1"},
        {"label": "x", "deposit_chf": "NaN"},
    ):
        assert client.post("/api/v1/keys/", json=body).status_code == 400, body
    dup = client.post("/api/v1/keys/", json={"label": "Copy", "number": "A-1"})
    assert dup.status_code == 409


def test_issue_and_return_key_logs_history(client, auth_headers, key, other_member):
    resp = client.post(
        f"/api/v1/keys/{key.id}/issue", json={"member_id": other_member.id}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "issued"
    assert body["holderName"] == "Hanna Holder"

    # Cannot issue twice or delete while issued.
    again = client.post(
        f"/api/v1/keys/{key.id}/issue", json={"member_id": other_member.id}
    )
    assert again.status_code == 409
    assert client.delete(f"/api/v1/keys/{key.id}").status_code == 409

    resp = client.post(f"/api/v1/keys/{key.id}/return", json={"note": "ok"})
    body = resp.get_json()
    assert body["status"] == "available" and body["holderId"] is None
    assert [h["action"] for h in body["history"]] == ["return", "issue"]


def test_lost_and_found(client, auth_headers, key):
    assert client.post(f"/api/v1/keys/{key.id}/lost").get_json()["status"] == "lost"
    assert client.post(f"/api/v1/keys/{key.id}/lost").status_code == 409
    assert (
        client.post(f"/api/v1/keys/{key.id}/found").get_json()["status"] == "available"
    )


def test_my_keys(client, db, auth_headers, key, seeded_db):
    key.status = "issued"
    key.holder_id = seeded_db["admin"].id
    key.notes = "Depot noch offen, nachfragen"
    db.session.commit()
    mine = client.get("/api/v1/keys/mine").get_json()
    assert [k["id"] for k in mine] == [key.id]
    # Manager notes stay with the managers.
    assert "notes" not in mine[0] and "codeId" not in mine[0]

    key.status = "retired"
    db.session.commit()
    assert client.get("/api/v1/keys/mine").get_json() == []


def test_keys_need_inventory(client, db, auth_headers):
    set_modules(False, "inventory")
    resp = client.get("/api/v1/keys/")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MODULE_DISABLED"


def test_overdue_invoice_notifies_key_managers(db, seeded_db, key, other_member):
    from hubra.core.modules import emit

    key.status = "issued"
    key.holder_id = other_member.id
    db.session.commit()
    called = emit(
        "invoice.overdue", tenant_id=None, member_id=other_member.id, invoice_id=1
    )
    assert "inventory.keys" in called
    notes = (
        db.session.query(Notification).filter_by(member_id=seeded_db["admin"].id).all()
    )
    assert any("Front door" in n.msg for n in notes)
