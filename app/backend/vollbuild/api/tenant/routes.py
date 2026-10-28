"""Tenant management API — create / read / update / delete tenants.

These routes live at ``/api/v1/system/tenants`` and are NOT tenant-scoped —
they are used by the platform administrator (SystemUser with is_superadmin)
to manage the multi-tenant lifecycle.

All routes require the ``@require_system_admin`` decorator, which checks
``User.is_superadmin`` via the ``user_id`` JWT claim.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, make_response, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
)
from sqlalchemy import func, select

from vollbuild.api.permissions import (
    check_impersonation_restriction,
    require_global_permission,
)
from vollbuild.errors import raise_error
from vollbuild.extensions import db
from vollbuild.core.models.member import Member
from vollbuild.core.models.tenant import GlobalAuditEntry, Tenant
from vollbuild.core.models.tenant_request import TenantRequest
from vollbuild.core.models.user import User
from vollbuild.core.tenant.service import TenantService, TenantProvisioningError

tenant_admin_bp = Blueprint("tenant_admin", __name__)

_VALID_STATUSES = {"active", "suspended", "archived"}
_VALID_PLANS = {"starter", "growth", "enterprise"}


# ── Routes ──────────────────────────────────────────────────────────────────


@tenant_admin_bp.route("/tenants", methods=["GET"])
@require_global_permission("tenants.read")
def list_tenants():
    """List all tenants with optional search, filtering, sorting, pagination."""
    args = request.args
    result = TenantService.list_tenants(
        search=args.get("search"),
        plan=args.get("plan"),
        status=args.get("status"),
        sort_by=args.get("sort_by", "created_at"),
        sort_dir=args.get("sort_dir", "asc"),
        page=int(args.get("page", 1)),
        per_page=min(int(args.get("per_page", 20)), 100),
        include_deleted=args.get("include_deleted", "0") == "1",
    )
    return jsonify(
        {
            "tenants": [_tenant_to_dict(t) for t in result["tenants"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
        }
    )


@tenant_admin_bp.route("/tenants", methods=["POST"])
@require_global_permission("tenants.create")
def provision_tenant():
    """Provision a new tenant (creates record + schema + seeds)."""
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    slug = data.get("slug", "").strip()
    plan = data.get("plan", "starter")
    admin_email = data.get("admin_email")
    admin_password = data.get("admin_password")

    if not name or not slug:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": "name and slug are required",
            }
        ), 422

    if not (3 <= len(slug) <= 64):
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": "slug must be between 3 and 64 characters",
            }
        ), 422

    if plan not in _VALID_PLANS:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": f"plan must be one of {sorted(_VALID_PLANS)}",
            }
        ), 422

    try:
        tenant = TenantService.provision_tenant(
            name=name,
            slug=slug,
            plan=plan,
            admin_email=admin_email,
            admin_password=admin_password,
        )
        return (
            jsonify(
                {
                    "tenant": _tenant_to_dict(tenant),
                    "provisioning_status_url": f"/api/v1/system/tenants/{tenant.id}/provisioning-status",
                }
            ),
            201,
        )
    except TenantProvisioningError as exc:
        return jsonify({"error": "PROVISION_FAILED", "message": str(exc)}), 422


@tenant_admin_bp.route("/tenants/<int:tenant_id>", methods=["GET"])
@require_global_permission("tenants.read")
def get_tenant(tenant_id: int):
    """Get a single tenant by ID, including usage summary."""
    tenant = TenantService.get_by_id(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    data = _tenant_to_dict(tenant)
    data["usage"] = TenantService.get_usage_stats(tenant_id)
    return jsonify({"tenant": data})


@tenant_admin_bp.route("/tenants/<int:tenant_id>", methods=["PATCH"])
@require_global_permission("tenants.update")
def update_tenant(tenant_id: int):
    """Update tenant attributes (name, plan, settings)."""
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    plan = data.get("plan")
    settings = data.get("settings")

    if plan is not None and plan not in _VALID_PLANS:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": f"plan must be one of {sorted(_VALID_PLANS)}",
            }
        ), 422

    if plan is not None:
        restriction = check_impersonation_restriction("change_plan")
        if restriction:
            return jsonify({"error": restriction[0], "message": restriction[1]}), 403

    tenant = TenantService.update_tenant(
        tenant_id,
        name=name,
        plan=plan,
        settings=settings,
    )
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>", methods=["DELETE"])
@require_global_permission("tenants.delete")
def delete_tenant(tenant_id: int):
    """Delete a tenant. Soft-delete by default; force=true for permanent deletion."""
    restriction = check_impersonation_restriction("delete_tenant")
    if restriction:
        return jsonify({"error": restriction[0], "message": restriction[1]}), 403

    force = request.args.get("force", "0") == "1"
    deleted = TenantService.delete_tenant(tenant_id, force=force)
    if not deleted:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    action = "permanently deleted" if force else "archived (soft-delete)"
    return jsonify({"message": f"Tenant {action}"}), 200


@tenant_admin_bp.route("/tenants/<int:tenant_id>/disable", methods=["POST"])
@require_global_permission("tenants.update")
def disable_tenant(tenant_id: int):
    """Suspend a tenant."""
    tenant = TenantService.suspend(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/enable", methods=["POST"])
@require_global_permission("tenants.update")
def enable_tenant(tenant_id: int):
    """Reactivate a tenant."""
    tenant = TenantService.activate(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/archive", methods=["POST"])
@require_global_permission("tenants.update")
def archive_tenant(tenant_id: int):
    """Archive a tenant."""
    tenant = TenantService.archive(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/status", methods=["PATCH"])
@require_global_permission("tenants.update")
def update_tenant_status(tenant_id: int):
    """Update tenant status (active / suspended / archived).

    Kept for backward compatibility with the original #133 endpoint.
    Prefer the dedicated /disable, /enable, /archive endpoints.
    """
    data = request.get_json(silent=True) or {}
    status = data.get("status", "").strip()

    if status not in _VALID_STATUSES:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": f"status must be one of {sorted(_VALID_STATUSES)}",
            }
        ), 422

    tenant = TenantService.set_status(tenant_id, status)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify({"tenant": _tenant_to_dict(tenant)})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/stats", methods=["GET"])
@require_global_permission("tenants.read")
def get_tenant_stats(tenant_id: int):
    """Get detailed usage statistics for a tenant."""
    tenant = TenantService.get_by_id(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    stats = TenantService.get_usage_stats(tenant_id)
    return jsonify({"stats": stats})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/provisioning-status", methods=["GET"])
@require_global_permission("tenants.read")
def get_provisioning_status(tenant_id: int):
    """Get async provisioning status for a tenant.

    Currently provisioning is synchronous, so the status is either 'complete'
    or 'not_found'.  When async provisioning is implemented, this endpoint
    will return progress information.
    """
    tenant = TenantService.get_by_id(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404
    return jsonify(
        {
            "tenant_id": tenant_id,
            "status": "complete",
            "slug": tenant.slug,
        }
    )


# ── Impersonation ───────────────────────────────────────────────────────────

_IMPERSONATION_TIMEOUT_MINUTES = 30


@tenant_admin_bp.route("/tenants/<int:tenant_id>/impersonate", methods=["POST"])
@require_global_permission("impersonate")
def impersonate_tenant_user(tenant_id: int):
    """Start impersonating a user within a tenant.

    Requires System Admin. Issues a new JWT with impersonation claims.
    The original admin's identity is stored in ``impersonator_id`` and
    ``impersonator_user_id`` claims for restoration.
    """
    tenant = TenantService.get_by_id(tenant_id)
    if tenant is None:
        return jsonify({"error": "NOT_FOUND", "message": "Tenant not found"}), 404

    if tenant.status != "active":
        return jsonify(
            {
                "error": "TENANT_INACTIVE",
                "message": "Cannot impersonate in an inactive tenant",
            }
        ), 422

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    target_user_id = data.get("user_id")

    if not reason:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": "A reason is required for impersonation",
            }
        ), 422

    claims = get_jwt()
    admin_user_id = claims.get("user_id")
    from vollbuild.api.auth.helpers import parse_identity

    admin_member_id = parse_identity(claims.get("sub", "0"))

    # Find the target member: either a specific user_id or the tenant's admin
    target_member = None

    if target_user_id:
        target_user = db.session.get(User, int(target_user_id))
        if target_user is None:
            return jsonify(
                {"error": "NOT_FOUND", "message": "Target user not found"}
            ), 404
        if target_user.is_superadmin:
            return jsonify(
                {
                    "error": "FORBIDDEN",
                    "message": "Cannot impersonate another system admin",
                }
            ), 403
        # Resolve member from user_id in this tenant
        target_member = _find_member_in_tenant(tenant_id, int(target_user_id))
    else:
        # Find the first member in this tenant
        target_member = _find_member_in_tenant(tenant_id, None)

    if target_member is None:
        return jsonify(
            {"error": "NOT_FOUND", "message": "No members found in this tenant"}
        ), 404

    # Check if target user is a superadmin
    if target_member.user_id:
        target_user = db.session.get(User, target_member.user_id)
        if target_user and target_user.is_superadmin:
            return jsonify(
                {
                    "error": "FORBIDDEN",
                    "message": "Cannot impersonate another system admin",
                }
            ), 403

    target_member_id = target_member.id
    target_user_id = target_member.user_id

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=_IMPERSONATION_TIMEOUT_MINUTES
    )

    additional_claims = {
        "impersonator_id": admin_member_id,
        "impersonator_user_id": admin_user_id,
        "impersonation_reason": reason,
        "impersonation_expires_at": expires_at.isoformat(),
        "tenant_slug": tenant.slug,
    }
    if target_user_id:
        additional_claims["user_id"] = int(target_user_id)

    impersonation_identity = (
        f"user:{target_user_id}" if target_user_id else str(target_member_id)
    )
    access_token = create_access_token(
        identity=impersonation_identity,
        additional_claims=additional_claims,
    )
    refresh_token = create_refresh_token(
        identity=impersonation_identity,
        additional_claims=additional_claims,
    )

    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant_id,
            actor_id=admin_user_id,
            action="impersonation.start",
            target_type="Member",
            target_id=str(target_member_id),
            details={
                "reason": reason,
                "tenant_slug": tenant.slug,
                "target_user_id": target_user_id,
            },
        )
    )
    db.session.commit()

    response = make_response(
        jsonify(
            {
                "impersonating": True,
                "tenant_slug": tenant.slug,
                "member_id": target_member_id,
                "expires_at": expires_at.isoformat(),
            }
        ),
        200,
    )
    set_access_cookies(response, access_token)
    set_refresh_cookies(
        response, refresh_token, max_age=_IMPERSONATION_TIMEOUT_MINUTES * 60
    )
    return response


@tenant_admin_bp.route("/impersonation/stop", methods=["POST"])
@require_global_permission("impersonate")
def stop_impersonation():
    """Stop impersonating and restore the original admin's JWT.

    Reads ``impersonator_id`` and ``impersonator_user_id`` from the
    current JWT claims to re-issue tokens for the original admin.
    """
    claims = get_jwt()
    impersonator_member_id = claims.get("impersonator_id")
    impersonator_user_id = claims.get("impersonator_user_id")

    if impersonator_member_id is None:
        return jsonify(
            {
                "error": "NOT_IMPERSONATING",
                "message": "You are not impersonating anyone",
            }
        ), 400

    admin_member = db.session.get(Member, int(impersonator_member_id))
    if admin_member is None:
        return jsonify(
            {"error": "NOT_FOUND", "message": "Original admin member not found"}
        ), 404

    tenant = TenantService.get_by_slug(claims.get("tenant_slug", ""))
    additional_claims = {}
    restore_identity = str(impersonator_member_id)
    if impersonator_user_id:
        additional_claims["user_id"] = int(impersonator_user_id)
        restore_identity = f"user:{int(impersonator_user_id)}"

    access_token = create_access_token(
        identity=restore_identity,
        additional_claims=additional_claims,
    )
    refresh_token = create_refresh_token(
        identity=restore_identity,
        additional_claims=additional_claims,
    )

    if tenant:
        db.session.add(
            GlobalAuditEntry(
                tenant_id=tenant.id,
                actor_id=impersonator_user_id,
                action="impersonation.end",
                target_type="Member",
                target_id=str(impersonator_member_id),
                details={"tenant_slug": tenant.slug},
            )
        )
        db.session.commit()

    response = make_response(
        jsonify(
            {
                "impersonating": False,
                "member_id": impersonator_member_id,
            }
        ),
        200,
    )
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token, max_age=30 * 24 * 3600)
    return response


# ── Tenant Requests ──────────────────────────────────────────────────────────


def _tenant_request_to_dict(req: TenantRequest) -> dict:
    return {
        "id": req.id,
        "user_id": req.user_id,
        "name": req.name,
        "slug": req.slug,
        "plan": req.plan,
        "status": req.status,
        "admin_note": req.admin_note,
        "reviewed_by": req.reviewed_by,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "updated_at": req.updated_at.isoformat() if req.updated_at else None,
    }


@tenant_admin_bp.route("/tenant-requests", methods=["POST"])
@jwt_required()
def submit_tenant_request():
    """Submit a request for a new tenant (any authenticated user)."""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    slug = (body.get("slug") or "").strip()
    plan = body.get("plan", "starter")

    if not name or not slug:
        raise_error(400, "VALIDATION_ERROR", "name and slug are required")

    if not (3 <= len(slug) <= 64):
        raise_error(400, "VALIDATION_ERROR", "slug must be between 3 and 64 characters")

    if plan not in _VALID_PLANS:
        raise_error(
            400, "VALIDATION_ERROR", f"plan must be one of {sorted(_VALID_PLANS)}"
        )

    existing_tenant = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
    if existing_tenant is not None:
        raise_error(409, "CONFLICT", "A tenant with this slug already exists")

    existing_request = db.session.scalar(
        select(TenantRequest).where(
            TenantRequest.slug == slug,
            TenantRequest.status == "pending",
        )
    )
    if existing_request is not None:
        raise_error(409, "CONFLICT", "A pending request with this slug already exists")

    claims = get_jwt()
    user_id = claims.get("user_id")
    if not user_id:
        raise_error(401, "UNAUTHORIZED", "No user_id in token")

    req = TenantRequest(
        user_id=int(user_id),
        name=name,
        slug=slug,
        plan=plan,
        status="pending",
    )
    db.session.add(req)
    db.session.commit()

    return jsonify({"request": _tenant_request_to_dict(req)}), 201


@tenant_admin_bp.route("/tenant-requests", methods=["GET"])
@require_global_permission("requests.read.all")
def list_tenant_requests():
    """List all tenant requests (superadmin only)."""
    status_filter = request.args.get("status")
    query = select(TenantRequest).order_by(TenantRequest.created_at.desc())
    if status_filter:
        query = query.where(TenantRequest.status == status_filter)

    requests = db.session.scalars(query).all()
    return jsonify({"requests": [_tenant_request_to_dict(r) for r in requests]})


@tenant_admin_bp.route("/tenant-requests/mine", methods=["GET"])
@jwt_required()
def list_my_tenant_requests():
    """List the current user's tenant requests."""
    claims = get_jwt()
    user_id = claims.get("user_id")
    if not user_id:
        raise_error(401, "UNAUTHORIZED", "No user_id in token")

    requests = db.session.scalars(
        select(TenantRequest)
        .where(TenantRequest.user_id == int(user_id))
        .order_by(TenantRequest.created_at.desc())
    ).all()
    return jsonify({"requests": [_tenant_request_to_dict(r) for r in requests]})


