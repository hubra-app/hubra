"""Marshmallow schemas for Post, PostComment, likes, and comments."""

from __future__ import annotations

from marshmallow import EXCLUDE, RAISE, fields, validate
from sqlalchemy import func, select

from vollbuild.extensions import db, ma
from vollbuild.core.models.post import Post, PostComment


class PostCommentSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = PostComment
        load_instance = True
        unknown = EXCLUDE
        exclude = ("post", "author")

    author_name = fields.Method("get_author_name", dump_only=True)
    author_avatar_color = fields.Method("get_author_avatar_color", dump_only=True)

    def get_author_name(self, obj):
        if obj.author is None:
            return None
        return f"{obj.author.first_name} {obj.author.last_name}"

    def get_author_avatar_color(self, obj):
        return obj.author.avatar_color if obj.author else None


class PostSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Post
        load_instance = True
        unknown = EXCLUDE
        exclude = ("likes", "comments", "author")

    like_count = fields.Method("get_like_count", dump_only=True)
    like_member_ids = fields.Method("get_like_member_ids", dump_only=True)
    comment_count = fields.Method("get_comment_count", dump_only=True)
    author_name = fields.Method("get_author_name", dump_only=True)
    author_avatar_color = fields.Method("get_author_avatar_color", dump_only=True)

    def get_like_count(self, obj):
        return len(obj.likes)

    def get_like_member_ids(self, obj):
        return [like.member_id for like in obj.likes]

    def get_comment_count(self, obj):
        return (
            db.session.scalar(select(func.count()).where(PostComment.post_id == obj.id))
            or 0
        )

    def get_author_name(self, obj):
        if obj.author is None:
            return None
        return f"{obj.author.first_name} {obj.author.last_name}"

    def get_author_avatar_color(self, obj):
        return obj.author.avatar_color if obj.author else None


# ── Write schemas ─────────────────────────────────────────────────────────────


class PostCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    summary = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=500)
    )
    body = fields.Str(required=True, validate=validate.Length(min=1))


class PostUpdateSchema(ma.Schema):
    """PATCH — all fields optional."""

    class Meta:
        unknown = RAISE

    title = fields.Str(validate=validate.Length(min=1, max=255))
    summary = fields.Str(allow_none=True, validate=validate.Length(max=500))
    body = fields.Str(validate=validate.Length(min=1))


class CommentCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    body = fields.Str(required=True, validate=validate.Length(min=1, max=2000))
