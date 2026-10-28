"""Poll service — business logic for polls and voting."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from vollbuild.api.notifications.services import (
    notify_all_active,
    notify_member,
)
from vollbuild.api.utils import log_audit
from vollbuild.errors import raise_error
from vollbuild.extensions import db
from vollbuild.core.models.function import Function
from vollbuild.core.models.group import Group
from vollbuild.core.models.member import Member
from vollbuild.core.models.poll import Poll, PollOption, PollVote


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
    def vote(poll: Poll, member_id: int, option_index: int) -> Poll:
        """Cast or change a vote in a poll. Raises 409 if closed."""
        if poll.status == "closed":
            raise_error(409, "CONFLICT", "This poll is closed")

        options = db.session.scalars(
            select(PollOption)
            .where(PollOption.poll_id == poll.id)
            .order_by(PollOption.id)
        ).all()

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
            )

        return poll

    @staticmethod
    def update(poll: Poll, data: dict, actor_id: int) -> Poll:
        """Update allowed fields on a poll."""
        for field in ("question", "closes_at", "is_required"):
            if field in data:
                setattr(poll, field, data[field])
        if "required_group_ids" in data:
            poll.required_group_ids = data["required_group_ids"]
        if "required_function_ids" in data:
            poll.required_function_ids = data["required_function_ids"]
        if "options" in data:
            existing_options = db.session.scalars(
                select(PollOption).where(PollOption.poll_id == poll.id)
            ).all()
            for opt in existing_options:
                db.session.delete(opt)
            db.session.flush()
            for opt_data in data["options"]:
                db.session.add(PollOption(poll_id=poll.id, label=opt_data["label"]))

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
            required_group_ids=data.get("required_group_ids"),
            required_function_ids=data.get("required_function_ids"),
        )
        db.session.add(poll)
        db.session.flush()

        for opt in data["options"]:
            db.session.add(PollOption(poll_id=poll.id, label=opt["label"]))

        notify_all_active("info", "New poll", poll.question, skip_member_id=actor_id)

        log_audit(
            actor_id=actor_id,
            action="create_poll",
            target_type="Poll",
            target_id=poll.id,
            target_label=poll.question,
        )

        db.session.refresh(poll)
        return PollService.get(poll.id)
