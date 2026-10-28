"""Post, PostLike, and PostComment models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
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
