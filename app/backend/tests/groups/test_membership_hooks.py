"""Integration tests for membership change hooks — managed mail sync dispatch.

Contracts verified:
  POST   /api/v1/groups/<id>/members/<member_id>  — triggers managed mail sync
  DELETE /api/v1/groups/<id>/members/<member_id>  — triggers managed mail sync
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hubra.core.models.group import Group
from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.models.member import Member
from hubra.core.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_group(db, *, name: str = "Test Group", **overrides) -> Group:
    g = Group(name=name, **overrides)
    db.session.add(g)
    db.session.commit()
    return g


def _make_member(db, seeded_db, *, email: str, **overrides) -> Member:
    role = seeded_db["role"]
    user = User(
        email=email,
        first_name="Hook",
        last_name="Tester",
    )
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


def _add_member_to_group(db, member: Member, group: Group) -> None:
    from sqlalchemy import insert
    from hubra.core.models.member import member_groups

    db.session.execute(
        insert(member_groups).values(member_id=member.id, group_id=group.id)
    )
    db.session.commit()


def _make_group_mma(db, group: Group) -> ManagedMailAddress:
    """Create a mailbox-backed MMA for a group (so the dispatch guard passes)."""
    addr = ManagedMailAddress(
        address=f"group{group.id}@club.ch",
        address_type="mailbox",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
        kind="group",
        enabled=True,
        local_part=f"group{group.id}",
        domain="club.ch",
    )
    db.session.add(addr)
    db.session.commit()
    return addr


# ── POST /groups/<id>/members — managed mail sync dispatch ────────────────────


def test_add_member_triggers_managed_mail_sync(client, db, seeded_db, auth_headers):
    """POST /groups/<id>/members/<member_id> dispatches reconcile_entity_forwarding for group."""
    group = _make_group(db, name="SyncAddGroup")
    _make_group_mma(db, group)
    member = _make_member(db, seeded_db, email="sync_add@test.ch")

    with patch(
        "hubra.core.tasks.mail_tasks.reconcile_entity_forwarding_task"
    ) as mock_task:
        mock_task.delay = MagicMock()
        resp = client.post(
            f"/api/v1/groups/{group.id}/members/{member.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 204
    mock_task.delay.assert_called_once_with("group", group.id)


def test_remove_member_triggers_managed_mail_sync(client, db, seeded_db, auth_headers):
    """DELETE /groups/<id>/members/<member_id> dispatches reconcile_entity_forwarding for group."""
    group = _make_group(db, name="SyncRemoveGroup")
    _make_group_mma(db, group)
    member = _make_member(db, seeded_db, email="sync_remove@test.ch")
    _add_member_to_group(db, member, group)

    with patch(
        "hubra.core.tasks.mail_tasks.reconcile_entity_forwarding_task"
    ) as mock_task:
        mock_task.delay = MagicMock()
        resp = client.delete(
            f"/api/v1/groups/{group.id}/members/{member.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 204
    mock_task.delay.assert_called_once_with("group", group.id)


def test_add_member_no_dispatch_when_no_mma(client, db, seeded_db, auth_headers):
    """POST /groups/<id>/members/<member_id> does not dispatch when group has no MMA."""
    group = _make_group(db, name="NoMMAGroup")
    member = _make_member(db, seeded_db, email="no_mma@test.ch")

    with patch(
        "hubra.core.tasks.mail_tasks.reconcile_entity_forwarding_task"
    ) as mock_task:
        mock_task.delay = MagicMock()
        resp = client.post(
            f"/api/v1/groups/{group.id}/members/{member.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 204
    mock_task.delay.assert_not_called()


# ── Negative tests ─────────────────────────────────────────────────────────────


def test_add_already_member_returns_conflict(client, db, seeded_db, auth_headers):
    """POST /groups/<id>/members/<member_id> twice returns 409 on the second call."""
    group = _make_group(db, name="ConflictGroup")
    member = _make_member(db, seeded_db, email="conflict_member@test.ch")

    # First add — succeeds
    resp1 = client.post(
        f"/api/v1/groups/{group.id}/members/{member.id}",
        headers=auth_headers,
    )
    assert resp1.status_code == 204

    # Second add — conflict
    resp2 = client.post(
        f"/api/v1/groups/{group.id}/members/{member.id}",
        headers=auth_headers,
    )
    assert resp2.status_code == 409


def test_remove_nonexistent_member_returns_404(client, db, seeded_db, auth_headers):
    """DELETE /groups/<id>/members/<member_id> returns 404 when member is not in the group."""
    group = _make_group(db, name="NonMemberGroup")
    member = _make_member(db, seeded_db, email="non_member@test.ch")

    resp = client.delete(
        f"/api/v1/groups/{group.id}/members/{member.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 404
