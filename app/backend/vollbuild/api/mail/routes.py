"""Mail blueprint — HTTP layer only. Business logic lives in services.py."""

from __future__ import annotations

import re as _re

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity
from vollbuild.api.auth.helpers import get_current_member

from vollbuild.api.mail.services import (
    AliasService,
    AliasesService,
    MailAdminService,
    MailService,
    MailboxService,
    MailboxesService,
)
from vollbuild.core.extensions import db
from vollbuild.api.permissions import permission_required
from vollbuild.api.settings.services import SettingService
from vollbuild.api.utils import log_audit
from vollbuild.core.errors import api_error, raise_error
from vollbuild.core.models.group import Group
from vollbuild.core.models.managed_mail import ManagedMailAddress
from vollbuild.core.services import managed_mail as mma_service

mail_bp = Blueprint("mail_bp", __name__)

_OBJECTID_RE = _re.compile(r"^[0-9a-fA-F]{24}$")


@mail_bp.before_request
def _gate_mail_feature():
    from flask_jwt_extended import verify_jwt_in_request

    from vollbuild.api.features.services import FeatureFlagService

    # Health check is always accessible — no auth, no feature gate.
    # (request.path is the full /api/.../mail/health, so match the endpoint.)
    if (request.endpoint or "").endswith(".mail_health"):
        return None

    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None

    if get_jwt_identity() is None:
        return None

    if not FeatureFlagService.is_enabled("mail"):
        return api_error("FEATURE_DISABLED", "Mail feature is disabled", 409)


def _validate_wd_id(wd_id: str) -> None:
    """Reject IDs that don't match WildDuck's 24-hex-char ObjectId format."""
    if not _OBJECTID_RE.match(wd_id):
        raise_error(400, "VALIDATION_ERROR", f"Invalid ID format: {wd_id!r}")


# ── Mailboxes ─────────────────────────────────────────────────────────────────


@mail_bp.get("/mailboxes")
@permission_required("mailboxes", "read", "View mailboxes")
def list_mailboxes():
    data = MailboxesService.list()
    return jsonify({"data": data}), 200


@mail_bp.post("/mailboxes")
@permission_required("mailboxes", "create", "Create mailboxes")
def create_mailbox():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    display_name = (body.get("displayName") or body.get("display_name") or "").strip()
    quota_gb = float(body.get("quotaGb") or body.get("quota_gb") or 1.0)
    password = body.get("password")

    if not username:
        return api_error("VALIDATION_ERROR", "'username' is required", 400)

    created = MailboxesService.create(
        username=username,
        display_name=display_name,
        quota_gb=quota_gb,
        password=password,
    )

    log_audit(
        actor_id=get_current_member().id,
        action="create_mailbox",
        target_type="Mailbox",
        target_id=0,
        target_label=created["address"],
    )

    return jsonify(created), 201


@mail_bp.patch("/mailboxes/<string:wd_id>")
@permission_required("mailboxes", "update", "Update mailboxes")
def update_mailbox(wd_id: str):
    _validate_wd_id(wd_id)
    body = request.get_json(silent=True) or {}
    fields: dict = {}
    if "displayName" in body or "display_name" in body:
        fields["name"] = body.get("displayName") or body.get("display_name")
    if "quotaGb" in body or "quota_gb" in body:
        from vollbuild.api.mail.services import _gb_to_bytes

        gb = float(body.get("quotaGb") or body.get("quota_gb"))  # type: ignore[arg-type]
        if gb < 0.1 or gb > 100:
            return api_error(
                "VALIDATION_ERROR",
                "Quota must be between 0.1 GB and 100 GB",
                400,
            )
        fields["quota"] = _gb_to_bytes(gb)

    if not fields:
        return api_error("VALIDATION_ERROR", "Nothing to update", 400)

    user = MailboxService.update(wd_id, **fields)

    log_audit(
        actor_id=get_current_member().id,
        action="update_mailbox",
        target_type="Mailbox",
        target_id=0,
        target_label=user.get("address", wd_id),
    )

    from vollbuild.api.mail.services import MailboxService as _MS

    return jsonify(_MS.map_user(user)), 200


@mail_bp.delete("/mailboxes/<string:wd_id>")
@permission_required("mailboxes", "delete", "Delete mailboxes")
def delete_mailbox(wd_id: str):
    _validate_wd_id(wd_id)
    user = MailboxService.delete(wd_id)

    log_audit(
        actor_id=get_current_member().id,
        action="delete_mailbox",
        target_type="Mailbox",
        target_id=0,
        target_label=user.get("address", wd_id),
    )
    return "", 204


# ── Aliases ───────────────────────────────────────────────────────────────────


@mail_bp.get("/aliases")
@permission_required("aliases", "read", "View aliases")
def list_aliases():
    group_id = request.args.get("groupId", type=int)
    data = AliasesService.list(group_id=group_id)
    return jsonify({"data": data}), 200


@mail_bp.post("/aliases")
@permission_required("aliases", "create", "Create aliases")
def create_alias():
    body = request.get_json(silent=True) or {}
    address = (body.get("address") or "").strip()
    delivers_to = body.get("deliversTo") or body.get("delivers_to") or []
    alias_type = body.get("type", "Alias")
    group_id = body.get("groupId") or body.get("group_id")

    if not address:
        return api_error("VALIDATION_ERROR", "'address' is required", 400)

    created = AliasesService.create(
        address=address,
        delivers_to=delivers_to,
        alias_type=alias_type,
        group_id=group_id,
        name=body.get("name"),
    )

    log_audit(
        actor_id=get_current_member().id,
        action="create_alias",
        target_type="Alias",
        target_id=0,
        target_label=address,
    )

    return jsonify(created), 201


@mail_bp.patch("/aliases/<string:wd_id>")
@permission_required("aliases", "update", "Update aliases")
def update_alias(wd_id: str):
    _validate_wd_id(wd_id)
    body = request.get_json(silent=True) or {}
    delivers_to = body.get("deliversTo") or body.get("delivers_to")

    if delivers_to is None:
        return api_error("VALIDATION_ERROR", "'deliversTo' is required", 400)
    if not isinstance(delivers_to, list):
        return api_error("VALIDATION_ERROR", "'deliversTo' must be a list", 400)

    AliasService.update(wd_id, delivers_to)

    log_audit(
        actor_id=get_current_member().id,
        action="update_alias",
        target_type="Alias",
        target_id=0,
        target_label=wd_id,
    )

    return jsonify(
        {
            "id": wd_id,
            "deliversTo": delivers_to,
            "enabled": not body.get("disabled", False),
        }
    ), 200


