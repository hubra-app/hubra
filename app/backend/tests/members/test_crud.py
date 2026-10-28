"""Tests for the members blueprint (/api/v1/members)."""

from datetime import date


def _create_member(client, auth_headers, **overrides):
    """Helper: POST a member with sensible defaults."""
    payload = {
        "first_name": "Test",
        "last_name": "Member",
        "email": "member@test.ch",
    }
    payload.update(overrides)
    return client.post("/api/v1/members/", json=payload, headers=auth_headers)


# ── List ──────────────────────────────────────────────────────────────────────


def test_list_members(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/members/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "data" in body
    assert isinstance(body["data"], list)


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_member(client, auth_headers, seeded_db):
    resp = _create_member(
        client, auth_headers, email="newmember@test.ch", tier_id=seeded_db["tier"].id
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["email"] == "newmember@test.ch"
    assert "id" in body


def test_create_member_duplicate_email(client, auth_headers, seeded_db):
    _create_member(client, auth_headers, email="dup@test.ch")
    resp = _create_member(client, auth_headers, email="dup@test.ch")
    assert resp.status_code == 409


# ── Get single ───────────────────────────────────────────────────────────────


def test_get_member(client, auth_headers, seeded_db):
    created = _create_member(client, auth_headers, email="getme@test.ch")
    member_id = created.get_json()["id"]

    resp = client.get(f"/api/v1/members/{member_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == member_id


def test_get_member_nonexistent(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/members/999999", headers=auth_headers)
    assert resp.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────


def test_update_member(client, auth_headers, seeded_db):
    created = _create_member(client, auth_headers, email="updateme@test.ch")
    member_id = created.get_json()["id"]

    # MemberUpdateSchema has tool_hours load_default=None, so we must include it
    # explicitly to avoid the route setting tool_hours=None on the NOT NULL column.
    resp = client.patch(
        f"/api/v1/members/{member_id}",
        json={"first_name": "Updated", "last_name": "Name", "tool_hours": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Updated Name"


# ── Soft delete ───────────────────────────────────────────────────────────────


def test_soft_delete_member(client, auth_headers, seeded_db):
    created = _create_member(client, auth_headers, email="deleteme@test.ch")
    member_id = created.get_json()["id"]

    archive_resp = client.post(
        f"/api/v1/members/{member_id}/archive", headers=auth_headers
    )
    assert archive_resp.status_code == 204

    # Archived member is no longer accessible via GET (active list)
    get_resp = client.get(f"/api/v1/members/{member_id}", headers=auth_headers)
    assert get_resp.status_code == 404


# ── Permanent delete ──────────────────────────────────────────────────────────


def test_permanent_delete_cleans_up_fk_dependants(client, auth_headers, seeded_db, db):
    """Permanently deleting an archived member must not raise an FK violation.

    Notifications/mailbox folders (NOT NULL FK) are deleted; invoices,
    transactions, audit entries (nullable FK) are nulled out so
    financial/audit records survive per Swiss OR Art. 957.
    """
    from hubra.core.models.audit import AuditEntry
    from hubra.core.models.finance import Invoice
    from hubra.core.models.mail import MailboxFolder
    from hubra.core.models.member import Member
    from hubra.core.models.notification import Notification

    created = _create_member(client, auth_headers, email="permadelete@test.ch")
    member_id = created.get_json()["id"]

    invoice = Invoice(
        member_id=member_id,
        issued=date(2026, 1, 1),
        due=date(2026, 1, 31),
        amount="100.00",
        status="Open",
    )
    notification = Notification(
        member_id=member_id, kind="info", title="Hi", msg="Hello"
    )
    mailbox_folder = MailboxFolder(
        member_id=member_id, wildduck_mailbox_id="wd-1", path="INBOX"
    )
    audit_entry = AuditEntry(
        actor_id=member_id,
        actor_name="Permadelete Test",
        action="login",
        target_type="Member",
        target_id=member_id,
        target_label="Permadelete Test",
    )
    db.session.add_all([invoice, notification, mailbox_folder, audit_entry])
    db.session.commit()

    invoice_id = invoice.id
    notification_id = notification.id
    mailbox_folder_id = mailbox_folder.id
    audit_entry_id = audit_entry.id

    archive_resp = client.post(
        f"/api/v1/members/{member_id}/archive", headers=auth_headers
    )
    assert archive_resp.status_code == 204

    delete_resp = client.delete(f"/api/v1/members/{member_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    # Route committed bulk deletes/updates; expunge identity map so fresh queries work.
    db.session.expunge_all()

    assert db.session.get(Member, member_id) is None
    assert db.session.get(Notification, notification_id) is None
    assert db.session.get(MailboxFolder, mailbox_folder_id) is None

    inv = db.session.get(Invoice, invoice_id)
    assert inv is not None and inv.member_id is None
    ae = db.session.get(AuditEntry, audit_entry_id)
    assert ae is not None and ae.actor_id is None
    assert ae.actor_name == "Permadelete Test"
    # ── Filter by status ──────────────────────────────────────────────────────────


def test_filter_members_by_status(client, auth_headers, seeded_db):
    # Create a member with status=trial (default)
    _create_member(client, auth_headers, email="trial@test.ch")

    resp = client.get("/api/v1/members/?status=trial", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert all(m["status"] == "trial" for m in data)


# ── Validation ────────────────────────────────────────────────────────────────


def test_create_member_negative_tool_hours(client, auth_headers, seeded_db):
    resp = _create_member(
        client, auth_headers, email="toolhours@test.ch", tool_hours=-1
    )
    assert resp.status_code == 400
