"""Tests for member mail provisioning endpoints and Celery tasks.

GET   /api/v1/mail/members         — list members with mail flags
PATCH /api/v1/members/<id>         — update mail flags (consolidated endpoint)
POST  /api/v1/members/<id>/provision — trigger provisioning (consolidated endpoint)
Celery task: provision_member_mail  — update_user(targets, disabledScopes)
"""

from __future__ import annotations

from unittest.mock import patch


from vollbuild.core.models.member import Member
from vollbuild.core.models.managed_mail import ManagedMailAddress
from vollbuild.core.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_member(db, seeded_db, *, email: str, **overrides) -> Member:
    role = seeded_db["role"]
    user = User(email=email, first_name="Mail", last_name="User")
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
):
    """Create a ManagedMailAddress for a member (hub-pattern style)."""
    addr = ManagedMailAddress(
        address=f"{member.email.split('@')[0]}@club.ch",
        address_type="mailbox",
        is_protected=False,
        wildduck_user_id=wildduck_user_id,
        wildduck_filter_id=wildduck_filter_id,
        forwarding_enabled=forwarding_enabled,
        forward_enabled=forwarding_enabled,
        kind="member",
        enabled=True,
        is_enabled=True,
        local_part=member.email.split("@")[0],
        domain="club.ch",
        owner_type="member",
        owner_id=member.id,
    )
    db.session.add(addr)
    db.session.commit()
    return addr


# ── GET /mail/members ─────────────────────────────────────────────────────────


def test_list_member_mail(client, db, seeded_db, auth_headers):
    """GET /mail/members returns list with mail fields for all members."""
    resp = client.get("/api/v1/mail/members", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "data" in body
    assert isinstance(body["data"], list)
    # seeded_db creates 1 admin member
    assert len(body["data"]) >= 1
    item = body["data"][0]
    for key in (
        "id",
        "name",
        "public_email",
        "mailbox_enabled",
        "forwarding_enabled",
        "retention_days",
        "wildduck_id",
    ):
        assert key in item, f"Missing key: {key}"
    assert item["mailbox_enabled"] is False
    assert item["forwarding_enabled"] is False


def test_list_member_mail_unauthorized(client):
    """GET /mail/members requires authentication."""
    resp = client.get("/api/v1/mail/members")
    assert resp.status_code == 401


# ── PATCH /members/<id> — mail flags ─────────────────────────────────────────


def test_patch_member_mail_loop_detection(client, db, seeded_db, app):
    """PATCH /members/<id> with forwarding_enabled=True where private email is on club domain → 409."""
    member = _make_member(db, seeded_db, email="looptest@club.ch")

    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    headers = {}

    with patch.dict(app.config, {"MAIL_DOMAIN": "club.ch"}):
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"forwarding_enabled": True},
            headers=headers,
        )

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["error"] == "LOOP_DETECTED"


def test_patch_member_mail_update_flags(client, db, seeded_db, auth_headers):
    """PATCH /members/<id> with retention_days updates member and dispatches provisioning."""
    member = _make_member(db, seeded_db, email="flagtest@example.com")

    with patch("vollbuild.core.tasks.wildduck.provision_member_mail") as mock_task:
        mock_task.delay.return_value = None
        resp = client.patch(
            f"/api/v1/members/{member.id}",
            json={"retention_days": 30},
            headers=auth_headers,
        )
    assert resp.status_code == 200

    # Verify persisted in DB
    db.session.expire(member)
    assert member.retention_days == 30
    mock_task.delay.assert_called_once_with(member.id)