@mail_bp.delete("/aliases/<string:wd_id>")
@permission_required("aliases", "delete", "Delete aliases")
def delete_alias(wd_id: str):
    _validate_wd_id(wd_id)
    alias_address = AliasService.delete(wd_id)

    log_audit(
        actor_id=get_current_member().id,
        action="delete_alias",
        target_type="Alias",
        target_id=0,
        target_label=alias_address or wd_id,
    )
    return "", 204


# ── Member mail provisioning ──────────────────────────────────────────────────


@mail_bp.get("/members")
@permission_required("member_mail", "read", "View member mail")
def list_member_mail():
    data = MailboxesService.list_members()
    return jsonify({"data": data}), 200


@mail_bp.patch("/members/<int:member_id>")
@permission_required("member_mail", "update", "Update member mail")
def update_member_mail(member_id: int):
    body = request.get_json(silent=True) or {}
    updates = {
        k: v
        for k, v in body.items()
        if k in {"forwarding_enabled", "forward_enabled", "retention_days", "quota_mb"}
    }
    if not updates:
        return api_error("VALIDATION_ERROR", "No valid fields provided", 400)

    result = MailboxesService.update_member_mail(
        member_id=member_id,
        updates=updates,
        actor_id=get_current_member().id,
    )

    db.session.commit()

    return jsonify(result), 200


# ── Member mail (ManagedMailAddress) ──────────────────────────────────────────


@mail_bp.get("/members-mail")
@permission_required("member_mail", "read", "View member mail")
def list_member_mail_mma():
    from sqlalchemy import select

    from vollbuild.core.models.member import Member

    addrs = db.session.scalars(
        select(ManagedMailAddress)
        .where(ManagedMailAddress.owner_type == "member")
        .order_by(ManagedMailAddress.address)
    ).all()
    member_ids = [a.owner_id for a in addrs if a.owner_id is not None]
    members_by_id: dict[int, Member] = {}
    if member_ids:
        members_by_id = {
            m.id: m
            for m in db.session.scalars(
                select(Member).where(Member.id.in_(member_ids))
            ).all()
        }
    result = []
    for addr in addrs:
        m = members_by_id.get(addr.owner_id) if addr.owner_id else None
        item = mma_service.serialize(addr)
        item["memberName"] = m.name if m else None
        result.append(item)
    return jsonify({"data": result}), 200


@mail_bp.post("/members-mail/<int:member_id>")
@permission_required("member_mail", "update", "Update member mail")
def create_member_mail_mma(member_id: int):
    from vollbuild.core.models.member import Member

    member = db.session.get(Member, member_id)
    if member is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

    existing = db.session.scalar(
        ManagedMailAddress.__table__.select().where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )
    from sqlalchemy import select as _sel

    existing = db.session.scalar(
        _sel(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )
    if existing is not None:
        return api_error(
            "VALIDATION_ERROR",
            f"Member '{member.name}' already has a managed mail address",
            409,
        )

    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        prefix = (
            member.public_email.split("@")[0]
            if member.public_email
            else member.name.lower().replace(" ", ".")
        )

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )

    addr = mma_service.get_or_create_for_member(member_id, prefix, club_domain)
    db.session.flush()

    from vollbuild.core.services.mail_provisioning import ensure_alias, ensure_mailbox

    ensure_mailbox(addr, password_hash=member.password_hash)
    ensure_alias(addr)
    addr.provisioning_status = "provisioned"
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="create_member_mail",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=addr.address,
    )

    return jsonify(mma_service.serialize(addr)), 201


@mail_bp.delete("/members-mail/<int:member_id>")
@permission_required("member_mail", "update", "Update member mail")
def delete_member_mail_mma(member_id: int):
    from sqlalchemy import select as _sel
    from vollbuild.core.models.member import Member

    member = db.session.get(Member, member_id)
    if member is not None and member.archived_at is None:
        return api_error(
            "MMA_LOCKED_TO_OWNER",
            f"Cannot delete managed mail address for member '{member.name}' while the member exists. "
            "Delete or archive the member first — the MMA is cleaned up automatically.",
            409,
        )

    addr = db.session.scalar(
        _sel(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )
    if addr is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} has no managed mail address")

    address_label = addr.address
    mma_service.remove_for_member(member_id)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="delete_member_mail",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=address_label,
    )

    return "", 204


@mail_bp.patch("/members-mail/<int:member_id>/toggle")
@permission_required("member_mail", "update", "Update member mail")
def toggle_member_mail_mma(member_id: int):
    from sqlalchemy import select as _sel

    addr = db.session.scalar(
        _sel(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )
    if addr is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} has no managed mail address")

    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        return api_error("VALIDATION_ERROR", "'enabled' (bool) is required", 400)

    mma_service.toggle_mail_enabled(addr, enabled)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="toggle_member_mail",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=f"{addr.address} ({'enabled' if enabled else 'disabled'})",
    )

    return jsonify(mma_service.serialize(addr)), 200


# ── Group mail (ManagedMailAddress) ───────────────────────────────────────────


@mail_bp.get("/groups")
@permission_required("aliases", "read", "View aliases")
def list_group_mail():
    from sqlalchemy import select

    addrs = db.session.scalars(
        select(ManagedMailAddress)
        .where(ManagedMailAddress.owner_type == "group")
        .order_by(ManagedMailAddress.address)
    ).all()
    group_ids = [a.owner_id for a in addrs if a.owner_id is not None]
    groups_by_id: dict[int, Group] = {}
    if group_ids:
        groups_by_id = {
            g.id: g
            for g in db.session.scalars(
                select(Group).where(Group.id.in_(group_ids))
            ).all()
        }
    result = []
    for addr in addrs:
        group = groups_by_id.get(addr.owner_id) if addr.owner_id else None
        item = mma_service.serialize(addr)
        item["groupName"] = group.name if group else None
        result.append(item)
    return jsonify({"data": result}), 200


