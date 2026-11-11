"""Post service — business logic for posts, likes, and comments."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from hubra.core.notifications.services import notify_on_publish
from hubra.core.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.models.post import Post, PostComment, PostLike, PostRead
from hubra.core.modules import emit
from hubra.core.modules.events import POST_PUBLISHED
from hubra.core.timeutil import as_utc

# How far ahead a post can be scheduled.
SCHEDULE_MAX = timedelta(days=366)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check_times(publish_at: datetime | None, hide_after: datetime | None) -> None:
    """400 unless *publish_at* is within a year and *hide_after* comes after
    the post is out (and is still ahead)."""
    now = _now()
    if publish_at is not None and publish_at > now + SCHEDULE_MAX:
        raise_error(400, "VALIDATION_ERROR", "publish_at: at most a year ahead")
    if hide_after is not None and hide_after <= max(now, publish_at or now):
        raise_error(
            400, "VALIDATION_ERROR", "hide_after: must be after the post is out"
        )


def announce(post: Post, skip_member_id: int | None = None) -> None:
    """Tell the club a post is out: the bell (unless switched off) and
    ``post.published`` for webhooks, Discord and the messengers."""
    notify_on_publish(
        "posts",
        "info",
        "New post",
        post.title,
        skip_member_id=skip_member_id,
        link=f"/app/operations/posts/{post.id}",
    )
    emit(POST_PUBLISHED, post_id=post.id)


class PostService:
    """Operations on a single post."""

    @staticmethod
    def get(post_id: int) -> Post:
        """Return a post with author and likes eager-loaded, or raise 404."""
        post = db.session.scalar(
            select(Post)
            .where(Post.id == post_id)
            .options(selectinload(Post.author), selectinload(Post.likes))
        )
        if post is None:
            raise_error(404, "NOT_FOUND", f"Post {post_id} not found")
        return post  # type: ignore[return-value]

    @staticmethod
    def update(post: Post, data: dict, actor_id: int) -> Post:
        """Update allowed fields on a post."""
        if "language" in data or "translations" in data:
            from marshmallow import ValidationError

            from hubra.core.schemas.post import POST_BODY_MAX
            from hubra.core.services.content_languages import clean_translations

            language = data.get("language", post.language)
            try:
                data["translations"] = clean_translations(
                    data.get("translations", post.translations), language, POST_BODY_MAX
                )
            except ValidationError as exc:
                raise_error(400, "VALIDATION_ERROR", str(exc.messages))
        for field in (
            "title",
            "summary",
            "body",
            "group_id",
            "language",
            "translations",
            "must_read",
        ):
            if field in data:
                setattr(post, field, data[field])
        go_out = False
        if "publish_at" in data:
            if post.publish_at is None:
                raise_error(409, "POST_ALREADY_OUT", "The post is already out")
            when = data["publish_at"]
            if when is None or when <= _now():
                go_out = True
            else:
                post.publish_at = when
        if "hide_after" in data or "publish_at" in data:
            hide_after = data.get("hide_after", as_utc(post.hide_after))
            _check_times(None if go_out else as_utc(post.publish_at), hide_after)
            post.hide_after = hide_after
        if go_out:
            PostService.publish(post)

        log_audit(
            actor_id=actor_id,
            action="update_post",
            target_type="Post",
            target_id=post.id,
            target_label=post.title,
        )
        return post

    @staticmethod
    def publish(post: Post) -> None:
        """A scheduled post goes out now: at the top of the list, announced."""
        post.publish_at = None
        post.created_at = _now()
        db.session.flush()
        announce(post, skip_member_id=post.author_id)

    @staticmethod
    def confirm_read(post: Post, member_id: int) -> None:
        """The member read a must-read post (again is fine)."""
        if not post.must_read:
            raise_error(400, "NOT_MUST_READ", "This post asks for no confirmation")
        exists = db.session.scalar(
            select(PostRead.id).where(
                PostRead.post_id == post.id, PostRead.member_id == member_id
            )
        )
        if exists is None:
            db.session.add(PostRead(post_id=post.id, member_id=member_id))

    @staticmethod
    def read_status(post: Post) -> dict:
        """Who confirmed a must-read post and which active members have not."""
        reads = dict(
            db.session.execute(
                select(PostRead.member_id, PostRead.read_at).where(
                    PostRead.post_id == post.id
                )
            ).all()
        )
        confirmed, missing = [], []
        members = db.session.scalars(
            select(Member).where(Member.status == "active", Member.archived_at.is_(None))
        ).all()
        members.sort(key=lambda m: ((m.last_name or "").lower(), (m.first_name or "").lower(), m.id))
        for member in members:
            row = {"member_id": member.id, "name": f"{member.first_name} {member.last_name}"}
            if member.id in reads:
                confirmed.append({**row, "read_at": as_utc(reads[member.id]).isoformat()})
            else:
                missing.append(row)
        return {
            "confirmed": confirmed,
            "missing": missing,
            "reminder_sent_at": as_utc(post.read_reminder_sent_at).isoformat()
            if post.read_reminder_sent_at
            else None,
        }

    @staticmethod
    def delete(post_id: int, actor_id: int) -> None:
        """Delete a post."""
        post = PostService.get(post_id)

        log_audit(
            actor_id=actor_id,
            action="delete_post",
            target_type="Post",
            target_id=post.id,
            target_label=post.title,
        )
        db.session.delete(post)

    @staticmethod
    def like(post_id: int, member_id: int) -> None:
        """Add a like to a post. Raises 409 if already liked."""
        existing = db.session.scalar(
            select(func.count())
            .select_from(PostLike)
            .where(
                PostLike.post_id == post_id,
                PostLike.member_id == member_id,
            )
        )
        if existing:
            raise_error(
                409,
                "CONFLICT",
                f"Member {member_id} has already liked post {post_id}",
            )

        db.session.add(PostLike(post_id=post_id, member_id=member_id))

    @staticmethod
    def unlike(post_id: int, member_id: int) -> None:
        """Remove a like from a post. Raises 404 if not liked."""
        liked = db.session.scalar(
            select(func.count())
            .select_from(PostLike)
            .where(
                PostLike.post_id == post_id,
                PostLike.member_id == member_id,
            )
        )
        if not liked:
            raise_error(
                404,
                "NOT_FOUND",
                f"Member {member_id} has not liked post {post_id}",
            )

        db.session.execute(
            delete(PostLike).where(
                PostLike.post_id == post_id,
                PostLike.member_id == member_id,
            )
        )

    @staticmethod
    def add_comment(post_id: int, member_id: int, body: str) -> PostComment:
        """Add a comment to a post."""
        comment = PostComment(post_id=post_id, author_id=member_id, body=body)
        db.session.add(comment)
        db.session.flush()

        log_audit(
            actor_id=member_id,
            action="comment_post",
            target_type="Post",
            target_id=post_id,
            target_label=str(post_id),
        )
        return comment

    @staticmethod
    def get_comment(comment_id: int) -> PostComment:
        """Return a comment with author eager-loaded, or raise 404."""
        comment = db.session.scalar(
            select(PostComment)
            .where(PostComment.id == comment_id)
            .options(selectinload(PostComment.author))
        )
        if comment is None:
            raise_error(404, "NOT_FOUND", f"Comment {comment_id} not found")
        return comment  # type: ignore[return-value]

    @staticmethod
    def delete_comment(comment_id: int, actor_id: int) -> None:
        """Delete a comment."""
        comment = PostService.get_comment(comment_id)

        log_audit(
            actor_id=actor_id,
            action="delete_comment",
            target_type="PostComment",
            target_id=comment.id,
            target_label=comment.body[:60],
        )
        db.session.delete(comment)

    @staticmethod
    def list_comments(post_id: int) -> list[PostComment]:
        """Return all comments for a post, ordered by created_at."""
        return db.session.scalars(  # type: ignore[return-value]
            select(PostComment)
            .where(PostComment.post_id == post_id)
            .options(selectinload(PostComment.author))
            .order_by(PostComment.created_at)
        ).all()


class PostsService:
    """Operations on the post collection."""

    @staticmethod
    def list(may_see_hidden=None) -> list[Post]:
        """Posts newest first: those members see, plus scheduled and expired
        ones for which ``may_see_hidden(post)`` holds (who manages them)."""
        now = _now()
        query = (
            select(Post)
            .options(selectinload(Post.author), selectinload(Post.likes))
            .order_by(Post.publish_at.is_(None), Post.created_at.desc())
        )
        if may_see_hidden is None:
            return db.session.scalars(query.where(Post.shown(now))).all()  # type: ignore[return-value]
        return [
            post
            for post in db.session.scalars(query)
            if post.is_shown(now) or may_see_hidden(post)
        ]

    @staticmethod
    def create(data: dict, author_id: int) -> Post:
        """Create a new post. Returns the post."""
        publish_at = data.get("publish_at")
        if publish_at is not None and publish_at <= _now():
            publish_at = None
        _check_times(publish_at, data.get("hide_after"))
        post = Post(
            publish_at=publish_at,
            hide_after=data.get("hide_after"),
            author_id=author_id,
            title=data["title"],
            summary=data.get("summary"),
            body=data["body"],
            group_id=data.get("group_id"),
            language=data.get("language"),
            translations=data.get("translations"),
            must_read=data.get("must_read", False),
        )
        db.session.add(post)
        db.session.flush()

        if publish_at is None:
            announce(post, skip_member_id=author_id)

        log_audit(
            actor_id=author_id,
            action="create_post",
            target_type="Post",
            target_id=post.id,
            target_label=post.title,
        )

        db.session.refresh(post)
        return PostService.get(post.id)


def publish_due_posts(now: datetime | None = None) -> int:
    """Scheduled posts whose time has come go out (the beat, every few
    minutes). Returns how many."""
    now = now or _now()
    due = db.session.scalars(
        select(Post)
        .where(Post.publish_at.is_not(None), Post.publish_at <= now)
        .order_by(Post.publish_at, Post.id)
    ).all()
    for post in due:
        PostService.publish(post)
    return len(due)


def read_counts(post_ids: list[int], member_id: int | None) -> tuple[dict, set]:
    """Confirmations per post, and the posts *member_id* confirmed."""
    if not post_ids:
        return {}, set()
    counts = dict(
        db.session.execute(
            select(PostRead.post_id, func.count())
            .where(PostRead.post_id.in_(post_ids))
            .group_by(PostRead.post_id)
        ).all()
    )
    mine = set(
        db.session.scalars(
            select(PostRead.post_id).where(
                PostRead.post_id.in_(post_ids), PostRead.member_id == member_id
            )
        )
    )
    return counts, mine


def remind_unread(now: datetime | None = None) -> int:
    """One reminder to the active members who have not confirmed a
    must-read post N days after it went out (posts setting
    ``must_read_reminder_days``; 0: none). Returns how many were reminded."""
    from hubra.core.modules import get_config
    from hubra.core.notifications.services import notify_member

    days = int(get_config("posts").get("must_read_reminder_days", 7) or 0)
    if days <= 0:
        return 0
    now = now or _now()
    posts = db.session.scalars(
        select(Post)
        .where(Post.must_read.is_(True), Post.read_reminder_sent_at.is_(None))
        .where(Post.shown(now), Post.created_at <= now - timedelta(days=days))
        .order_by(Post.id)
    ).all()
    reminded = 0
    for post in posts:
        post.read_reminder_sent_at = now
        for row in PostService.read_status(post)["missing"]:
            notify_member(
                row["member_id"],
                "warning",
                "Please confirm you read this",
                post.title,
                link=f"/app/operations/posts/{post.id}",
                topic="posts",
            )
            reminded += 1
    return reminded
