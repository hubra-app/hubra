"""Tests for audit log denormalization and action filter (M003/S05)."""

from hubra.api.utils import log_audit


# ── helpers ───────────────────────────────────────────────────────────────────


def _get_audit(client, auth_headers, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/api/v1/audit/{'?' + qs if qs else ''}"
    return client.get(url, headers=auth_headers)


def _make_member(db, seeded_db, first="Alice", last="Test", email="alice@test.ch"):
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    user = User(
        email=email,
        first_name=first,
        last_name=last,
    )
    user.set_password("pw")
    db.session.add(user)
    db.session.flush()

    m = Member(
        user_id=user.id,
        status="active",
    )
    m.roles = [seeded_db["role"]]
    m.tier_id = seeded_db["tier"].id
    db.session.add(m)
    db.session.flush()
    return m


# ── tests ─────────────────────────────────────────────────────────────────────


def test_actor_name_stored_on_create(client, db, auth_headers, seeded_db):
    """log_audit() stores actor_name; GET /audit returns it."""
    member = _make_member(db, seeded_db)
    expected_name = f"{member.first_name} {member.last_name}"

    log_audit(member.id, "create_member", "Member", member.id, expected_name)
    db.session.commit()

    resp = _get_audit(client, auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) >= 1
    entry = next(e for e in data if e["action"] == "create_member")
    assert entry["actor_name"] == expected_name
    assert entry["actor_avatar_color"] is not None


def test_actor_name_survives_member_delete(client, db, auth_headers, seeded_db):
    """actor_name is retained in audit entry even after the member row is deleted."""
    member = _make_member(db, seeded_db, first="Bob", last="Gone", email="bob@test.ch")
    member_id = member.id
    expected_name = f"{member.first_name} {member.last_name}"

    log_audit(member_id, "deactivate_member", "Member", member_id, expected_name)
    db.session.commit()

    # SQLite FK constraints are OFF by default; deleting the member leaves
    # the audit entry's actor_id as a dangling ref but actor_name is preserved.
    postgres = db.engine.dialect.name == "postgresql"
    off, on = (
        ("SET session_replication_role = replica", "SET session_replication_role = DEFAULT")
        if postgres
        else ("PRAGMA foreign_keys = OFF", "PRAGMA foreign_keys = ON")
    )
    db.session.execute(db.text(off))
    db.session.execute(db.text("DELETE FROM members WHERE id = :id"), {"id": member_id})
    db.session.execute(db.text(on))
    db.session.commit()

    resp = _get_audit(client, auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    entry = next(
        (
            e
            for e in data
            if e["action"] == "deactivate_member" and e["actor_id"] == member_id
        ),
        None,
    )
    assert entry is not None, "audit entry not found after member delete"
    assert entry["actor_name"] == expected_name


def test_action_filter(client, db, auth_headers, seeded_db):
    """GET /audit?action=X returns only entries with that action."""
    member = _make_member(
        db, seeded_db, first="Carl", last="Filter", email="carl@test.ch"
    )

    log_audit(member.id, "create_member", "Member", member.id, "Carl Filter")
    log_audit(member.id, "update_member", "Member", member.id, "Carl Filter")
    db.session.commit()

    resp = _get_audit(client, auth_headers, action="create_member")
    assert resp.status_code == 200
    body = resp.get_json()
    data = body["data"]
    assert len(data) >= 1
    assert all(e["action"] == "create_member" for e in data)

    resp2 = _get_audit(client, auth_headers, action="update_member")
    data2 = resp2.get_json()["data"]
    assert len(data2) >= 1
    assert all(e["action"] == "update_member" for e in data2)


def test_pagination(client, db, auth_headers, seeded_db):
    """GET /audit?page=1&pageSize=2 returns 2 items with correct totalPages."""
    member = _make_member(
        db, seeded_db, first="Dana", last="Page", email="dana@test.ch"
    )

    for i in range(3):
        log_audit(member.id, "paginate_test", "Member", member.id, "Dana Page")
    db.session.commit()

    resp = _get_audit(client, auth_headers, action="paginate_test", page=1, pageSize=2)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 2
    assert body["total"] == 3
    assert body["totalPages"] == 2
    assert body["page"] == 1
    assert body["pageSize"] == 2


def test_long_label_is_shortened_to_fit(db, seeded_db):
    """A label built from many addresses can outgrow the column; Postgres
    would refuse the entry and fail the change it records."""
    from hubra.core.models.audit import AuditEntry

    log_audit(seeded_db["admin"].id, "set_forwarding", "Mail", 1, "a@x.ch → " + "b" * 400)
    db.session.commit()

    entry = db.session.query(AuditEntry).filter_by(action="set_forwarding").one()
    assert len(entry.target_label) == 255 and entry.target_label.endswith("…")