@tenant_admin_bp.route("/tenant-requests/<int:req_id>/approve", methods=["POST"])
@require_global_permission("requests.approve")
def approve_tenant_request(req_id: int):
    """Approve a tenant request and provision the tenant (superadmin only)."""
    req = db.session.get(TenantRequest, req_id)
    if req is None:
        raise_error(404, "NOT_FOUND", "Tenant request not found")

    if req.status != "pending":
        raise_error(409, "CONFLICT", f"Request is already {req.status}")

    claims = get_jwt()
    reviewer_id = claims.get("user_id")

    try:
        tenant = TenantService.provision_tenant(
            name=req.name,
            slug=req.slug,
            plan=req.plan,
            admin_email=None,
            admin_password=None,
            admin_user_id=req.user_id,
        )
    except TenantProvisioningError as exc:
        raise_error(422, "PROVISION_FAILED", str(exc))

    req.status = "approved"
    req.reviewed_by = int(reviewer_id) if reviewer_id else None
    db.session.commit()

    return jsonify(
        {
            "request": _tenant_request_to_dict(req),
            "tenant": {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "plan": tenant.plan,
                "status": tenant.status,
            },
        }
    ), 200


@tenant_admin_bp.route("/tenant-requests/<int:req_id>/reject", methods=["POST"])
@require_global_permission("requests.approve")
def reject_tenant_request(req_id: int):
    """Reject a tenant request (superadmin only)."""
    body = request.get_json(silent=True) or {}
    note = (body.get("note") or "").strip() or None

    req = db.session.get(TenantRequest, req_id)
    if req is None:
        raise_error(404, "NOT_FOUND", "Tenant request not found")

    if req.status != "pending":
        raise_error(409, "CONFLICT", f"Request is already {req.status}")

    claims = get_jwt()
    reviewer_id = claims.get("user_id")

    req.status = "rejected"
    req.admin_note = note
    req.reviewed_by = int(reviewer_id) if reviewer_id else None
    db.session.commit()

    return jsonify({"request": _tenant_request_to_dict(req)}), 200


