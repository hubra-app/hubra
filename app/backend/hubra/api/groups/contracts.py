"""What Groups offers other modules through contracts (docs/contracts.md).

- ``groups.self_join.list`` (query): the open groups a member may join or
  leave on their own, and whether they are in.
- ``groups.self_join.set`` (action): join or leave an open group.
"""

from __future__ import annotations

from pydantic import BaseModel


class MemberRef(BaseModel):
    member_id: int


class JoinableGroup(BaseModel):
    id: int
    name: str
    description: str | None = None
    color: str | None = None
    icon_name: str | None = None
    type: str | None = None
    member_count: int
    joined: bool


def joinable(ctx, data: MemberRef) -> list[JoinableGroup]:
    from hubra.api.groups.services import SelfJoinService

    return [
        JoinableGroup(
            id=g["id"],
            name=g["name"],
            description=g.get("description"),
            color=g.get("color"),
            icon_name=g.get("iconName"),
            type=g.get("type"),
            member_count=g.get("memberCount", 0),
            joined=g["joined"],
        )
        for g in SelfJoinService.joinable(data.member_id)
    ]


class SelfJoinIn(BaseModel):
    group_id: int
    member_id: int
    joined: bool


class SelfJoin(BaseModel):
    group_id: int
    member_id: int
    joined: bool


def set_self_join(ctx, data: SelfJoinIn) -> SelfJoin:
    from hubra.api.groups.services import SelfJoinService
    from hubra.core.contracts import Refused
    from hubra.core.extensions import db
    from hubra.core.models.member import Member

    member = db.session.get(Member, data.member_id)
    if member is None:
        raise Refused(
            f"Member {data.member_id} not found", code="NOT_FOUND", status=404
        )
    if data.joined:
        SelfJoinService.join(data.group_id, member)
    else:
        SelfJoinService.leave(data.group_id, member)
    return SelfJoin(**data.model_dump())
