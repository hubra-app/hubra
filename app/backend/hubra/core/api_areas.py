"""The three areas of the API, and the old paths that still lead there.

    /api/v1/platform/...  manage: platform settings, plugins, backups, all
                          clubs, club admin, club requests, support desk.
                          Served by the platform backend.
    /api/v1/app/...       the club app: members, events, finance, ...
                          Served by the club backend.
    /api/v1/global/...    sign-in, the account, translations, version,
                          health and public data: everything that belongs
                          to neither. Served by the club backend, so a
                          platform rollout never touches sign-in.

Plugin routes keep the prefix their manifest gives them and are served by
the club backend.

The paths before this split (``/api/v1/members``, ``/api/v1/manager/...``)
still work: :class:`LegacyApiPaths` rewrites them to the new ones before
Flask matches the URL, so older frontends, plugins and links in sent mail
keep working. URLs registered outside Hubra (the Discord OAuth callbacks
and the interactions endpoint) keep using the old form until they are
changed in the Discord Developer Portal; see docs/platform-backend.md.

The ingress rules and the frontend nginx route old and new paths to the
right backend; tests/test_api_areas.py checks them against ``LEGACY``.
"""

from __future__ import annotations

V1 = "/api/v1"

PLATFORM = f"{V1}/platform"
APP = f"{V1}/app"
GLOBAL = f"{V1}/global"

# Old prefix (after /api/v1) -> new prefix (after /api/v1). The first
# match wins, so a longer prefix comes before a shorter one it starts with.
LEGACY: tuple[tuple[str, str], ...] = (
    # Platform (manage)
    ("/manager/platform", "/platform"),
    ("/manager/plugins", "/platform/plugins"),
    ("/manager/support", "/platform/support"),
    # Under /system but not platform work: the club directory, invites,
    # join and club requests of the signed-in person, ending a support
    # session (global), and a club's permission catalogue (app).
    ("/system/clubs", "/global/clubs"),
    ("/system/invites", "/global/invites"),
    ("/system/join-requests", "/global/join-requests"),
    ("/system/tenant-requests/mine", "/global/tenant-requests/mine"),
    ("/system/impersonation", "/global/impersonation"),
    ("/system/permissions", "/app/permissions"),
    ("/system", "/platform/system"),
    # Global: sign-in, account, public and shared
    ("/auth", "/global/auth"),
    ("/account", "/global/account"),
    ("/i18n", "/global/i18n"),
    ("/health", "/global/health"),
    ("/version", "/global/version"),
    ("/instance", "/global/instance"),
    ("/maintenance", "/global/maintenance"),
    ("/status", "/global/status"),
    ("/public", "/global/public"),
    ("/roadmap", "/global/roadmap"),
    ("/support", "/global/support"),
    ("/apps", "/global/apps"),
    ("/plugins", "/global/plugins"),
    # Club app
    ("/admin", "/app/admin"),  # club admin: domains, club and bank settings
    ("/applications", "/app/applications"),
    ("/audit", "/app/audit"),
    ("/bindings", "/app/bindings"),
    ("/codes", "/app/codes"),
    ("/dashboard", "/app/dashboard"),
    ("/events", "/app/events"),
    ("/features", "/app/features"),
    ("/finance", "/app/finance"),
    ("/functions", "/app/functions"),
    ("/groups", "/app/groups"),
    ("/inventory", "/app/inventory"),
    ("/mail", "/app/mail"),
    ("/members", "/app/members"),
    ("/modules", "/app/modules"),
    ("/notifications", "/app/notifications"),
    ("/polls", "/app/polls"),
    ("/posts", "/app/posts"),
    ("/roles", "/app/roles"),
    ("/settings", "/app/settings"),
    ("/tiers", "/app/tiers"),
)

_LEGACY_FULL = tuple((V1 + old, V1 + new) for old, new in LEGACY)


def _under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def canonical_path(path: str) -> str:
    """The current path for *path*; unchanged when it isn't an old one."""
    if not path.startswith(V1 + "/"):
        return path
    for old, new in _LEGACY_FULL:
        if _under(path, old):
            return new + path[len(old) :]
    return path


def legacy_prefixes(new_prefix: str) -> tuple[str, ...]:
    """Old full prefixes that now lead under *new_prefix* (for the ingress
    and nginx rules that must still route them)."""
    return tuple(old for old, new in _LEGACY_FULL if _under(new, new_prefix))


class LegacyApiPaths:
    """WSGI wrapper: rewrite an old API path to its new one before Flask
    matches the URL. Runs inside the tenant-slug wrapper, so
    ``/api/<slug>/v1/members`` becomes ``/api/v1/members`` first, then
    ``/api/v1/app/members``."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        new = canonical_path(path)
        if new != path:
            environ["PATH_INFO"] = new
            environ["hubra.legacy_api_path"] = path
        return self.wsgi_app(environ, start_response)
