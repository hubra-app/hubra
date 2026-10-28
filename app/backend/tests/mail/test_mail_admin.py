"""Tests for the unified Mail Administration endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


def _mock_wd():
    """Create a mock WildDuck client."""
    wd = MagicMock()
    wd.list_users.return_value = {
        "results": [
            {
                "id": "5f8d0b1a2c3e4f5a6b7c8d9e",
                "address": "alice@club.ch",
                "name": "Alice",
                "disabled": False,
                "targets": ["alice@gmail.com"],
                "quota": {"used": 1048576, "allowed": 1073741824},
            },
            {
                "id": "aabbccddee11223344556677",
                "address": "orphan@club.ch",
                "name": "Orphan",
                "disabled": False,
                "targets": [],
                "quota": {"used": 0, "allowed": 104857600},
            },
        ],
        "total": 2,
    }
    wd.list_addresses.return_value = {
        "results": [
            {
                "id": "11223344556677889900aabb",
                "address": "team@club.ch",
                "name": "Team",
                "disabled": False,
                "targets": ["alice@club.ch"],
                "user": None,
            },
            {
                "id": "aabbccddeeff001122334455",
                "address": "stale@club.ch",
                "name": "Stale",
                "disabled": False,
                "targets": [],
                "user": None,
            },
        ],
        "total": 2,
    }
    wd.get_user.return_value = {
        "id": "aabbccddee11223344556677",
        "address": "orphan@club.ch",
        "name": "Orphan",
    }
    wd.delete_user.return_value = {"deleted": True}
    wd.safe_delete_forwarding_alias.return_value = True
    return wd


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


# ── wildduck-live ─────────────────────────────────────────────────────────────


def test_wildduck_live_lists_managed_and_orphan(client, db, seeded_db, auth_headers):
    _ensure_mail_domain(db)
    _make_member_mma(db, seeded_db["admin"].id, wildduck_id="5f8d0b1a2c3e4f5a6b7c8d9e")
    mock_wd = _mock_wd()

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        with patch("hubra.api.mail.services.try_get_client", return_value=mock_wd):
            resp = client.get("/api/v1/mail/wildduck-live", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 4

    managed = [d for d in data if d["managed"]]
    orphans = [d for d in data if not d["managed"]]
    assert len(managed) == 1
    assert len(orphans) == 3
    assert managed[0]["address"] == "alice@club.ch"
    assert managed[0]["kind"] == "member"


# ── delete orphan ──────────────────────────────────────────────────────────────


def test_delete_orphan_mailbox(client, db, seeded_db, auth_headers):
    _ensure_mail_domain(db)
    mock_wd = _mock_wd()

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        with patch("hubra.api.mail.services.try_get_client", return_value=mock_wd):
            resp = client.delete(
                "/api/v1/mail/wildduck-live/mailbox/aabbccddee11223344556677",
                headers=auth_headers,
            )

    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    mock_wd.delete_user.assert_called_once_with("aabbccddee11223344556677")


def test_delete_orphan_rejects_managed(client, db, seeded_db, auth_headers):
    _ensure_mail_domain(db)
    _make_member_mma(db, seeded_db["admin"].id, wildduck_id="5f8d0b1a2c3e4f5a6b7c8d9e")
    mock_wd = _mock_wd()

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        with patch("hubra.api.mail.services.try_get_client", return_value=mock_wd):
            resp = client.delete(
                "/api/v1/mail/wildduck-live/mailbox/5f8d0b1a2c3e4f5a6b7c8d9e",
                headers=auth_headers,
            )

    assert resp.status_code == 409
    mock_wd.delete_user.assert_not_called()


def test_delete_orphan_alias(client, db, seeded_db, auth_headers):
    _ensure_mail_domain(db)
    mock_wd = _mock_wd()

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        with patch("hubra.api.mail.services.try_get_client", return_value=mock_wd):
            resp = client.delete(
                "/api/v1/mail/wildduck-live/alias/aabbccddeeff001122334455",
                headers=auth_headers,
            )

    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    mock_wd.safe_delete_forwarding_alias.assert_called_once_with(
        "aabbccddeeff001122334455"
    )


def test_delete_orphan_invalid_type(client, db, seeded_db, auth_headers):
    resp = client.delete(
        "/api/v1/mail/wildduck-live/invalid/wd-orphan",
        headers=auth_headers,
    )
    assert resp.status_code == 400


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
