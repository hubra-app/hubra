"""Members blueprint — HTTP layer only. Business logic lives in services.py."""

from __future__ import annotations


import csv
import io

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import jwt_required
from hubra.api.auth.helpers import get_current_member
from marshmallow import ValidationError

from hubra.api.members.services import (
    MemberService,
    MembersService,
)
from hubra.api.permissions import (
    permission_required,
    can_update,
    filter_updatable_fields,
)
from hubra.api.utils import log_audit
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db
from hubra.core.schemas.member import (
    MemberCreateSchema,
    MemberSchema,
    MemberUpdateSchema,
)

members_bp = Blueprint("members_bp", __name__)

_member_schema = MemberSchema()
_members_schema = MemberSchema(many=True)
_create_schema = MemberCreateSchema()
_update_schema = MemberUpdateSchema()


# What the club's admins write about a member, and who to call in an
# emergency: only for those who may edit members, and the member themselves.
_ADMIN_ONLY_FIELDS = ("notes", "emergency_contact")


def _viewer_sees_admin_fields() -> bool:
    from hubra.api.permissions import _get_member_permission_keys, member_is_admin

    viewer = get_current_member()
    return member_is_admin(viewer) or (
        "members.members.update" in _get_member_permission_keys(viewer)
    )


def for_viewer(rows: list[dict]) -> list[dict]:
    if _viewer_sees_admin_fields():
        return rows
    me = get_current_member().id
    for row in rows:
        if row.get("id") != me:
            for field in _ADMIN_ONLY_FIELDS:
                row.pop(field, None)
    return rows


# ── GET /members/me/mail ──────────────────────────────────────────────────────


@members_bp.get("/me/mail")
@jwt_required()
def get_member_mail():
    """Return the authenticated member's mailbox and aliases."""
    member_id = get_current_member().id
    result = MemberService.get_member_mail(member_id)
    return jsonify(result), 200


# ── GET /members/count ───────────────────────────────────────────────────────


@members_bp.get("/count")
@permission_required("members", "read", "View members")
def count_members():
    result = MembersService.count()
    return jsonify(result), 200


# ── GET /members ──────────────────────────────────────────────────────────────


@members_bp.get("/")
@permission_required("members", "read", "View members")
def list_members():
    args = dict(request.args)
    if not _viewer_sees_admin_fields():
        # Former and deleted members are for those who manage members.
        args.pop("archived", None)
        args.pop("include_deleted", None)
    result = MembersService.list(args)
    for_viewer(result["data"])
    return jsonify(result), 200


# ── GET /members/export ───────────────────────────────────────────────────────


@members_bp.get("/export")
@permission_required("members", "export", "Export members")
def export_members():
    csv_output, truncated = MembersService.export(dict(request.args))
    headers = {"Content-Disposition": "attachment; filename=members.csv"}
    if truncated:
        headers["X-Truncated"] = "true"
    return Response(
        csv_output,
        status=200,
        mimetype="text/csv",
        headers=headers,
    )


# ── POST /members/import ─────────────────────────────────────────────────────


