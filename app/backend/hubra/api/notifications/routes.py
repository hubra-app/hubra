"""Notifications blueprint — per-member in-app notifications."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from hubra.api.auth.helpers import get_current_member
from hubra.core.extensions import db
from hubra.core.schemas.notification import NotificationSchema
from hubra.api.notifications.services import (
    NotificationService,
    NotificationsService,
)

notifications_bp = Blueprint("notifications_bp", __name__)

_schema = NotificationSchema()
_many_schema = NotificationSchema(many=True)


# ── POST /notifications ────────────────────────────────────────────────────────


@notifications_bp.post("/")
@jwt_required()
def create_notifications():
    return "", 204


# ── GET /notifications ────────────────────────────────────────────────────────


@notifications_bp.get("/")
@jwt_required()
def list_notifications():
    member_id = get_current_member().id
    result = NotificationsService.list(member_id)
    return jsonify(
        {
            "data": _many_schema.dump(result["data"]),
            "meta": result["meta"],
        }
    ), 200


# ── PATCH /notifications/<id>/read ────────────────────────────────────────────


@notifications_bp.patch("/<int:notification_id>/read")
@jwt_required()
def mark_read(notification_id: int):
    member_id = get_current_member().id
    notification = NotificationService.get(notification_id, member_id)
    NotificationService.mark_read(notification)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_schema.dump(notification)), 200


# ── POST /notifications/read-all ──────────────────────────────────────────────


@notifications_bp.post("/read-all")
@jwt_required()
def mark_all_read():
    member_id = get_current_member().id
    NotificationsService.mark_all_read(member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({"ok": True}), 200


# ── DELETE /notifications ─────────────────────────────────────────────────────


@notifications_bp.delete("/")
@jwt_required()
def delete_all_notifications():
    """Clear the caller's own notifications; ``?read=1`` keeps unread ones."""
    member_id = get_current_member().id
    read_only = request.args.get("read") in ("1", "true")
    deleted = NotificationsService.delete_all(member_id, read_only=read_only)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({"deleted": deleted}), 200


# ── DELETE /notifications/<id> ────────────────────────────────────────────────


@notifications_bp.delete("/<int:notification_id>")
@jwt_required()
def delete_notification(notification_id: int):
    member_id = get_current_member().id
    NotificationService.delete(notification_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204
