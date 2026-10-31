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
        from hubra.core.tenant.context import current_tenant

        # An account (SSO) token never opens a club: only the club token from
        # /auth/switch-tenant does, which checks that the membership is on
        # and the address confirmed, and which a club can revoke.
        if current_tenant() is not None:
            return None
        member = db.session.scalar(
            select(Member).where(
                Member.user_id == user_id,
                Member.archived_at.is_(None),
            )
        )
        if member is not None:
            return None if member.is_blocked else member
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


def _club_scope() -> str:
    """The schema whose roles and members the cache keys are about.

    Role and member ids restart in every club schema, so a key without the
    club would hand club A's member 5 the permissions of club B's member 5.
    """
    path = getattr(g, "_search_path", None)  # set by set_search_path on Postgres
    if path:
        return path.split(",")[0].strip()
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    return f"tenant_{tenant.id}" if tenant is not None else "public"


def _role_cache_key(role_id: int) -> str:
    return f"perms:{_club_scope()}:{role_id}"


def _member_cache_key(member_id: int) -> str:
    return f"perms:{_club_scope()}:member:{member_id}"


def _get_role_permission_keys(role_id: int) -> set[str]:
    """Return the set of permission keys for a role, using Redis cache if available."""
    cache_key = _role_cache_key(role_id)

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


def function_roles(member) -> list:
    """Roles the member holds through a club function whose term runs today
    (Kassier gives Treasurer). Derived on every check, never stored on the
    member, so leaving the function or the end of the term takes them away."""
    member_id = getattr(member, "id", None)
    if member_id is None or not hasattr(member, "roles"):
        return []  # a platform User, not a club member
    memo = g.setdefault("_function_roles", {})
    key = (_club_scope(), member_id)
    if key not in memo:
        from datetime import date

        from hubra.core.models.function import Function, FunctionHolder
        from hubra.core.models.role import Role

        memo[key] = list(
            db.session.scalars(
                select(Role)
                .join(Function, Function.grants_tenant_role_id == Role.id)
                .join(FunctionHolder, FunctionHolder.function_id == Function.id)
                .where(
                    FunctionHolder.member_id == member_id,
                    Role.is_owner.is_(False),
                    *_active_term(date.today()),
                )
                .distinct()
            ).all()
        )
    return memo[key]


def _active_term(today):
    from sqlalchemy import or_

    from hubra.core.models.function import FunctionHolder

    return (
        or_(FunctionHolder.term_start.is_(None), FunctionHolder.term_start <= today),
        or_(FunctionHolder.term_end.is_(None), FunctionHolder.term_end >= today),
    )


def function_role_grants() -> dict[int, list[dict]]:
    """For the members list: member id -> the roles they hold through a
    function, as ``{"id", "name", "function"}``. One query per request."""
    if "_function_role_grants" not in g:
        from datetime import date

        from hubra.core.models.function import Function, FunctionHolder
        from hubra.core.models.role import Role

        rows = db.session.execute(
            select(FunctionHolder.member_id, Role.id, Role.name, Function.name)
            .join(Function, Function.id == FunctionHolder.function_id)
            .join(Role, Role.id == Function.grants_tenant_role_id)
            .where(Role.is_owner.is_(False), *_active_term(date.today()))
            .order_by(Function.name)
        ).all()
        grants: dict[int, list[dict]] = {}
        for member_id, role_id, role_name, function_name in rows:
            grants.setdefault(member_id, []).append(
                {"id": role_id, "name": role_name, "function": function_name}
            )
        g._function_role_grants = grants
    return g._function_role_grants


def scoped_role_grants() -> dict[int, list[dict]]:
    """For the members list: member id -> the roles they hold for one group,
    as ``{"id", "name", "group_id", "group"}``. One query per request."""
    if "_scoped_role_grants" not in g:
        from hubra.core.models.group import Group
        from hubra.core.models.role import MemberRoleScope, Role

        rows = db.session.execute(
            select(MemberRoleScope.member_id, Role.id, Role.name, Group.id, Group.name)
            .join(Role, Role.id == MemberRoleScope.role_id)
            .join(Group, Group.id == MemberRoleScope.group_id)
            .order_by(Group.name)
        ).all()
        grants: dict[int, list[dict]] = {}
        for member_id, role_id, role_name, group_id, group_name in rows:
            grants.setdefault(member_id, []).append(
                {"id": role_id, "name": role_name, "group_id": group_id, "group": group_name}
            )
        g._scoped_role_grants = grants
    return g._scoped_role_grants


def held_roles(member) -> list:
    """The member's own roles and those of the functions they hold."""
    own = list(getattr(member, "roles", None) or [])
    ids = {r.id for r in own}
    return own + [r for r in function_roles(member) if r.id not in ids]


