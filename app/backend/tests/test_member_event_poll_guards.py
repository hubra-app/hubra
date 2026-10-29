"""Guards on removed members, event attendees, inventory check-in and poll proxies."""

from datetime import datetime, timezone

from hubra.core.extensions import db as _db
from hubra.core.models.role import Permission, RolePermission
from tests.authz.conftest import _create_member_with_role, _login_member

MEMBER_PERMS = [
    "members.members.read",
    "events.events.read",
    "polls.polls.read",
    "polls.polls.vote",
]


def _mk(seeded_db, email, keys=None, **userkw):
    m, _ = _create_member_with_role(
        email, "R" + email.split("@")[0], seeded_db["tier"].id, permission_keys=keys
    )
    for k, v in userkw.items():
        setattr(m.user, k, v)
    _db.session.commit()
    return m


def _login(client, email):
    _login_member(client, email)


def _admin(client):
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )


def _event(client, **kw):
    p = {"title": "E", "date": "2099-12-01", "type": "Social"}
    p.update(kw)
    r = client.post("/api/v1/events/", json=p)
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()["id"]


def _poll(client, **kw):
    p = {
        "question": "Q?",
        "options": [{"label": "a"}, {"label": "b"}],
        "allow_proxy": True,
    }
    p.update(kw)
    r = client.post("/api/v1/polls/", json=p)
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()["id"]


def test_soft_deleted_member_loses_access(client, seeded_db, auth_headers):
    v = _mk(seeded_db, "sd@test.ch", ["members.members.read"])
    assert client.delete(f"/api/v1/members/{v.id}/soft").status_code == 204
    _login(client, "sd@test.ch")
    r = client.get("/api/v1/members/")
    assert r.status_code in (401, 403), r.status_code


def test_deleted_member_is_not_restored_from_the_archive(
    app, client, seeded_db, auth_headers
):
    v = _mk(seeded_db, "back@test.ch", MEMBER_PERMS)
    assert client.delete(f"/api/v1/members/{v.id}/soft").status_code == 204
    # Restoring from the archive is not the way back for a deleted member.
    assert client.post(f"/api/v1/members/{v.id}/unarchive").status_code == 404


def test_archived_member_not_added_as_attendee(client, seeded_db, auth_headers):
    eid = _event(client)
    m = _mk(seeded_db, "arch@test.ch")
    m.archived_at = datetime.now(timezone.utc)
    _db.session.commit()
    _admin(client)
    r = client.post(f"/api/v1/events/{eid}/attendees/{m.id}")
    assert r.status_code == 404, r.status_code


def _item(client):
    return client.post(
        "/api/v1/inventory/", json={"name": "Drill", "category": "Tool"}
    ).get_json()["id"]


def test_checkin_notes_must_be_text(client, seeded_db, auth_headers):
    iid = _item(client)
    m1 = _mk(seeded_db, "i3@test.ch")
    _admin(client)
    client.post(f"/api/v1/inventory/{iid}/checkout", json={"member_id": m1.id})
    try:
        r = client.post(
            f"/api/v1/inventory/{iid}/checkin", json={"condition_notes": {"x": 1}}
        )
        status = r.status_code
    except Exception as exc:  # test client re-raises what would be a 500
        _db.session.rollback()
        status = f"500 ({type(exc).__name__})"
    assert status == 400, status


def test_proxy_lapses_when_poll_stops_allowing_proxies(client, seeded_db, auth_headers):
    a = _mk(seeded_db, "pa@test.ch", MEMBER_PERMS)
    b = _mk(seeded_db, "pb@test.ch")
    for p in _db.session.query(Permission).all():
        _db.session.add(RolePermission(role_id=b.roles[0].id, permission_id=p.id))
    _db.session.commit()
    pid = _poll(client)
    _login(client, "pb@test.ch")
    assert (
        client.post(f"/api/v1/polls/{pid}/proxy", json={"holder_id": a.id}).status_code
        == 201
    )
    _admin(client)
    assert (
        client.patch(f"/api/v1/polls/{pid}", json={"allow_proxy": False}).status_code
        == 200
    )
    _login(client, "pa@test.ch")
    r = client.post(
        f"/api/v1/polls/{pid}/vote", json={"option_index": 0, "on_behalf_of": b.id}
    )
    assert r.status_code in (403, 409), r.status_code


def test_proxy_holder_id_true_is_a_400(client, seeded_db, auth_headers):
    pid = _poll(client)
    _mk(seeded_db, "pc@test.ch", MEMBER_PERMS)
    _login(client, "pc@test.ch")
    r = client.post(f"/api/v1/polls/{pid}/proxy", json={"holder_id": True})
    assert r.status_code == 400, (r.status_code, r.get_json())
