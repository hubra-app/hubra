"""Shared utilities for API blueprints."""

from __future__ import annotations

import math

from flask import jsonify

from vollbuild.extensions import db
from vollbuild.core.models.audit import AuditEntry


def escape_like(value: str) -> str:
    """Escape SQL LIKE wildcard characters in user-supplied input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def success_response(data, meta=None, status=200):
    """Return a standardized JSON envelope: {"data": ..., "meta": ...}."""
    return jsonify({"data": data, "meta": meta or {}}), status


def paginated_response(items, total, page, per_page):
    """Return a success_response with pagination meta."""
    pages = math.ceil(total / per_page) if per_page else 1
    return success_response(
        data=items,
        meta={"total": total, "page": page, "per_page": per_page, "pages": pages},
    )


def log_audit(actor_id, action, target_type, target_id, target_label, color=None):
    from vollbuild.core.models.member import (
        Member,
    )  # lazy import to avoid circular deps

    actor_name = None
    actor_avatar_color = None
    safe_actor_id = None
    if actor_id is not None:
        actor = db.session.get(Member, actor_id)
        if actor:
            actor_name = f"{actor.first_name} {actor.last_name}"
            actor_avatar_color = actor.avatar_color
            safe_actor_id = actor_id
    db.session.add(
        AuditEntry(
            actor_id=safe_actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            actor_name=actor_name,
            actor_avatar_color=actor_avatar_color,
            color=color,
        )
    )
