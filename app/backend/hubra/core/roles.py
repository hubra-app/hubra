"""Which part of the API a backend process serves: ``HUBRA_ROLE``.

One build, one role per process (docs/platform-backend.md):

- ``all`` (default): every route, as before. Compose installs and tests.
- ``app``: the club app (``/api/v1/app``) and plugin routes.
- ``global``: sign-in, account and public data (``/api/v1/global``).
- ``club``: ``app`` and ``global`` together (Compose).

A path with the club in it (``/api/<slug>/v1/...``) can't be told apart by
an ingress path prefix, so it always reaches the app backend, which answers
only club paths that way. The frontends send the club as a header and never
use these paths.
- ``platform``: only the platform API (``/api/v1/platform``: manage's
  platform and club admin views, club requests, the support desk), plus
  health and version.

Each role registers (and imports) only the blueprints of the areas it
serves, plus the shared ones (probes, version, OAuth metadata): see
:func:`registers`. So a platform backend holds no club routes, and each
role's image carries only the code its routes and Hubra's core need
(``app/backend/scripts/role_files.py``). Plugins' routes, models and task
modules are imported only where they are served: ``global`` and
``platform`` read plugin manifests only
(``hubra.core.plugins.loader.MANIFEST_ONLY_ROLES``). The club permission
catalog comes from the club routes, so ``flask sync-permissions`` fills it
only in a role that loads them (``all``, ``club``, ``app``). A request for
a path the role doesn't serve gets a 404 before any other hook runs. The
ingress (or the frontend nginx) sends each area's prefixes to its backend,
so in a split install a wrong route is never hit.

Celery: with ``HUBRA_PLATFORM_QUEUE`` set (for example ``platform``), the
platform task modules below go to that queue and a platform worker
(``celery worker -Q platform``) runs them. Unset, every task stays on the
default queue, as before, so a single worker keeps running everything.
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, request

# app, global and platform each serve one API area (hubra.core.api_areas);
# club is app + global together, for a Compose install with one club
# backend next to the platform backend.
ROLES = ("all", "club", "app", "global", "platform")

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
    # OAuth server metadata (RFC 8414), at the root of the API host.
    "/.well-known/oauth-authorization-server",
    # OpenID Connect discovery (docs/oidc.md), same place.
    "/.well-known/openid-configuration",
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


def area_of(path: str) -> str:
    """``platform``, ``global`` or ``app`` for a request path. Old paths count
    as the new one they are rewritten to; plugin routes and anything else
    belong to the app."""
    from hubra.core.api_areas import GLOBAL, canonical_path

    path = canonical_path(path)
    if is_platform_path(path):
        return "platform"
    if _matches(path, (GLOBAL,)):
        return "global"
    return "app"


def serves(path: str, role: str) -> bool:
    """Whether a backend in *role* answers *path* (slug already stripped)."""
    from hubra.core.api_areas import canonical_path

    if role == "all" or _matches(canonical_path(path), SHARED_PATHS):
        return True
    area = area_of(path)
    if role == "club":
        return area in ("app", "global")
    return area == role


def registers(blueprint, role: str) -> bool:
    """Whether a backend in *role* registers *blueprint* (a module manifest's
    :class:`hubra.core.modules.base.Blueprint`): every one in ``all``, the
    shared ones everywhere, otherwise those whose ``url_prefix`` lies in an
    area the role serves. Plugin blueprints are club routes (``app``)."""
    if role == "all" or getattr(blueprint, "shared", False):
        return True
    area = area_of(blueprint.url_prefix or "/")
    if role == "club":
        return area in ("app", "global")
    return area == role


def loads_club_routes(role: str | None = None) -> bool:
    """Whether a backend in *role* (default: this one) registers the club
    app's routes, and so can fill the club permission catalog."""
    return (role or current_role()) in ("all", "club", "app")


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


# Club work that may take long and that nobody is waiting for: digests,
# monthly statements, mailbox counters, translation reports. With
# HUBRA_BULK_QUEUE set they go to that queue, so a worker of their own can
# run them and a password-reset mail never waits behind them.
BULK_TASK_MODULES = (
    "hubra.core.tasks.digest_tasks",
    "hubra.core.tasks.mail_sync",
    "hubra.core.tasks.i18n_tasks",
)


def bulk_queue() -> str:
    """The Celery queue for bulk club work, or "" to keep it on the default."""
    return (os.environ.get("HUBRA_BULK_QUEUE") or "").strip()


def task_routes() -> dict:
    """Celery ``task_routes``: platform tasks to the platform queue and bulk
    club work to the bulk queue, each only when its queue is set."""
    routes: dict = {}
    queue = platform_queue()
    if queue:
        routes.update({f"{m}.*": {"queue": queue} for m in PLATFORM_TASK_MODULES})
    queue = bulk_queue()
    if queue:
        routes.update({f"{m}.*": {"queue": queue} for m in BULK_TASK_MODULES})
    return routes


def build_component(kind: str) -> str:
    """Name for the build heartbeat (manage › Diagnose › Builds): ``api`` and
    ``worker`` for the app (or a single) backend, ``global-api``,
    ``platform-api``, ``platform-worker`` for the others.  Beat is always
    ``beat``: there is only ever one, it holds every schedule, and the role
    images run it from the platform image (``HUBRA_ROLE=platform``)."""
    if kind == "beat":
        return kind
    role = current_role()
    return f"{role}-{kind}" if role in ("platform", "global") else kind
