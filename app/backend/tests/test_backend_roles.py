"""HUBRA_ROLE: an app, global or platform backend serves only its area of the API
(hubra.core.roles, docs/platform-backend.md)."""

from __future__ import annotations

import pytest

from hubra import create_app
from hubra.core import roles


# path: (app, global, platform). club = app or global.
SERVES = [
    ("/health", True, True, True),
    ("/api/v1/health", True, True, True),
    ("/api/v1/version", True, True, True),
    ("/api/v1/version/changelog", True, True, True),
    ("/api/v1/instance", True, True, True),
    ("/api/v1/manager/platform/settings", False, False, True),
    ("/api/v1/manager/plugins", False, False, True),
    ("/api/v1/admin/domains", True, False, False),  # club admin: /app/admin
    ("/api/v1/system/clubs", False, True, False),  # the person's own: /global
    ("/api/v1/system/invites/mine", False, True, False),
    ("/api/v1/system/permissions", True, False, False),  # /app/permissions
    ("/api/v1/system/tenant-requests", False, False, True),
    ("/api/v1/platform/settings", False, False, True),
    ("/api/v1/platform/system/tenants", False, False, True),
    ("/api/v1/app/members", True, False, False),
    ("/api/v1/global/auth/refresh", False, True, False),
    ("/api/v1/global/version", True, True, True),
    ("/api/v1/system", False, False, True),
    ("/api/v1/system/tenants/3", False, False, True),
    ("/api/v1/members", True, False, False),
    ("/api/v1/auth/refresh", False, True, False),
    ("/api/v1/account", False, True, False),
    ("/api/v1/plugins/notes/index.js", False, True, False),  # plugin frontends
    ("/api/v1/keys/3", True, False, False),  # a plugin's own routes
    # A prefix match is per path segment.
    ("/api/v1/systemx", True, False, False),
    ("/api/v1/administration", True, False, False),
    ("/api/v1/platformx", True, False, False),
    ("/api/v1/globalx", True, False, False),
]


@pytest.mark.parametrize("path, on_app, on_global, on_platform", SERVES)
def test_serves(path, on_app, on_global, on_platform):
    assert roles.serves(path, "app") is on_app
    assert roles.serves(path, "global") is on_global
    assert roles.serves(path, "platform") is on_platform
    assert roles.serves(path, "club") is (on_app or on_global)
    assert roles.serves(path, "all") is True


def test_unknown_role_refused(monkeypatch):
    monkeypatch.setenv("HUBRA_ROLE", "frontend")
    with pytest.raises(RuntimeError):
        roles.current_role()


def test_task_routes_only_with_a_platform_queue(monkeypatch):
    monkeypatch.delenv("HUBRA_PLATFORM_QUEUE", raising=False)
    assert roles.task_routes() == {}
    monkeypatch.setenv("HUBRA_PLATFORM_QUEUE", "platform")
    routes = roles.task_routes()
    assert routes["hubra.core.tasks.backup_tasks.*"] == {"queue": "platform"}
    assert not any("finance_tasks" in k or "reminder_tasks" in k for k in routes)


def test_task_routes_route_real_task_names(monkeypatch):
    """Every platform task module's tasks are named after the module, so the
    glob routes catch them."""
    from celery.app.routes import prepare

    from hubra.core.tasks import celery_app

    celery_app.loader.import_default_modules()
    monkeypatch.setenv("HUBRA_PLATFORM_QUEUE", "platform")
    (route_for,) = prepare([roles.task_routes()])
    names = [n for n in celery_app.tasks if n.startswith("hubra.core.tasks.")]
    platform = {n for n in names if n.rsplit(".", 1)[0] in roles.PLATFORM_TASK_MODULES}
    assert "hubra.core.tasks.backup_tasks.create_backup" in platform
    assert "hubra.core.tasks.health_tasks.run_health_checks" in platform
    for name in names:
        queue_name = (route_for(name) or {}).get("queue")
        if name in platform:
            assert queue_name == "platform", name
        else:
            assert queue_name != "platform", name


