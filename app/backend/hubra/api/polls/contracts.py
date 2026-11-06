"""What Polls offers other modules through contracts (docs/contracts.md).

- ``polls.poll.get`` (query): whether a poll is closed, who it is for and
  who of them hasn't voted.
- ``polls.poll.create`` (action): a new poll, checked like one made in the
  app.
- ``polls.poll.vote`` (action): cast or change a vote, also as a proxy.
- ``polls.proxies.held`` (query): the proxies a member holds for a poll.

Hubra's service errors come back as ``Refused`` with the same code
(``CONFLICT`` for a closed poll, ``NOT_ELIGIBLE``, ``PROXY_GIVEN``, ...).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


def _actor_id(ctx, given: int | None) -> int | None:
    if given is not None:
        return given
    return ctx.actor.id if ctx.actor is not None else None


def _poll(poll_id: int):
    from hubra.api.polls.services import PollService

    return PollService.get(poll_id)  # 404 NOT_FOUND


class PollRef(BaseModel):
    poll_id: int


class PollInfo(BaseModel):
    id: int
    question: str
    closed: bool
    # Members who must vote (required groups and functions); empty when
    # the poll is for everyone.
    required_member_ids: list[int]
    # Of those, who hasn't voted yet (a proxy's vote counts for its giver).
    missing_member_ids: list[int]


def get_poll(ctx, data: PollRef) -> PollInfo:
    from hubra.api.polls.services import PollService, is_closed

    poll = _poll(data.poll_id)
    return PollInfo(
        id=poll.id,
        question=poll.question,
        closed=is_closed(poll),
        required_member_ids=PollService.get_required_members(poll),
        missing_member_ids=PollService.missing_voters(poll),
    )


class PollOptionIn(BaseModel):
    label: str


class PollCreateIn(BaseModel):
    """The fields of the app's poll form (``PollCreateSchema``)."""

    question: str
    options: list[PollOptionIn]
    closes_at: datetime | None = None
    auto_close: bool = False
    is_required: bool = False
    required_group_ids: list[int] | None = None
    required_function_ids: list[int] | None = None
    allow_proxy: bool = False
    group_id: int | None = None
    max_proxies_per_member: int = 1
    actor_id: int | None = None


class PollCreated(BaseModel):
    id: int
    question: str


def create_poll(ctx, data: PollCreateIn) -> PollCreated:
    from marshmallow import ValidationError

    from hubra.api.polls.services import PollsService
    from hubra.core.contracts import Refused
    from hubra.core.schemas.poll import PollCreateSchema

    body = data.model_dump(exclude={"actor_id"}, mode="json")
    try:
        fields = PollCreateSchema().load(body)
    except ValidationError as exc:
        raise Refused(str(exc.messages), code="VALIDATION_ERROR", status=400) from None
    poll = PollsService.create(fields, _actor_id(ctx, data.actor_id))
    return PollCreated(id=poll.id, question=poll.question)


class VoteIn(BaseModel):
    poll_id: int
    member_id: int
    # Position of the option, in the order the options were made.
    option_index: int
    # Vote as this member's proxy holder.
    on_behalf_of: int | None = None


class Vote(BaseModel):
    poll_id: int
    member_id: int
    option_index: int
    on_behalf_of: int | None = None


def vote(ctx, data: VoteIn) -> Vote:
    from hubra.api.polls.services import PollService

    poll = _poll(data.poll_id)
    PollService.vote(
        poll, data.member_id, data.option_index, on_behalf_of=data.on_behalf_of
    )
    return Vote(**data.model_dump())


class HeldIn(BaseModel):
    poll_id: int
    member_id: int


class Proxy(BaseModel):
    poll_id: int
    grantor_id: int
    holder_id: int


def proxies_held(ctx, data: HeldIn) -> list[Proxy]:
    from hubra.api.polls.services import ProxyService

    return [
        Proxy(poll_id=p.poll_id, grantor_id=p.grantor_id, holder_id=p.holder_id)
        for p in ProxyService.held(data.poll_id, data.member_id)
    ]
