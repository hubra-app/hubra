"""Tests for the unified Mail Administration endpoints."""

from __future__ import annotations


from unittest.mock import patch

from hubra.core.models.group import Group
from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.models.setting import Setting


def _ensure_mail_domain(db, domain: str = "club.ch"):
    existing = db.session.get(Setting, "mail.domain")
    if existing is None:
        db.session.add(Setting(key="mail.domain", value=domain))
    else:
        existing.value = domain
    db.session.commit()


def _make_member_mma(
    db,
    member_id: int,
    *,
    wildduck_id: str = "5f8d0b1a2c3e4f5a6b7c8d9e",
    address: str = "alice@club.ch",
) -> ManagedMailAddress:
    addr = ManagedMailAddress(
        address=address,
        address_type="mailbox",
        is_protected=False,
        is_enabled=True,
        is_system=False,
        kind="member",
        local_part=address.split("@")[0],
        domain="club.ch",
        wildduck_id=wildduck_id,
        wildduck_user_id=wildduck_id,
        owner_type="member",
        owner_id=member_id,
        provisioning_status="provisioned",
        sync_state="ok",
        sync_error=None,
    )
    db.session.add(addr)
    db.session.commit()
    return addr


# ── resolve-local-part ─────────────────────────────────────────────────────────


def test_resolve_local_part_endpoint(client, db, seeded_db, auth_headers):
    _ensure_mail_domain(db)
    resp = client.get(
        "/api/v1/mail/resolve-local-part?prefix=vorstand",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "localPart" in data
    assert data["localPart"] == "vorstand"


def test_resolve_local_part_empty_prefix(client, db, seeded_db, auth_headers):
    resp = client.get(
        "/api/v1/mail/resolve-local-part?prefix=",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["localPart"] == ""


def test_resolve_local_part_collision_suffixes(client, db, seeded_db, auth_headers):
    _ensure_mail_domain(db)
    addr = ManagedMailAddress(
        address="vorstand@club.ch",
        address_type="alias",
        is_protected=False,
        is_enabled=True,
        is_system=False,
        kind="group",
        local_part="vorstand",
        domain="club.ch",
        provisioning_status="provisioned",
    )
    db.session.add(addr)
    db.session.commit()

    resp = client.get(
        "/api/v1/mail/resolve-local-part?prefix=vorstand",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["localPart"] == "vorstand2"


# ── syncError in serialize ────────────────────────────────────────────────────


def test_serialize_includes_sync_error(client, db, seeded_db, auth_headers):
    from hubra.core.services.managed_mail import serialize

    addr = ManagedMailAddress(
        address="test@club.ch",
        address_type="mailbox",
        is_protected=False,
        is_enabled=True,
        is_system=False,
        kind="member",
        local_part="test",
        domain="club.ch",
        provisioning_status="provisioned",
        sync_state="error",
        sync_error="Connection refused",
    )
    db.session.add(addr)
    db.session.commit()
    data = serialize(addr)
    assert data["syncState"] == "error"
    assert data["syncError"] == "Connection refused"


# ── reconcile ──────────────────────────────────────────────────────────────────


def test_trigger_reconcile(client, db, seeded_db, auth_headers):
    with patch("hubra.core.tasks.mail_tasks.reconcile_mail") as mock_task:
        mock_task.delay.return_value = None
        resp = client.post("/api/v1/mail/reconcile", headers=auth_headers)

    assert resp.status_code == 202
    assert resp.get_json()["ok"] is True
    assert resp.get_json()["task"] == "reconcile_mail"
    mock_task.delay.assert_called_once()


# ── quota enrichment ───────────────────────────────────────────────────────────


def test_member_mail_list_includes_quota(client, db, seeded_db, auth_headers):
    _ensure_mail_domain(db)
    _make_member_mma(db, seeded_db["admin"].id, wildduck_id="5f8d0b1a2c3e4f5a6b7c8d9e")

    resp = client.get("/api/v1/mail/members-mail", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["quotaUsed"] is None
    assert data[0]["quotaTotal"] is None


def test_group_mail_list_includes_quota(client, db, seeded_db, auth_headers):
    _ensure_mail_domain(db)
    group = Group(name="Test Group")
    db.session.add(group)
    db.session.commit()

    addr = ManagedMailAddress(
        address="team@club.ch",
        address_type="alias",
        is_protected=False,
        is_enabled=True,
        is_system=False,
        kind="group",
        local_part="team",
        domain="club.ch",
        wildduck_id="5f8d0b1a2c3e4f5a6b7c8d9e",
        wildduck_user_id="5f8d0b1a2c3e4f5a6b7c8d9e",
        owner_type="group",
        owner_id=group.id,
        provisioning_status="provisioned",
    )
    db.session.add(addr)
    db.session.commit()

    resp = client.get("/api/v1/mail/groups", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["quotaUsed"] is None
    assert data[0]["quotaTotal"] is None


def test_quota_null_when_wildduck_unavailable(client, db, seeded_db, auth_headers):
    _ensure_mail_domain(db)
    _make_member_mma(db, seeded_db["admin"].id, wildduck_id="5f8d0b1a2c3e4f5a6b7c8d9e")

    resp = client.get("/api/v1/mail/members-mail", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["quotaUsed"] is None
    assert data[0]["quotaTotal"] is None
