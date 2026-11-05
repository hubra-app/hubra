"""Events, posts and polls can belong to a group, and a role held for that
group only manages that group's content.

"Anlässe Jugend" (events, posts and polls rights, held for Jugend) lets a
member run the youth team's events, posts and polls, and nothing in
Senioren or club-wide.
"""

from datetime import date, timedelta

from hubra.core.models.event import ClubEvent
from hubra.core.models.group import Group
from hubra.core.models.poll import Poll, PollOption
from hubra.core.models.post import Post
from hubra.core.models.role import MemberRoleScope

from tests.authz.conftest import _create_member_with_role, _login_member

CONTENT_LEAD = [
    "events.events.read",
    "events.events.create",
    "events.events.update",
    "events.events.delete",
    "events.events.add_attendee",
    "posts.posts.read",
    "posts.posts.create",
    "posts.posts.update",
    "posts.posts.delete",
    "polls.polls.read",
    "polls.polls.create",
    "polls.polls.update",
    "polls.polls.delete",
    "polls.polls.close",
]


def _setup(db, seeded_db):
    tier = seeded_db["tier"]
    _, lead_role = _create_member_with_role(
        "someone@test.ch", "Anlässe Jugend", tier.id, permission_keys=CONTENT_LEAD
    )
    # A plain member: reads and writes their own posts club-wide, like the
    # Member role, and manages Jugend content only through the scoped role.
    lead, _ = _create_member_with_role(
        "lead@test.ch",
        "Mitglied",
        tier.id,
        permission_keys=[
            "events.events.read",
            "posts.posts.read",
            "posts.posts.create",
            "posts.posts.update",
            "posts.posts.delete",
            "polls.polls.read",
        ],
    )
    jugend = Group(name="Jugend")
    senioren = Group(name="Senioren")
    db.session.add_all([jugend, senioren])
    db.session.commit()
    db.session.add(MemberRoleScope(member_id=lead.id, role_id=lead_role.id, group_id=jugend.id))
    db.session.commit()
    return lead, jugend, senioren


def _event(db, group):
    event = ClubEvent(
        title=f"Training {group.name if group else 'Verein'}",
        date=date.today() + timedelta(days=7),
        type="Workshop",
        group_id=group.id if group else None,
    )
    db.session.add(event)
    db.session.commit()
    return event


def _post(db, seeded_db, group):
    post = Post(
        author_id=seeded_db["admin"].id,
        title="Info",
        body="Text",
        group_id=group.id if group else None,
    )
    db.session.add(post)
    db.session.commit()
    return post


def _poll(db, group):
    poll = Poll(question="Wann?", status="open", group_id=group.id if group else None)
    db.session.add(poll)
    db.session.flush()
    db.session.add(PollOption(poll_id=poll.id, label="Montag"))
    db.session.commit()
    return poll


def test_events_of_the_group(client, db, seeded_db):
    _, jugend, senioren = _setup(db, seeded_db)
    own = _event(db, jugend)
    other = _event(db, senioren)
    club = _event(db, None)

    _login_member(client, "lead@test.ch")
    day = (date.today() + timedelta(days=3)).isoformat()
    new = {"title": "Lager", "date": day, "type": "Workshop"}

    resp = client.post("/api/v1/events/", json={**new, "group_id": jugend.id})
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["group_id"] == jugend.id
    assert client.post("/api/v1/events/", json={**new, "group_id": senioren.id}).status_code == 403
    assert client.post("/api/v1/events/", json=new).status_code == 403

    assert client.patch(f"/api/v1/events/{own.id}", json={"title": "Neu"}).status_code == 200
    assert client.patch(f"/api/v1/events/{other.id}", json={"title": "Neu"}).status_code == 403
    assert client.patch(f"/api/v1/events/{club.id}", json={"title": "Neu"}).status_code == 403
    # It stays in a group the role is for.
    resp = client.patch(f"/api/v1/events/{own.id}", json={"group_id": senioren.id})
    assert resp.status_code == 403
    assert client.patch(f"/api/v1/events/{own.id}", json={"group_id": None}).status_code == 403

    assert client.get(f"/api/v1/events/{own.id}/registrations").status_code == 200
    assert client.get(f"/api/v1/events/{other.id}/registrations").status_code == 403

    assert client.delete(f"/api/v1/events/{other.id}").status_code == 403
    assert client.delete(f"/api/v1/events/{own.id}").status_code == 204


def test_posts_of_the_group(client, db, seeded_db):
    _, jugend, senioren = _setup(db, seeded_db)
    own = _post(db, seeded_db, jugend)
    other = _post(db, seeded_db, senioren)

    _login_member(client, "lead@test.ch")
    resp = client.post(
        "/api/v1/posts/", json={"title": "Jugend", "body": "Hallo", "group_id": jugend.id}
    )
    assert resp.status_code == 201
    assert resp.get_json()["group_id"] == jugend.id

    # Someone else's post in Jugend: the role for Jugend may edit it.
    assert client.patch(f"/api/v1/posts/{own.id}", json={"title": "Neu"}).status_code == 200
    # In Senioren only the author or a moderator may.
    assert client.patch(f"/api/v1/posts/{other.id}", json={"title": "Neu"}).status_code == 403
    resp = client.patch(f"/api/v1/posts/{own.id}", json={"group_id": senioren.id})
    assert resp.status_code == 403

    assert client.delete(f"/api/v1/posts/{other.id}").status_code == 403
    assert client.delete(f"/api/v1/posts/{own.id}").status_code == 204


def test_polls_of_the_group(client, db, seeded_db):
    _, jugend, senioren = _setup(db, seeded_db)
    own = _poll(db, jugend)
    other = _poll(db, senioren)

    _login_member(client, "lead@test.ch")
    new = {"question": "Ausflug?", "options": [{"label": "Ja"}, {"label": "Nein"}]}
    resp = client.post("/api/v1/polls/", json={**new, "group_id": jugend.id})
    assert resp.status_code == 201
    assert resp.get_json()["group_id"] == jugend.id
    assert client.post("/api/v1/polls/", json=new).status_code == 403

    assert client.patch(f"/api/v1/polls/{own.id}", json={"question": "Neu?"}).status_code == 200
    assert client.patch(f"/api/v1/polls/{other.id}", json={"question": "Neu?"}).status_code == 403
    resp = client.patch(f"/api/v1/polls/{own.id}", json={"group_id": senioren.id})
    assert resp.status_code == 403

    assert client.patch(f"/api/v1/polls/{other.id}/close").status_code == 403
    assert client.patch(f"/api/v1/polls/{own.id}/close").status_code == 200
    assert client.delete(f"/api/v1/polls/{other.id}").status_code == 403
    assert client.delete(f"/api/v1/polls/{own.id}").status_code == 204


def test_admin_sets_and_clears_the_group(client, db, seeded_db):
    _, jugend, _ = _setup(db, seeded_db)
    post = _post(db, seeded_db, None)
    _login_member(client, "admin@test.ch")
    resp = client.patch(f"/api/v1/posts/{post.id}", json={"group_id": jugend.id})
    assert resp.status_code == 200
    assert resp.get_json()["group_id"] == jugend.id
    resp = client.patch(f"/api/v1/posts/{post.id}", json={"group_id": None})
    assert resp.get_json()["group_id"] is None
    assert client.patch(f"/api/v1/posts/{post.id}", json={"group_id": 99999}).status_code == 400
