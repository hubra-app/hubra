"""Server-side module gate.

One ``before_request`` hook maps the matched blueprint to its module and
refuses the request with ``403 MODULE_DISABLED`` while that module is off
for the current tenant.  Routes no longer need their own feature checks.
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
    endpoint = request.endpoint or ""
    bp, _, view = endpoint.rpartition(".")
    if f"{registry.canonical_blueprint(bp)}.{view}" in module.public_endpoints:
        return None
    if not is_enabled(module.code):
        return _disabled(module)
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
