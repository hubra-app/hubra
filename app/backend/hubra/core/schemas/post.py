"""Marshmallow schemas for Post, PostComment, likes, and comments."""

from __future__ import annotations

from datetime import timezone

from marshmallow import EXCLUDE, RAISE, fields, post_load, validate
from sqlalchemy import func, select

from hubra.core.extensions import db, ma
from hubra.core.models.post import Post, PostComment
from hubra.core.schemas.counts import cached_count, clear_counts, prime_counts
from hubra.core.schemas.group import valid_group_id
from hubra.core.services.content_languages import CONTENT_LANGUAGES, clean_translations

_COMMENT_COUNT = "_comment_count"


class PostCommentSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = PostComment
        load_instance = True
        unknown = EXCLUDE
        exclude = ("post", "author")

    # Auto schemas leave foreign keys out; the club app needs these.
    post_id = fields.Int(dump_only=True)
    author_id = fields.Int(dump_only=True, allow_none=True)
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

    # Auto schemas leave foreign keys out; the club app needs it.
    author_id = fields.Int(dump_only=True, allow_none=True)
    group_id = fields.Int(dump_only=True, allow_none=True)
    like_count = fields.Method("get_like_count", dump_only=True)
    like_member_ids = fields.Method("get_like_member_ids", dump_only=True)
    comment_count = fields.Method("get_comment_count", dump_only=True)
    author_name = fields.Method("get_author_name", dump_only=True)
    author_avatar_color = fields.Method("get_author_avatar_color", dump_only=True)

    def dump(self, obj, *, many=None):
        if not (self.many if many is None else many):
            return super().dump(obj, many=many)
        posts = list(obj)
        prime_counts(posts, _COMMENT_COUNT, PostComment.post_id)
        try:
            return super().dump(posts, many=many)
        finally:
            clear_counts(posts, _COMMENT_COUNT)

    def get_like_count(self, obj):
        return len(obj.likes)

    def get_like_member_ids(self, obj):
        return [like.member_id for like in obj.likes]

    def get_comment_count(self, obj):
        return cached_count(
            obj,
            _COMMENT_COUNT,
            lambda: db.session.scalar(
                select(func.count()).where(PostComment.post_id == obj.id)
            ),
        )

    def get_author_name(self, obj):
        if obj.author is None:
            return None
        return f"{obj.author.first_name} {obj.author.last_name}"

    def get_author_avatar_color(self, obj):
        return obj.author.avatar_color if obj.author else None


# ── Write schemas ─────────────────────────────────────────────────────────────


# Markdown body; generous for long announcements, small enough that one
# post cannot bloat every list response.
POST_BODY_MAX = 100_000


class PostCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    summary = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=500)
    )
    body = fields.Str(required=True, validate=validate.Length(min=1, max=POST_BODY_MAX))
    group_id = fields.Int(allow_none=True, load_default=None, validate=valid_group_id)
    language = fields.Str(
        allow_none=True, load_default=None, validate=validate.OneOf(CONTENT_LANGUAGES)
    )
    translations = fields.Dict(allow_none=True, load_default=None)
    # Scheduled: out at this time (empty or past: now). Expiring: hidden
    # from members after this time.
    publish_at = fields.AwareDateTime(
        allow_none=True, load_default=None, default_timezone=timezone.utc
    )
    hide_after = fields.AwareDateTime(
        allow_none=True, load_default=None, default_timezone=timezone.utc
    )

    @post_load
    def _translations(self, data, **_kwargs):
        data["translations"] = clean_translations(
            data.get("translations"), data.get("language"), POST_BODY_MAX
        )
        return data


class PostUpdateSchema(ma.Schema):
    """PATCH — all fields optional."""

    class Meta:
        unknown = RAISE

    title = fields.Str(validate=validate.Length(min=1, max=255))
    summary = fields.Str(allow_none=True, validate=validate.Length(max=500))
    body = fields.Str(validate=validate.Length(min=1, max=POST_BODY_MAX))
    group_id = fields.Int(allow_none=True, validate=valid_group_id)
    language = fields.Str(allow_none=True, validate=validate.OneOf(CONTENT_LANGUAGES))
    translations = fields.Dict(allow_none=True)
    publish_at = fields.AwareDateTime(allow_none=True, default_timezone=timezone.utc)
    hide_after = fields.AwareDateTime(allow_none=True, default_timezone=timezone.utc)


class CommentCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    body = fields.Str(required=True, validate=validate.Length(min=1, max=2000))