@mail_bp.post("/groups/<int:group_id>")
@permission_required("aliases", "create", "Create aliases")
def create_group_mail(group_id: int):
    from sqlalchemy import select

    group = db.session.scalar(
        select(Group).where(Group.id == group_id).where(Group.archived_at.is_(None))
    )
    if group is None:
        raise_error(404, "NOT_FOUND", f"Group {group_id} not found")

    existing = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if existing is not None:
        return api_error(
            "VALIDATION_ERROR",
            f"Group '{group.name}' already has a managed mail address",
            409,
        )

    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        prefix = mma_service.normalize_prefix_from_name(group.name)

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )

    addr = mma_service.get_or_create_for_group(group_id, prefix, club_domain)

    from vollbuild.core.services.mail_provisioning import (
        _resolve_group_member_targets,
        ensure_alias,
        ensure_forwarding,
        ensure_mailbox,
    )

    try:
        ensure_mailbox(addr)
        ensure_alias(addr)
        targets = _resolve_group_member_targets(group_id)
        ensure_forwarding(addr, targets)
    except Exception:
        db.session.rollback()
        raise

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="create_group_mail",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=addr.address,
    )

    return jsonify(mma_service.serialize(addr)), 201


@mail_bp.delete("/groups/<int:group_id>")
@permission_required("aliases", "delete", "Delete aliases")
def delete_group_mail(group_id: int):
    from sqlalchemy import select

    group = db.session.scalar(
        select(Group).where(Group.id == group_id).where(Group.archived_at.is_(None))
    )
    if group is None:
        raise_error(404, "NOT_FOUND", f"Group {group_id} not found")

    return api_error(
        "MMA_LOCKED_TO_OWNER",
        f"Cannot delete managed mail address for group '{group.name}' while the group exists. "
        "Delete the group first — the MMA is cleaned up automatically.",
        409,
    )


# ── Function mail (ManagedMailAddress) ────────────────────────────────────────


@mail_bp.get("/functions")
@permission_required("aliases", "read", "View aliases")
def list_function_mail():
    from sqlalchemy import select

    from vollbuild.core.models.function import Function

    addrs = db.session.scalars(
        select(ManagedMailAddress)
        .where(ManagedMailAddress.owner_type == "function")
        .order_by(ManagedMailAddress.address)
    ).all()
    function_ids = [a.owner_id for a in addrs if a.owner_id is not None]
    functions_by_id: dict[int, Function] = {}
    if function_ids:
        functions_by_id = {
            f.id: f
            for f in db.session.scalars(
                select(Function).where(Function.id.in_(function_ids))
            ).all()
        }
    result = []
    for addr in addrs:
        fn = functions_by_id.get(addr.owner_id) if addr.owner_id else None
        item = mma_service.serialize(addr)
        item["functionName"] = fn.name if fn else None
        result.append(item)
    return jsonify({"data": result}), 200


@mail_bp.post("/functions/<int:function_id>")
@permission_required("aliases", "create", "Create aliases")
def create_function_mail(function_id: int):
    from sqlalchemy import select

    from vollbuild.core.models.function import Function

    fn = db.session.get(Function, function_id)
    if fn is None:
        raise_error(404, "NOT_FOUND", f"Function {function_id} not found")

    existing = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if existing is not None:
        return api_error(
            "VALIDATION_ERROR",
            f"Function '{fn.name}' already has a managed mail address",
            409,
        )

    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        prefix = mma_service.normalize_prefix_from_name(fn.name)

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )

    addr = mma_service.get_or_create_for_function(function_id, prefix, club_domain)

    from vollbuild.core.services.mail_provisioning import (
        _resolve_function_holder_targets,
        ensure_alias,
        ensure_forwarding,
        ensure_mailbox,
        migrate_alias_to_mailbox,
    )

    try:
        if addr.wildduck_id and not addr.wildduck_id:
            migrate_alias_to_mailbox(addr)
        ensure_mailbox(addr)
        ensure_alias(addr)
        targets = _resolve_function_holder_targets(function_id)
        ensure_forwarding(addr, targets)
    except Exception:
        db.session.rollback()
        raise

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="create_function_mail",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=addr.address,
    )

    return jsonify(mma_service.serialize(addr)), 201


@mail_bp.delete("/functions/<int:function_id>")
@permission_required("aliases", "delete", "Delete aliases")
def delete_function_mail(function_id: int):

    from vollbuild.core.models.function import Function

    fn = db.session.get(Function, function_id)
    if fn is None:
        raise_error(404, "NOT_FOUND", f"Function {function_id} not found")

    return api_error(
        "MMA_LOCKED_TO_OWNER",
        f"Cannot delete managed mail address for function '{fn.name}' while the function exists. "
        "Delete the function first — the MMA is cleaned up automatically.",
        409,
    )


# ── Group mail: toggle / prefix / aliases ─────────────────────────────────────


@mail_bp.patch("/groups/<int:group_id>/toggle")
@permission_required("aliases", "update", "Update aliases")
def toggle_group_mail(group_id: int):
    from sqlalchemy import select

    addr = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if addr is None:
        raise_error(404, "NOT_FOUND", f"Group {group_id} has no managed mail address")

    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        return api_error("VALIDATION_ERROR", "'enabled' (bool) is required", 400)

    mma_service.toggle_mail_enabled(addr, enabled)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="toggle_group_mail",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=f"{addr.address} ({'enabled' if enabled else 'disabled'})",
    )

    return jsonify(mma_service.serialize(addr)), 200


@mail_bp.patch("/groups/<int:group_id>/prefix")
@permission_required("aliases", "update", "Update aliases")
def change_group_mail_prefix(group_id: int):
    from sqlalchemy import select

    addr = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if addr is None:
        raise_error(404, "NOT_FOUND", f"Group {group_id} has no managed mail address")

    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        return api_error("VALIDATION_ERROR", "'prefix' is required", 400)

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )

    try:
        mma_service.change_mail_prefix(addr, prefix, club_domain)
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="change_group_mail_prefix",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=addr.address,
    )

    return jsonify(mma_service.serialize(addr)), 200


@mail_bp.get("/groups/<int:group_id>/aliases")
@permission_required("aliases", "read", "View aliases")
def list_group_aliases(group_id: int):
    from sqlalchemy import select

    aliases = list(
        db.session.scalars(
            select(ManagedMailAddress)
            .where(
                ManagedMailAddress.owner_type == "group",
                ManagedMailAddress.owner_id == group_id,
                ManagedMailAddress.fixed_forward_targets.is_not(None),
            )
            .order_by(ManagedMailAddress.address)
        ).all()
    )
    return jsonify({"data": [mma_service.serialize(a) for a in aliases]}), 200