@members_bp.post("/import")
@permission_required("members", "import", "Import members")
def import_members():
    """Import members from a CSV file upload.

    Accepts multipart/form-data with a ``file`` field containing CSV data.
    Optional ``mapping`` JSON field maps CSV columns to member fields.
    Optional ``dry_run`` flag returns validation results without importing.
    """
    file = request.files.get("file")
    if file is None:
        return api_error("VALIDATION_ERROR", "No file provided", 400)

    if not file.filename or not file.filename.endswith(".csv"):
        return api_error("VALIDATION_ERROR", "File must be a CSV", 400)

    stream = io.StringIO(file.read().decode("utf-8-sig"), newline=None)
    reader = csv.DictReader(stream)
    rows = list(reader)

    if not rows:
        return api_error("VALIDATION_ERROR", "CSV file is empty", 400)

    mapping = None
    mapping_json = request.form.get("mapping")
    if mapping_json:
        import json

        try:
            mapping = json.loads(mapping_json)
        except json.JSONDecodeError:
            return api_error("VALIDATION_ERROR", "Invalid mapping JSON", 400)

    dry_run = request.form.get("dry_run", "").strip().lower() in ("1", "true", "yes")

    if dry_run:
        return jsonify(
            {
                "row_count": len(rows),
                "columns": list(rows[0].keys()) if rows else [],
                "preview": rows[:5],
            }
        ), 200

    result = MembersService.import_csv(
        rows=rows,
        mapping=mapping,
        actor_id=get_current_member().id,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(result), 200


# ── DELETE /members/<id>/soft ────────────────────────────────────────────────


@members_bp.delete("/<int:member_id>/soft")
@permission_required("members", "delete", "Delete members")
def soft_delete_member(member_id: int):
    """Soft-delete a member (sets deleted_at, preserves data)."""
    actor_id = get_current_member().id
    member = MembersService.soft_delete(member_id, actor_id)

    log_audit(
        actor_id=actor_id,
        action="soft_delete_member",
        target_type="Member",
        target_id=member.id,
        target_label=member.name,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── GET /members/<id> ─────────────────────────────────────────────────────────


@members_bp.get("/<int:member_id>")
@permission_required("members", "read", "View members")
def get_member(member_id: int):
    member = MemberService.get(member_id)
    if member is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
    return jsonify(for_viewer([_member_schema.dump(member)])[0]), 200


# ── POST /members ─────────────────────────────────────────────────────────────


@members_bp.post("/")
@permission_required("members", "create", "Create members")
def create_member():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    # A club invites; the person joins when they accept (see invite).
    result = MembersService.invite(
        data=data,
        actor_id=get_current_member().id,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(result), 202


# ── PATCH /members/<id> ───────────────────────────────────────────────────────


@members_bp.patch("/<int:member_id>")
@can_update("members", "Update members")
def update_member(member_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    data = filter_updatable_fields(data)

    member = MembersService.update(
        member_id=member_id,
        data=data,
        actor_id=get_current_member().id,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(member)
    return jsonify(_member_schema.dump(member)), 200


# ── POST /members/<id>/provision ──────────────────────────────────────────────


@members_bp.post("/<int:member_id>/provision")
@permission_required("members", "provision", "Provision member mail")
def provision_member(member_id: int):
    _member = MemberService.provision(
        member_id=member_id,
        actor_id=get_current_member().id,
    )
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({"ok": True, "memberId": member_id}), 202


# ── POST /members/<id>/archive ────────────────────────────────────────────────


@members_bp.post("/<int:member_id>/archive")
@permission_required("members", "archive", "Archive members")
def archive_member(member_id: int):
    actor_id = get_current_member().id
    member, affected_group_ids = MemberService.archive(member_id, actor_id)

    log_audit(
        actor_id=actor_id,
        action="archive_member",
        target_type="Member",
        target_id=member.id,
        target_label=member.name,
    )

    archived_email = member.email
    archived_name = member.name
    had_wildduck = _has_wildduck_mailbox(member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    _after_archive(member_id, affected_group_ids, had_wildduck)

    from hubra.core.services import email as email_svc

    email_svc.send_account_deleted(
        archived_email,
        archived_name,
        lang=getattr(member, "language", "de-CH") or "de-CH",
    )
    return "", 204


def _has_wildduck_mailbox(member_id: int) -> bool:
    """Read before commit: provision_member_mail reads the address and calls
    wd.delete_user() to tear down the WildDuck account."""
    from hubra.core.models.managed_mail import ManagedMailAddress
    from sqlalchemy import select as _select

    return (
        db.session.scalar(
            _select(ManagedMailAddress.id)
            .where(ManagedMailAddress.owner_type == "member")
            .where(ManagedMailAddress.owner_id == member_id)
            .where(ManagedMailAddress.wildduck_user_id.isnot(None))
        )
        is not None
    )


def _after_archive(member_id: int, affected_group_ids: set[int], had_wildduck: bool):
    """Side effects once an archive (or a member leaving) is committed."""
    if affected_group_ids:
        from hubra.api.groups.services import _trigger_group_mail_sync

        for gid in affected_group_ids:
            _trigger_group_mail_sync(gid)

    if had_wildduck:
        from hubra.core.tasks.wildduck import provision_member_mail

        provision_member_mail.delay(member_id)


# ── Leaving the club ──────────────────────────────────────────────────────────
#
# A member leaves on their own, or, when the club switched on "leaving needs
# approval" (club settings), asks to leave and a club admin approves it.


def _leave_needs_approval() -> bool:
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    branding = (tenant.settings or {}).get("branding", {}) if tenant else {}
    return bool(branding.get("leave_requires_approval"))


def _leave_state(member) -> dict:
    requested = member.leave_requested_at
    return {
        "requiresApproval": _leave_needs_approval(),
        "requestedAt": requested.isoformat() if requested else None,
    }


def _leave_now(member, actor_id: int, action: str) -> None:
    member_id = member.id
    had_wildduck = _has_wildduck_mailbox(member_id)
    affected_group_ids = MemberService.leave(member)
    log_audit(
        actor_id=actor_id,
        action=action,
        target_type="Member",
        target_id=member_id,
        target_label=member.name,
    )
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    _after_archive(member_id, affected_group_ids, had_wildduck)


@members_bp.get("/me/leave")
@jwt_required()
def get_my_leave():
    return jsonify(_leave_state(get_current_member())), 200


@members_bp.post("/me/leave")
@jwt_required()
def leave_club():
    """Leave the club now, or ask to leave when the club wants to approve it."""
    member = get_current_member()
    if not _leave_needs_approval():
        _leave_now(member, member.id, "left")
        return jsonify({"status": "left"}), 200

    if member.leave_requested_at is None:
        from datetime import datetime, timezone

        from hubra.api.members.services import _check_last_owner

        _check_last_owner(member)
        member.leave_requested_at = datetime.now(timezone.utc)
        log_audit(
            actor_id=member.id,
            action="leave_requested",
            target_type="Member",
            target_id=member.id,
            target_label=member.name,
        )
        from hubra.api.notifications.staff import notify_permitted

        notify_permitted(
            "members.members.archive",
            "info",
            "Request to leave",
            member.name,
            skip_member_id=member.id,
        )
        db.session.commit()
    return jsonify({"status": "requested", **_leave_state(member)}), 200


@members_bp.delete("/me/leave")
@jwt_required()
def cancel_leave_request():
    member = get_current_member()
    if member.leave_requested_at is not None:
        member.leave_requested_at = None
        log_audit(
            actor_id=member.id,
            action="leave_request_withdrawn",
            target_type="Member",
            target_id=member.id,
            target_label=member.name,
        )
        db.session.commit()
    return jsonify(_leave_state(member)), 200


@members_bp.get("/leave-requests")
@permission_required("members", "archive", "Archive members")
def list_leave_requests():
    from sqlalchemy import select as _select

    from hubra.core.models.member import Member

    rows = db.session.scalars(
        _select(Member)
        .where(Member.leave_requested_at.isnot(None))
        .where(Member.archived_at.is_(None))
        .order_by(Member.leave_requested_at)
    ).all()
    return jsonify(
        [
            {
                "id": m.id,
                "name": m.name,
                "email": m.email,
                "avatarColor": m.avatar_color,
                "requestedAt": m.leave_requested_at.isoformat(),
            }
            for m in rows
        ]
    ), 200


def _pending_leave(member_id: int):
    from hubra.core.models.member import Member

    member = db.session.get(Member, member_id)
    if (
        member is None
        or member.archived_at is not None
        or member.leave_requested_at is None
    ):
        raise_error(404, "NOT_FOUND", "No request to leave from this member")
    return member


@members_bp.post("/<int:member_id>/leave/approve")
@permission_required("members", "archive", "Archive members")
def approve_leave(member_id: int):
    _leave_now(_pending_leave(member_id), get_current_member().id, "leave_approved")
    return "", 204


@members_bp.post("/<int:member_id>/leave/decline")
@permission_required("members", "archive", "Archive members")
def decline_leave(member_id: int):
    member = _pending_leave(member_id)
    member.leave_requested_at = None
    log_audit(
        actor_id=get_current_member().id,
        action="leave_declined",
        target_type="Member",
        target_id=member.id,
        target_label=member.name,
    )
    db.session.commit()
    return "", 204


# ── POST /members/<id>/unarchive ──────────────────────────────────────────────


@members_bp.post("/<int:member_id>/unarchive")
@permission_required("members", "unarchive", "Unarchive members")
def unarchive_member(member_id: int):
    member = MemberService.unarchive(member_id)

    log_audit(
        actor_id=get_current_member().id,
        action="unarchive_member",
        target_type="Member",
        target_id=member.id,
        target_label=member.name,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(member)
    return jsonify(_member_schema.dump(member)), 200


# ── DELETE /members/<id> — permanent hard delete (archived only) ──────────────


@members_bp.delete("/<int:member_id>")
@permission_required("members", "delete", "Delete members")
def delete_member_permanent(member_id: int):
    actor_id = get_current_member().id
    member = MemberService.delete_permanent(member_id, actor_id)

    log_audit(
        actor_id=actor_id,
        action="delete_member_permanent",
        target_type="Member",
        target_id=member.id,
        target_label=member.name,
    )

    try:
        db.session.delete(member)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /members/<id>/disable ────────────────────────────────────────────────


@members_bp.post("/<int:member_id>/disable")
@permission_required("members", "disable", "Disable members")
def disable_member(member_id: int):
    actor_id = get_current_member().id
    member = MemberService.disable(member_id, actor_id)

    log_audit(
        actor_id=actor_id,
        action="disable_member",
        target_type="Member",
        target_id=member.id,
        target_label=member.name,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(member)
    return jsonify(_member_schema.dump(member)), 200


# ── POST /members/<id>/enable ─────────────────────────────────────────────────


@members_bp.post("/<int:member_id>/enable")
@permission_required("members", "enable", "Enable members")
def enable_member(member_id: int):
    actor_id = get_current_member().id
    member = MemberService.enable(member_id, actor_id)

    log_audit(
        actor_id=actor_id,
        action="enable_member",
        target_type="Member",
        target_id=member.id,
        target_label=member.name,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(member)
    return jsonify(_member_schema.dump(member)), 200


# ── DELETE /members/<id>/sessions ────────────────────────────────────────────


@members_bp.delete("/<int:member_id>/sessions")
@permission_required("members", "update", "Revoke member sessions")
def revoke_member_sessions(member_id: int):
    """Admin endpoint: revoke all sessions for a member (force logout)."""
    from hubra.api.auth import session_service

    count = session_service.admin_revoke_all_sessions(member_id)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="revoke_member_sessions",
        target_type="Member",
        target_id=member_id,
        target_label=f"{count} sessions revoked",
    )
    db.session.commit()

    return jsonify({"ok": True, "revoked": count}), 200