# ── Tenant member management ──────────────────────────────────────────────────


@tenant_admin_bp.route("/tenants/<int:tenant_id>/members", methods=["GET"])
@require_global_permission("tenants.members.read")
def list_tenant_members(tenant_id: int):
    """List all members in a tenant schema."""
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise_error(404, "NOT_FOUND", "Tenant not found")

    from vollbuild.core.tenant.context import set_search_path, reset_search_path

    try:
        set_search_path(tenant_id)
        members = db.session.scalars(
            select(Member).where(Member.archived_at.is_(None)).order_by(Member.id)
        ).all()
    finally:
        reset_search_path()

    return jsonify({"members": [_member_to_dict(m) for m in members]})


@tenant_admin_bp.route("/tenants/<int:tenant_id>/members", methods=["POST"])
@require_global_permission("tenants.members.write")
def add_tenant_member(tenant_id: int):
    """Add an existing User to a tenant as a Member.

    Body: ``{ "email": str }`` or ``{ "user_id": int }``.
    Creates a Member in the tenant schema + a UserTenant link if not
    already present. Returns 409 if the user is already a member.
    """
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise_error(404, "NOT_FOUND", "Tenant not found")

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    user_id_body = body.get("user_id")

    if email:
        user = db.session.scalar(select(User).where(User.email == email))
        if user is None:
            raise_error(404, "NOT_FOUND", f"No user found with email {email}")
    elif user_id_body:
        user = db.session.get(User, int(user_id_body))
        if user is None:
            raise_error(404, "NOT_FOUND", f"No user found with id {user_id_body}")
    else:
        raise_error(400, "VALIDATION_ERROR", "email or user_id is required")

    from vollbuild.core.models.user_tenant import UserTenant

    existing = db.session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == user.id,
            UserTenant.tenant_id == tenant_id,
        )
    )
    if existing is not None:
        raise_error(409, "CONFLICT", "User is already a member of this tenant")

    from vollbuild.core.tenant.context import set_search_path, reset_search_path

    try:
        set_search_path(tenant_id)

        from vollbuild.core.models.role import Role

        default_role = db.session.scalar(
            select(Role).where(Role.is_default.is_(True)).limit(1)
        )
        from vollbuild.core.models.member import MembershipTier

        tier = db.session.scalar(select(MembershipTier).limit(1))

        member = Member(
            tier_id=tier.id if tier else None,
            user_id=user.id,
            status="active",
        )
        if default_role:
            member.roles = [default_role]
        db.session.add(member)
        db.session.flush()

        # Build response dict WHILE search_path is still set to tenant schema
        # to avoid ObjectDeletedError after commit expires attributes
        member_dict = _member_to_dict(member)
        reset_search_path()
    except Exception:
        reset_search_path()
        raise

    db.session.add(UserTenant(user_id=user.id, tenant_id=tenant_id))
    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant_id,
            action="tenant.add_member",
            target_type="User",
            target_id=str(user.id),
            details={"email": user.email, "member_id": member.id},
        )
    )
    db.session.commit()

    return jsonify({"member": member_dict}), 201


