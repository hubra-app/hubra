"""Permission decorators for role-based access control (RBAC).

Usage (new structured-key style):

    @permission_required("transactions", "create", "Create transactions")
    def create_transaction(): ...

The permission key is auto-derived as ``{blueprint}.{resource}.{action}``
(e.g. ``finance.transactions.create``).  The ``display_name`` is shown in
the admin UI.

Admin roles (``is_admin=True``) bypass all permission checks.
Other roles need an explicit RolePermission row linking to the Permission.
Includes JWT verification — no need for @jwt_required() alongside it.

Caching: role→permission-key sets are cached in Redis with a 5-minute TTL.
If Redis is unavailable, falls back to a DB query per request.

Tenant-aware: ``_current_member()`` resolves the current Member from either
``current_user`` (if it is already a Member) or the User's ``user_id`` in
the current tenant (future multi-tenant path).
"""

from __future__ import annotations

import logging
from functools import wraps

from flask import g, jsonify, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.redis_client import get_redis_client as _get_redis_client
from hubra.core.redis_client import mark_redis_down as _mark_redis_down


def _current_member():
    """Resolve the current Member from the request context.

    Backward-compatible: returns ``current_user`` if it is a Member instance.
    Multi-tenant path: resolves Member from the User's ``user_id`` + current tenant.

    Returns None when neither path succeeds.
    """
    if current_user is not None and hasattr(current_user, "roles"):
        return current_user
    user_id = getattr(current_user, "id", None)
    if user_id is None:
        user_id = getattr(g, "current_user_id", None)
    if user_id is not None:
        from hubra.core.models.member import Member

        try:
            from hubra.core.tenant.context import current_tenant

            current_tenant()
        except Exception:
            pass
        member = db.session.scalar(
            select(Member).where(
                Member.user_id == user_id,
                Member.archived_at.is_(None),
            )
        )
        if member is not None:
            return member
        # No Member found — fall back to the User object so that
        # require_password_changed can pass it through for noTenant routes.
        return current_user
    return current_user if current_user is not None else None


logger = logging.getLogger(__name__)

_PERM_CACHE_TTL = 300  # 5 minutes


def _derive_perm_key(blueprint_name: str | None, resource: str, action: str) -> str:
    """Build a structured permission key from blueprint + resource + action."""
    prefix = blueprint_name.removesuffix("_bp") if blueprint_name else "app"
    return f"{prefix}.{resource}.{action}"


def _get_role_permission_keys(role_id: int) -> set[str]:
    """Return the set of permission keys for a role, using Redis cache if available."""
    cache_key = f"perms:{role_id}"

    client = _get_redis_client()
    if client is not None:
        try:
            cached = client.smembers(cache_key)
            if cached:
                return {c.decode() if isinstance(c, bytes) else c for c in cached}
        except Exception:
            logger.debug("Redis cache read failed, falling back to DB")
            _mark_redis_down()

    from hubra.core.models.role import Permission, RolePermission

    keys = set(
        db.session.scalars(
            select(Permission.key)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        ).all()
    )

    if client is not None and keys:
        try:
            pipe = client.pipeline()
            pipe.delete(cache_key)
            pipe.sadd(cache_key, *keys)
            pipe.expire(cache_key, _PERM_CACHE_TTL)
            pipe.execute()
        except Exception:
            logger.debug("Redis cache write failed, continuing without cache")
            _mark_redis_down()

    return keys


def _get_member_permission_keys(member) -> set[str]:
    """Return the union of permission keys across all of a member's roles.

    Uses Redis cache keyed by member id when available. Admin roles contribute
    no individual keys (they bypass checks via ``is_admin`` instead).
    """
    role_ids = [r.id for r in (member.roles or [])]
    if not role_ids:
        return set()

    cache_key = f"perms:member:{member.id}"
    client = _get_redis_client()
    if client is not None:
        try:
            cached = client.smembers(cache_key)
            if cached:
                return {c.decode() if isinstance(c, bytes) else c for c in cached}
        except Exception:
            logger.debug("Redis member-perms cache read failed")
            _mark_redis_down()

    keys: set[str] = set()
    for rid in role_ids:
        keys |= _get_role_permission_keys(rid)

    if client is not None and keys:
        try:
            pipe = client.pipeline()
            pipe.delete(cache_key)
            pipe.sadd(cache_key, *keys)
            pipe.expire(cache_key, _PERM_CACHE_TTL)
            pipe.execute()
        except Exception:
            logger.debug("Redis member-perms cache write failed")
            _mark_redis_down()

    return keys


def invalidate_member_permissions(member_id: int) -> None:
    """Delete the cached union permission set for a member."""
    client = _get_redis_client()
    if client is not None:
        try:
            client.delete(f"perms:member:{member_id}")
        except Exception:
            logger.debug("Redis member cache invalidation failed for %s", member_id)
            _mark_redis_down()


def member_is_admin(member) -> bool:
    """Return True if any of the member's roles has ``is_admin=True``."""
    return any(r.is_admin for r in (getattr(member, "roles", None) or []))


