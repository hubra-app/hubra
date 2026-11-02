"""Which part of the API a backend process serves: ``HUBRA_ROLE``.

One image, three roles (docs/platform-backend.md):

- ``all`` (default): every route, as before. Compose installs and tests.
- ``club``: everything except the platform API.
- ``platform``: only the platform API (manage's platform and club admin
  views, club requests, support sessions), plus health and version.

Every role registers every blueprint, so the URL map, ``url_for``,
``flask sync-permissions`` and the permission listing stay complete. A
request for a path the role doesn't serve gets a 404 before any other
hook runs. The ingress (or the frontend nginx) sends the same prefixes to
the platform backend, so in a split install a wrong route is never hit.

Celery: with ``HUBRA_PLATFORM_QUEUE`` set (for example ``platform``), the
platform task modules below go to that queue and a platform worker
(``celery worker -Q platform``) runs them. Unset, every task stays on the
default queue, as before, so a single worker keeps running everything.
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, request

ROLES = ("all", "club", "platform")

# Paths of the platform API. Keep in step with the ingress rules
# (deploy/app/ingress.yaml, deploy/clusters/*/ingress.yaml) and the frontend
# nginx (app/deploy/nginx/40-hubra-runtime.sh).
PLATFORM_PREFIXES = (
    "/api/v1/manager",
    "/api/v1/admin",
    "/api/v1/system",
)

# Served by every role: probes and the build/version info.
SHARED_PATHS = (
    "/health",
    "/api/v1/health",
    "/api/v1/version",
    "/api/v1/instance",
)

# Celery task modules that belong to the platform: backups, health and
# infrastructure checks, upgrades, plugins, quotas, platform alerts and the
# platform Discord log. Club work (invoices, reminders, mail, push, club
# Discord bot) stays on the default queue.
PLATFORM_TASK_MODULES = (
    "hubra.core.tasks.backup_tasks",
    "hubra.core.tasks.health_tasks",
    "hubra.core.tasks.infra_checks",
    "hubra.core.tasks.monitoring",
    "hubra.core.tasks.domain_tasks",
    "hubra.core.tasks.mail_monitor_tasks",
    "hubra.core.tasks.platform_discord_tasks",
    "hubra.core.tasks.plugin_tasks",
    "hubra.core.tasks.quota_tasks",
    "hubra.core.tasks.upgrade_tasks",
)


def current_role() -> str:
    """The role from ``HUBRA_ROLE``; ``all`` when unset."""
    role = (os.environ.get("HUBRA_ROLE") or "all").strip().lower()
    if role not in ROLES:
        raise RuntimeError(
            f"HUBRA_ROLE={role!r} is not one of {', '.join(ROLES)}"
        )
    return role


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def is_platform_path(path: str) -> bool:
    return _matches(path, PLATFORM_PREFIXES)


def serves(path: str, role: str) -> bool:
    """Whether a backend in *role* answers *path* (slug already stripped)."""
    if role == "all" or _matches(path, SHARED_PATHS):
        return True
    if role == "platform":
        return is_platform_path(path)
    return not is_platform_path(path)


def install_role_gate(app: Flask) -> None:
    """Answer 404 for paths this process's role doesn't serve.

    Registered before every other ``before_request`` hook, so a refused
    request never touches the tenant resolver, the maintenance gate or a
    route.
    """
    role = current_role()
    app.config["HUBRA_ROLE"] = role
    if role == "all":
        return

    @app.before_request
    def _role_gate():
        if serves(request.path, role):
            return None
        return jsonify(
            {
                "error": "NOT_FOUND",
                "message": f"Not served by the {role} backend.",
            }
        ), 404


def platform_queue() -> str:
    """The Celery queue for platform tasks, or "" to keep them on the default."""
    return (os.environ.get("HUBRA_PLATFORM_QUEUE") or "").strip()


def task_routes() -> dict:
    """Celery ``task_routes`` sending platform tasks to the platform queue."""
    queue = platform_queue()
    if not queue:
        return {}
    return {f"{module}.*": {"queue": queue} for module in PLATFORM_TASK_MODULES}


def build_component(kind: str) -> str:
    """Name for the build heartbeat (manage › Diagnose › Builds)."""
    return f"platform-{kind}" if current_role() == "platform" else kind