# ── Global RBAC management ───────────────────────────────────────────────────


@tenant_admin_bp.route("/global-roles", methods=["GET"])
@require_global_permission("roles.manage")
def list_global_roles():
    """List all global roles with their permissions."""
    from vollbuild.core.models.global_role import (
        GlobalRole,
        GlobalRolePermission,
        GlobalPermission,
    )

    roles = db.session.scalars(select(GlobalRole).order_by(GlobalRole.id)).all()
    result = []
    for role in roles:
        perms = (
            db.session.execute(
                select(GlobalPermission.key)
                .join(
                    GlobalRolePermission,
                    GlobalRolePermission.permission_id == GlobalPermission.id,
                )
                .where(GlobalRolePermission.role_id == role.id)
            )
            .scalars()
            .all()
        )
        result.append(
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system,
                "permissions": sorted(perms),
            }
        )
    return jsonify({"roles": result}), 200


@tenant_admin_bp.route("/global-roles", methods=["POST"])
@require_global_permission("roles.manage")
def create_global_role():
    """Create a custom global role."""
    from vollbuild.core.models.global_role import GlobalRole

    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    description = (body.get("description") or "").strip() or None
    permission_keys = body.get("permissions") or []

    if not name:
        raise_error(400, "VALIDATION_ERROR", "name is required")

    existing = db.session.scalar(select(GlobalRole).where(GlobalRole.name == name))
    if existing is not None:
        raise_error(409, "CONFLICT", "A role with this name already exists")

    role = GlobalRole(name=name, description=description, is_system=False)
    db.session.add(role)
    db.session.flush()

    from vollbuild.core.models.global_role import GlobalPermission, GlobalRolePermission

    for key in permission_keys:
        perm = db.session.scalar(
            select(GlobalPermission).where(GlobalPermission.key == key)
        )
        if perm:
            db.session.add(GlobalRolePermission(role_id=role.id, permission_id=perm.id))

    db.session.commit()
    return jsonify(
        {
            "role": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": False,
                "permissions": sorted(permission_keys),
            }
        }
    ), 201


