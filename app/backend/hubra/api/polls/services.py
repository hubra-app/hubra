"""Poll service — business logic for polls and voting."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from hubra.api.notifications.services import (
    notify_member,
    notify_on_publish,
)
from hubra.api.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.function import Function, FunctionHolder
from hubra.core.models.group import Group
from hubra.core.models.member import Member, member_groups
from hubra.core.models.poll import Poll, PollOption, PollProxy, PollVote
from hubra.core.modules import emit
from hubra.core.modules.events import POLL_PUBLISHED


def member_circles(member_id: int) -> tuple[set[int], set[int]]:
    """The groups and functions *member_id* belongs to."""
    groups = set(
        db.session.scalars(
            select(member_groups.c.group_id).where(member_groups.c.member_id == member_id)
        )
    )
    functions = set(
        db.session.scalars(
            select(FunctionHolder.function_id).where(FunctionHolder.member_id == member_id)
        )
    )
    return groups, functions


def may_vote(poll: Poll, circles: tuple[set[int], set[int]]) -> bool:
    """A poll for named groups or functions is theirs to vote on; one with
    neither is open to every member with the vote right."""
    group_ids = set(poll.required_group_ids or ())
    function_ids = set(poll.required_function_ids or ())
    if not group_ids and not function_ids:
        return True
    groups, functions = circles
    return bool(group_ids & groups or function_ids & functions)


def is_closed(poll: Poll) -> bool:
    """Closed by hand, or its closing time has passed."""
    if poll.status == "closed":
        return True
    closes_at = poll.closes_at
    if closes_at is None:
        return False
    if closes_at.tzinfo is None:  # SQLite hands back naive datetimes
        closes_at = closes_at.replace(tzinfo=timezone.utc)
    return closes_at <= datetime.now(timezone.utc)


def poll_link(poll_id: int) -> str:
    """The polls page showing one poll."""
    return f"/app/operations/polls?poll={poll_id}"


class PollService:
    """Operations on a single poll."""

    @staticmethod
    def get(poll_id: int) -> Poll:
        """Return a poll with options eager-loaded, or raise 404."""
        poll = db.session.scalar(
            select(Poll).where(Poll.id == poll_id).options(selectinload(Poll.options))
        )
        if poll is None:
            raise_error(404, "NOT_FOUND", f"Poll {poll_id} not found")
        return poll  # type: ignore[return-value]

    @staticmethod
    def vote(
        poll: Poll,
        member_id: int,
        option_index: int,
        on_behalf_of: int | None = None,
    ) -> Poll:
        """Cast or change a vote in a poll. Raises 409 if closed.

        With ``on_behalf_of`` the caller votes as that member's proxy holder.
        """
        if is_closed(poll):
            raise_error(409, "CONFLICT", "This poll is closed")
        cast_by_id = None
        if on_behalf_of is not None and on_behalf_of != member_id:
            ProxyService.require_holder(
                poll, grantor_id=on_behalf_of, holder_id=member_id
            )
            cast_by_id, member_id = member_id, on_behalf_of
        elif ProxyService.given(poll.id, member_id) is not None:
            raise_error(
                409,
                "PROXY_GIVEN",
                "You gave your vote to a proxy; take it back to vote yourself",
            )

        options = db.session.scalars(
            select(PollOption)
            .where(PollOption.poll_id == poll.id)
            .order_by(PollOption.id)
        ).all()

        if not may_vote(poll, member_circles(member_id)):
            raise_error(
                403,
                "NOT_ELIGIBLE",
                "This poll is for the groups and functions it names",
            )

        if option_index < 0 or option_index >= len(options):
            raise_error(
                400,
                "VALIDATION_ERROR",
                f"option_index {option_index} is out of range (0–{len(options) - 1})",
            )

        existing_vote = db.session.scalar(
            select(PollVote).where(
                PollVote.poll_id == poll.id,
                PollVote.member_id == member_id,
            )
        )
        if existing_vote is not None:
            db.session.delete(existing_vote)
            db.session.flush()

        chosen_option = options[option_index]

        db.session.add(
            PollVote(
                poll_id=poll.id,
                option_id=chosen_option.id,
                member_id=member_id,
                cast_by_id=cast_by_id,
            )
        )

        if poll.created_by_id is not None and poll.created_by_id != member_id:
            member = db.session.get(Member, member_id)
            voter_name = member.name if member else f"Member {member_id}"
            notify_member(
                poll.created_by_id,
                "info",
                f"New vote: {poll.question}",
                f"{voter_name} voted for {chosen_option.label}",
                link=poll_link(poll.id),
            )

        return poll

    @staticmethod
    def update(poll: Poll, data: dict, actor_id: int) -> Poll:
        """Update allowed fields on a poll."""
        for field in (
            "question",
            "closes_at",
            "is_required",
            "allow_proxy",
            "max_proxies_per_member",
        ):
            if field in data:
                setattr(poll, field, data[field])
        if "required_group_ids" in data:
            poll.required_group_ids = data["required_group_ids"]
        if "required_function_ids" in data:
            poll.required_function_ids = data["required_function_ids"]
        if "options" in data:
            existing_options = db.session.scalars(
                select(PollOption)
                .where(PollOption.poll_id == poll.id)
                .order_by(PollOption.id)
            ).all()
            labels = [opt_data["label"] for opt_data in data["options"]]
            # The club app sends the options with every edit; the same
            # options keep their votes. Replacing them would delete every
            # vote cast (the votes go with their option).
            if labels != [opt.label for opt in existing_options]:
                has_votes = db.session.scalar(
                    select(PollVote.id).where(PollVote.poll_id == poll.id).limit(1)
                )
                if has_votes is not None:
                    raise_error(
                        409,
                        "POLL_HAS_VOTES",
                        "The options cannot change once votes have been cast",
                    )
                for opt in existing_options:
                    db.session.delete(opt)
                db.session.flush()
                for label in labels:
                    db.session.add(PollOption(poll_id=poll.id, label=label))

        log_audit(
            actor_id=actor_id,
            action="update_poll",
            target_type="Poll",
            target_id=poll.id,
            target_label=poll.question,
        )
        return poll

    @staticmethod
    def close(poll: Poll, actor_id: int) -> Poll:
        """Close a poll."""
        poll.status = "closed"

        log_audit(
            actor_id=actor_id,
            action="close_poll",
            target_type="Poll",
            target_id=poll.id,
            target_label=poll.question,
        )
        return poll

    @staticmethod
    def delete(poll_id: int, actor_id: int) -> None:
        """Delete a poll."""
        poll = PollService.get(poll_id)

        log_audit(
            actor_id=actor_id,
            action="delete_poll",
            target_type="Poll",
            target_id=poll.id,
            target_label=poll.question,
        )
        # Club schemas have no foreign keys, so proxies do not cascade.
        db.session.execute(delete(PollProxy).where(PollProxy.poll_id == poll.id))
        db.session.delete(poll)

    @staticmethod
    def get_required_members(poll: Poll) -> list[int]:
        """Return list of member IDs who must vote on this poll."""
        member_ids: set[int] = set()

        if poll.required_group_ids:
            for gid in poll.required_group_ids:
                group = db.session.get(Group, gid)
                if group:
                    for m in group.members:
                        member_ids.add(m.id)

        if poll.required_function_ids:
            for fid in poll.required_function_ids:
                func_ = db.session.get(Function, fid)
                if func_:
                    for h in func_.holders:
                        member_ids.add(h.member_id)

        return list(member_ids)

    @staticmethod
    def remind(poll_id: int, actor_id: int) -> int:
        """Send reminder notifications to required members who haven't voted."""
        poll = PollService.get(poll_id)
        if is_closed(poll):
            raise_error(409, "CONFLICT", "This poll is closed")
        required = PollService.get_required_members(poll)

        voters = set(
            db.session.scalars(
                select(PollVote.member_id).where(PollVote.poll_id == poll.id)
            ).all()
        )

        sent = 0
        for member_id in required:
            if member_id not in voters:
                notify_member(
                    member_id,
                    "warning",
                    f"Reminder: {poll.question}",
                    "Please cast your vote before the poll closes.",
                    link=poll_link(poll.id),
                )
                sent += 1

        log_audit(
            actor_id=actor_id,
            action="remind_poll",
            target_type="Poll",
            target_id=poll.id,
            target_label=poll.question,
        )
        return sent


