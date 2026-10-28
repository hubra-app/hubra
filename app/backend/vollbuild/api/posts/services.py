"""Post service — business logic for posts, likes, and comments."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from vollbuild.api.notifications.services import notify_all_active
from vollbuild.api.utils import log_audit
from vollbuild.errors import raise_error
from vollbuild.extensions import db
from vollbuild.core.models.post import Post, PostComment, PostLike


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
        for field in ("title", "summary", "body"):
            if field in data:
                setattr(post, field, data[field])

        log_audit(
            actor_id=actor_id,
            action="update_post",
            target_type="Post",
            target_id=post.id,
            target_label=post.title,
        )
        return post

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
    def list() -> list[Post]:
        """Return all posts ordered by created_at descending."""
        return db.session.scalars(  # type: ignore[return-value]
            select(Post)
            .options(selectinload(Post.author), selectinload(Post.likes))
            .order_by(Post.created_at.desc())
        ).all()

    @staticmethod
    def create(data: dict, author_id: int) -> Post:
        """Create a new post. Returns the post."""
        post = Post(
            author_id=author_id,
            title=data["title"],
            summary=data.get("summary"),
            body=data["body"],
        )
        db.session.add(post)
        db.session.flush()

        notify_all_active("info", "New post", post.title, skip_member_id=author_id)

        log_audit(
            actor_id=author_id,
            action="create_post",
            target_type="Post",
            target_id=post.id,
            target_label=post.title,
        )

        db.session.refresh(post)
        return PostService.get(post.id)
