"""Posts blueprint — CRUD, likes, and comments."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from hubra.core.auth.helpers import get_current_member
from marshmallow import ValidationError

from hubra.core.models.post import Post
from hubra.core.permissions import (
    _current_member,
    body_group,
    member_has_permission,
    permission_required,
    row_group,
    scoped_permission_keys,
)
from hubra.api.posts import moderation
from hubra.api.posts.services import PostService, PostsService, read_counts
from hubra.core.errors import api_error, raise_error, validation_error
from hubra.core.extensions import db, limiter
from hubra.core.schemas.post import (
    CommentCreateSchema,
    PostCommentSchema,
    PostCreateSchema,
    PostSchema,
    PostUpdateSchema,
)

posts_bp = Blueprint("posts_bp", __name__)

_posts_schema = PostSchema(many=True)
_create_schema = PostCreateSchema()
_update_schema = PostUpdateSchema()
_comment_schema = PostCommentSchema()
_comments_schema = PostCommentSchema(many=True)
_comment_create_schema = CommentCreateSchema()


_MODERATE = "posts.posts.moderate"


# The group a post is for: a role held for that group manages its posts.
_post_group = row_group(Post, "post_id")


def _is_author_or_moderator(item, member_id: int) -> bool:
    """The author of a post or comment, an admin, or a member whose role may
    moderate (``posts.posts.moderate``)."""
    if item.author_id == member_id:
        return True
    return member_has_permission(_current_member(), _MODERATE)


def _may_moderate(post: Post) -> bool:
    """Hide others' comments, keep reported ones: a club-wide moderator, or
    one whose role for the post's group may moderate."""
    if member_has_permission(_current_member(), _MODERATE):
        return True
    return _MODERATE in _group_keys(post.group_id)


def _group_keys(group_id: int | None) -> set[str]:
    """The keys the current member holds for *group_id* only."""
    if group_id is None:
        return set()
    return set(scoped_permission_keys(_current_member()).get(group_id, ()))


def _may_manage(post: Post, member_id: int, action: str) -> bool:
    """The author, a club-wide moderator, or a member whose role for the
    post's group may update/delete or moderate (the youth team's lead)."""
    if _is_author_or_moderator(post, member_id):
        return True
    keys = _group_keys(post.group_id)
    return f"posts.posts.{action}" in keys or _MODERATE in keys


def _may_move(post: Post, member_id: int, data: dict) -> bool:
    """A member who manages the post only through a role for its group keeps
    it in a group they manage."""
    if "group_id" not in data or data["group_id"] == post.group_id:
        return True
    if g.get("permission_scope") != "group" and _is_author_or_moderator(post, member_id):
        return True
    keys = _group_keys(data["group_id"])
    return "posts.posts.update" in keys or _MODERATE in keys


def _may_see_hidden(post: Post) -> bool:
    """A scheduled or expired post: only those who may edit it see it."""
    return _may_manage(post, get_current_member().id, "update")


def _shown_post(post_id: int) -> Post:
    """The post, or 404 when it is scheduled or expired and the member may
    not edit it (to them it does not exist)."""
    post = PostService.get(post_id)
    if not post.is_shown(datetime.now(timezone.utc)) and not _may_see_hidden(post):
        raise_error(404, "NOT_FOUND", f"Post {post_id} not found")
    return post


def _dump(posts: list[Post]) -> list[dict]:
    """Posts as JSON, with how many confirmed a must-read post and whether
    the current member did."""
    counts, mine = read_counts(
        [p.id for p in posts if p.must_read], get_current_member().id
    )
    out = _posts_schema.dump(posts)
    for row in out:
        row["read_count"] = counts.get(row["id"], 0)
        row["read_by_me"] = row["id"] in mine
    return out


def _dump_one(post: Post) -> dict:
    return _dump([post])[0]


# ── GET /posts ────────────────────────────────────────────────────────────────


@posts_bp.get("/")
@permission_required("posts", "read", "View posts")
def list_posts():
    return jsonify(_dump(PostsService.list(_may_see_hidden))), 200


# ── Machine translation for the editor ──────────────────────────────────────


@posts_bp.get("/translate")
@permission_required("posts", "create", "Create posts")
def translation_available():
    """Whether the editor offers "Translate" (the platform set up DeepL)."""
    from hubra.core.services import machine_translation
    from hubra.core.services.content_languages import CONTENT_LANGUAGES

    return jsonify(
        {"available": machine_translation.available(), "languages": list(CONTENT_LANGUAGES)}
    ), 200


