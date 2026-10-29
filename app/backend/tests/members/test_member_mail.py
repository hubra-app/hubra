"""Integration tests for member mail endpoints and provision_member_mail task.

Covers the user-targets provisioning approach (update_user with targets/disabledScopes)
and /members endpoint consolidation (PATCH /members/<id> for mail flags,
POST /members/<id>/provision for provisioning trigger).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from hubra.core.models.member import Member
from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_member(db, seeded_db, *, email: str, **overrides) -> Member:
    role = seeded_db["role"]
    user = User(email=email, first_name="Mail", last_name="Test")
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


def _make_member_mma(
    db,
    member,
    *,
    wildduck_user_id=None,
    wildduck_filter_id=None,
    forwarding_enabled=False,
    forward_enabled=None,
    enabled=True,
):
    """Create a ManagedMailAddress for a member (hub-pattern style)."""
    fwd = forward_enabled if forward_enabled is not None else forwarding_enabled
    addr = ManagedMailAddress(
        address=f"{member.email.split('@')[0]}@club.ch",
        address_type="mailbox",
        is_protected=False,
        wildduck_user_id=wildduck_user_id,
        wildduck_filter_id=wildduck_filter_id,
        forwarding_enabled=fwd,
        forward_enabled=fwd,
        kind="member",
        enabled=enabled,
        is_enabled=enabled,
        local_part=member.email.split("@")[0],
        domain="club.ch",
        owner_type="member",
        owner_id=member.id,
    )
    db.session.add(addr)
    db.session.commit()
    return addr


# ── PATCH /members/<id> — mail flags ─────────────────────────────────────────


def test_patch_member_mail_flags(client, db, seeded_db, auth_headers):
    """PATCH /members/<id> persists forwarding_enabled on MMA and dispatches provisioning task."""
    member = _make_member(db, seeded_db, email="flags@example.com")
    _make_member_mma(db, member, forwarding_enabled=False)

    with patch("hubra.core.tasks.wildduck.provision_member_mail") as mock_task:
        mock_task.delay.return_value = None
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={
                "forwarding_enabled": True,
                "retention_days": 14,
            },
            headers=auth_headers,
        )

    assert resp.status_code == 200
    from sqlalchemy import select as _sel

    addr = db.session.scalar(
        _sel(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member.id,
        )
    )
    db.session.expire(addr)
    addr = db.session.scalar(
        _sel(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member.id,
        )
    )
    assert addr.forwarding_enabled is True
    assert addr.forward_enabled is True
    assert member.retention_days == 14
    mock_task.delay.assert_called_once_with(member.id)


def test_patch_member_loop_detection(client, db, seeded_db, app):
    """PATCH /members/<id> with forwarding_enabled=True where private email is on club domain → 409 LOOP_DETECTED."""
    member = _make_member(db, seeded_db, email="alice@club.org")

    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    headers = {}

    with patch.dict(app.config, {"MAIL_DOMAIN": "club.org"}):
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"forwarding_enabled": True},
            headers=headers,
        )

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["error"] == "LOOP_DETECTED"


def test_patch_member_not_found(client, db, seeded_db, auth_headers):
    """PATCH /members/<id> for non-existent member returns 404 NOT_FOUND."""
    resp = client.patch(
        "/api/v1/members/99999",
        json={"forwarding_enabled": True},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "NOT_FOUND"


# ── POST /members/<id>/provision ─────────────────────────────────────────────


def test_provision_endpoint_via_members(client, db, seeded_db, auth_headers):
    """POST /members/<id>/provision returns 202, writes audit entry, dispatches task."""
    from sqlalchemy import select

    from hubra.core.models.audit import AuditEntry

    member = _make_member(db, seeded_db, email="provision@example.com")

    with patch("hubra.core.tasks.wildduck.provision_member_mail") as mock_task:
        mock_task.delay.return_value = None
        resp = client.post(
            f"/api/v1/members/{member.id}/provision",
            headers=auth_headers,
        )

    assert resp.status_code == 202
    body = resp.get_json()
    assert body["ok"] is True
    assert body["memberId"] == member.id

    entry = db.session.scalar(
        select(AuditEntry)
        .where(AuditEntry.action == "provision_member_mail")
        .where(AuditEntry.target_id == member.id)
    )
    assert entry is not None
    mock_task.delay.assert_called_once_with(member.id)


# ── Celery task: provision_member_mail ────────────────────────────────────────


def test_provision_mail_creates_user_with_targets(app, db, seeded_db):
    """provision_member_mail creates mailbox and sets targets array for forwarding."""
    from hubra.core.tasks.wildduck import provision_member_mail

    member = _make_member(db, seeded_db, email="forward@gmail.com")
    member.public_email = "alice@club.org"
    db.session.commit()
    addr = _make_member_mma(db, member, forwarding_enabled=True)
    addr.wildduck_user_id = None
    db.session.commit()

    mock_wd = MagicMock()
    mock_wd.create_user.return_value = {"id": "wd-created-abc"}
    mock_wd.safe_get_user.return_value = None
    mock_wd.list_user_addresses.return_value = {"results": []}

    with patch.dict(app.config, {"MAIL_DOMAIN": "club.org"}):
        with patch(
            "hubra.core.services.mail_provisioning.try_get_client",
            return_value=mock_wd,
        ):
            with patch(
                "hubra.core.services.wildduck.try_get_client", return_value=mock_wd
            ):
                with patch(
                    "hubra.core.services.mail_provisioning._get_club_domain",
                    return_value="club.org",
                ):
                    provision_member_mail.run(member.id)

    mock_wd.create_user.assert_called_once()
    mock_wd.update_user_attributes.assert_any_call(
        "wd-created-abc", targets=["forward@gmail.com"]
    )
    mock_wd.create_forward_filter.assert_not_called()

    db.session.expire(addr)
    assert addr.wildduck_id == "wd-created-abc"


def test_remove_for_member_ensure_absent(app, db, seeded_db):
    """remove_for_member uses ensure_absent to delete WildDuck user and MMA."""
    from hubra.core.services.managed_mail import remove_for_member

    member = _make_member(db, seeded_db, email="disabled@gmail.com")
    addr = _make_member_mma(
        db, member, wildduck_user_id="wd-disable-test", wildduck_filter_id="filter-old"
    )

    mock_wd = MagicMock()
    mock_wd.safe_delete_user.return_value = True

    with patch(
        "hubra.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        remove_for_member(member.id)

    mock_wd.safe_delete_user.assert_called_once_with("wd-disable-test")
    db.session.expire(addr)
    from sqlalchemy import select as _sel

    gone = db.session.scalar(
        _sel(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member.id,
        )
    )
    assert gone is None


def test_provision_forwarding_loop_guard(app, db, seeded_db):
    """provision_member_mail skips forwarding when private email domain matches club domain."""
    from hubra.core.tasks.wildduck import provision_member_mail

    member = _make_member(db, seeded_db, email="member@club.org")
    _make_member_mma(
        db, member, wildduck_user_id="wd-loop-guard", forwarding_enabled=True
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = {"id": "wd-loop-guard"}
    mock_wd.list_user_addresses.return_value = {"results": []}

    with patch.dict(app.config, {"MAIL_DOMAIN": "club.org"}):
        with patch(
            "hubra.core.services.mail_provisioning.try_get_client",
            return_value=mock_wd,
        ):
            with patch(
                "hubra.core.services.wildduck.try_get_client", return_value=mock_wd
            ):
                with patch(
                    "hubra.core.services.mail_provisioning._get_club_domain",
                    return_value="club.org",
                ):
                    provision_member_mail.run(member.id)

    # Loop detected → no targets set (forwarding skipped)
    mock_wd.create_forward_filter.assert_not_called()
    mock_wd.update_user_attributes.assert_any_call("wd-loop-guard", targets=[])


def test_provision_no_forwarding_when_disabled(app, db, seeded_db):
    """provision_member_mail clears targets when forwarding_enabled=False."""
    from hubra.core.tasks.wildduck import provision_member_mail

    member = _make_member(db, seeded_db, email="clearfwd@gmail.com")
    _make_member_mma(
        db,
        member,
        wildduck_user_id="wd-clear-targets",
        forwarding_enabled=False,
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = {"id": "wd-clear-targets"}
    mock_wd.list_user_addresses.return_value = {"results": []}

    with patch(
        "hubra.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
            with patch(
                "hubra.core.services.mail_provisioning._get_club_domain",
                return_value="club.ch",
            ):
                provision_member_mail.run(member.id)

    mock_wd.create_forward_filter.assert_not_called()
    mock_wd.update_user_attributes.assert_any_call("wd-clear-targets", targets=[])


def test_no_separate_forwarding_alias_created(app, db, seeded_db):
    """provision_member_mail uses targets array, not create_forwarding_alias."""
    from hubra.core.tasks.wildduck import provision_member_mail

    member = _make_member(db, seeded_db, email="noalias@gmail.com")
    member.public_email = "noalias@club.org"
    db.session.commit()
    _make_member_mma(
        db, member, wildduck_user_id="wd-no-alias", forwarding_enabled=True
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = {"id": "wd-no-alias"}
    mock_wd.list_user_addresses.return_value = {"results": []}

    with patch(
        "hubra.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
            with patch(
                "hubra.core.services.mail_provisioning._get_club_domain",
                return_value="other.org",
            ):
                provision_member_mail.run(member.id)

    mock_wd.create_forwarding_alias.assert_not_called()
    mock_wd.create_forward_filter.assert_not_called()
    mock_wd.update_user_attributes.assert_any_call(
        "wd-no-alias", targets=["noalias@gmail.com"]
    )


# ── PATCH /members/<id> — managed mail sync dispatch for group changes ────────


def test_patch_member_group_add_dispatches_managed_mail_sync(
    client, db, seeded_db, auth_headers
):
    """PATCH /members/<id> with new group_ids dispatches reconcile_entity_forwarding for group MMA."""
    from hubra.core.models.group import Group
    from hubra.core.models.managed_mail import ManagedMailAddress

    group = Group(name="MMASyncGroup")
    db.session.add(group)
    db.session.commit()
    addr = ManagedMailAddress(
        address="mma-sync@club.ch",
        address_type="alias",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
    )
    db.session.add(addr)
    db.session.commit()

    member = _make_member(db, seeded_db, email="mma_sync@example.com")

    with patch(
        "hubra.core.tasks.mail_tasks.reconcile_entity_forwarding_task"
    ) as mock_task:
        mock_task.delay = MagicMock()
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"group_ids": [group.id]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    mock_task.delay.assert_called_once_with("group", group.id)


def test_patch_member_no_sync_dispatch_for_group_without_mma(
    client, db, seeded_db, auth_headers
):
    """PATCH /members/<id> does NOT dispatch reconcile_entity_forwarding when group has no MMA."""
    from hubra.core.models.group import Group

    group = Group(name="NoMMASyncGroup")
    db.session.add(group)
    db.session.commit()

    member = _make_member(db, seeded_db, email="no_mma_sync@example.com")

    with patch(
        "hubra.core.tasks.mail_tasks.reconcile_entity_forwarding_task"
    ) as mock_task:
        mock_task.delay = MagicMock()
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"group_ids": [group.id]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    mock_task.delay.assert_not_called()


# ── GET /members/me/mail — mailbox status (from S04 mail wiring) ──────────────


from hubra.core.services.wildduck import WildDuckError  # noqa: E402


def _create_member_with_wildduck(db, **overrides):
    """Helper: Create a member with a WildDuck mailbox via MMA."""
    from hubra.core.models.managed_mail import ManagedMailAddress

    data = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@test.ch",
        "status": "active",
    }
    data.update(overrides)
    user = User(
        email=data["email"],
        first_name=data["first_name"],
        last_name=data["last_name"],
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    member = Member(user_id=user.id, status=data["status"])
    db.session.add(member)
    db.session.commit()
    addr = ManagedMailAddress(
        address="john@club.ch",
        address_type="mailbox",
        is_protected=False,
        owner_type="member",
        owner_id=member.id,
        wildduck_user_id="test_user_123",
    )
    db.session.add(addr)
    db.session.commit()
    return member


def test_get_member_mail_not_provisioned(client, auth_headers, seeded_db):
    """Test /members/me/mail when member has no WildDuck mailbox."""
    resp = client.get("/api/v1/members/me/mail", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "not_provisioned"
    assert body["mailbox"] is None
    assert body["aliases"] == []


def test_get_member_mail_provisioned(client, db, seeded_db):
    """Test /members/me/mail when member has a provisioned mailbox."""
    _create_member_with_wildduck(db, email="mail@test.ch")

    client.post(
        "/api/v1/auth/login",
        json={"email": "mail@test.ch", "password": "password123"},
    )
    headers = {}

    with patch("hubra.api.members.services.try_get_client") as mock_try_get:
        mock_wd = MagicMock()
        mock_try_get.return_value = mock_wd

        mock_wd.list_mailboxes.return_value = {"results": []}
        mock_wd.get_user.return_value = {
            "id": "test_user_123",
            "address": "john@club.ch",
            "name": "John Doe",
            "quota": {
                "used": 536870912,
                "allowed": 1073741824,
            },
            "storageUsed": 0,
        }
        mock_wd.list_user_addresses.return_value = {
            "results": [
                {"id": "addr_001", "address": "john@club.ch", "main": True},
                {"id": "addr_002", "address": "jd@club.ch", "main": False},
            ]
        }

        resp = client.get("/api/v1/members/me/mail", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "provisioned"
        assert body["mailbox"] is not None
        assert body["mailbox"]["address"] == "john@club.ch"
        assert body["mailbox"]["displayName"] == "John Doe"
        assert body["mailbox"]["quotaUsed"] == 0.5
        assert body["mailbox"]["quotaTotal"] == 1.0
        assert len(body["aliases"]) == 2
        assert body["aliases"][0]["address"] == "john@club.ch"
        assert body["aliases"][0]["main"] is True


def test_get_member_mail_service_unavailable(client, db, seeded_db):
    """Test /members/me/mail when WildDuck service is unavailable."""
    _create_member_with_wildduck(db, email="mail2@test.ch")

    client.post(
        "/api/v1/auth/login",
        json={"email": "mail2@test.ch", "password": "password123"},
    )
    headers = {}

    with patch("hubra.api.members.services.try_get_client") as mock_try_get:
        mock_wd = MagicMock()
        mock_try_get.return_value = mock_wd

        mock_wd.get_user.side_effect = WildDuckError(503, "Service Unavailable")

        resp = client.get("/api/v1/members/me/mail", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "service_unavailable"
        assert body["mailbox"] is None
        assert body["aliases"] == []


def test_get_member_mail_no_client_configured(client, db, seeded_db):
    """Test /members/me/mail when WildDuck client is not configured."""
    _create_member_with_wildduck(db, email="mail3@test.ch")

    client.post(
        "/api/v1/auth/login",
        json={"email": "mail3@test.ch", "password": "password123"},
    )
    headers = {}

    with patch("hubra.api.members.services.try_get_client") as mock_try_get:
        mock_try_get.return_value = None

        resp = client.get("/api/v1/members/me/mail", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "service_unavailable"
        assert body["mailbox"] is None
        assert body["aliases"] == []


def test_get_member_mail_unauthorized(client):
    """Test /members/me/mail without authentication."""
    resp = client.get("/api/v1/members/me/mail")
    assert resp.status_code == 401


def test_get_member_mail_with_quota_conversion(client, db, seeded_db):
    """Test /members/me/mail correctly converts bytes to GB."""
    _create_member_with_wildduck(db, email="quota@test.ch")

    client.post(
        "/api/v1/auth/login",
        json={"email": "quota@test.ch", "password": "password123"},
    )
    headers = {}

    with patch("hubra.api.members.services.try_get_client") as mock_try_get:
        mock_wd = MagicMock()
        mock_try_get.return_value = mock_wd

        mock_wd.list_mailboxes.return_value = {"results": []}
        mock_wd.get_user.return_value = {
            "id": "test_user_123",
            "address": "quota@club.ch",
            "name": "Quota Test",
            "quota": {
                "used": 1610612736,
                "allowed": 5368709120,
            },
            "storageUsed": 0,
        }
        mock_wd.list_user_addresses.return_value = {"results": []}

        resp = client.get("/api/v1/members/me/mail", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["mailbox"]["quotaUsed"] == 1.5
        assert body["mailbox"]["quotaTotal"] == 5.0


def test_failed_inline_mail_sync_keeps_the_new_group_member(
    client, db, seeded_db, auth_headers
):
    """Without Celery the sync runs inline; if it fails, the member still joins."""
    from sqlalchemy import select

    from hubra.core.models.group import Group, member_groups
    from hubra.core.models.managed_mail import ManagedMailAddress

    group = Group(name="InlineSyncGroup")
    db.session.add(group)
    db.session.commit()
    db.session.add(
        ManagedMailAddress(
            address="inline-sync@club.ch",
            address_type="alias",
            is_protected=True,
            owner_type="group",
            owner_id=group.id,
        )
    )
    db.session.commit()
    member = _make_member(db, seeded_db, email="inline_sync@example.com")

    with (
        patch(
            "hubra.core.tasks.mail_tasks.reconcile_entity_forwarding_task.delay",
            side_effect=RuntimeError("no broker"),
        ),
        patch(
            "hubra.core.services.mail_provisioning.reconcile_entity_forwarding",
            side_effect=RuntimeError("mail server down"),
        ),
    ):
        resp = client.post(
            f"/api/v1/groups/{group.id}/members/{member.id}", headers=auth_headers
        )

    assert resp.status_code == 204
    db.session.expire_all()
    assert db.session.scalar(
        select(member_groups.c.member_id).where(member_groups.c.group_id == group.id)
    ) == member.id