@tenant_admin_bp.route("/global-roles/<int:role_id>", methods=["PATCH"])
@require_global_permission("roles.manage")
def update_global_role(role_id: int):
    """Update a global role's permissions."""
    from vollbuild.core.models.global_role import (
        GlobalRole,
        GlobalRolePermission,
        GlobalPermission,
    )

    role = db.session.get(GlobalRole, role_id)
    if role is None:
        raise_error(404, "NOT_FOUND", "Role not found")

    body = request.get_json(silent=True) or {}
    permission_keys = body.get("permissions")
    description = body.get("description")

    if description is not None:
        role.description = description.strip() or None

    if permission_keys is not None:
        # Replace all permissions
        db.session.query(GlobalRolePermission).filter(
            GlobalRolePermission.role_id == role_id
        ).delete()
        for key in permission_keys:
            perm = db.session.scalar(
                select(GlobalPermission).where(GlobalPermission.key == key)
            )
            if perm:
                db.session.add(
                    GlobalRolePermission(role_id=role.id, permission_id=perm.id)
                )

    db.session.commit()
    perms = sorted(
        db.session.execute(
            select(GlobalPermission.key)
            .join(
                GlobalRolePermission,
                GlobalRolePermission.permission_id == GlobalPermission.id,
            )
            .where(GlobalRolePermission.role_id == role.id)
        )
        .scalars()
        .all()
    )
    return jsonify(
        {
            "role": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system,
                "permissions": perms,
            }
        }
    ), 200