@mail_bp.post("/groups/<int:group_id>/aliases")
@permission_required("aliases", "create", "Create aliases")
def create_group_alias(group_id: int):
    from sqlalchemy import func, select

    MAX_GROUP_ALIASES = 10

    primary = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if primary is None:
        raise_error(404, "NOT_FOUND", f"Group {group_id} has no primary mail address")

    # Rate limit: count main + additional aliases for this group.
    alias_count = (
        db.session.scalar(
            select(func.count())
            .select_from(ManagedMailAddress)
            .where(
                ManagedMailAddress.owner_type == "group",
                ManagedMailAddress.owner_id == group_id,
            )
        )
        or 0
    )
    if alias_count >= MAX_GROUP_ALIASES:
        return api_error(
            "RATE_LIMITED",
            f"Group {group_id} has reached the maximum of {MAX_GROUP_ALIASES} aliases",
            429,
        )

    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        return api_error("VALIDATION_ERROR", "'prefix' is required", 400)

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )

    try:
        alias = mma_service.get_or_create_group_additional_alias(
            group_id, prefix, club_domain, actor_id=get_current_member().id
        )
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    from vollbuild.core.services.mail_provisioning import ensure_alias

    try:
        ensure_alias(alias)
    except Exception:
        db.session.rollback()
        raise

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="create_group_alias",
        target_type="ManagedMailAddress",
        target_id=alias.id,
        target_label=alias.address,
    )

    from vollbuild.core.services.binding_engine import sync_for_source

    sync_for_source("group", str(group_id))
    sync_for_source("mail_address", str(alias.id))
    db.session.commit()

    return jsonify(mma_service.serialize(alias)), 201


@mail_bp.delete("/groups/<int:group_id>/aliases/<int:alias_id>")
@permission_required("aliases", "delete", "Delete aliases")
def delete_group_alias(group_id: int, alias_id: int):
    from sqlalchemy import select

    alias = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.id == alias_id,
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
            ManagedMailAddress.address_type == "alias",
        )
    )
    if alias is None:
        raise_error(404, "NOT_FOUND", f"Alias {alias_id} not found")

    address_label = alias.address
    mma_service.delete_group_additional_alias(alias_id)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="delete_group_alias",
        target_type="ManagedMailAddress",
        target_id=alias_id,
        target_label=address_label,
    )

    from vollbuild.core.services.binding_engine import sync_for_source

    sync_for_source("group", str(group_id))
    db.session.commit()

    return "", 204


@mail_bp.patch("/groups/<int:group_id>/aliases/<int:alias_id>/toggle")
@permission_required("aliases", "update", "Update aliases")
def toggle_group_alias(group_id: int, alias_id: int):
    from sqlalchemy import select

    alias = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.id == alias_id,
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
            ManagedMailAddress.address_type == "alias",
        )
    )
    if alias is None:
        raise_error(404, "NOT_FOUND", f"Alias {alias_id} not found")

    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        return api_error("VALIDATION_ERROR", "'enabled' (bool) is required", 400)

    mma_service.toggle_mail_enabled(alias, enabled)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="toggle_group_alias",
        target_type="ManagedMailAddress",
        target_id=alias.id,
        target_label=f"{alias.address} ({'enabled' if enabled else 'disabled'})",
    )

    from vollbuild.core.services.binding_engine import sync_for_source

    sync_for_source("mail_address", str(alias.id))
    db.session.commit()

    return jsonify(mma_service.serialize(alias)), 200


# ── Function mail: toggle / prefix / aliases ──────────────────────────────────


@mail_bp.patch("/functions/<int:function_id>/toggle")
@permission_required("aliases", "update", "Update aliases")
def toggle_function_mail(function_id: int):
    from sqlalchemy import select

    addr = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if addr is None:
        raise_error(
            404, "NOT_FOUND", f"Function {function_id} has no managed mail address"
        )
        return

    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        return api_error("VALIDATION_ERROR", "'enabled' (bool) is required", 400)

    mma_service.toggle_mail_enabled(addr, enabled)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="toggle_function_mail",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=f"{addr.address} ({'enabled' if enabled else 'disabled'})",
    )

    return jsonify(mma_service.serialize(addr)), 200


@mail_bp.patch("/functions/<int:function_id>/prefix")
@permission_required("aliases", "update", "Update aliases")
def change_function_mail_prefix(function_id: int):
    from sqlalchemy import select

    addr = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if addr is None:
        raise_error(
            404, "NOT_FOUND", f"Function {function_id} has no managed mail address"
        )
        return

    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        return api_error("VALIDATION_ERROR", "'prefix' is required", 400)

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )

    try:
        mma_service.change_mail_prefix(addr, prefix, club_domain)
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="change_function_mail_prefix",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=addr.address,
    )

    return jsonify(mma_service.serialize(addr)), 200


@mail_bp.get("/functions/<int:function_id>/aliases")
@permission_required("aliases", "read", "View aliases")
def list_function_aliases(function_id: int):
    from sqlalchemy import select

    aliases = list(
        db.session.scalars(
            select(ManagedMailAddress)
            .where(
                ManagedMailAddress.owner_type == "function",
                ManagedMailAddress.owner_id == function_id,
                ManagedMailAddress.fixed_forward_targets.is_not(None),
            )
            .order_by(ManagedMailAddress.address)
        ).all()
    )
    return jsonify({"data": [mma_service.serialize(a) for a in aliases]}), 200


@mail_bp.post("/functions/<int:function_id>/aliases")
@permission_required("aliases", "create", "Create aliases")
def create_function_alias(function_id: int):
    from sqlalchemy import select

    primary = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if primary is None:
        raise_error(
            404, "NOT_FOUND", f"Function {function_id} has no primary mail address"
        )
        return

    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        return api_error("VALIDATION_ERROR", "'prefix' is required", 400)

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )

    try:
        alias = mma_service.get_or_create_function_additional_alias(
            function_id, prefix, club_domain, actor_id=get_current_member().id
        )
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    from vollbuild.core.services.mail_provisioning import ensure_alias

    try:
        ensure_alias(alias)
    except Exception:
        db.session.rollback()
        raise

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="create_function_alias",
        target_type="ManagedMailAddress",
        target_id=alias.id,
        target_label=alias.address,
    )

    from vollbuild.core.services.binding_engine import sync_for_source

    sync_for_source("function", str(function_id))
    sync_for_source("mail_address", str(alias.id))
    db.session.commit()

    return jsonify(mma_service.serialize(alias)), 201