def test_patch_member_mail_no_loop_when_domain_differs(client, db, seeded_db, app):
    """PATCH /members/<id> with forwarding_enabled=True and external domain → 200."""
    member = _make_member(db, seeded_db, email="external@gmail.com")
    _make_member_mma(db, member, forwarding_enabled=False)

    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    headers = {}

    with patch("vollbuild.core.tasks.wildduck.provision_member_mail") as mock_task:
        mock_task.delay.return_value = None
        with patch.dict(app.config, {"MAIL_DOMAIN": "club.ch"}):
            resp = client.patch(
                f"/api/v1/members/{member.id}",
                json={"forwarding_enabled": True},
                headers=headers,
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


# ── POST /members/<id>/provision ─────────────────────────────────────────────


def test_provision_member_dispatches(client, db, seeded_db, auth_headers):
    """POST /members/<id>/provision returns 202 and writes audit entry."""
    from vollbuild.core.models.audit import AuditEntry
    from sqlalchemy import select

    member = _make_member(db, seeded_db, email="provision@example.com")

    with patch("vollbuild.core.tasks.wildduck.provision_member_mail") as mock_task:
        mock_task.delay.return_value = None
        resp = client.post(
            f"/api/v1/members/{member.id}/provision",
            headers=auth_headers,
        )

    assert resp.status_code == 202
    body = resp.get_json()
    assert body["ok"] is True
    assert body["memberId"] == member.id

    # Audit entry written
    entry = db.session.scalar(
        select(AuditEntry)
        .where(AuditEntry.action == "provision_member_mail")
        .where(AuditEntry.target_id == member.id)
    )
    assert entry is not None


def test_provision_member_not_found(client, db, seeded_db, auth_headers):
    """POST /members/<id>/provision for non-existent member returns 404."""
    resp = client.post("/api/v1/members/99999/provision", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "NOT_FOUND"


# ── Celery task: provision_member_mail (refactored) ───────────────────────────


def test_provision_member_mail_uses_targets_array(app, db, seeded_db):
    """provision_member_mail calls update_user_attributes with targets when forwarding_enabled=True."""
    from unittest.mock import MagicMock, patch

    from vollbuild.core.tasks.wildduck import provision_member_mail

    member = _make_member(db, seeded_db, email="external@gmail.com")
    member.public_email = "alice@club.org"
    db.session.commit()
    addr = _make_member_mma(
        db, member, wildduck_user_id="wd-existing", forwarding_enabled=True
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = {"id": "wd-existing"}
    mock_wd.list_user_addresses.return_value = {"results": []}

    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        with patch(
            "vollbuild.core.services.wildduck.try_get_client", return_value=mock_wd
        ):
            with patch(
                "vollbuild.core.services.mail_provisioning._get_club_domain",
                return_value="club.ch",
            ):
                provision_member_mail.run(member.id)

    mock_wd.update_user_attributes.assert_any_call(
        "wd-existing", targets=["external@gmail.com"]
    )
    mock_wd.create_forward_filter.assert_not_called()
    mock_wd.create_forwarding_alias.assert_not_called()

    db.session.expire(addr)
    assert addr.wildduck_id == "wd-existing"


def test_provision_member_mail_ensure_absent_on_remove(app, db, seeded_db):
    """remove_for_member uses ensure_absent to delete the WildDuck user."""
    from unittest.mock import MagicMock, patch

    from vollbuild.core.services.managed_mail import remove_for_member

    member = _make_member(db, seeded_db, email="external@gmail.com")
    addr = _make_member_mma(
        db, member, wildduck_user_id="wd-existing", wildduck_filter_id="ff-existing"
    )

    mock_wd = MagicMock()
    mock_wd.safe_delete_user.return_value = True

    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        remove_for_member(member.id)

    mock_wd.safe_delete_user.assert_called_once_with("wd-existing")
    db.session.expire(addr)
    from sqlalchemy import select as _sel

    gone = db.session.scalar(
        _sel(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member.id,
        )
    )
    assert gone is None


def test_provision_member_mail_loop_detection_skips_forwarding(app, db, seeded_db):
    """provision_member_mail skips forwarding when private email is on club domain."""
    from unittest.mock import MagicMock, patch

    from vollbuild.core.tasks.wildduck import provision_member_mail

    member = _make_member(db, seeded_db, email="alice@club.ch")
    _make_member_mma(
        db, member, wildduck_user_id="wd-existing", forwarding_enabled=True
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = {"id": "wd-existing"}
    mock_wd.list_user_addresses.return_value = {"results": []}

    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        with patch(
            "vollbuild.core.services.wildduck.try_get_client", return_value=mock_wd
        ):
            with patch(
                "vollbuild.core.services.mail_provisioning._get_club_domain",
                return_value="club.ch",
            ):
                provision_member_mail.run(member.id)

    # targets must be [] due to loop detection even though forwarding_enabled=True
    mock_wd.update_user_attributes.assert_any_call("wd-existing", targets=[])
    mock_wd.create_forward_filter.assert_not_called()


def test_provision_member_mail_creates_mailbox_when_enabled(app, db, seeded_db):
    """provision_member_mail creates mailbox when MMA exists but no wildduck_user_id."""
    from unittest.mock import MagicMock, patch

    from vollbuild.core.tasks.wildduck import provision_member_mail

    member = _make_member(db, seeded_db, email="newmember@gmail.com")
    member.public_email = "new@club.org"
    db.session.commit()
    addr = _make_member_mma(db, member, wildduck_user_id=None, forwarding_enabled=False)

    mock_wd = MagicMock()
    mock_wd.create_user.return_value = {"id": "wd-new-123"}
    mock_wd.safe_get_user.return_value = None
    mock_wd.list_user_addresses.return_value = {"results": []}

    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        with patch(
            "vollbuild.core.services.wildduck.try_get_client", return_value=mock_wd
        ):
            with patch(
                "vollbuild.core.services.mail_provisioning._get_club_domain",
                return_value="club.org",
            ):
                provision_member_mail.run(member.id)

    mock_wd.create_user.assert_called_once()
    mock_wd.update_user_attributes.assert_any_call("wd-new-123", targets=[])
    db.session.expire(addr)
    assert addr.wildduck_id == "wd-new-123"