@tenant_admin_bp.route("/global-permissions", methods=["GET"])
@require_global_permission("roles.manage")
def list_global_permissions():
    """List all available global permissions."""
    from vollbuild.core.models.global_role import GlobalPermission

    perms = db.session.scalars(
        select(GlobalPermission).order_by(GlobalPermission.key)
    ).all()
    return jsonify(
        {
            "permissions": [
                {
                    "id": p.id,
                    "key": p.key,
                    "display_name": p.display_name,
                    "description": p.description,
                }
                for p in perms
            ]
        }
    ), 200


@tenant_admin_bp.route("/users/<int:user_id>/roles", methods=["GET"])
@require_global_permission("roles.manage")
def list_user_global_roles(user_id: int):
    """List a user's global role assignments."""
    from vollbuild.core.models.global_role import GlobalRole, UserGlobalRole

    user = db.session.get(User, user_id)
    if user is None:
        raise_error(404, "NOT_FOUND", "User not found")

    roles = (
        db.session.execute(
            select(GlobalRole)
            .join(UserGlobalRole, UserGlobalRole.role_id == GlobalRole.id)
            .where(UserGlobalRole.user_id == user_id)
        )
        .scalars()
        .all()
    )

    return jsonify(
        {
            "user_id": user_id,
            "email": user.email,
            "roles": [{"id": r.id, "name": r.name} for r in roles],
        }
    ), 200


