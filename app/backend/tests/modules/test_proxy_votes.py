"""Proxy votes in polls (general assembly)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from vollbuild.api.polls.services import PollService, ProxyService
from vollbuild.core.errors import ApiError
from vollbuild.core.models.member import Member
from vollbuild.core.models.poll import Poll, PollOption, PollVote
from vollbuild.core.models.user import User


def _member(db, seeded_db, email):
    user = User(email=email, first_name=email.split("@")[0], last_name="Test")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    m = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    db.session.add(m)
    db.session.flush()
    return m


@pytest.fixture
def setup(db, seeded_db):
    poll = Poll(question="Approve budget?", allow_proxy=True)
    db.session.add(poll)
    db.session.flush()
    db.session.add_all(
        [
            PollOption(poll_id=poll.id, label="Yes"),
            PollOption(poll_id=poll.id, label="No"),
        ]
    )
    anna = _member(db, seeded_db, "anna@test.ch")
    ben = _member(db, seeded_db, "ben@test.ch")
    db.session.commit()
    return poll, seeded_db["admin"], anna, ben


def _code(fn):
    with pytest.raises(ApiError) as exc:
        fn()
    return exc.value.code


def test_holder_votes_for_grantor_via_api(client, db, auth_headers, setup):
    poll, admin, anna, _ = setup
    ProxyService.grant(poll, anna.id, admin.id)
    db.session.commit()

    state = client.get(f"/api/v1/polls/{poll.id}/proxy").get_json()
    assert state["holding"] == [{"id": anna.id, "name": anna.name, "voted": False}]

    resp = client.post(
        f"/api/v1/polls/{poll.id}/vote",
        json={"option_index": 1, "on_behalf_of": anna.id},
    )
    assert resp.status_code == 200
    assert resp.get_json()["total_votes"] == 1
    vote = db.session.scalar(select(PollVote).where(PollVote.member_id == anna.id))
    assert vote.cast_by_id == admin.id
    # The holder still has their own vote.
    client.post(f"/api/v1/polls/{poll.id}/vote", json={"option_index": 0})
    assert client.get(f"/api/v1/polls/{poll.id}").get_json()["total_votes"] == 2


def test_cannot_vote_for_someone_without_proxy(client, auth_headers, setup):
    poll, _, anna, _ = setup
    resp = client.post(
        f"/api/v1/polls/{poll.id}/vote",
        json={"option_index": 0, "on_behalf_of": anna.id},
    )
    assert resp.status_code == 403


def test_grant_via_api_and_revoke(client, db, auth_headers, setup):
    poll, admin, anna, _ = setup
    resp = client.post(f"/api/v1/polls/{poll.id}/proxy", json={"holder_id": anna.id})
    assert resp.status_code == 201
    assert resp.get_json()["given_to"]["id"] == anna.id
    # Gave the vote away: voting personally is refused.
    vote = client.post(f"/api/v1/polls/{poll.id}/vote", json={"option_index": 0})
    assert vote.get_json()["error"] == "PROXY_GIVEN"
    # Anna votes for admin, then admin takes the proxy back: that vote goes.
    PollService.vote(poll, anna.id, 0, on_behalf_of=admin.id)
    db.session.commit()
    assert client.delete(f"/api/v1/polls/{poll.id}/proxy").status_code == 200
    assert (
        db.session.scalar(select(PollVote).where(PollVote.member_id == admin.id))
        is None
    )


def test_rules(db, setup):
    poll, admin, anna, ben = setup
    assert (
        _code(lambda: ProxyService.grant(poll, anna.id, anna.id)) == "VALIDATION_ERROR"
    )
    ProxyService.grant(poll, anna.id, ben.id)
    assert _code(lambda: ProxyService.grant(poll, anna.id, admin.id)) == "PROXY_EXISTS"
    # Ben holds a proxy, so cannot hand his own vote on; nobody can give to
    # Anna, who gave hers away.
    assert _code(lambda: ProxyService.grant(poll, ben.id, admin.id)) == "PROXY_CHAIN"
    assert _code(lambda: ProxyService.grant(poll, admin.id, anna.id)) == "PROXY_CHAIN"
    # Ben is at the default limit of one.
    assert _code(lambda: ProxyService.grant(poll, admin.id, ben.id)) == "PROXY_LIMIT"


def test_already_voted_and_not_allowed(db, setup):
    poll, admin, anna, ben = setup
    PollService.vote(poll, anna.id, 0)
    assert _code(lambda: ProxyService.grant(poll, anna.id, ben.id)) == "ALREADY_VOTED"
    poll.allow_proxy = False
    assert (
        _code(lambda: ProxyService.grant(poll, admin.id, ben.id)) == "PROXY_NOT_ALLOWED"
    )


def test_create_poll_with_proxy(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/polls/",
        json={
            "question": "AGM",
            "options": [{"label": "a"}, {"label": "b"}],
            "allow_proxy": True,
            "max_proxies_per_member": 2,
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["allow_proxy"] is True and body["max_proxies_per_member"] == 2