@posts_bp.post("/translate")
@permission_required("posts", "create", "Create posts")
@limiter.limit("30 per minute")
def translate_post_text():
    """Title, summary and text in another language, to pre-fill the editor."""
    from hubra.core.services import machine_translation
    from hubra.core.services.content_languages import CONTENT_LANGUAGES
    from hubra.core.schemas.post import POST_BODY_MAX

    body = request.get_json(silent=True) or {}
    target = body.get("target")
    source = body.get("source")
    if target not in CONTENT_LANGUAGES or (source and source not in CONTENT_LANGUAGES):
        return api_error("VALIDATION_ERROR", "Unknown language", 400)
    texts = [body.get("title") or "", body.get("summary") or "", body.get("body") or ""]
    if not all(isinstance(t, str) for t in texts) or len(texts[0]) > 255 or (
        len(texts[2]) > POST_BODY_MAX or len(texts[1]) > 500
    ):
        return api_error("VALIDATION_ERROR", "title, summary and body as text", 400)
    title, summary, text = machine_translation.translate(texts, target, source)
    return jsonify({"title": title[:255], "summary": summary[:500] or None, "body": text}), 200


# ── GET /posts/channels ──────────────────────────────────────────────────────


@posts_bp.get("/channels")
@permission_required("posts", "create", "Create posts")
def list_channels():
    """Where a post can be announced: ``app`` and each module that posts
    them (Discord, Messengers), for the editor's "Send to"."""
    from .services import channels

    return jsonify(channels()), 200


# ── GET /posts/<id> ───────────────────────────────────────────────────────────


@posts_bp.get("/<int:post_id>")
@permission_required("posts", "read", "View posts")
def get_post(post_id: int):
    post = _shown_post(post_id)
    return jsonify(_dump_one(post)), 200


# ── POST /posts ───────────────────────────────────────────────────────────────


@posts_bp.post("/")
@permission_required("posts", "create", "Create posts", scope=body_group)
def create_post():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return validation_error(exc)

    post = PostsService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_dump_one(post)), 201


# ── PATCH /posts/<id> ─────────────────────────────────────────────────────────


