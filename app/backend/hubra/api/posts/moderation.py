"""Comment moderation: members report comments, moderators hide them or
mute a member in comments for some days.

Who moderates is a role right: ``posts.posts.moderate`` (club-wide, or for
a group's posts through a role held for that group). Admins always do.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.models.post import CommentMute, CommentReport, Post, PostComment
from hubra.core.utils import log_audit

MODERATE = "posts.posts.moderate"
MAX_MUTE_DAYS = 365
REASON_MAX = 300
TITLE_REPORTED = "A comment was reported"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _name(member: Member | None) -> str:
    if member is None:
        return ""
    return f"{member.first_name} {member.last_name}".strip()


def _reason(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise_error(400, "VALIDATION_ERROR", "reason is text")
    value = value.strip()
    return value[:REASON_MAX] or None


# ── Reports ──────────────────────────────────────────────────────────────────


def report(comment: PostComment, member_id: int, reason) -> bool:
    """Report *comment*; True when this is the comment's first report (the
    moderators are told then). Reporting twice changes nothing."""
    from hubra.core.notifications.staff import notify_permitted

    if comment.author_id == member_id:
        raise_error(400, "OWN_COMMENT", "You cannot report your own comment")
    text = _reason(reason)
    exists = db.session.scalar(
        select(CommentReport.id).where(
            CommentReport.comment_id == comment.id,
            CommentReport.member_id == member_id,
        )
    )
    if exists:
        return False
    first = not db.session.scalar(
        select(CommentReport.id).where(CommentReport.comment_id == comment.id).limit(1)
    )
    db.session.add(
        CommentReport(comment_id=comment.id, member_id=member_id, reason=text)
    )
    db.session.flush()
    if first and comment.hidden_at is None:
        notify_permitted(
            MODERATE,
            "warning",
            TITLE_REPORTED,
            comment.body[:120],
            skip_member_id=member_id,
            link=f"/app/operations/posts/{comment.post_id}",
        )
    return first


def clear_reports(comment: PostComment, actor_id: int) -> int:
    """A moderator keeps the comment: its reports are done."""
    reports = db.session.scalars(
        select(CommentReport).where(CommentReport.comment_id == comment.id)
    ).all()
    for r in reports:
        db.session.delete(r)
    if reports:
        log_audit(
            actor_id=actor_id,
            action="keep_comment",
            target_type="PostComment",
            target_id=comment.id,
            target_label=comment.body[:60],
        )
    return len(reports)


def report_counts(comment_ids: list[int]) -> dict[int, int]:
    if not comment_ids:
        return {}
    return dict(
        db.session.execute(
            select(CommentReport.comment_id, func.count())
            .where(CommentReport.comment_id.in_(comment_ids))
            .group_by(CommentReport.comment_id)
        ).all()
    )


def reported_by(member_id: int, comment_ids: list[int]) -> set[int]:
    if not comment_ids:
        return set()
    return set(
        db.session.scalars(
            select(CommentReport.comment_id).where(
                CommentReport.member_id == member_id,
                CommentReport.comment_id.in_(comment_ids),
            )
        ).all()
    )


def open_reports(may_moderate) -> list[dict]:
    """Reported comments that are still shown, most reports first, for the
    posts *may_moderate(post)* allows."""
    rows = db.session.execute(
        select(CommentReport, PostComment)
        .join(PostComment, PostComment.id == CommentReport.comment_id)
        .where(PostComment.hidden_at.is_(None))
        .order_by(CommentReport.created_at)
    ).all()
    by_comment: dict[int, dict] = {}
    for rep, comment in rows:
        item = by_comment.get(comment.id)
        if item is None:
            item = by_comment[comment.id] = {
                "comment": comment,
                "reasons": [],
                "count": 0,
                "last": rep.created_at,
            }
        item["count"] += 1
        item["last"] = max(item["last"], rep.created_at)
        if rep.reason:
            item["reasons"].append(rep.reason)
    if not by_comment:
        return []
    posts = {
        p.id: p
        for p in db.session.scalars(
            select(Post).where(
                Post.id.in_({i["comment"].post_id for i in by_comment.values()})
            )
        ).all()
    }
    authors = {
        m.id: m
        for m in db.session.scalars(
            select(Member).where(
                Member.id.in_({i["comment"].author_id for i in by_comment.values()})
            )
        ).all()
    }
    out = []
    for item in by_comment.values():
        comment = item["comment"]
        post = posts.get(comment.post_id)
        if post is None or not may_moderate(post):
            continue
        out.append(
            {
                "comment_id": comment.id,
                "post_id": comment.post_id,
                "post_title": post.title,
                "author_id": comment.author_id,
                "author_name": _name(authors.get(comment.author_id)),
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
                "reports": item["count"],
                "reasons": item["reasons"][:5],
                "last_reported_at": item["last"].isoformat(),
            }
        )
    out.sort(key=lambda r: (-r["reports"], r["last_reported_at"]))
    return out


# ── Hiding ───────────────────────────────────────────────────────────────────


def set_hidden(comment: PostComment, hidden: bool, actor_id: int) -> None:
    if hidden == (comment.hidden_at is not None):
        return
    comment.hidden_at = _now() if hidden else None
    comment.hidden_by_id = actor_id if hidden else None
    if hidden:
        # Hidden: the reports are done.
        for r in db.session.scalars(
            select(CommentReport).where(CommentReport.comment_id == comment.id)
        ).all():
            db.session.delete(r)
    log_audit(
        actor_id=actor_id,
        action="hide_comment" if hidden else "show_comment",
        target_type="PostComment",
        target_id=comment.id,
        target_label=comment.body[:60],
    )


# ── Muting ───────────────────────────────────────────────────────────────────


def muted_until(member_id: int) -> datetime | None:
    """When *member_id* may comment again; None when they may now."""
    mute = db.session.scalar(
        select(CommentMute).where(CommentMute.member_id == member_id)
    )
    if mute is None:
        return None
    until = _aware(mute.until)
    return until if until > _now() else None


def ensure_may_comment(member_id: int) -> None:
    until = muted_until(member_id)
    if until is not None:
        raise_error(
            403,
            "COMMENTS_MUTED",
            f"You can comment again from {until.date().isoformat()}",
        )


def mute(member_id, days, reason, actor_id: int) -> CommentMute:
    if not isinstance(member_id, int) or isinstance(member_id, bool):
        raise_error(400, "VALIDATION_ERROR", "member_id is a number")
    if (
        not isinstance(days, int)
        or isinstance(days, bool)
        or not 1 <= days <= MAX_MUTE_DAYS
    ):
        raise_error(400, "VALIDATION_ERROR", f"days is 1 to {MAX_MUTE_DAYS}")
    if member_id == actor_id:
        raise_error(400, "VALIDATION_ERROR", "You cannot mute yourself")
    member = db.session.get(Member, member_id)
    if member is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
    text = _reason(reason)
    row = db.session.scalar(
        select(CommentMute).where(CommentMute.member_id == member_id)
    )
    if row is None:
        row = CommentMute(member_id=member_id)
        db.session.add(row)
    row.until = _now() + timedelta(days=days)
    row.by_id = actor_id
    row.reason = text
    row.created_at = _now()
    log_audit(
        actor_id=actor_id,
        action="mute_commenter",
        target_type="Member",
        target_id=member_id,
        target_label=f"{_name(member)} · {days} d",
    )
    return row


def unmute(member_id: int, actor_id: int) -> None:
    row = db.session.scalar(
        select(CommentMute).where(CommentMute.member_id == member_id)
    )
    if row is None:
        raise_error(404, "NOT_FOUND", "This member is not muted")
    member = db.session.get(Member, member_id)
    db.session.delete(row)
    log_audit(
        actor_id=actor_id,
        action="unmute_commenter",
        target_type="Member",
        target_id=member_id,
        target_label=_name(member),
    )


def active_mutes() -> list[dict]:
    rows = db.session.scalars(
        select(CommentMute)
        .where(CommentMute.until > _now())
        .order_by(CommentMute.until)
    ).all()
    ids = {r.member_id for r in rows} | {r.by_id for r in rows if r.by_id}
    members = (
        {
            m.id: m
            for m in db.session.scalars(select(Member).where(Member.id.in_(ids))).all()
        }
        if ids
        else {}
    )
    return [
        {
            "member_id": r.member_id,
            "member_name": _name(members.get(r.member_id)),
            "until": _aware(r.until).isoformat(),
            "reason": r.reason,
            "by_name": _name(members.get(r.by_id)) if r.by_id else None,
        }
        for r in rows
    ]
