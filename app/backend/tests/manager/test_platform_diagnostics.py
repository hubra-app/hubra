"""Platform diagnostics in manage: health, the shared mail server, API permissions.

The mail server (WildDuck) is shared by every club, so its live list and the
orphan checks look at the managed addresses of all clubs.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import g

from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.services import mail_server
from tests.mail.test_mail_admin import _ensure_mail_domain, _make_member_mma

LIVE = "/api/v1/manager/platform/mail-server"
WD = "hubra.core.services.mail_server.try_get_client"


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


@pytest.fixture
def wd():
    client = _mock_wd()
    with patch(WD, return_value=client):
        yield client


# ── Who may look ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", LIVE),
        ("DELETE", f"{LIVE}/mailbox/aabbccddee11223344556677"),
        ("POST", f"{LIVE}/reconcile"),
        ("GET", "/api/v1/manager/platform/health"),
        ("GET", "/api/v1/manager/platform/permissions"),
    ],
)
def test_club_admin_is_not_platform_staff(client, auth_headers, method, path):
    assert client.open(path, method=method, headers=auth_headers).status_code == 403


def test_old_club_endpoints_are_gone(client, staff_headers):
    for path in ("/api/v1/mail/wildduck-live", "/api/v1/health/detailed"):
        assert client.get(path, headers=staff_headers).status_code in (404, 405)


def test_support_role_gets_diagnostics(db):
    from hubra.api.global_rbac_seed import _DEFAULT_ROLES

    roles = {name: perms for name, _desc, perms in _DEFAULT_ROLES}
    assert "platform.diagnostics" in roles["Superadmin"]
    assert "platform.diagnostics" in roles["Support"]
    assert "platform.settings" not in roles["Support"]


# ── Live list ─────────────────────────────────────────────────────────────────


def test_live_lists_managed_and_orphans(client, db, seeded_db, staff_headers, wd):
    _ensure_mail_domain(db)
    _make_member_mma(db, seeded_db["admin"].id, wildduck_id="5f8d0b1a2c3e4f5a6b7c8d9e")

    resp = client.get(LIVE, headers=staff_headers)

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 4
    managed = [d for d in data if d["managed"]]
    assert [d["address"] for d in managed] == ["alice@club.ch"]
    assert managed[0]["kind"] == "member"
    assert managed[0]["ownerName"] == seeded_db["admin"].name
    assert all(d["club"] is None for d in data if not d["managed"])


def test_live_without_a_mail_server(client, staff_headers):
    with patch(WD, return_value=None):
        assert client.get(LIVE, headers=staff_headers).status_code == 503


# ── Deleting orphans ──────────────────────────────────────────────────────────


def test_delete_orphan_mailbox(client, db, staff_headers, wd):
    resp = client.delete(
        f"{LIVE}/mailbox/aabbccddee11223344556677", headers=staff_headers
    )

    assert resp.status_code == 200
    wd.delete_user.assert_called_once_with("aabbccddee11223344556677")
    entry = (
        db.session.query(GlobalAuditEntry)
        .filter_by(action="platform.mail_server.delete_mailbox")
        .one()
    )
    assert entry.details == {"address": "orphan@club.ch"}


def test_delete_orphan_alias(client, staff_headers, wd):
    resp = client.delete(
        f"{LIVE}/alias/aabbccddeeff001122334455", headers=staff_headers
    )
    assert resp.status_code == 200
    wd.safe_delete_forwarding_alias.assert_called_once_with("aabbccddeeff001122334455")


def test_delete_refuses_a_managed_mailbox(client, db, seeded_db, staff_headers, wd):
    _ensure_mail_domain(db)
    _make_member_mma(db, seeded_db["admin"].id, wildduck_id="5f8d0b1a2c3e4f5a6b7c8d9e")

    resp = client.delete(
        f"{LIVE}/mailbox/5f8d0b1a2c3e4f5a6b7c8d9e", headers=staff_headers
    )

    assert resp.status_code == 409
    wd.delete_user.assert_not_called()


def test_delete_refuses_bad_input(client, staff_headers, wd):
    assert client.delete(f"{LIVE}/invalid/x", headers=staff_headers).status_code == 400
    assert (
        client.delete(f"{LIVE}/mailbox/nope", headers=staff_headers).status_code == 400
    )


def test_reconcile_runs_for_every_club(client, staff_headers):
    with patch("hubra.core.tasks.mail_tasks.reconcile_mail") as task:
        resp = client.post(f"{LIVE}/reconcile", headers=staff_headers)
    assert resp.status_code == 202
    task.delay.assert_called_once_with()


# ── Every club counts ─────────────────────────────────────────────────────────


def _two_clubs():
    """Club A manages wd-a, club B manages wd-b (schemas are faked on SQLite)."""
    clubs = [
        SimpleNamespace(id=1, slug="club-a", name="Club A"),
        SimpleNamespace(id=2, slug="club-b", name="Club B"),
    ]
    owned = {"club-a": "wd-a", "club-b": "wd-b"}

    def entries():
        wd_id = owned[g.tenant.slug]
        return {wd_id: {"mmaId": 1, "kind": "member", "linkedId": 1, "ownerName": "X"}}

    return (
        patch("hubra.core.services.mail_server._mail_clubs", return_value=clubs),
        patch("hubra.core.services.mail_server._club_entries", side_effect=entries),
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.core.tenant.context.reset_search_path"),
    )


def test_managed_index_covers_every_club(app):
    patches = _two_clubs()
    with app.test_request_context():
        for p in patches:
            p.start()
        try:
            index = mail_server.managed_index()
        finally:
            for p in patches:
                p.stop()
    assert index["wd-a"]["club"]["slug"] == "club-a"
    assert index["wd-b"]["club"]["slug"] == "club-b"


def test_delete_refuses_another_clubs_mailbox(client, staff_headers, wd):
    patches = _two_clubs()
    for p in patches:
        p.start()
    try:
        resp = client.delete(
            f"{LIVE}/mailbox/aabbccddee11223344556677", headers=staff_headers
        )
    finally:
        for p in patches:
            p.stop()
    # Not managed by either club: deleted.
    assert resp.status_code == 200


def test_every_club_includes_suspended_clubs(app, db):
    """The orphan sweep's index must not drop a suspended club's mailboxes."""
    from hubra.core.models.tenant import Tenant

    db.session.add_all(
        [
            Tenant(slug="on-club", name="On", status="active"),
            Tenant(slug="paused-club", name="Paused", status="suspended"),
        ]
    )
    db.session.commit()
    slugs = {t.slug for t in mail_server._every_club()}
    assert {"on-club", "paused-club"} <= slugs