@mail_bp.delete("/functions/<int:function_id>/aliases/<int:alias_id>")
@permission_required("aliases", "delete", "Delete aliases")
def delete_function_alias(function_id: int, alias_id: int):
    from sqlalchemy import select

    alias = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.id == alias_id,
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
            ManagedMailAddress.address_type == "alias",
        )
    )
    if alias is None:
        raise_error(404, "NOT_FOUND", f"Alias {alias_id} not found")

    address_label = alias.address
    mma_service.delete_function_additional_alias(alias_id)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="delete_function_alias",
        target_type="ManagedMailAddress",
        target_id=alias_id,
        target_label=address_label,
    )

    from vollbuild.core.services.binding_engine import sync_for_source

    sync_for_source("function", str(function_id))
    db.session.commit()

    return "", 204


@mail_bp.patch("/functions/<int:function_id>/aliases/<int:alias_id>/toggle")
@permission_required("aliases", "update", "Update aliases")
def toggle_function_alias(function_id: int, alias_id: int):
    from sqlalchemy import select

    alias = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.id == alias_id,
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
            ManagedMailAddress.address_type == "alias",
        )
    )
    if alias is None:
        raise_error(404, "NOT_FOUND", f"Alias {alias_id} not found")

    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        return api_error("VALIDATION_ERROR", "'enabled' (bool) is required", 400)

    mma_service.toggle_mail_enabled(alias, enabled)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="toggle_function_alias",
        target_type="ManagedMailAddress",
        target_id=alias.id,
        target_label=f"{alias.address} ({'enabled' if enabled else 'disabled'})",
    )

    from vollbuild.core.services.binding_engine import sync_for_source

    sync_for_source("mail_address", str(alias.id))
    db.session.commit()

    return jsonify(mma_service.serialize(alias)), 200


# ── Unified address management ────────────────────────────────────────────────


@mail_bp.get("/addresses")
@permission_required("aliases", "read", "View aliases")
def list_addresses_route():
    owner_type = request.args.get("owner_type")
    enabled = request.args.get("enabled")
    sync_state = request.args.get("sync_state")
    search = request.args.get("search")
    enabled_val: bool | None = None
    if enabled == "true":
        enabled_val = True
    elif enabled == "false":
        enabled_val = False
    result = mma_service.list_addresses(
        owner_type=owner_type,
        enabled=enabled_val,
        sync_state=sync_state or None,
        search=search or None,
        include_system=False,
    )
    return jsonify({"data": result}), 200


@mail_bp.get("/addresses/all")
@permission_required("aliases", "read", "View aliases")
def list_all_addresses_route():
    owner_type = request.args.get("owner_type")
    enabled = request.args.get("enabled")
    sync_state = request.args.get("sync_state")
    search = request.args.get("search")
    enabled_val: bool | None = None
    if enabled == "true":
        enabled_val = True
    elif enabled == "false":
        enabled_val = False
    result = mma_service.list_addresses(
        owner_type=owner_type or None,
        enabled=enabled_val,
        sync_state=sync_state or None,
        search=search or None,
        include_system=True,
    )
    return jsonify({"data": result}), 200


@mail_bp.get("/addresses/selectable")
@permission_required("aliases", "read", "View aliases")
def list_selectable_route():
    return jsonify(mma_service.list_selectable_addresses()), 200


@mail_bp.get("/addresses/<int:address_id>")
@permission_required("aliases", "read", "View aliases")
def get_address_route(address_id: int):
    result = mma_service.get_address(address_id)
    if result is None:
        raise_error(404, "NOT_FOUND", f"Address {address_id} not found")
    return jsonify(result), 200


@mail_bp.patch("/addresses/<int:address_id>")
@permission_required("aliases", "update", "Update aliases")
def update_address_route(address_id: int):
    body = request.get_json(silent=True) or {}
    fields: dict = {}
    if "forwardingEnabled" in body:
        fields["forwarding_enabled"] = bool(body["forwardingEnabled"])
    if "retentionMs" in body:
        fields["retention_ms"] = body["retentionMs"]
    if "quotaBytes" in body:
        fields["quota_bytes"] = body["quotaBytes"]
    result = mma_service.update_address(address_id, **fields)
    if result is None:
        raise_error(404, "NOT_FOUND", f"Address {address_id} not found")
    db.session.commit()
    log_audit(
        get_current_member().id,
        "update_address",
        "ManagedMailAddress",
        address_id,
        result.get("address"),
    )
    return jsonify(result), 200


@mail_bp.patch("/addresses/<int:address_id>/toggle")
@permission_required("aliases", "update", "Update aliases")
def toggle_address_route(address_id: int):
    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        return api_error("VALIDATION_ERROR", "'enabled' (bool) is required", 400)
    result = mma_service.toggle_address(address_id, enabled)
    if result is None:
        raise_error(404, "NOT_FOUND", f"Address {address_id} not found")
    db.session.commit()
    log_audit(
        get_current_member().id,
        "toggle_address",
        "ManagedMailAddress",
        address_id,
        f"{result.get('address')} ({'enabled' if enabled else 'disabled'})",
    )
    return jsonify(result), 200


@mail_bp.patch("/addresses/<int:address_id>/prefix")
@permission_required("aliases", "update", "Update aliases")
def change_address_prefix_route(address_id: int):
    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        return api_error("VALIDATION_ERROR", "'prefix' is required", 400)
    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )
    try:
        result = mma_service.change_address_prefix(address_id, prefix, club_domain)
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)
    if result is None:
        raise_error(404, "NOT_FOUND", f"Address {address_id} not found")
    db.session.commit()
    log_audit(
        get_current_member().id,
        "change_prefix",
        "ManagedMailAddress",
        address_id,
        result.get("address"),
    )
    return jsonify(result), 200


@mail_bp.get("/addresses/<int:address_id>/aliases")
@permission_required("aliases", "read", "View aliases")
def list_aliases_route(address_id: int):
    return jsonify({"data": mma_service.list_aliases(address_id)}), 200


@mail_bp.post("/addresses/<int:address_id>/aliases")
@permission_required("aliases", "create", "Create aliases")
def create_alias_route(address_id: int):
    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        return api_error("VALIDATION_ERROR", "'prefix' is required", 400)
    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )
    try:
        alias = mma_service.create_alias(
            address_id, prefix, club_domain, actor_id=get_current_member().id
        )
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    from vollbuild.core.services.binding_engine import sync_for_source

    sync_for_source("mail_address", str(alias.id))
    db.session.commit()

    log_audit(
        get_current_member().id,
        "create_alias",
        "ManagedMailAddress",
        alias.id,
        alias.address,
    )
    return jsonify(mma_service.serialize(alias)), 201


