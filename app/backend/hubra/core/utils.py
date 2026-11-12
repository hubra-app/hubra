"""Shared utilities for API blueprints."""

from __future__ import annotations

import re



from hubra.core.extensions import db
from hubra.core.models.audit import AuditEntry


def escape_like(value: str) -> str:
    """Escape SQL LIKE wildcard characters in user-supplied input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def id_from_body(value, field: str) -> int | None:
    """An id sent in a JSON body: None stays None, a whole number (or its
    digits as text) becomes an int, anything else is a 400."""
    from hubra.core.errors import raise_error

    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    raise_error(400, "VALIDATION_ERROR", f"{field} must be an id")


def log_audit(actor_id, action, target_type, target_id, target_label, color=None):
    from hubra.core.models.member import (
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
    from hubra.core.auth.api_tokens import audit_label

    via_token = audit_label()
    if via_token and actor_name:
        # Written through an API token: say which one.
        actor_name = (actor_name + via_token)[:255]
    if target_label is not None and len(target_label) > 255:
        # Labels built from several names or addresses can outgrow the
        # column; the entry must not fail the change it records.
        target_label = target_label[:254] + "…"
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


_PLAIN_NUMBER = re.compile(r"[+-]?[\d\s/().'-]*")


def csv_safe(value):
    """Neutralise spreadsheet formulas in a CSV cell (CWE-1236).

    Excel and LibreOffice run a cell that starts with = + - @ (or a tab or
    carriage return) as a formula. Such text gets a leading apostrophe;
    plain numbers like +41 79 123 45 67 or -12.50 stay as they are.
    """
    if not isinstance(value, str) or not value:
        return value
    if value[0] in "=@\t\r" or (
        value[0] in "+-" and not _PLAIN_NUMBER.fullmatch(value)
    ):
        return "'" + value
    return value


def public_api_base() -> str:
    """The API's public origin for addresses outside services keep (OAuth
    issuer, sign-in callbacks): API_PUBLIC_URL.

    Without it the request's own host stands in, which the client chooses;
    production warns at start-up (ProductionConfig.validate) so it gets set.
    """
    from flask import current_app, request

    base = current_app.config.get("API_PUBLIC_URL") or request.host_url
    return base.rstrip("/")
