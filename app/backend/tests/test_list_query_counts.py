"""List endpoints run a fixed number of queries, however many rows they return.

Each test counts the queries of one list request, adds six more rows, and
counts again. A per-row query (N+1) adds at least six.
"""

from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import event, func, select

from hubra.core.models.member import Member


@contextmanager
def _count_queries(db):
    statements: list[str] = []

    def _on_execute(conn, cursor, statement, params, context, executemany):
        # Postgres resets search_path whenever a pooled connection is
        # checked out; that is not a query of the endpoint.
        if not statement.startswith("SET search_path"):
            statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", _on_execute)
    try:
        yield statements
    finally:
        event.remove(db.engine, "before_cursor_execute", _on_execute)


def _queries(client, db, url):
    client.get(url)  # the first request of a session also writes last_seen
    # Start from an empty session, as a request in production does.
    db.session.expire_all()
    with _count_queries(db) as statements:
        resp = client.get(url)
    assert resp.status_code == 200, resp.get_json()
    return len(statements), resp.get_json()


def _add_member(db, tier, n):
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    user = User(email=f"m{n}@test.ch", first_name=f"First{n}", last_name=f"Last{n}")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    member = Member(user_id=user.id, status="active", tier_id=tier.id)
    db.session.add(member)
    db.session.flush()
    return member


@pytest.fixture
def members(db, seeded_db):
    made = [_add_member(db, seeded_db["tier"], n) for n in range(10)]
    db.session.commit()
    return made


def test_groups_list(client, auth_headers, db, members):
    from hubra.core.models.group import Group

    def add_groups(start, count):
        for n in range(start, start + count):
            group = Group(name=f"Group {n}", lead_id=members[n].id)
            group.members = members[: n + 1]
            db.session.add(group)
        db.session.commit()

    add_groups(0, 3)
    before, _ = _queries(client, db, "/api/v1/groups")
    add_groups(3, 6)
    after, body = _queries(client, db, "/api/v1/groups")

    assert after == before
    counts = {g["name"]: (g["member_count"], g["lead_name"]) for g in body}
    assert counts["Group 0"] == (1, "First0 Last0")
    assert counts["Group 5"] == (6, "First5 Last5")


def test_polls_list(client, auth_headers, db, members):
    from hubra.core.models.poll import Poll, PollOption, PollVote

    def add_polls(start, count):
        for n in range(start, start + count):
            poll = Poll(question=f"Poll {n}", status="open")
            poll.options = [PollOption(label="Yes"), PollOption(label="No")]
            db.session.add(poll)
            db.session.flush()
            for member in members[: n + 1]:
                db.session.add(
                    PollVote(
                        poll_id=poll.id,
                        option_id=poll.options[0].id,
                        member_id=member.id,
                    )
                )
        db.session.commit()

    add_polls(0, 3)
    before, _ = _queries(client, db, "/api/v1/polls")
    add_polls(3, 6)
    after, body = _queries(client, db, "/api/v1/polls")

    assert after == before
    poll = next(p for p in body if p["question"] == "Poll 4")
    assert poll["total_votes"] == 5
    assert sorted(o["vote_count"] for o in poll["options"]) == [0, 5]


def test_posts_list(client, auth_headers, db, seeded_db, members):
    from hubra.core.models.post import Post, PostComment

    def add_posts(start, count):
        for n in range(start, start + count):
            post = Post(author_id=seeded_db["admin"].id, title=f"Post {n}", body="x")
            db.session.add(post)
            db.session.flush()
            for member in members[:n]:
                db.session.add(
                    PostComment(post_id=post.id, author_id=member.id, body="c")
                )
        db.session.commit()

    add_posts(0, 3)
    before, _ = _queries(client, db, "/api/v1/posts")
    add_posts(3, 6)
    after, body = _queries(client, db, "/api/v1/posts")

    assert after == before
    assert {p["title"]: p["comment_count"] for p in body}["Post 4"] == 4


def test_events_list(client, auth_headers, db, members):
    from hubra.core.models.event import ClubEvent, EventRegistration

    def add_events(start, count):
        for n in range(start, start + count):
            ev = ClubEvent(title=f"Event {n}", date=date(2026, 1, n + 1), type="Social")
            db.session.add(ev)
            db.session.flush()
            for i, member in enumerate(members[: n + 1]):
                status = "cancelled" if i == 0 else "registered"
                db.session.add(
                    EventRegistration(
                        event_id=ev.id, member_id=member.id, status=status
                    )
                )
        db.session.commit()

    add_events(0, 3)
    before, _ = _queries(client, db, "/api/v1/events")
    add_events(3, 6)
    after, body = _queries(client, db, "/api/v1/events")

    assert after == before
    # Cancelled registrations do not count.
    assert {e["title"]: e["registration_count"] for e in body}["Event 5"] == 5


def test_invoices_list(client, auth_headers, db, members):
    from hubra.core.models.finance import Invoice

    def add_invoices(rows):
        for member in rows:
            db.session.add(
                Invoice(
                    member_id=member.id,
                    issued=date(2026, 1, 1),
                    due=date(2026, 2, 1),
                    amount=50,
                    status="open",
                )
            )
        db.session.commit()

    add_invoices(members[:3])
    before, _ = _queries(client, db, "/api/v1/finance/invoices")
    add_invoices(members[3:9])
    after, body = _queries(client, db, "/api/v1/finance/invoices")

    assert after == before
    assert {i["member_name"] for i in body["data"]} >= {"First5 Last5"}


def test_tier_and_group_members(client, auth_headers, db, seeded_db, members):
    from hubra.core.models.group import Group

    group = Group(name="Everyone")
    group.members = members[:3]
    db.session.add(group)
    db.session.commit()
    tier_id = seeded_db["tier"].id

    tier_before, _ = _queries(client, db, f"/api/v1/tiers/{tier_id}/members")
    group_before, _ = _queries(client, db, f"/api/v1/groups/{group.id}/members")
    for n in range(10, 16):
        _add_member(db, seeded_db["tier"], n)
    group.members = members
    db.session.commit()
    tier_after, tier_body = _queries(client, db, f"/api/v1/tiers/{tier_id}/members")
    group_after, group_body = _queries(client, db, f"/api/v1/groups/{group.id}/members")

    assert tier_after == tier_before
    assert group_after == group_before
    assert len(tier_body["data"]) == 17
    assert len(group_body["data"]) == 10


def test_dashboard_growth_is_one_query(client, auth_headers, db, members):
    count, body = _queries(client, db, "/api/v1/dashboard/summary")

    assert len(body["growth"]) == 12
    # Every member gets a join date, so this month counts them all.
    assert body["growth"][-1] == db.session.scalar(
        select(func.count(Member.id)).where(Member.archived_at.is_(None))
    )
    assert count < 20