@mail_bp.delete("/addresses/<int:address_id>/aliases/<int:alias_id>")
@permission_required("aliases", "delete", "Delete aliases")
def delete_alias_route(address_id: int, alias_id: int):
    mma_service.delete_alias(alias_id)
    db.session.commit()
    log_audit(
        get_current_member().id,
        "delete_alias",
        "ManagedMailAddress",
        alias_id,
        None,
    )
    return "", 204


@mail_bp.patch("/addresses/<int:address_id>/aliases/<int:alias_id>/toggle")
@permission_required("aliases", "update", "Update aliases")
def toggle_alias_route(address_id: int, alias_id: int):
    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        return api_error("VALIDATION_ERROR", "'enabled' (bool) is required", 400)
    result = mma_service.toggle_alias_mma(alias_id, enabled)
    if result is None:
        raise_error(404, "NOT_FOUND", f"Alias {alias_id} not found")
    db.session.commit()
    return jsonify(result), 200


@mail_bp.delete("/addresses/<int:address_id>")
@permission_required("aliases", "delete", "Delete aliases")
def delete_address_route(address_id: int):
    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"Address {address_id} not found")

    if addr.is_system:
        return api_error(
            "MMA_LOCKED_TO_OWNER",
            "Cannot delete system address from unified API. Use system-addresses endpoint.",
            409,
        )

    owner_type = addr.owner_type
    owner_id = addr.owner_id
    if owner_type and owner_id and owner_type != "mail_address":
        if owner_type == "group":
            from vollbuild.core.models.group import Group

            if db.session.get(Group, owner_id) is not None:
                return api_error(
                    "MMA_LOCKED_TO_OWNER",
                    "Cannot delete address for group while the group exists.",
                    409,
                )
        elif owner_type == "function":
            from vollbuild.core.models.function import Function

            if db.session.get(Function, owner_id) is not None:
                return api_error(
                    "MMA_LOCKED_TO_OWNER",
                    "Cannot delete address for function while the function exists.",
                    409,
                )
        elif owner_type == "member":
            from vollbuild.core.models.member import Member

            m = db.session.get(Member, owner_id)
            if m is not None and m.archived_at is None:
                return api_error(
                    "MMA_LOCKED_TO_OWNER",
                    "Cannot delete address for member while the member exists.",
                    409,
                )

    from vollbuild.core.services.binding_engine import cascade_delete_disabled
    from vollbuild.core.services.mail_provisioning import ensure_absent

    cascade_delete_disabled("mail_address", str(address_id))
    ensure_absent(addr)
    db.session.delete(addr)
    db.session.commit()
    log_audit(
        get_current_member().id,
        "delete_address",
        "ManagedMailAddress",
        address_id,
        addr.address,
    )
    return "", 204


# ── System addresses ──────────────────────────────────────────────────────────


@mail_bp.get("/system-addresses")
@permission_required("system", "read", "View system mail")
def list_system_addresses():
    from sqlalchemy import select

    addrs = mma_service.get_system_addresses()

    from vollbuild.core.services.key_service import KeyService

    sender_addr = KeyService.get("mail.smtp.user")
    sender_addr_str = str(sender_addr) if sender_addr else None

    addr_ids = [a.id for a in addrs]
    aliases_by_mma: dict[int, list] = {}
    if addr_ids:
        all_aliases = db.session.scalars(
            select(ManagedMailAddress)
            .where(ManagedMailAddress.owner_type == "mail_address")
            .where(ManagedMailAddress.owner_id.in_(addr_ids))
            .order_by(ManagedMailAddress.address)
        ).all()
        for alias in all_aliases:
            aliases_by_mma.setdefault(alias.owner_id, []).append(alias)

    result = []
    for addr in addrs:
        item = mma_service.serialize(addr)
        item["isOutboundAuth"] = (
            sender_addr_str is not None and addr.address == sender_addr_str
        )
        child_aliases = aliases_by_mma.get(addr.id, [])
        item["aliases"] = [mma_service.serialize(a) for a in child_aliases]
        result.append(item)
    return jsonify({"data": result}), 200


@mail_bp.post("/system-addresses")
@permission_required("system", "manage", "Manage system mail")
def create_system_address():
    body = request.get_json(silent=True) or {}
    address = (body.get("address") or "").strip()
    address_type = (body.get("addressType") or body.get("address_type") or "").strip()
    display_name = (body.get("displayName") or body.get("display_name") or "").strip()
    forward_targets = body.get("forwardTargets") or body.get("forward_targets") or []
    is_protected = bool(body.get("isProtected", False))

    if not address:
        return api_error("VALIDATION_ERROR", "'address' is required", 400)
    if address_type not in ("mailbox", "alias"):
        return api_error(
            "VALIDATION_ERROR", "'addressType' must be 'mailbox' or 'alias'", 400
        )

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain and "@" not in address:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )

    try:
        addr = mma_service.create_system_address(
            address=address,
            address_type=address_type,
            display_name=display_name or None,
            forward_targets=forward_targets if forward_targets else None,
            is_protected=is_protected,
            domain=club_domain,
        )
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="create_system_address",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=addr.address,
    )

    return jsonify(mma_service.serialize(addr)), 201


@mail_bp.delete("/system-addresses/<int:address_id>")
@permission_required("system", "manage", "Manage system mail")
def delete_system_address(address_id: int):

    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"System address {address_id} not found")

    if not addr.is_system:
        raise_error(404, "NOT_FOUND", f"Address {address_id} is not a system address")

    if addr.is_protected:
        return api_error(
            "FORBIDDEN",
            f"Cannot delete protected system address {addr.address}",
            403,
        )

    address_label = addr.address
    try:
        mma_service.delete_system_address(addr)
    except PermissionError as exc:
        return api_error("FORBIDDEN", str(exc), 403)

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="delete_system_address",
        target_type="ManagedMailAddress",
        target_id=address_id,
        target_label=address_label,
    )

    return "", 204


@mail_bp.patch("/system-addresses/<int:address_id>/toggle")
@permission_required("system", "manage", "Manage system mail")
def toggle_system_address(address_id: int):

    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"System address {address_id} not found")

    if not addr.is_system:
        raise_error(404, "NOT_FOUND", f"Address {address_id} is not a system address")

    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        return api_error("VALIDATION_ERROR", "'enabled' (bool) is required", 400)

    mma_service.toggle_mail_enabled(addr, enabled)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="toggle_system_address",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=f"{addr.address} ({'enabled' if enabled else 'disabled'})",
    )

    return jsonify(mma_service.serialize(addr)), 200