def _get_member_permission_keys(member) -> set[str]:
    """Return the union of permission keys across all of a member's roles.

    Uses Redis cache keyed by member id when available. Admin roles contribute
    no individual keys (they bypass checks via ``is_admin`` instead).
    """
    role_ids = [r.id for r in held_roles(member)]
    if not role_ids:
        return set()

    cache_key = _member_cache_key(member.id)
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


def scoped_permission_keys(member) -> dict[int, set[str]]:
    """Group id -> the permission keys the member holds for that group only
    (``member_role_scopes``). Admin roles are never held for one group."""
    member_id = getattr(member, "id", None)
    if member_id is None or not hasattr(member, "roles"):
        return {}
    memo = g.setdefault("_scoped_keys", {})
    key = (_club_scope(), member_id)
    if key not in memo:
        from hubra.core.models.role import MemberRoleScope, Role

        rows = db.session.execute(
            select(MemberRoleScope.group_id, MemberRoleScope.role_id)
            .join(Role, Role.id == MemberRoleScope.role_id)
            .where(MemberRoleScope.member_id == member_id, Role.is_admin.is_(False))
        ).all()
        scoped: dict[int, set[str]] = {}
        for group_id, role_id in rows:
            scoped.setdefault(group_id, set()).update(_get_role_permission_keys(role_id))
        memo[key] = scoped
    return memo[key]


def _scope_id(kwargs: dict, scope: str | None) -> int | None:
    if scope is None:
        return None
    value = kwargs.get(scope)
    return value if isinstance(value, int) else None


def invalidate_member_permissions(member_id: int) -> None:
    """Delete the cached union permission set for a member."""
    g.pop("_function_roles", None)
    g.pop("_function_role_grants", None)
    g.pop("_scoped_keys", None)
    g.pop("_scoped_role_grants", None)
    client = _get_redis_client()
    if client is not None:
        try:
            client.delete(_member_cache_key(member_id))
        except Exception:
            logger.debug("Redis member cache invalidation failed for %s", member_id)
            _mark_redis_down()


def member_is_admin(member) -> bool:
    """Return True if any of the member's roles has ``is_admin=True``."""
    return any(r.is_admin for r in held_roles(member))


# Rights that no single route stands for (a route checks them itself).
# sync-permissions adds them to the Permission table like the route ones.
EXTRA_PERMISSIONS = (
    {
        "key": "posts.posts.moderate",
        "display_name": "Moderate posts and comments",
        "resource": "posts",
        "action": "moderate",
        "blueprint": "posts_bp",
    },
    {
        "key": "inventory.items.create_own",
        "display_name": "Add own inventory items",
        "resource": "items",
        "action": "create_own",
        "blueprint": "inventory_bp",
    },
)


def member_has_permission(member, key: str) -> bool:
    """True for an admin, or when one of the member's roles grants *key*."""
    if member is None:
        return False
    return member_is_admin(member) or key in _get_member_permission_keys(member)


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
    held = held_roles(actor)
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
            "You can only give or take permissions you have yourself: "
            + ", ".join(sorted(missing)[:5]),
        )


def check_global_grant(keys) -> None:
    """403 unless the platform user of this request holds every platform
    permission in *keys* (a superadmin holds all). The platform's version of
    ``check_grant``: ``roles.manage`` alone does not let anyone climb."""
    user = getattr(g, "system_user", None)
    if user is None:
        return  # the system itself (CLI, tasks)
    held = get_user_global_permissions(user.id)
    if "*" in held:
        return
    missing = set(keys) - held
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
        client.delete(_role_cache_key(role_id))
        # Best-effort: clear member caches for members holding this role.
        from hubra.core.models.member import member_roles

        from hubra.core.models.function import Function, FunctionHolder

        member_ids = set(
            db.session.scalars(
                select(member_roles.c.member_id).where(member_roles.c.role_id == role_id)
            ).all()
        )
        # ... and those who hold it through a function.
        member_ids |= set(
            db.session.scalars(
                select(FunctionHolder.member_id)
                .join(Function, Function.id == FunctionHolder.function_id)
                .where(Function.grants_tenant_role_id == role_id)
            ).all()
        )
        if member_ids:
            client.delete(*[_member_cache_key(mid) for mid in member_ids])
    except Exception:
        logger.debug("Redis cache invalidation failed for role %s", role_id)
        _mark_redis_down()


def created_by(model, column: str = "created_by", arg: str = "id"):
    """``allow`` for ``permission_required``: the member who created the row
    in the route argument *arg* acts on it (their own event, their own poll)."""
    col = getattr(model, column)

    def allow(member, **kwargs):
        object_id = kwargs.get(arg)
        if object_id is None:
            return None
        owner = db.session.scalar(select(col).where(model.id == object_id))
        return "creator" if owner is not None and owner == member.id else None

    return allow


