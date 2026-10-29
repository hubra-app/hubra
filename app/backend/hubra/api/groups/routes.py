"""Groups blueprint — CRUD for project/interest groups."""

from __future__ import annotations


from flask import Blueprint, jsonify, request
from hubra.api.auth.helpers import get_current_member

from marshmallow import ValidationError
from sqlalchemy import select

from hubra.api.permissions import (
    permission_required,
    require_member,
    can_update,
    filter_updatable_fields,
)
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db
from hubra.core.models.group import Group
from hubra.core.models.member import Member, member_groups
from hubra.core.schemas.group import (
    GroupCreateSchema,
    GroupSchema,
    GroupUpdateSchema,
    GroupMembershipSchema,
    GroupMembershipUpdateSchema,
)
from hubra.core.schemas.member import MemberSchema
from hubra.api.groups.services import GroupService, GroupsService, SelfJoinService
from hubra.api.utils import log_audit


groups_bp = Blueprint("groups_bp", __name__)

_group_schema = GroupSchema()
_groups_schema = GroupSchema(many=True)
_create_schema = GroupCreateSchema()
_update_schema = GroupUpdateSchema()
_members_schema = MemberSchema(many=True)


# ── GET /groups/count ─────────────────────────────────────────────────────────


@groups_bp.get("/count")
@permission_required("groups", "read", "View groups")
def count_groups():
    """Return total non-archived group count and archived count."""
    return jsonify(GroupsService.count()), 200


# ── GET /groups ───────────────────────────────────────────────────────────────


@groups_bp.get("/")
@permission_required("groups", "read", "View groups")
def list_groups():
    groups = GroupsService.list()
    return jsonify(_groups_schema.dump(groups)), 200


# ── Self-join groups (any member) ────────────────────────────────────────────


@groups_bp.get("/joinable")
@require_member
def list_joinable_groups():
    member = get_current_member()
    return jsonify(SelfJoinService.joinable(member.id)), 200


@groups_bp.post("/<int:group_id>/join")
@require_member
def join_group(group_id: int):
    SelfJoinService.join(group_id, get_current_member())
    db.session.commit()
    return "", 204


@groups_bp.post("/<int:group_id>/leave")
@require_member
def leave_group(group_id: int):
    SelfJoinService.leave(group_id, get_current_member())
    db.session.commit()
    return "", 204


# ── GET /groups/<id> ──────────────────────────────────────────────────────────


@groups_bp.get("/<int:id>")
@permission_required("groups", "read", "View groups")
def get_group(id: int):
    group = GroupService.get_by_id(id)

    member_ids = db.session.scalars(
        select(member_groups.c.member_id).where(member_groups.c.group_id == id)
    ).all()

    data = _group_schema.dump(group)
    data["member_ids"] = list(member_ids)
    return jsonify(data), 200


# ── POST /groups ──────────────────────────────────────────────────────────────


@groups_bp.post("/")
@permission_required("groups", "create", "Create groups")
def create_group():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    group = GroupsService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_group_schema.dump(group)), 201


# ── PATCH /groups/<id> ────────────────────────────────────────────────────────


@groups_bp.patch("/<int:id>")
@can_update("groups", "Update groups")
def update_group(id: int):
    group = GroupService.get_by_id(id)

    body = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    data = filter_updatable_fields(data)

    GroupService.update(group, data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(group)
    return jsonify(_group_schema.dump(group)), 200


# ── DELETE /groups/<id> ───────────────────────────────────────────────────────


@groups_bp.delete("/<int:id>")
@permission_required("groups", "delete", "Delete groups")
def delete_group(id: int):
    GroupService.delete(id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── GET /groups/<id>/members ──────────────────────────────────────────────────


@groups_bp.get("/<int:group_id>/members")
@permission_required("groups", "read", "View group members")
def list_group_members(group_id: int):
    group = db.session.get(Group, group_id)
    if group is None:
        raise_error(404, "NOT_FOUND", f"Group {group_id} not found")
        return

    search = request.args.get("search", "").strip()
    members = GroupService.list_members(group_id, search)
    from hubra.api.members.routes import for_viewer

    return jsonify({"data": for_viewer(_members_schema.dump(members))}), 200


# ── POST /groups/<id>/members/<member_id> ────────────────────────────────────


@groups_bp.post("/<int:group_id>/members/<int:member_id>")
@permission_required("groups", "add_member", "Add member to group")
def add_member_to_group(group_id: int, member_id: int):
    group = db.session.get(Group, group_id)
    if group is None:
        raise_error(404, "NOT_FOUND", f"Group {group_id} not found")
        return

    member = db.session.get(Member, member_id)
    if member is None or member.archived_at is not None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
        return

    GroupService.add_member(group, member)
    log_audit(
        get_current_member().id,
        "add_group_member",
        "Group",
        group.id,
        f"{group.name}: {member.name}",
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── DELETE /groups/<id>/members/<member_id> ──────────────────────────────────


@groups_bp.delete("/<int:group_id>/members/<int:member_id>")
@permission_required("groups", "remove_member", "Remove member from group")
def remove_group_member(group_id: int, member_id: int):
    GroupService.remove_member(member_id, group_id)
    group = db.session.get(Group, group_id)
    member = db.session.get(Member, member_id)
    log_audit(
        get_current_member().id,
        "remove_group_member",
        "Group",
        group_id,
        f"{group.name if group else group_id}: {member.name if member else member_id}",
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── PATCH /groups/<id>/members/<member_id> — update role ─────────────────────


@groups_bp.patch("/<int:group_id>/members/<int:member_id>")
@permission_required("groups", "add_member", "Update group member role")
def update_group_member_role(group_id: int, member_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = GroupMembershipUpdateSchema().load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    membership = GroupService.update_member_role(
        group_id=group_id,
        member_id=member_id,
        role=data["role"],
        notes=data.get("notes"),
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(GroupMembershipSchema().dump(membership)), 200


# ── GET /groups/<id>/mailing-list ────────────────────────────────────────────


@groups_bp.get("/<int:group_id>/mailing-list")
@permission_required("groups", "read", "View group mailing list")
def get_mailing_list(group_id: int):
    """Return email addresses of all group members for mailing list export."""
    group = db.session.get(Group, group_id)
    if group is None:
        raise_error(404, "NOT_FOUND", f"Group {group_id} not found")
        return

    emails = GroupService.get_mailing_list(group_id)
    return jsonify({"data": emails, "count": len(emails)}), 200