def test_build_component(monkeypatch):
    monkeypatch.setenv("HUBRA_ROLE", "platform")
    assert roles.build_component("api") == "platform-api"
    monkeypatch.setenv("HUBRA_ROLE", "global")
    assert roles.build_component("api") == "global-api"
    for role in ("app", "club"):
        monkeypatch.setenv("HUBRA_ROLE", role)
        assert roles.build_component("worker") == "worker"
        assert roles.build_component("api") == "api"


@pytest.fixture
def role_app(monkeypatch):
    def make(role: str):
        monkeypatch.setenv("HUBRA_ROLE", role)
        return create_app("testing")

    return make


def test_platform_backend_refuses_club_paths(role_app):
    app = role_app("platform")
    assert app.config["HUBRA_ROLE"] == "platform"
    client = app.test_client()
    resp = client.get("/api/v1/members")
    assert resp.status_code == 404
    assert "platform backend" in resp.get_json()["message"]
    # A club slug in the path is stripped first, so it can't sneak past.
    assert client.get("/api/some-club/v1/members").status_code == 404
    # Its own paths reach the routes (401: no sign-in, not 404).
    assert client.get("/api/v1/manager/platform/settings").status_code == 401
    assert client.get("/health").status_code == 200


def test_club_backend_refuses_platform_paths(role_app):
    app = role_app("club")
    client = app.test_client()
    resp = client.get("/api/v1/manager/platform/settings")
    assert resp.status_code == 404
    assert "club backend" in resp.get_json()["message"]
    assert client.get("/api/some-club/v1/system/tenants").status_code == 404
    assert client.get("/api/v1/version").status_code == 200


def test_app_and_global_backends_split_the_rest(role_app):
    app_client = role_app("app").test_client()
    global_client = role_app("global").test_client()
    # Club app: the app backend only.
    assert app_client.get("/api/v1/members").status_code == 401
    resp = global_client.get("/api/v1/members")
    assert resp.status_code == 404
    assert "global backend" in resp.get_json()["message"]
    # Sign-in and account: the global backend only.
    assert global_client.get("/api/v1/global/account/profile").status_code == 401
    assert app_client.get("/api/v1/account/profile").status_code == 404
    # Neither serves the platform.
    assert app_client.get("/api/v1/platform/settings").status_code == 404
    assert global_client.get("/api/v1/platform/settings").status_code == 404
    # With the club in the path an ingress can't tell the areas apart, so
    # such a request reaches the app backend, which answers it (the role gate
    # lets it through; the unknown club is the route's business).
    from hubra.core.extensions import db

    with app_client.application.app_context():
        db.create_all()
    resp = app_client.get("/api/some-club/v1/account/profile")
    assert "Not served" not in (resp.get_json() or {}).get("message", "")
    resp = global_client.get("/api/some-club/v1/members")
    assert "Not served" in resp.get_json()["message"]
    assert global_client.get("/api/v1/version").status_code == 200


def test_every_role_keeps_the_full_url_map(role_app):
    """sync-permissions and the permission listing read the URL map, so a
    split backend must still register every blueprint."""
    full = {r.rule for r in role_app("all").url_map.iter_rules()}
    assert {r.rule for r in role_app("platform").url_map.iter_rules()} == full
    for role in ("club", "app", "global"):
        assert {r.rule for r in role_app(role).url_map.iter_rules()} == full


def test_platform_prefixes_cover_the_platform_blueprints():
    """A platform blueprint mounted outside PLATFORM_PREFIXES would stay on
    the club backend unnoticed."""
    from hubra.modules.core import module

    platform_mounts = {
        bp.url_prefix
        for bp in module.blueprints
        if bp.attr
        in (
            "platform_bp",
            "platform_backups_bp",
            "plugins_bp",
            "support_admin_bp",
            "tenant_admin_bp",
        )
    }
    assert platform_mounts
    for prefix in platform_mounts:
        assert roles.is_platform_path(prefix), prefix