def permission_required(
    resource: str,
    action: str,
    display_name: str | None = None,
    *,
    scope: str | None = None,
    allow=None,
):
    """Decorator: enforces RBAC check AND registers metadata for auto-discovery.

    Args:
        resource: The resource being accessed (e.g. "transactions", "invoices").
        action: The action being performed (e.g. "read", "create", "update").
        display_name: Human-readable label for the admin UI.
                      Defaults to "{action} {resource}".
        scope: The route argument holding a group id (``"group_id"``). A role
               held for that group only (``member_role_scopes``) passes too.
        allow: Object-level access for members without the right, called as
               ``allow(member, **kwargs)`` with the route arguments. When it
               returns a reason (``"owner"``), the request passes with
               ``g.permission_scope = "object"`` and ``g.object_access`` set
               to that reason, and the route keeps to what the reason allows.
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

            perm_key = _derive_perm_key(request.blueprint, resource, action)
            if held_roles(member) and perm_key in _get_member_permission_keys(member):
                g.permission_scope = "tenant"
                return fn(*args, **kwargs)

            group_id = _scope_id(kwargs, scope)
            if group_id is not None and perm_key in scoped_permission_keys(member).get(
                group_id, ()
            ):
                g.permission_scope = "group"
                return fn(*args, **kwargs)

            if allow is not None and hasattr(member, "roles"):
                reason = allow(member, **kwargs)
                if reason:
                    g.permission_scope = "object"
                    g.object_access = reason
                    return fn(*args, **kwargs)

            return jsonify(
                {"error": "FORBIDDEN", "message": "Insufficient permissions"}
            ), 403

        wrapper._perm_resource = resource
        wrapper._perm_action = action
        wrapper._perm_display_name = label
        return wrapper

    return decorator


def can_update(resource: str, display_name: str | None = None, *, scope: str | None = None):
    """Decorator: enforces field-level RBAC for PATCH/UPDATE routes.

    Behaviour:
      - Admin roles → pass, all fields allowed.
      - Has coarse ``{bp}.{resource}.update`` → pass, all fields allowed.
      - Has any ``{bp}.{resource}.update.{field}`` → pass, but only
        granted fields are allowed (stored in ``g.updatable_fields``).
      - Otherwise → 403.

    Routes decorated with this should call ``filter_updatable_fields(data)``
    on the validated body before passing it to the service layer. ``scope``
    works as on ``permission_required``: a role held for that group adds its
    keys.
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

            perms = set(_get_member_permission_keys(member)) if held_roles(member) else set()
            group_id = _scope_id(kwargs, scope)
            if group_id is not None:
                perms |= scoped_permission_keys(member).get(group_id, set())
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


# Platform rights that amount to control of the whole server: plugin code
# runs inside the backend, and a restore overwrites every club. Only the
# superadmin flag carries them; no global role can.
SUPERADMIN_ONLY = frozenset({"plugins.manage", "backups.manage"})


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

    return set(rows) - SUPERADMIN_ONLY


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


# Support sees a club as the member does, but never changes their account.
_IMPERSONATION_RESTRICTED_ACTIONS = {"delete_tenant", "change_plan", "change_account"}


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


# Requests a read-only impersonation may still make: ending it, and keeping
# the session alive.
_READ_ONLY_IMPERSONATION_ALLOWED = {
    "tenant_admin.stop_impersonation",
    "auth_bp.logout",
    "auth_bp.refresh",
}


def read_only_impersonation():
    """before_request: an impersonation started without "allow changes"
    only looks. Every write is refused, whatever the member may do."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    if request.endpoint in _READ_ONLY_IMPERSONATION_ALLOWED:
        return None
    try:
        verify_jwt_in_request(optional=True)
        from flask_jwt_extended import get_jwt

        claims = get_jwt()
    except Exception:  # noqa: BLE001 - the route's own check reports it
        return None
    if claims.get("impersonator_id") is None:
        return None
    if claims.get("impersonation_mode") == "act":
        return None
    return jsonify(
        {
            "error": "IMPERSONATION_READ_ONLY",
            "message": "This support session can only look; start one that allows changes",
        }
    ), 403


def refuse_during_impersonation() -> None:
    """Support sees a club as the member does, but doesn't end the member's
    membership or sessions for them."""
    from flask_jwt_extended import get_jwt

    if get_jwt().get("impersonator_id") is not None:
        raise_error(
            403, "IMPERSONATION_RESTRICTED", "Not allowed during impersonation"
        )