class PollsService:
    """Operations on the poll collection."""

    @staticmethod
    def list() -> list[Poll]:
        """Return all polls ordered by created_at descending."""
        return db.session.scalars(  # type: ignore[return-value]
            select(Poll)
            .options(selectinload(Poll.options))
            .order_by(Poll.created_at.desc())
        ).all()

    @staticmethod
    def create(data: dict, actor_id: int) -> Poll:
        """Create a new poll with options. Returns the poll."""
        poll = Poll(
            created_by_id=actor_id,
            question=data["question"],
            closes_at=data.get("closes_at"),
            status="open",
            is_required=data.get("is_required", False),
            allow_proxy=data.get("allow_proxy", False),
            max_proxies_per_member=data.get("max_proxies_per_member", 1),
            required_group_ids=data.get("required_group_ids"),
            required_function_ids=data.get("required_function_ids"),
        )
        db.session.add(poll)
        db.session.flush()

        for opt in data["options"]:
            db.session.add(PollOption(poll_id=poll.id, label=opt["label"]))

        notify_on_publish(
            "polls",
            "info",
            "New poll",
            poll.question,
            skip_member_id=actor_id,
            link=poll_link(poll.id),
        )
        emit(POLL_PUBLISHED, poll_id=poll.id)

        log_audit(
            actor_id=actor_id,
            action="create_poll",
            target_type="Poll",
            target_id=poll.id,
            target_label=poll.question,
        )

        db.session.refresh(poll)
        return PollService.get(poll.id)


