"""Integration tests for group mail endpoints and ManagedMailAddress provisioning.

Contracts verified:
  GET    /api/v1/mail/groups           — list managed mail addresses for groups
  POST   /api/v1/mail/groups/<id>      — create managed mail address for a group
  DELETE /api/v1/mail/groups/<id>      — remove managed mail address for a group
  GET    /api/v1/mail/aliases          — groupName populated for group-owned aliases
  DELETE /api/v1/mail/aliases/<id>     — 409 when alias is tied to a group
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy import select

from hubra.core.models.group import Group
from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.models.member import Member
from hubra.core.models.user import User
from tests.helpers import patch_mail_domain


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_group(db, *, name: str = "Test Group", **overrides) -> Group:
    g = Group(name=name, **overrides)
    db.session.add(g)
    db.session.commit()
    return g


def _make_member(db, seeded_db, *, email: str, **overrides) -> Member:
    role = seeded_db["role"]
    user = User(email=email, first_name="Group", last_name="Member")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    m = Member(
        user_id=user.id,
        status="active",
        **overrides,
    )
    m.roles = [role]
    db.session.add(m)
    db.session.commit()
    return m


# ── GET /mail/groups ──────────────────────────────────────────────────────────


def test_list_group_mail_empty(client, db, seeded_db, auth_headers):
    """GET /mail/groups returns empty list when no group MMAs exist."""
    resp = client.get("/api/v1/mail/groups", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"] == []


def test_list_group_mail_returns_addresses(client, db, seeded_db, auth_headers):
    """GET /mail/groups returns managed mail addresses linked to groups."""
    group = _make_group(db, name="ListMMAGroup")
    addr = ManagedMailAddress(
        address="listtest@club.ch",
        address_type="alias",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
    )
    db.session.add(addr)
    db.session.commit()

    resp = client.get("/api/v1/mail/groups", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["address"] == "listtest@club.ch"
    assert data[0]["linkedGroupId"] == group.id
    assert data[0]["groupName"] == "ListMMAGroup"


# ── POST /mail/groups/<group_id> ──────────────────────────────────────────────


def test_create_group_mail_success(client, db, seeded_db, auth_headers):
    """POST /mail/groups/<id> creates a managed mail address for the group."""
    group = _make_group(db, name="CreateMMAGroup")

    with patch_mail_domain("club.ch"):
        resp = client.post(
            f"/api/v1/mail/groups/{group.id}",
            json={"prefix": "vorstand"},
            headers=auth_headers,
        )

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["address"] == "vorstand@club.ch"
    assert body["linkedGroupId"] == group.id
    assert body["kind"] == "group"
    assert body["mailboxBacked"] is False

    mma = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group.id,
        )
    )
    assert mma is not None
    assert mma.address == "vorstand@club.ch"
    assert mma.kind == "group"
    assert mma.local_part == "vorstand"
    assert mma.domain == "club.ch"


def test_create_group_mail_auto_derives_prefix(client, db, seeded_db, auth_headers):
    """POST /mail/groups/<id> auto-derives prefix from group name when not provided."""
    group = _make_group(db, name="AutoPrefixGroup")

    with patch_mail_domain("club.ch"):
        resp = client.post(
            f"/api/v1/mail/groups/{group.id}",
            json={},
            headers=auth_headers,
        )

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["address"] == "autoprefixgroup@club.ch"
    assert body["linkedGroupId"] == group.id


def test_create_group_mail_group_not_found(client, db, seeded_db, auth_headers):
    """POST /mail/groups/9999 returns 404 for non-existent group."""
    with patch_mail_domain("club.ch"):
        resp = client.post(
            "/api/v1/mail/groups/9999",
            json={"prefix": "test"},
            headers=auth_headers,
        )
    assert resp.status_code == 404


def test_create_group_mail_duplicate_returns_409(client, db, seeded_db, auth_headers):
    """POST /mail/groups/<id> returns 409 when group already has a primary MMA."""
    group = _make_group(db, name="DuplicateMMAGroup")
    addr = ManagedMailAddress(
        address="existing@club.ch",
        address_type="mailbox",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
        kind="group",
    )
    db.session.add(addr)
    db.session.commit()

    with patch_mail_domain("club.ch"):
        resp = client.post(
            f"/api/v1/mail/groups/{group.id}",
            json={"prefix": "newprefix"},
            headers=auth_headers,
        )
    assert resp.status_code == 409


# ── DELETE /mail/groups/<group_id> ────────────────────────────────────────────


def test_delete_group_mail_blocked_while_group_exists(
    client, db, seeded_db, auth_headers
):
    """DELETE /mail/groups/<id> returns 409 while the group exists."""
    group = _make_group(db, name="DeleteMMAGroup")
    addr = ManagedMailAddress(
        address="deletetest@club.ch",
        address_type="alias",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
    )
    db.session.add(addr)
    db.session.commit()
    addr_id = addr.id

    resp = client.delete(
        f"/api/v1/mail/groups/{group.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.get_json().get("error") == "MMA_LOCKED_TO_OWNER"

    # Verify MMA was NOT deleted
    assert db.session.get(ManagedMailAddress, addr_id) is not None


def test_delete_group_mail_no_address_returns_409(client, db, seeded_db, auth_headers):
    """DELETE /mail/groups/<id> returns 409 when group exists (even without MMA)."""
    group = _make_group(db, name="NoMMAGroup")
    resp = client.delete(
        f"/api/v1/mail/groups/{group.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_delete_group_mail_group_not_found(client, db, seeded_db, auth_headers):
    """DELETE /mail/groups/9999 returns 404 for non-existent group."""
    resp = client.delete(
        "/api/v1/mail/groups/9999",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── GET /mail/aliases — groupName via MMA ─────────────────────────────────────


def test_list_aliases_shows_group_name(client, db, seeded_db, auth_headers):
    """GET /mail/aliases returns groupName for aliases linked to a group via MMA."""
    group = _make_group(db, name="AliasNameGroup")
    addr = ManagedMailAddress(
        address="alias-name-group@club.ch",
        address_type="alias",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
        wildduck_id="wd-g-alias-01",
    )
    db.session.add(addr)
    db.session.commit()

    mock_wd = MagicMock()
    mock_wd.list_addresses.return_value = {
        "results": [
            {
                "id": "wd-g-alias-01",
                "address": "alias-name-group@club.ch",
                "targets": ["a@b.ch"],
            },
        ]
    }

    with (
        patch("hubra.api.mail.services.try_get_client", return_value=mock_wd),
        patch_mail_domain("club.ch"),
    ):
        resp = client.get("/api/v1/mail/aliases", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["groupName"] == "AliasNameGroup"
    assert data[0]["groupId"] == group.id


# ── DELETE /mail/aliases/<id> — 409 for group-tied alias ─────────────────────


def test_delete_group_tied_alias_returns_409(client, db, seeded_db, auth_headers):
    """DELETE /mail/aliases/<id> returns 409 when the alias is managed by a group MMA."""
    alias_id = "a1b2c3d4e5f6a1b2c3d4e5f6"
    group = _make_group(db, name="BlockDeleteGroup")
    addr = ManagedMailAddress(
        address="block-delete@club.ch",
        address_type="alias",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
        wildduck_id=alias_id,
    )
    db.session.add(addr)
    db.session.commit()

    mock_wd = MagicMock()
    mock_wd.get_address.return_value = {"address": "block-delete@club.ch"}
    with (
        patch("hubra.api.mail.services.try_get_client", return_value=mock_wd),
        patch_mail_domain("club.ch"),
    ):
        resp = client.delete(f"/api/v1/mail/aliases/{alias_id}", headers=auth_headers)

    assert resp.status_code == 409
    mock_wd.delete_address.assert_not_called()


def test_delete_non_group_alias_succeeds(client, db, seeded_db, auth_headers):
    """DELETE /mail/aliases/<id> succeeds (204) when the alias is not tied to any group."""
    alias_id = "f6e5d4c3b2a1f6e5d4c3b2a1"
    mock_wd = MagicMock()
    mock_wd.get_address.return_value = {"address": "loose@club.ch"}
    with (
        patch("hubra.api.mail.services.try_get_client", return_value=mock_wd),
        patch_mail_domain("club.ch"),
    ):
        resp = client.delete(f"/api/v1/mail/aliases/{alias_id}", headers=auth_headers)

    assert resp.status_code == 204
    mock_wd.delete_forwarding_alias.assert_called_once_with(alias_id)


# ── POST /groups/ — no auto-alias creation ────────────────────────────────────


def test_post_group_no_longer_auto_creates_alias(client, db, seeded_db, auth_headers):
    """POST /groups/ creates a group without any WildDuck calls."""
    resp = client.post(
        "/api/v1/groups/",
        json={"name": "NoAutoAliasGroup"},
        headers=auth_headers,
    )

    assert resp.status_code == 201
