"""Which part of the API a backend process serves: ``HUBRA_ROLE``.

One image, three roles (docs/platform-backend.md):

- ``all`` (default): every route, as before. Compose installs and tests.
- ``club``: everything except the platform API: the club app
  (``/api/v1/app``), sign-in and account (``/api/v1/global``) and plugins.
- ``platform``: only the platform API (``/api/v1/platform``: manage's
  platform and club admin views, club requests, the support desk), plus
  health and version.

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

# The platform API (hubra.core.api_areas). The role gate sees the new path,
# after old ones were rewritten; the ingress and the frontend nginx also
# route the old platform paths (api_areas.legacy_prefixes) here.
PLATFORM_PREFIXES = ("/api/v1/platform",)

# Served by every role: probes and the build/version info.
SHARED_PATHS = (
    "/health",
    "/api/v1/global/health",
    "/api/v1/global/version",
    "/api/v1/global/instance",
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
        raise RuntimeError(f"HUBRA_ROLE={role!r} is not one of {', '.join(ROLES)}")
    return role


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def is_platform_path(path: str) -> bool:
    return _matches(path, PLATFORM_PREFIXES)


def serves(path: str, role: str) -> bool:
    """Whether a backend in *role* answers *path* (slug already stripped;
    an old path counts as the new one it is rewritten to)."""
    from hubra.core.api_areas import canonical_path

    path = canonical_path(path)
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
