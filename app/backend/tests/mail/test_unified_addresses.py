"""Tests for the unified /mail/addresses API."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from hubra.core.models.group import Group
from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.models.member import Member
from hubra.core.models.setting import Setting
from hubra.core.models.user import User


def _make_mma(db, *, address: str, **overrides) -> ManagedMailAddress:
    defaults = {
        "address_type": "alias",
        "is_protected": False,
        "is_enabled": True,
        "is_system": False,
    }
    defaults.update(overrides)
    addr = ManagedMailAddress(address=address, **defaults)
    db.session.add(addr)
    db.session.commit()
    return addr


def _make_member(db, name="Test Member", email="test@example.ch"):
    parts = name.split()
    user = User(email=email, first_name=parts[0], last_name=parts[-1])
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    m = Member(user_id=user.id)
    db.session.add(m)
    db.session.commit()
    return m


# ── GET /addresses ────────────────────────────────────────────────────────────


def test_list_addresses(client, db, seeded_db, auth_headers):
    db.session.add(Setting(key="mail.domain", value="test.ch"))
    m = _make_member(db, "Alice Smith", "alice@test.ch")
    _make_mma(
        db, address="alice@test.ch", owner_type="member", owner_id=m.id, kind="member"
    )
    resp = client.get("/api/v1/mail/addresses", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert any(d["address"] == "alice@test.ch" for d in data)


def test_list_addresses_excludes_system(client, db, seeded_db, auth_headers):
    _make_mma(db, address="sys@test.ch", is_system=True)
    resp = client.get("/api/v1/mail/addresses", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert not any(d["address"] == "sys@test.ch" for d in data)


def test_list_all_addresses_includes_system(client, db, seeded_db, auth_headers):
    _make_mma(db, address="sysall@test.ch", is_system=True)
    resp = client.get("/api/v1/mail/addresses/all", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert any(d["address"] == "sysall@test.ch" for d in data)


def test_list_addresses_filter_owner_type(client, db, seeded_db, auth_headers):
    m = _make_member(db, "Bob Jones", "bob@test.ch")
    g = Group(name="FilterGroup")
    db.session.add(g)
    db.session.commit()
    _make_mma(
        db, address="bob@test.ch", owner_type="member", owner_id=m.id, kind="member"
    )
    _make_mma(
        db, address="filter@test.ch", owner_type="group", owner_id=g.id, kind="group"
    )
    resp = client.get("/api/v1/mail/addresses?owner_type=group", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert all(d["ownerType"] == "group" for d in data)
    assert any(d["address"] == "filter@test.ch" for d in data)


def test_list_addresses_filter_enabled(client, db, seeded_db, auth_headers):
    _make_mma(db, address="enabled@test.ch", is_enabled=True)
    _make_mma(db, address="disabled@test.ch", is_enabled=False)
    resp = client.get("/api/v1/mail/addresses?enabled=false", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert any(d["address"] == "disabled@test.ch" for d in data)
    assert not any(d["address"] == "enabled@test.ch" for d in data)


# ── GET /addresses/<id> ───────────────────────────────────────────────────────


def test_get_address(client, db, seeded_db, auth_headers):
    addr = _make_mma(db, address="getaddr@test.ch")
    resp = client.get(f"/api/v1/mail/addresses/{addr.id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["address"] == "getaddr@test.ch"


def test_get_address_not_found(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/mail/addresses/99999", headers=auth_headers)
    assert resp.status_code == 404


# ── PATCH /addresses/<id>/toggle ──────────────────────────────────────────────


def test_toggle_address(client, db, seeded_db, auth_headers):
    addr = _make_mma(db, address="toggle@test.ch", is_enabled=True)
    resp = client.patch(
        f"/api/v1/mail/addresses/{addr.id}/toggle",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert resp.status_code == 200
    assert resp.get_json()["isEnabled"] is False


# ── GET /addresses/<id>/aliases ───────────────────────────────────────────────


def test_list_aliases(client, db, seeded_db, auth_headers):
    parent = _make_mma(
        db, address="parent@test.ch", owner_type="group", owner_id=1, kind="group"
    )
    _make_mma(
        db,
        address="alias1@test.ch",
        owner_type="mail_address",
        owner_id=parent.id,
        kind="alias",
        fixed_forward_targets=json.dumps(["parent@test.ch"]),
    )
    resp = client.get(
        f"/api/v1/mail/addresses/{parent.id}/aliases", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["address"] == "alias1@test.ch"


def test_list_aliases_excludes_primary(client, db, seeded_db, auth_headers):
    parent = _make_mma(db, address="primary@test.ch", owner_type="group", owner_id=1)
    resp = client.get(
        f"/api/v1/mail/addresses/{parent.id}/aliases", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 0


# ── POST /addresses/<id>/aliases ──────────────────────────────────────────────


def test_create_alias(client, db, seeded_db, auth_headers):
    db.session.add(Setting(key="mail.domain", value="test.ch"))
    parent = _make_mma(
        db, address="createalias@test.ch", owner_type="group", owner_id=1, kind="group"
    )
    mock_wd = MagicMock()
    mock_wd.create_forwarding_alias.return_value = {"id": "wd-001"}
    with patch(
        "hubra.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.post(
            f"/api/v1/mail/addresses/{parent.id}/aliases",
            headers=auth_headers,
            json={"prefix": "newalias"},
        )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["address"] == "newalias@test.ch"
    assert body["ownerType"] == "mail_address"
    assert body["ownerId"] == parent.id


def test_create_alias_for_member(client, db, seeded_db, auth_headers):
    db.session.add(Setting(key="mail.domain", value="test.ch"))
    m = _make_member(db, "Carol White", "carol@test.ch")
    parent = _make_mma(
        db, address="carol@test.ch", owner_type="member", owner_id=m.id, kind="member"
    )
    mock_wd = MagicMock()
    mock_wd.create_forwarding_alias.return_value = {"id": "wd-002"}
    with patch(
        "hubra.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.post(
            f"/api/v1/mail/addresses/{parent.id}/aliases",
            headers=auth_headers,
            json={"prefix": "carol-alt"},
        )
    assert resp.status_code == 201
    assert resp.get_json()["address"] == "carol-alt@test.ch"


# ── DELETE /addresses/<id>/aliases/<alias_id> ─────────────────────────────────


def test_delete_alias(client, db, seeded_db, auth_headers):
    parent = _make_mma(db, address="delparent@test.ch")
    alias = _make_mma(
        db,
        address="delalias@test.ch",
        owner_type="mail_address",
        owner_id=parent.id,
        kind="alias",
        wildduck_id="wd-del",
    )
    mock_wd = MagicMock()
    with patch(
        "hubra.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.delete(
            f"/api/v1/mail/addresses/{parent.id}/aliases/{alias.id}",
            headers=auth_headers,
        )
    assert resp.status_code == 204
    assert db.session.get(ManagedMailAddress, alias.id) is None


# ── GET /addresses/selectable ─────────────────────────────────────────────────


def test_list_selectable(client, db, seeded_db, auth_headers):
    m = _make_member(db, "Dave Black", "dave@test.ch")
    _make_mma(
        db,
        address="dave@test.ch",
        owner_type="member",
        owner_id=m.id,
        kind="member",
        is_enabled=True,
    )
    _make_mma(
        db,
        address="disabled-sel@test.ch",
        owner_type="group",
        owner_id=1,
        is_enabled=False,
    )
    resp = client.get("/api/v1/mail/addresses/selectable", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    addresses = [d["address"] for d in data]
    assert "dave@test.ch" in addresses
    assert "disabled-sel@test.ch" not in addresses


# ── DELETE /addresses/<id> ────────────────────────────────────────────────────


def test_delete_address_blocked_while_owner_exists(client, db, seeded_db, auth_headers):
    g = Group(name="DeleteBlockGroup")
    db.session.add(g)
    db.session.commit()
    addr = _make_mma(
        db, address="block@test.ch", owner_type="group", owner_id=g.id, kind="group"
    )
    resp = client.delete(f"/api/v1/mail/addresses/{addr.id}", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.get_json().get("error") == "MMA_LOCKED_TO_OWNER"


def test_delete_alias_address_allowed(client, db, seeded_db, auth_headers):
    parent = _make_mma(db, address="aliasparent@test.ch")
    alias = _make_mma(
        db,
        address="aliasdel@test.ch",
        owner_type="mail_address",
        owner_id=parent.id,
        kind="alias",
        wildduck_id="wd-del-2",
    )
    mock_wd = MagicMock()
    with patch(
        "hubra.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.delete(f"/api/v1/mail/addresses/{alias.id}", headers=auth_headers)
    assert resp.status_code == 204
    assert db.session.get(ManagedMailAddress, alias.id) is None


# ── System address aliases ────────────────────────────────────────────────────


def test_list_system_aliases(client, db, seeded_db, auth_headers):
    parent = _make_mma(db, address="sysparent@test.ch", is_system=True)
    _make_mma(
        db,
        address="sysalias@test.ch",
        owner_type="mail_address",
        owner_id=parent.id,
        kind="alias",
        fixed_forward_targets=json.dumps(["sysparent@test.ch"]),
    )
    resp = client.get(
        f"/api/v1/mail/system-addresses/{parent.id}/aliases",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["address"] == "sysalias@test.ch"


def test_create_system_alias(client, db, seeded_db, auth_headers):
    db.session.add(Setting(key="mail.domain", value="test.ch"))
    parent = _make_mma(db, address="syscreate@test.ch", is_system=True)
    mock_wd = MagicMock()
    mock_wd.create_forwarding_alias.return_value = {"id": "wd-sys-001"}
    with patch(
        "hubra.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.post(
            f"/api/v1/mail/system-addresses/{parent.id}/aliases",
            headers=auth_headers,
            json={"prefix": "sys-alt"},
        )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["address"] == "sys-alt@test.ch"
    assert body["ownerType"] == "mail_address"
    assert body["ownerId"] == parent.id


def test_create_system_alias_non_system_404(client, db, seeded_db, auth_headers):
    parent = _make_mma(db, address="nonsys@test.ch", is_system=False)
    resp = client.post(
        f"/api/v1/mail/system-addresses/{parent.id}/aliases",
        headers=auth_headers,
        json={"prefix": "test"},
    )
    assert resp.status_code == 404


def test_delete_system_alias(client, db, seeded_db, auth_headers):
    parent = _make_mma(db, address="sysdelparent@test.ch", is_system=True)
    alias = _make_mma(
        db,
        address="sysdelalias@test.ch",
        owner_type="mail_address",
        owner_id=parent.id,
        kind="alias",
        wildduck_id="wd-sys-del",
    )
    mock_wd = MagicMock()
    with patch(
        "hubra.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.delete(
            f"/api/v1/mail/system-addresses/{parent.id}/aliases/{alias.id}",
            headers=auth_headers,
        )
    assert resp.status_code == 204
    assert db.session.get(ManagedMailAddress, alias.id) is None


def test_toggle_system_alias(client, db, seeded_db, auth_headers):
    parent = _make_mma(db, address="systoggle@test.ch", is_system=True)
    alias = _make_mma(
        db,
        address="systogglealt@test.ch",
        owner_type="mail_address",
        owner_id=parent.id,
        kind="alias",
        is_enabled=True,
        fixed_forward_targets=json.dumps(["systoggle@test.ch"]),
    )
    resp = client.patch(
        f"/api/v1/mail/system-addresses/{parent.id}/aliases/{alias.id}/toggle",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert resp.status_code == 200
    assert resp.get_json()["isEnabled"] is False