@posts_bp.patch("/<int:post_id>")
@permission_required("posts", "update", "Update posts", scope=_post_group)
def update_post(post_id: int):
    post = PostService.get(post_id)
    member_id = get_current_member().id

    if not _may_manage(post, member_id, "update"):
        return api_error("FORBIDDEN", "You can only edit your own posts", 403)

    body = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return validation_error(exc)
    if not _may_move(post, member_id, data):
        return api_error(
            "GROUP_SCOPE", "You can only move this to a group you manage", 403
        )

    PostService.update(post, data, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(post)
    return jsonify(_dump_one(post)), 200


# ── DELETE /posts/<id> ────────────────────────────────────────────────────────


@posts_bp.delete("/<int:post_id>")
@permission_required("posts", "delete", "Delete posts", scope=_post_group)
def delete_post(post_id: int):
    post = PostService.get(post_id)
    member_id = get_current_member().id

    if not _may_manage(post, member_id, "delete"):
        return api_error("FORBIDDEN", "You can only delete your own posts", 403)

    PostService.delete(post_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── Must-read: confirm, and who has ──────────────────────────────────────────


@posts_bp.post("/<int:post_id>/read")
@permission_required("posts", "read", "View posts")
def confirm_read(post_id: int):
    """The member confirms they read a must-read post."""
    post = _shown_post(post_id)
    PostService.confirm_read(post, get_current_member().id)
    db.session.commit()
    return jsonify(_dump_one(post)), 200


@posts_bp.get("/<int:post_id>/reads")
@permission_required("posts", "read", "View posts")
def read_status(post_id: int):
    """Who confirmed a must-read post and who has not: for those who may
    edit it."""
    post = PostService.get(post_id)
    if not _may_manage(post, get_current_member().id, "update"):
        return api_error("FORBIDDEN", "Only those who manage the post see this", 403)
    return jsonify(PostService.read_status(post)), 200


# ── POST /posts/<id>/like ─────────────────────────────────────────────────────


@posts_bp.post("/<int:post_id>/like")
@permission_required("posts", "like", "Like posts")
def like_post(post_id: int):
    _shown_post(post_id)  # 404 if not found
    member_id = get_current_member().id

    PostService.like(post_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    post = PostService.get(post_id)
    return jsonify(_dump_one(post)), 200


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
    return jsonify(_dump_one(post)), 200


# ── GET /posts/<id>/comments ──────────────────────────────────────────────────


@posts_bp.get("/<int:post_id>/comments")
@permission_required("posts", "read", "View posts")
def list_comments(post_id: int):
    post = _shown_post(post_id)  # 404 if not found
    comments = PostService.list_comments(post_id)
    return jsonify(_dump_comments(post, comments)), 200


def _dump_comments(post: Post, comments: list) -> list[dict]:
    """Comments as JSON. A hidden comment keeps its place but not its text,
    except for moderators; moderators also see how often each was reported."""
    me = get_current_member().id
    moderator = _may_moderate(post)
    ids = [c.id for c in comments]
    counts = moderation.report_counts(ids) if moderator else {}
    mine = moderation.reported_by(me, ids)
    out = _comments_schema.dump(comments)
    for row, comment in zip(out, comments, strict=True):
        hidden = comment.hidden_at is not None
        row["hidden"] = hidden
        row.pop("hidden_by_id", None)
        if hidden and not moderator:
            row["body"] = ""
        row["reported_by_me"] = comment.id in mine
        if moderator:
            row["reports"] = counts.get(comment.id, 0)
    return out


# ── POST /posts/<id>/comments ─────────────────────────────────────────────────


@posts_bp.post("/<int:post_id>/comments")
@permission_required("posts", "comment", "Comment on posts")
def add_comment(post_id: int):
    _shown_post(post_id)  # 404 if not found
    member_id = get_current_member().id
    moderation.ensure_may_comment(member_id)

    body = request.get_json(silent=True) or {}
    try:
        data = _comment_create_schema.load(body)
    except ValidationError as exc:
        return validation_error(exc)

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

    if not _is_author_or_moderator(comment, member_id):
        return api_error("FORBIDDEN", "You can only delete your own comments", 403)

    PostService.delete_comment(comment_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── Comment moderation (moderation.py) ────────────────────────────────────────


def _comment_on(post_id: int, comment_id: int):
    post = _shown_post(post_id)
    comment = PostService.get_comment(comment_id)
    if comment.post_id != post_id:
        raise_error(
            404, "NOT_FOUND", f"Comment {comment_id} not found on post {post_id}"
        )
    return post, comment


def _moderated_comment(post_id: int, comment_id: int):
    post, comment = _comment_on(post_id, comment_id)
    if not _may_moderate(post):
        raise_error(403, "FORBIDDEN", "Only moderators can do this")
    return comment


def _one_comment(post_id: int, comment) -> dict:
    db.session.refresh(comment)
    return _dump_comments(PostService.get(post_id), [comment])[0]


@posts_bp.post("/<int:post_id>/comments/<int:comment_id>/report")
@permission_required("posts", "read", "View posts")
@limiter.limit("30 per hour")
def report_comment(post_id: int, comment_id: int):
    """Report a comment to the moderators (``{reason?}``)."""
    _, comment = _comment_on(post_id, comment_id)
    body = request.get_json(silent=True) or {}
    moderation.report(comment, get_current_member().id, body.get("reason"))
    db.session.commit()
    return jsonify(_one_comment(post_id, comment)), 200


@posts_bp.post("/<int:post_id>/comments/<int:comment_id>/hide")
@permission_required("posts", "read", "View posts")
def hide_comment(post_id: int, comment_id: int):
    comment = _moderated_comment(post_id, comment_id)
    moderation.set_hidden(comment, True, get_current_member().id)
    db.session.commit()
    return jsonify(_one_comment(post_id, comment)), 200


@posts_bp.post("/<int:post_id>/comments/<int:comment_id>/show")
@permission_required("posts", "read", "View posts")
def show_comment(post_id: int, comment_id: int):
    comment = _moderated_comment(post_id, comment_id)
    moderation.set_hidden(comment, False, get_current_member().id)
    db.session.commit()
    return jsonify(_one_comment(post_id, comment)), 200


@posts_bp.delete("/<int:post_id>/comments/<int:comment_id>/reports")
@permission_required("posts", "read", "View posts")
def keep_comment(post_id: int, comment_id: int):
    """A moderator keeps a reported comment: its reports are done."""
    comment = _moderated_comment(post_id, comment_id)
    moderation.clear_reports(comment, get_current_member().id)
    db.session.commit()
    return jsonify(_one_comment(post_id, comment)), 200


@posts_bp.get("/comments/reports")
@permission_required("posts", "moderate", "Moderate posts and comments")
def list_reported_comments():
    """Reported comments that are still shown, for the moderation list."""
    return jsonify({"items": moderation.open_reports(_may_moderate)}), 200


@posts_bp.get("/comments/mutes")
@permission_required("posts", "moderate", "Moderate posts and comments")
def list_comment_mutes():
    return jsonify({"items": moderation.active_mutes()}), 200


@posts_bp.post("/comments/mutes")
@permission_required("posts", "moderate", "Moderate posts and comments")
def mute_commenter():
    """``{member_id, days, reason?}``: the member may not comment for *days*."""
    body = request.get_json(silent=True) or {}
    moderation.mute(
        body.get("member_id"),
        body.get("days"),
        body.get("reason"),
        get_current_member().id,
    )
    db.session.commit()
    return jsonify({"items": moderation.active_mutes()}), 200


@posts_bp.delete("/comments/mutes/<int:member_id>")
@permission_required("posts", "moderate", "Moderate posts and comments")
def unmute_commenter(member_id: int):
    moderation.unmute(member_id, get_current_member().id)
    db.session.commit()
    return jsonify({"items": moderation.active_mutes()}), 200
