"""Notifications blueprint — per-member in-app notifications."""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from vollbuild.api.auth.helpers import get_current_member
from vollbuild.extensions import db
from vollbuild.core.schemas.notification import NotificationSchema
from vollbuild.api.notifications.services import (
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