# ── System address aliases ────────────────────────────────────────────────────


@mail_bp.get("/system-addresses/<int:address_id>/aliases")
@permission_required("system", "read", "View system mail")
def list_system_aliases(address_id: int):
    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"System address {address_id} not found")
    if not addr.is_system:
        raise_error(404, "NOT_FOUND", f"Address {address_id} is not a system address")
    return jsonify({"data": mma_service.list_aliases(address_id)}), 200


@mail_bp.post("/system-addresses/<int:address_id>/aliases")
@permission_required("system", "manage", "Manage system mail")
def create_system_alias(address_id: int):
    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"System address {address_id} not found")
    if not addr.is_system:
        raise_error(404, "NOT_FOUND", f"Address {address_id} is not a system address")

    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip()
    if not prefix:
        return api_error("VALIDATION_ERROR", "'prefix' is required", 400)

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return api_error(
            "VALIDATION_ERROR", "mail.domain setting is not configured", 400
        )

    try:
        alias = mma_service.create_alias(
            address_id, prefix, club_domain, actor_id=get_current_member().id
        )
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="create_system_alias",
        target_type="ManagedMailAddress",
        target_id=alias.id,
        target_label=alias.address,
    )
    return jsonify(mma_service.serialize(alias)), 201


@mail_bp.delete("/system-addresses/<int:address_id>/aliases/<int:alias_id>")
@permission_required("system", "manage", "Manage system mail")
def delete_system_alias(address_id: int, alias_id: int):
    mma_service.delete_alias(alias_id)
    db.session.commit()
    log_audit(
        actor_id=get_current_member().id,
        action="delete_system_alias",
        target_type="ManagedMailAddress",
        target_id=alias_id,
        target_label=None,
    )
    return "", 204


@mail_bp.patch("/system-addresses/<int:address_id>/aliases/<int:alias_id>/toggle")
@permission_required("system", "manage", "Manage system mail")
def toggle_system_alias(address_id: int, alias_id: int):
    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        return api_error("VALIDATION_ERROR", "'enabled' (bool) is required", 400)
    result = mma_service.toggle_alias_mma(alias_id, enabled)
    if result is None:
        raise_error(404, "NOT_FOUND", f"Alias {alias_id} not found")
    db.session.commit()
    return jsonify(result), 200


# ── System address forwarding targets ─────────────────────────────────────────


@mail_bp.get("/system-addresses/<int:address_id>/forwarding")
@permission_required("system", "read", "View system mail")
def get_system_forwarding(address_id: int):
    import json as _json

    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"System address {address_id} not found")

    if not addr.is_system:
        raise_error(404, "NOT_FOUND", f"Address {address_id} is not a system address")

    targets: list[str] = []
    if addr.fixed_forward_targets:
        try:
            targets = _json.loads(addr.fixed_forward_targets)
        except (ValueError, TypeError):
            targets = []
    elif addr.address_type == "mailbox" and addr.owner_type == "group":
        from vollbuild.core.services.managed_mail import resolve_alias_targets

        targets = resolve_alias_targets(addr)

    return jsonify({"targets": targets}), 200


@mail_bp.put("/system-addresses/<int:address_id>/forwarding")
@permission_required("system", "manage", "Manage system mail")
def update_system_forwarding(address_id: int):
    import json as _json

    from vollbuild.core.services.mail_provisioning import ensure_forwarding

    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"System address {address_id} not found")

    if not addr.is_system:
        raise_error(404, "NOT_FOUND", f"Address {address_id} is not a system address")

    if addr.local_part == "*":
        return api_error(
            "VALIDATION_ERROR",
            "Forwarding targets cannot be set on catch-all addresses",
            400,
        )

    body = request.get_json(silent=True) or {}
    targets = body.get("targets")
    if targets is None or not isinstance(targets, list):
        return api_error("VALIDATION_ERROR", "'targets' (list) is required", 400)

    if not all(isinstance(t, str) and t.strip() for t in targets):
        return api_error(
            "VALIDATION_ERROR", "All targets must be non-empty strings", 400
        )

    targets = [t.strip() for t in targets]

    addr.fixed_forward_targets = _json.dumps(targets) if targets else None

    try:
        ensure_forwarding(addr, targets)
    except Exception as exc:
        db.session.rollback()
        return api_error("VALIDATION_ERROR", f"Failed to update forwarding: {exc}", 500)

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="update_system_forwarding",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=f"{addr.address} → {targets}",
    )

    return jsonify({"targets": targets}), 200


# ── System address password set ───────────────────────────────────────────────


@mail_bp.post("/system-addresses/<int:address_id>/reset-password")
@permission_required("system", "manage", "Manage system mail")
def reset_system_address_password(address_id: int):
    import secrets as _secrets

    from vollbuild.core.services.mail_provisioning import set_system_mailbox_password

    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"System address {address_id} not found")

    if not addr.is_system:
        raise_error(404, "NOT_FOUND", f"Address {address_id} is not a system address")

    if addr.address_type != "mailbox":
        return api_error(
            "VALIDATION_ERROR",
            "Password set is only available for mailbox-type system addresses",
            400,
        )

    if not addr.wildduck_id:
        return api_error(
            "VALIDATION_ERROR",
            "This system address has no provisioned WildDuck mailbox",
            400,
        )

    body = request.get_json(silent=True) or {}
    user_password = (body.get("password") or "").strip()
    auto_generated = False
    if not user_password:
        user_password = _secrets.token_urlsafe(16)
        auto_generated = True

    if len(user_password) < 8:
        return api_error(
            "VALIDATION_ERROR",
            "Password must be at least 8 characters",
            400,
        )

    try:
        set_system_mailbox_password(addr, user_password)
    except Exception as exc:
        return api_error(
            "VALIDATION_ERROR",
            f"Failed to set password: {exc}",
            500,
        )

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="reset_system_mailbox_password",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=addr.address,
    )

    if auto_generated:
        return jsonify({"password": user_password}), 200
    return jsonify({"password": user_password}), 200


# ── fromWhitelist curation ────────────────────────────────────────────────────