@tenant_admin_bp.route("/users/<int:user_id>/roles", methods=["POST"])
@require_global_permission("roles.manage")
def assign_user_global_role(user_id: int):
    """Assign a global role to a user."""
    from vollbuild.core.models.global_role import GlobalRole, UserGlobalRole

    user = db.session.get(User, user_id)
    if user is None:
        raise_error(404, "NOT_FOUND", "User not found")

    body = request.get_json(silent=True) or {}
    role_id = body.get("role_id")
    if not role_id:
        raise_error(400, "VALIDATION_ERROR", "role_id is required")

    role = db.session.get(GlobalRole, int(role_id))
    if role is None:
        raise_error(404, "NOT_FOUND", "Role not found")

    existing = db.session.scalar(
        select(UserGlobalRole).where(
            UserGlobalRole.user_id == user_id,
            UserGlobalRole.role_id == role.id,
        )
    )
    if existing is not None:
        raise_error(409, "CONFLICT", "User already has this role")

    db.session.add(UserGlobalRole(user_id=user_id, role_id=role.id))
    db.session.commit()
    return jsonify(
        {"user_id": user_id, "role_id": role.id, "role_name": role.name}
    ), 201


@tenant_admin_bp.route("/users/<int:user_id>/roles/<int:role_id>", methods=["DELETE"])
@require_global_permission("roles.manage")
def remove_user_global_role(user_id: int, role_id: int):
    """Remove a global role from a user."""
    from vollbuild.core.models.global_role import UserGlobalRole

    link = db.session.scalar(
        select(UserGlobalRole).where(
            UserGlobalRole.user_id == user_id,
            UserGlobalRole.role_id == role_id,
        )
    )
    if link is None:
        raise_error(404, "NOT_FOUND", "Role assignment not found")

    db.session.delete(link)
    db.session.commit()
    return jsonify({"ok": True}), 200


@tenant_admin_bp.route("/users/search", methods=["GET"])
@require_global_permission("roles.manage")
def search_users():
    """Search users by email for role assignment."""
    query = (request.args.get("q") or "").strip().lower()
    if len(query) < 2:
        return jsonify({"users": []}), 200

    users = db.session.scalars(
        select(User).where(User.email.ilike(f"%{query}%")).limit(20)
    ).all()
    return jsonify(
        {"users": [{"id": u.id, "email": u.email, "name": u.name} for u in users]}
    ), 200


# ── Platform audit log ──────────────────────────────────────────────────────


