"""Server-side module gate.

One ``before_request`` hook maps the matched blueprint to its module and
refuses the request with ``403 MODULE_DISABLED`` while that module is off
for the current tenant.  Routes no longer need their own feature checks.
A module priced per licence also needs a licence for the signed-in member
(``403 LICENSE_REQUIRED``, ``services.licenses``).
"""

from __future__ import annotations

from functools import wraps

from flask import request

from hubra.core.errors import api_error

from .registry import registry
from .state import is_enabled


def _disabled(module):
    return api_error("MODULE_DISABLED", f"The {module.name} module is not enabled", 403)


def module_gate():
    if request.method == "OPTIONS":
        return None
    module = registry.module_for_blueprint(request.blueprint)
    if module is None or module.required:
        return None
    if (request.endpoint or "") in module.public_endpoints:
        return None
    if not is_enabled(module.code):
        return _disabled(module)
    return _license_check(module)


def _license_check(module):
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    if tenant is None:
        return None
    from hubra.core.services import licenses

    if module.code not in licenses.licensed_modules(tenant):
        return None
    member_id = _member_id()
    if member_id is None:
        # Not signed in: the route's own check answers 401.
        return None
    if licenses.may_use(tenant, module.code, member_id):
        return None
    return api_error(
        "LICENSE_REQUIRED",
        f"You need a licence for {module.name}; ask the club's admin",
        403,
    )


def _member_id() -> int | None:
    try:
        from flask_jwt_extended import verify_jwt_in_request

        if verify_jwt_in_request(optional=True) is None:
            return None
        from hubra.core.permissions import _current_member

        member = _current_member()
        return getattr(member, "id", None) if hasattr(member, "roles") else None
    except Exception:
        return None


def module_required(code: str):
    """Decorator for a route that needs a module other than its blueprint's."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_enabled(code):
                return _disabled(registry.get(code))
            return fn(*args, **kwargs)

        return wrapper

    return decorator
