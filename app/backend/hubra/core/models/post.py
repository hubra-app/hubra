"""Post, PostLike, and PostComment models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


class Post(db.Model):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # The language the post was written in ("de", "fr", "it", "en"); None:
    # not said (older posts). ``translations`` holds the other languages:
    # {"fr": {"title": ..., "summary": ..., "body": ...}}. Members see the
    # one for their language, else the original.
    language: Mapped[str | None] = mapped_column(db.String(5), nullable=True)
    translations: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    # The group the post is for: a role held for that group may manage it.
    group_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Scheduled: members see the post from this time on; until then only
    # those who manage it do. Cleared when the post goes out (then
    # ``created_at`` becomes that time, so it lands at the top).
    publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # Members no longer see the post after this (an outdated notice).
    hide_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    author: Mapped["Member"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[author_id]
    )
    likes: Mapped[list["PostLike"]] = relationship(
        "PostLike", back_populates="post", cascade="all, delete-orphan"
    )
    comments: Mapped[list["PostComment"]] = relationship(
        "PostComment",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostComment.created_at",
    )

    @staticmethod
    def shown(now: datetime):
        """SQL clause: posts members see at *now* (out and not expired)."""
        return Post.publish_at.is_(None) & (
            Post.hide_after.is_(None) | (Post.hide_after > now)
        )

    def is_shown(self, now: datetime) -> bool:
        """Whether members see the post at *now* (``shown`` in Python)."""
        from hubra.core.timeutil import as_utc

        return self.publish_at is None and (
            self.hide_after is None or as_utc(self.hide_after) > now
        )

    def __repr__(self) -> str:
        return f"<Post id={self.id} title={self.title!r:.40}>"


class PostLike(db.Model):
    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint("post_id", "member_id", name="uq_post_like_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    post: Mapped["Post"] = relationship("Post", back_populates="likes")
    member: Mapped["Member"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[member_id]
    )

    def __repr__(self) -> str:
        return (
            f"<PostLike id={self.id} post_id={self.post_id} member_id={self.member_id}>"
        )


class PostComment(db.Model):
    __tablename__ = "post_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    post: Mapped["Post"] = relationship("Post", back_populates="comments")
    author: Mapped["Member"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[author_id]
    )

    def __repr__(self) -> str:
        return f"<PostComment id={self.id} post_id={self.post_id}>"