@tenant_admin_bp.route("/audit", methods=["GET"])
@require_global_permission("audit.read")
def list_global_audit():
    """List platform-wide audit entries with pagination and filters."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 100)

    query = select(GlobalAuditEntry).order_by(GlobalAuditEntry.time.desc())

    tenant_id = request.args.get("tenant_id")
    if tenant_id:
        query = query.where(GlobalAuditEntry.tenant_id == int(tenant_id))

    action = request.args.get("action")
    if action:
        query = query.where(GlobalAuditEntry.action.ilike(f"%{action}%"))

    total = db.session.scalar(
        select(func.count()).select_from(
            select(GlobalAuditEntry.id).order_by(None).subquery()
        )
    )
    entries = list(
        db.session.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()
    )

    return jsonify(
        {
            "entries": [
                {
                    "id": e.id,
                    "tenant_id": e.tenant_id,
                    "actor_id": e.actor_id,
                    "action": e.action,
                    "target_type": e.target_type,
                    "target_id": e.target_id,
                    "details": e.details,
                    "ip_address": e.ip_address,
                    "time": e.time.isoformat() if e.time else None,
                }
                for e in entries
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    ), 200


# ── Platform metrics ────────────────────────────────────────────────────────


@tenant_admin_bp.route("/metrics", methods=["GET"])
@require_global_permission("audit.read")
def platform_metrics():
    """Aggregate platform metrics from Redis counters."""
    from vollbuild.api.metrics import get_metrics_summary

    summary = get_metrics_summary()
    return jsonify(summary), 200


# ── User management ─────────────────────────────────────────────────────────


@tenant_admin_bp.route("/users", methods=["GET"])
@require_global_permission("users.read")
def list_users():
    """List all users with pagination and search."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 100)
    search = (request.args.get("search") or "").strip().lower()

    query = select(User).order_by(User.id.desc())
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))

    total = db.session.scalar(
        select(func.count()).select_from(select(User.id).order_by(None).subquery())
    )
    users = list(
        db.session.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()
    )

    return jsonify(
        {
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "name": u.name,
                    "is_superadmin": u.is_superadmin,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    ), 200


@tenant_admin_bp.route("/users/<int:user_id>", methods=["GET"])
@require_global_permission("users.read")
def get_user_detail(user_id: int):
    """Get a user's details including tenant memberships."""
    user = db.session.get(User, user_id)
    if user is None:
        raise_error(404, "NOT_FOUND", f"User {user_id} not found")

    from vollbuild.core.models.user_tenant import UserTenant

    memberships = list(
        db.session.scalars(
            select(UserTenant).where(UserTenant.user_id == user.id)
        ).all()
    )

    tenant_ids = [m.tenant_id for m in memberships]
    tenants = (
        list(db.session.scalars(select(Tenant).where(Tenant.id.in_(tenant_ids))).all())
        if tenant_ids
        else []
    )

    return jsonify(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_superadmin": user.is_superadmin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "tenants": [
                {
                    "tenant_id": t.id,
                    "slug": t.slug,
                    "name": t.name,
                    "status": t.status,
                    "is_owner": next(
                        (m.is_owner for m in memberships if m.tenant_id == t.id),
                        False,
                    ),
                }
                for t in tenants
            ],
        }
    ), 200


# ── Helpers ─────────────────────────────────────────────────────────────────


def _find_member_in_tenant(tenant_id: int, user_id: int | None) -> Member | None:
    """Find a member in a tenant schema.

    On PostgreSQL, sets the search_path to the tenant schema.
    On SQLite (tests), falls back to a simple query since all tables
    are in the single schema.
    """
    from vollbuild.core.tenant.context import set_search_path, reset_search_path

    try:
        set_search_path(tenant_id)
        if user_id is not None:
            member = db.session.scalar(
                select(Member).where(
                    Member.user_id == user_id,
                    Member.archived_at.is_(None),
                )
            )
        else:
            member = db.session.scalar(
                select(Member)
                .where(Member.archived_at.is_(None))
                .order_by(Member.id)
                .limit(1)
            )
    except Exception:
        member = None
    finally:
        try:
            reset_search_path()
        except Exception:
            pass
    return member


def _tenant_to_dict(tenant) -> dict:
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "status": tenant.status,
        "settings": tenant.settings or {},
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
        "deleted_at": tenant.deleted_at.isoformat() if tenant.deleted_at else None,
    }


def _member_to_dict(member) -> dict:
    user = member.user
    return {
        "id": member.id,
        "user_id": member.user_id,
        "name": user.name if user else "",
        "email": user.email if user else "",
        "status": member.status,
        "roles": [r.name for r in (member.roles or [])],
    }


# ── Helpers (existing) ──────────────────────────────────────────────────────