@mail_bp.get("/addresses/<int:address_id>/from-whitelist")
@permission_required("system", "read", "View system mail")
def get_from_whitelist(address_id: int):
    import json as _json

    from vollbuild.core.services.mail_provisioning import (
        compute_effective_from_whitelist,
    )
    from vollbuild.core.services.wildduck import try_get_client

    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"Address {address_id} not found")

    if addr.address_type != "mailbox":
        return api_error(
            "VALIDATION_ERROR",
            "fromWhitelist is only available for mailbox-type addresses",
            400,
        )

    curated: list[str] = []
    if addr.from_whitelist:
        try:
            parsed = _json.loads(addr.from_whitelist)
            if isinstance(parsed, list):
                curated = [str(x) for x in parsed if isinstance(x, str)]
        except (ValueError, TypeError):
            pass

    effective = compute_effective_from_whitelist(addr)

    live = None
    wd = try_get_client()
    if wd is not None and addr.wildduck_id:
        try:
            user = wd.get_user(addr.wildduck_id)
            live = user.get("fromWhitelist", [])
        except Exception:
            current_app.logger.warning(
                "WildDuck lookup failed for %s", addr.address, exc_info=True
            )

    return jsonify({"curated": curated, "effective": effective, "live": live}), 200


@mail_bp.put("/addresses/<int:address_id>/from-whitelist")
@permission_required("system", "manage", "Manage system mail")
def update_from_whitelist(address_id: int):
    import json as _json

    addr = db.session.get(ManagedMailAddress, address_id)
    if addr is None:
        raise_error(404, "NOT_FOUND", f"Address {address_id} not found")

    if addr.address_type != "mailbox":
        return api_error(
            "VALIDATION_ERROR",
            "fromWhitelist is only available for mailbox-type addresses",
            400,
        )

    body = request.get_json(silent=True) or {}
    raw = body.get("whitelist")
    if not isinstance(raw, list):
        return api_error("VALIDATION_ERROR", "'whitelist' must be a list", 400)

    email_re = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    cleaned: list[str] = []
    for entry in raw:
        entry = str(entry).strip() if entry else ""
        if not entry:
            continue
        if entry.startswith("*@"):
            return api_error(
                "VALIDATION_ERROR", f"Wildcards are not allowed: {entry}", 400
            )
        if not email_re.match(entry):
            return api_error("VALIDATION_ERROR", f"Invalid email address: {entry}", 400)
        if entry not in cleaned:
            cleaned.append(entry)

    addr.from_whitelist = _json.dumps(cleaned)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(
        actor_id=get_current_member().id,
        action="update_from_whitelist",
        target_type="ManagedMailAddress",
        target_id=addr.id,
        target_label=addr.address,
    )

    try:
        from vollbuild.core.services.mail_provisioning import (
            sync_from_whitelist_for_mma,
        )

        sync_from_whitelist_for_mma(addr)
    except Exception:
        current_app.logger.exception(
            "Saved from-whitelist for %s but could not sync it to WildDuck",
            addr.address,
        )

    return jsonify({"whitelist": cleaned}), 200


# ── Test email ────────────────────────────────────────────────────────────────


@mail_bp.post("/test")
@permission_required("test_email", "send", "Send test email")
def send_test_email():
    body = request.get_json(silent=True) or {}
    from_addr = (body.get("from") or "").strip()
    to_addr = (body.get("to") or "").strip()
    subject = (body.get("subject") or "").strip()

    if not from_addr or not to_addr or not subject:
        return api_error(
            "VALIDATION_ERROR",
            "Fields 'from', 'to', and 'subject' are required",
            400,
        )

    _email_re = _re.compile(r"[^@]+@[^@]+\.[^@]+")
    if not _email_re.match(from_addr):
        return api_error("VALIDATION_ERROR", "Invalid 'from' email address", 400)
    if not _email_re.match(to_addr):
        return api_error("VALIDATION_ERROR", "Invalid 'to' email address", 400)

    configured_sender = SettingService.get("club.notification_sender_email") or ""
    if configured_sender and from_addr != configured_sender:
        return api_error(
            "VALIDATION_ERROR",
            f"'from' must match the club sender address ({configured_sender})",
            400,
        )

    result = MailService.send_test(
        from_addr=from_addr,
        to_addr=to_addr,
        subject=subject,
    )

    return jsonify(result), 200


# ── Mail Administration (unified) ──────────────────────────────────────────────


@mail_bp.get("/resolve-local-part")
@permission_required("aliases", "read", "View aliases")
def resolve_local_part():
    prefix = (request.args.get("prefix") or "").strip()
    if not prefix:
        return jsonify({"localPart": ""}), 200
    resolved = MailAdminService.resolve_local_part(prefix)
    return jsonify({"localPart": resolved}), 200


@mail_bp.get("/wildduck-live")
@permission_required("wildduck", "read", "View WildDuck live state")
def list_wildduck_live():
    data = MailAdminService.list_wildduck_live()
    return jsonify({"data": data}), 200


@mail_bp.delete("/wildduck-live/<string:entry_type>/<string:entry_id>")
@permission_required("wildduck", "delete", "Delete orphan WildDuck entries")
def delete_wildduck_orphan(entry_type: str, entry_id: str):
    if entry_type not in ("mailbox", "alias"):
        return api_error("VALIDATION_ERROR", "Type must be 'mailbox' or 'alias'", 400)
    if not _OBJECTID_RE.match(entry_id):
        return api_error("VALIDATION_ERROR", f"Invalid ID format: {entry_id!r}", 400)

    result = MailAdminService.delete_orphan(
        entry_type=entry_type,
        entry_id=entry_id,
        actor_id=get_current_member().id,
    )
    return jsonify(result), 200


@mail_bp.post("/reconcile")
@permission_required("reconcile", "run", "Trigger mail reconciliation")
def trigger_reconcile():
    from vollbuild.core.tasks.mail_tasks import reconcile_mail

    reconcile_mail.delay()
    return jsonify({"ok": True, "task": "reconcile_mail"}), 202


# ── Health check (no auth required) ─────────────────────────────────────────


@mail_bp.get("/health")
def mail_health():
    """Return WildDuck reachability status. No authentication required."""
    from vollbuild.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        return jsonify({"status": "degraded", "wildduck": "not_configured"}), 200

    try:
        wd.list_users(limit=1)
        return jsonify({"status": "ok", "wildduck": "reachable"}), 200
    except WildDuckError as exc:
        return jsonify(
            {"status": "degraded", "wildduck": "unreachable", "error": str(exc)}
        ), 200