def check_grant(actor, *, given=(), taken=(), keys=()) -> None:
    """403 unless *actor* may give the roles *given* (and permission *keys*)
    and take the roles *taken*.

    Only an owner gives or takes the Owner role, only an admin an admin role,
    and anyone else gives only permissions they hold themselves, so a
    ``members.update`` or ``roles.set_permissions`` holder can't climb.
    ``actor`` None is the system itself.
    """
    if actor is None:
        return
    held = getattr(actor, "roles", None) or []
    is_owner = any(r.is_owner for r in held)
    is_admin = member_is_admin(actor)
    for role in (*given, *taken):
        if role.is_owner and not is_owner:
            raise_error(403, "OWNER_ONLY", "Only an owner can give or take the Owner role")
        if role.is_admin and not is_admin:
            raise_error(403, "ADMIN_ONLY", "Only an admin can give or take an admin role")
    if is_admin:
        return
    wanted = set(keys)
    for role in given:
        wanted |= _get_role_permission_keys(role.id)
    missing = wanted - _get_member_permission_keys(actor)
    if missing:
        raise_error(
            403,
            "BEYOND_OWN_PERMISSIONS",
            "You can only give permissions you have yourself: "
            + ", ".join(sorted(missing)[:5]),
        )


def invalidate_role_permissions(role_id: int) -> None:
    """Delete the cached permission set for a role and any member caches that
    include it. Member caches are invalidated by looking up which members hold
    the role at call time (best-effort; silently skips on Redis errors)."""
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.delete(f"perms:{role_id}")
        # Best-effort: clear member caches for members holding this role.
        from hubra.core.models.member import member_roles

        member_ids = db.session.scalars(
            select(member_roles.c.member_id).where(member_roles.c.role_id == role_id)
        ).all()
        if member_ids:
            client.delete(*[f"perms:member:{mid}" for mid in member_ids])
    except Exception:
        logger.debug("Redis cache invalidation failed for role %s", role_id)
        _mark_redis_down()


