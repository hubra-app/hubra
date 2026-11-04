"""HUBRA_ROLE: a club or platform backend serves only its side of the API
(hubra.core.roles, docs/platform-backend.md)."""

from __future__ import annotations

import pytest

from hubra import create_app
from hubra.core import roles


@pytest.mark.parametrize(
    "path, club, platform",
    [
        ("/health", True, True),
        ("/api/v1/health", True, True),
        ("/api/v1/version", True, True),
        ("/api/v1/version/changelog", True, True),
        ("/api/v1/instance", True, True),
        ("/api/v1/manager/platform/settings", False, True),
        ("/api/v1/manager/plugins", False, True),
        ("/api/v1/admin/domains", True, False),  # club admin: /app/admin
        ("/api/v1/system/clubs", True, False),  # the person's own: /global
        ("/api/v1/system/invites/mine", True, False),
        ("/api/v1/system/permissions", True, False),  # /app/permissions
        ("/api/v1/system/tenant-requests", False, True),
        ("/api/v1/platform/settings", False, True),
        ("/api/v1/platform/system/tenants", False, True),
        ("/api/v1/app/members", True, False),
        ("/api/v1/global/auth/refresh", True, False),
        ("/api/v1/global/version", True, True),
        ("/api/v1/system", False, True),
        ("/api/v1/system/tenants/3", False, True),
        ("/api/v1/members", True, False),
        ("/api/v1/auth/refresh", True, False),
        ("/api/v1/account", True, False),
        ("/api/v1/plugins/notes/index.js", True, False),
        # A prefix match is per path segment.
        ("/api/v1/systemx", True, False),
        ("/api/v1/administration", True, False),
        ("/api/v1/platformx", True, False),
    ],
)
def test_serves(path, club, platform):
    assert roles.serves(path, "club") is club
    assert roles.serves(path, "platform") is platform
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
    platform = {
        n for n in names if n.rsplit(".", 1)[0] in roles.PLATFORM_TASK_MODULES
    }
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
    monkeypatch.setenv("HUBRA_ROLE", "club")
    assert roles.build_component("worker") == "worker"


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


def test_every_role_keeps_the_full_url_map(role_app):
    """sync-permissions and the permission listing read the URL map, so a
    split backend must still register every blueprint."""
    full = {r.rule for r in role_app("all").url_map.iter_rules()}
    assert {r.rule for r in role_app("platform").url_map.iter_rules()} == full
    assert {r.rule for r in role_app("club").url_map.iter_rules()} == full


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
