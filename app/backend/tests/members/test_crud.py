"""Tests for the members blueprint (/api/v1/members)."""

from tests.helpers import add_member

from datetime import date


def _create_member(client, auth_headers, **overrides):
    """Helper: a member with sensible defaults (they accepted an invite)."""
    payload = {
        "first_name": "Test",
        "last_name": "Member",
        "email": "member@test.ch",
    }
    payload.update(overrides)
    return add_member(client, auth_headers, **payload)


# ── List ──────────────────────────────────────────────────────────────────────


def test_list_members(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/members/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "data" in body
    assert isinstance(body["data"], list)


# ── Create ────────────────────────────────────────────────────────────────────


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
        json={"notes": "Key holder", "tool_hours": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["notes"] == "Key holder"

    # The name is the person's own account: the club only reads it.
    resp = client.patch(
        f"/api/v1/members/{member_id}",
        json={"first_name": "Updated", "last_name": "Name", "tool_hours": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "ACCOUNT_FIELDS_READ_ONLY"


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
    resp = client.post(
        "/api/v1/members/",
        json={"email": "toolhours@test.ch", "tool_hours": -1},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_permanent_delete_of_a_poll_author_group_lead_and_voter(
    client, auth_headers, seeded_db, db
):
    """Every other row that points at the member is cleared or removed, so
    the delete does not trip a foreign key on Postgres."""
    from hubra.core.models.code import Code
    from hubra.core.models.group import Group
    from hubra.core.models.member import Member
    from hubra.core.models.poll import Poll, PollOption, PollVote
    from hubra.core.models.translation import Translation

    member_id = _create_member(
        client, auth_headers, email="leaving@test.ch"
    ).get_json()["id"]

    poll = Poll(question="Picnic?", created_by_id=member_id)
    poll.options = [PollOption(label="Yes")]
    group = Group(name="Gardeners", lead_id=member_id)
    code = Code(
        name="Door", code="1234", created_by_id=member_id, updated_by_id=member_id
    )
    translation = Translation(
        locale="de-CH", key="t.k", value="v", updated_by_id=member_id
    )
    db.session.add_all([poll, group, code, translation])
    db.session.flush()
    db.session.add(
        PollVote(poll_id=poll.id, option_id=poll.options[0].id, member_id=member_id)
    )
    db.session.commit()
    ids = (poll.id, group.id, code.id, translation.id)

    client.post(f"/api/v1/members/{member_id}/archive", headers=auth_headers)
    resp = client.delete(f"/api/v1/members/{member_id}", headers=auth_headers)
    assert resp.status_code == 204

    db.session.expunge_all()
    assert db.session.get(Member, member_id) is None
    assert db.session.get(Poll, ids[0]).created_by_id is None
    assert db.session.get(Group, ids[1]).lead_id is None
    code = db.session.get(Code, ids[2])
    assert (code.created_by_id, code.updated_by_id) == (None, None)
    assert db.session.get(Translation, ids[3]).updated_by_id is None
    # The vote stays, anonymous, so the poll's result does not change.
    assert db.session.query(PollVote).filter_by(member_id=member_id).count() == 0
    [vote] = db.session.query(PollVote).filter_by(poll_id=ids[0]).all()
    assert vote.member_id is None


def test_permanent_delete_removes_sign_in_devices(client, auth_headers, seeded_db, db):
    """Entering the club app records a Device and Session in the club.

    In public these rows cascade, but club schemas get the FKs without
    ON DELETE CASCADE (schema_manager), so the service has to remove them
    itself; there the delete failed for anyone who had opened the app.
    """
    from hubra.api.members.services import MemberService
    from hubra.core.models.device_session import Device, Session

    member_id = _create_member(client, auth_headers, email="devices@test.ch").get_json()["id"]
    device = Device(member_id=member_id, fingerprint="fp1")
    db.session.add(device)
    db.session.flush()
    db.session.add(Session(device_id=device.id, jti="jti-perm-1"))
    db.session.commit()
    assert client.post(f"/api/v1/members/{member_id}/archive", headers=auth_headers).status_code == 204

    MemberService.delete_permanent(member_id, seeded_db["admin"].id)

    assert db.session.query(Device).filter_by(member_id=member_id).count() == 0
    assert db.session.query(Session).filter_by(jti="jti-perm-1").count() == 0
    db.session.rollback()


def test_permanent_delete_does_what_the_foreign_keys_declare(
    client, auth_headers, seeded_db, db
):
    """Club schemas have no foreign keys (LIKE ... INCLUDING ALL copies
    none), so the service itself cascades and nulls what the models declare;
    checked here before the member row goes, where public's FKs would hide it.
    """
    from datetime import date

    from sqlalchemy import insert, select

    from hubra.api.members.services import MemberService
    from hubra.core.models.event import ClubEvent, EventRegistration
    from hubra.core.models.group import Group
    from hubra.core.models.inventory import InventoryCheckout, InventoryItem
    from hubra.core.models.member import member_groups
    from hubra.core.models.post import Post, PostComment, PostLike

    admin_id = seeded_db["admin"].id
    member_id = _create_member(client, auth_headers, email="gone@test.ch").get_json()["id"]

    post = Post(author_id=member_id, title="Hallo", body="Text")
    event = ClubEvent(title="Fest", date=date(2030, 1, 1), type="Social", created_by=member_id)
    item = InventoryItem(name="Bohrer", category="tools", responsible_id=member_id)
    group = Group(name="Werkstatt")
    db.session.add_all([post, event, item, group])
    db.session.flush()
    db.session.add_all(
        [
            PostComment(post_id=post.id, author_id=admin_id, body="Antwort"),
            PostLike(post_id=post.id, member_id=admin_id),
            EventRegistration(event_id=event.id, member_id=member_id, status="registered"),
            InventoryCheckout(item_id=item.id, member_id=member_id),
        ]
    )
    db.session.execute(insert(member_groups).values(member_id=member_id, group_id=group.id))
    db.session.commit()
    post_id, event_id, item_id = post.id, event.id, item.id
    assert client.post(f"/api/v1/members/{member_id}/archive", headers=auth_headers).status_code == 204

    MemberService.delete_permanent(member_id, admin_id)

    # CASCADE: the member's post goes, with the comments and likes on it.
    assert db.session.get(Post, post_id) is None
    assert db.session.query(PostComment).filter_by(post_id=post_id).count() == 0
    assert db.session.query(PostLike).filter_by(post_id=post_id).count() == 0
    assert db.session.query(EventRegistration).filter_by(member_id=member_id).count() == 0
    assert db.session.query(InventoryCheckout).filter_by(member_id=member_id).count() == 0
    assert not db.session.execute(
        select(member_groups).where(member_groups.c.member_id == member_id)
    ).all()
    # SET NULL: the event and the item stay, unattributed.
    db.session.expire_all()
    assert db.session.get(ClubEvent, event_id).created_by is None
    assert db.session.get(InventoryItem, item_id).responsible_id is None
    db.session.rollback()
