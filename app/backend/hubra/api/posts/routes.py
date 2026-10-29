"""Posts blueprint — CRUD, likes, and comments."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from hubra.api.auth.helpers import get_current_member
from marshmallow import ValidationError

from hubra.api.permissions import (
    _current_member,
    _get_member_permission_keys,
    member_is_admin,
    permission_required,
)
from hubra.api.posts.services import PostService, PostsService
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.schemas.post import (
    CommentCreateSchema,
    PostCommentSchema,
    PostCreateSchema,
    PostSchema,
    PostUpdateSchema,
)

posts_bp = Blueprint("posts_bp", __name__)

_post_schema = PostSchema()
_posts_schema = PostSchema(many=True)
_create_schema = PostCreateSchema()
_update_schema = PostUpdateSchema()
_comment_schema = PostCommentSchema()
_comments_schema = PostCommentSchema(many=True)
_comment_create_schema = CommentCreateSchema()


def _is_author_or_admin(post, member_id: int) -> bool:
    """Return True if *member_id* is the post author or the member is admin."""
    if post.author_id == member_id:
        return True
    member = _current_member()
    if member is not None and member_is_admin(member):
        return True
    return False


# ── GET /posts ────────────────────────────────────────────────────────────────


@posts_bp.get("/")
@permission_required("posts", "read", "View posts")
def list_posts():
    return jsonify(_posts_schema.dump(PostsService.list())), 200


# ── GET /posts/<id> ───────────────────────────────────────────────────────────


@posts_bp.get("/<int:post_id>")
@permission_required("posts", "read", "View posts")
def get_post(post_id: int):
    post = PostService.get(post_id)
    return jsonify(_post_schema.dump(post)), 200


# ── POST /posts ───────────────────────────────────────────────────────────────


@posts_bp.post("/")
@permission_required("posts", "create", "Create posts")
def create_post():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    post = PostsService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_post_schema.dump(post)), 201


# ── PATCH /posts/<id> ─────────────────────────────────────────────────────────


@posts_bp.patch("/<int:post_id>")
@permission_required("posts", "update", "Update posts")
def update_post(post_id: int):
    post = PostService.get(post_id)
    member_id = get_current_member().id

    if not _is_author_or_admin(post, member_id):
        return api_error("FORBIDDEN", "You can only edit your own posts", 403)

    body = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    PostService.update(post, data, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(post)
    return jsonify(_post_schema.dump(post)), 200


# ── DELETE /posts/<id> ────────────────────────────────────────────────────────


@posts_bp.delete("/<int:post_id>")
@permission_required("posts", "delete", "Delete posts")
def delete_post(post_id: int):
    post = PostService.get(post_id)
    member_id = get_current_member().id

    if not _is_author_or_admin(post, member_id):
        return api_error("FORBIDDEN", "You can only delete your own posts", 403)

    PostService.delete(post_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /posts/<id>/like ─────────────────────────────────────────────────────


@posts_bp.post("/<int:post_id>/like")
@permission_required("posts", "like", "Like posts")
def like_post(post_id: int):
    PostService.get(post_id)  # 404 if not found
    member_id = get_current_member().id

    PostService.like(post_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    post = PostService.get(post_id)
    return jsonify(_post_schema.dump(post)), 200


# ── DELETE /posts/<id>/like ───────────────────────────────────────────────────


@posts_bp.delete("/<int:post_id>/like")
@permission_required("posts", "like", "Like posts")
def unlike_post(post_id: int):
    member_id = get_current_member().id

    PostService.unlike(post_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    post = PostService.get(post_id)
    return jsonify(_post_schema.dump(post)), 200


# ── GET /posts/<id>/comments ──────────────────────────────────────────────────


@posts_bp.get("/<int:post_id>/comments")
@permission_required("posts", "read", "View posts")
def list_comments(post_id: int):
    PostService.get(post_id)  # 404 if not found
    comments = PostService.list_comments(post_id)
    return jsonify(_comments_schema.dump(comments)), 200


# ── POST /posts/<id>/comments ─────────────────────────────────────────────────


@posts_bp.post("/<int:post_id>/comments")
@permission_required("posts", "comment", "Comment on posts")
def add_comment(post_id: int):
    PostService.get(post_id)  # 404 if not found
    member_id = get_current_member().id

    body = request.get_json(silent=True) or {}
    try:
        data = _comment_create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    comment = PostService.add_comment(post_id, member_id, data["body"])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(comment)
    return jsonify(_comment_schema.dump(comment)), 201


# ── DELETE /posts/<id>/comments/<comment_id> ──────────────────────────────────


@posts_bp.delete("/<int:post_id>/comments/<int:comment_id>")
@permission_required("posts", "comment", "Comment on posts")
def delete_comment(post_id: int, comment_id: int):
    comment = PostService.get_comment(comment_id)
    member_id = get_current_member().id

    if comment.post_id != post_id:
        return api_error(
            "NOT_FOUND", f"Comment {comment_id} not found on post {post_id}", 404
        )

    # Whoever may delete posts may also remove a comment (moderation).
    actor = _current_member()
    if (
        comment.author_id != member_id
        and not member_is_admin(actor)
        and "posts.posts.delete" not in _get_member_permission_keys(actor)
    ):
        return api_error("FORBIDDEN", "You can only delete your own comments", 403)

    PostService.delete_comment(comment_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204