def permission_required(resource: str, action: str, display_name: str | None = None):
    """Decorator: enforces RBAC check AND registers metadata for auto-discovery.

    Args:
        resource: The resource being accessed (e.g. "transactions", "invoices").
        action: The action being performed (e.g. "read", "create", "update").
        display_name: Human-readable label for the admin UI.
                      Defaults to "{action} {resource}".
    """
    label = display_name or f"{action} {resource}"

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                return jsonify(
                    {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
                ), 401

            member = _current_member()
            if member is None:
                return jsonify(
                    {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
                ), 401

            if member_is_admin(member):
                g.permission_scope = "tenant"
                return fn(*args, **kwargs)

            roles = getattr(member, "roles", None)
            if not roles:
                return jsonify(
                    {"error": "FORBIDDEN", "message": "Insufficient permissions"}
                ), 403

            perm_key = _derive_perm_key(request.blueprint, resource, action)
            allowed = _get_member_permission_keys(member)
            if perm_key not in allowed:
                return jsonify(
                    {"error": "FORBIDDEN", "message": "Insufficient permissions"}
                ), 403

            g.permission_scope = "tenant"
            return fn(*args, **kwargs)

        wrapper._perm_resource = resource
        wrapper._perm_action = action
        wrapper._perm_display_name = label
        return wrapper

    return decorator


def can_update(resource: str, display_name: str | None = None):
    """Decorator: enforces field-level RBAC for PATCH/UPDATE routes.

    Behaviour:
      - Admin roles → pass, all fields allowed.
      - Has coarse ``{bp}.{resource}.update`` → pass, all fields allowed.
      - Has any ``{bp}.{resource}.update.{field}`` → pass, but only
        granted fields are allowed (stored in ``g.updatable_fields``).
      - Otherwise → 403.

    Routes decorated with this should call ``filter_updatable_fields(data)``
    on the validated body before passing it to the service layer.
    """
    label = display_name or f"Update {resource}"

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                return jsonify(
                    {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
                ), 401

            member = _current_member()
            if member is None:
                return jsonify(
                    {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
                ), 401

            if member_is_admin(member):
                g.updatable_fields = None  # None = all fields allowed
                return fn(*args, **kwargs)

            roles = getattr(member, "roles", None)
            if not roles:
                return jsonify(
                    {"error": "FORBIDDEN", "message": "Insufficient permissions"}
                ), 403

            perms = _get_member_permission_keys(member)
            coarse_key = _derive_perm_key(request.blueprint, resource, "update")

            if coarse_key in perms:
                g.updatable_fields = None
                return fn(*args, **kwargs)

            # Check for field-level permissions
            field_prefix = f"{coarse_key}."
            field_perms = {
                p[len(field_prefix) :] for p in perms if p.startswith(field_prefix)
            }
            if field_perms:
                g.updatable_fields = field_perms
                return fn(*args, **kwargs)

            return jsonify(
                {"error": "FORBIDDEN", "message": "Insufficient permissions"}
            ), 403

        wrapper._perm_resource = resource
        wrapper._perm_action = "update"
        wrapper._perm_display_name = label
        return wrapper

    return decorator


def filter_updatable_fields(data: dict) -> dict:
    """Filter a validated body dict to only fields the current user can update.

    Call this inside a route decorated with ``@can_update`` after schema
    validation.  When coarse or admin access is in effect (``g.updatable_fields``
    is None), the dict is returned unchanged.
    """
    allowed = getattr(g, "updatable_fields", None)
    if allowed is None:
        return data
    return {k: v for k, v in data.items() if k in allowed}


def require_admin(fn):
    """Decorator: verifies JWT and checks that the member has an admin role."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify(
                {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
            ), 401

        member = _current_member()
        if member is None:
            return jsonify(
                {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
            ), 401

        if not member_is_admin(member):
            return jsonify(
                {"error": "FORBIDDEN", "message": "Admin role required"}
            ), 403

        return fn(*args, **kwargs)

    return wrapper


def require_member(fn):
    """Decorator: verifies JWT; any authenticated member passes."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify(
                {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
            ), 401

        member = _current_member()
        if member is None:
            return jsonify(
                {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
            ), 401

        return fn(*args, **kwargs)

    return wrapper


def get_user_global_permissions(user_id: int) -> set[str]:
    """Return the set of global permission keys for a user.

    Superadmins return ``{"*"}`` (bypass all checks).
    Queries UserGlobalRole -> GlobalRolePermission -> GlobalPermission.
    """
    from hubra.core.models.user import User

    user = db.session.get(User, user_id)
    if user is not None and user.is_superadmin:
        return {"*"}

    from hubra.core.models.global_role import (
        GlobalPermission,
        GlobalRolePermission,
        UserGlobalRole,
    )

    rows = (
        db.session.execute(
            select(GlobalPermission.key)
            .join(
                GlobalRolePermission,
                GlobalRolePermission.permission_id == GlobalPermission.id,
            )
            .join(
                UserGlobalRole, UserGlobalRole.role_id == GlobalRolePermission.role_id
            )
            .where(UserGlobalRole.user_id == user_id)
        )
        .scalars()
        .all()
    )

    return set(rows)


def require_global_permission(permission_key: str):
    """Decorator: verifies JWT and checks the user has a global permission.

    Superadmins (is_superadmin=True) bypass all checks for backward compat.
    Otherwise queries UserGlobalRole -> GlobalRolePermission -> GlobalPermission
    for the user's effective permission set.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                return jsonify(
                    {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
                ), 401

            from flask_jwt_extended import get_jwt

            claims = get_jwt()
            user_id = claims.get("user_id")
            if user_id is None:
                return jsonify(
                    {"error": "FORBIDDEN", "message": "Authentication required"}
                ), 403

            from hubra.core.models.user import User

            user = db.session.get(User, int(user_id))
            if user is None:
                return jsonify(
                    {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
                ), 401

            if user.is_superadmin:
                g.system_user = user
                g.permission_scope = "global"
                return fn(*args, **kwargs)

            perms = get_user_global_permissions(int(user_id))
            if permission_key not in perms and "*" not in perms:
                return jsonify(
                    {
                        "error": "FORBIDDEN",
                        "message": f"Permission '{permission_key}' required",
                    }
                ), 403

            g.system_user = user
            g.permission_scope = "global"
            return fn(*args, **kwargs)

        return wrapper

    return decorator


_IMPERSONATION_RESTRICTED_ACTIONS = {"delete_tenant", "change_plan"}


def check_impersonation_restriction(action: str) -> tuple[str, str] | None:
    """Check if *action* is restricted during impersonation.

    Returns ``(error_code, message)`` if the action is blocked, or ``None``
    if it's allowed.  Must be called within a JWT-authenticated request
    context.
    """
    if action not in _IMPERSONATION_RESTRICTED_ACTIONS:
        return None

    try:
        from flask_jwt_extended import get_jwt

        claims = get_jwt()
    except Exception:
        return None

    if claims.get("impersonator_id") is not None:
        return (
            "IMPERSONATION_RESTRICTED",
            f"Action '{action}' is not allowed during impersonation",
        )

    return None


def require_password_changed(fn):
    """Decorator: verifies JWT and blocks access if must_change_password is True.

    Apply to any @jwt_required route that should be inaccessible until the member
    sets a permanent password. The change-password and logout endpoints must NOT
    use this decorator — they are the escape hatches.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify(
                {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
            ), 401

        member = _current_member()
        if member is None:
            return jsonify(
                {"error": "UNAUTHORIZED", "message": "Token invalid or expired"}
            ), 401

        from hubra.core.models.user import User

        if isinstance(member, User):
            return fn(*args, **kwargs)

        if member.must_change_password:
            return jsonify(
                {
                    "error": "MUST_CHANGE_PASSWORD",
                    "message": "You must change your password before continuing",
                }
            ), 403

        return fn(*args, **kwargs)

    return wrapper