class ProxyService:
    """Proxy votes: a member lets another member vote for them in one poll.

    Rules: the poll must allow proxies and be open; no chains (a holder
    cannot have given their own vote away, and a grantor cannot hold
    proxies); a holder carries at most ``max_proxies_per_member`` votes
    besides their own; a member who already voted cannot give a proxy.
    """

    @staticmethod
    def given(poll_id: int, grantor_id: int) -> PollProxy | None:
        return db.session.scalar(
            select(PollProxy).where(
                PollProxy.poll_id == poll_id, PollProxy.grantor_id == grantor_id
            )
        )

    @staticmethod
    def held(poll_id: int, holder_id: int) -> list[PollProxy]:
        return list(
            db.session.scalars(
                select(PollProxy)
                .where(PollProxy.poll_id == poll_id, PollProxy.holder_id == holder_id)
                .order_by(PollProxy.id)
            )
        )

    @staticmethod
    def _vote_of(poll_id: int, member_id: int) -> PollVote | None:
        return db.session.scalar(
            select(PollVote).where(
                PollVote.poll_id == poll_id, PollVote.member_id == member_id
            )
        )

    @staticmethod
    def grant(poll: Poll, grantor_id: int, holder_id: int) -> PollProxy:
        if not poll.allow_proxy:
            raise_error(409, "PROXY_NOT_ALLOWED", "This poll does not allow proxies")
        if is_closed(poll):
            raise_error(409, "CONFLICT", "This poll is closed")
        if holder_id == grantor_id:
            raise_error(400, "VALIDATION_ERROR", "You cannot be your own proxy")
        if not may_vote(poll, member_circles(grantor_id)):
            raise_error(
                403, "NOT_ELIGIBLE", "This poll is for the groups and functions it names"
            )
        holder = db.session.get(Member, holder_id)
        if holder is None or holder.archived_at is not None:
            raise_error(404, "NOT_FOUND", "Member not found")
        if ProxyService.given(poll.id, grantor_id) is not None:
            raise_error(409, "PROXY_EXISTS", "You already gave your vote to someone")
        if ProxyService._vote_of(poll.id, grantor_id) is not None:
            raise_error(409, "ALREADY_VOTED", "You already voted in this poll")
        if ProxyService.held(poll.id, grantor_id):
            raise_error(
                409, "PROXY_CHAIN", "You hold proxies and cannot give yours away"
            )
        if ProxyService.given(poll.id, holder_id) is not None:
            raise_error(
                409, "PROXY_CHAIN", f"{holder.name} gave their own vote to a proxy"
            )
        if len(ProxyService.held(poll.id, holder_id)) >= poll.max_proxies_per_member:
            raise_error(409, "PROXY_LIMIT", f"{holder.name} cannot hold more proxies")
        proxy = PollProxy(poll_id=poll.id, grantor_id=grantor_id, holder_id=holder_id)
        db.session.add(proxy)
        db.session.flush()
        grantor = db.session.get(Member, grantor_id)
        log_audit(
            grantor_id,
            "grant_proxy",
            "Poll",
            poll.id,
            f"{grantor.name if grantor else grantor_id} → {holder.name}",
        )
        notify_member(
            holder_id,
            "info",
            f"Proxy vote: {poll.question}",
            f"{grantor.name if grantor else 'A member'} asked you to vote for them.",
            link=poll_link(poll.id),
        )
        return proxy

    @staticmethod
    def revoke(poll: Poll, grantor_id: int) -> None:
        """Take a proxy back. A vote the holder already cast for the grantor
        is withdrawn too, so the grantor can vote themselves."""
        if is_closed(poll):
            raise_error(409, "CONFLICT", "This poll is closed")
        proxy = ProxyService.given(poll.id, grantor_id)
        if proxy is None:
            raise_error(404, "NOT_FOUND", "You have not given a proxy")
        vote = ProxyService._vote_of(poll.id, grantor_id)
        if vote is not None and vote.cast_by_id is not None:
            db.session.delete(vote)
        log_audit(grantor_id, "revoke_proxy", "Poll", poll.id, str(proxy.holder_id))
        db.session.delete(proxy)
        db.session.flush()

    @staticmethod
    def require_holder(poll: Poll, grantor_id: int, holder_id: int) -> None:
        proxy = ProxyService.given(poll.id, grantor_id)
        if proxy is None or proxy.holder_id != holder_id:
            raise_error(403, "NOT_PROXY", "You do not hold this member's proxy")
        # A proxy given earlier lapses when the poll stops allowing proxies
        # or the member who gave it has left the club.
        grantor = db.session.get(Member, grantor_id)
        if not poll.allow_proxy or grantor is None or grantor.archived_at is not None:
            raise_error(409, "PROXY_NOT_ALLOWED", "This proxy is no longer valid")

    @staticmethod
    def state(poll: Poll, member_id: int) -> dict:
        given = ProxyService.given(poll.id, member_id)
        return {
            "allow_proxy": poll.allow_proxy,
            "max_proxies_per_member": poll.max_proxies_per_member,
            "given_to": (
                {"id": given.holder_id, "name": given.holder.name} if given else None
            ),
            "holding": [
                {
                    "id": p.grantor_id,
                    "name": p.grantor.name,
                    "voted": ProxyService._vote_of(poll.id, p.grantor_id) is not None,
                }
                for p in ProxyService.held(poll.id, member_id)
            ],
        }
