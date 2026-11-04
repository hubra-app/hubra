"""The API areas /api/v1/platform, /api/v1/app and /api/v1/global, the old
paths that still lead there (hubra.core.api_areas), and the proxies that
must route both the same way."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from hubra.core import api_areas
from hubra.core.api_areas import canonical_path
from hubra.core.roles import area_of

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "old, new",
    [
        ("/api/v1/members", "/api/v1/app/members"),
        ("/api/v1/members/5/archive", "/api/v1/app/members/5/archive"),
        ("/api/v1/admin/domains", "/api/v1/app/admin/domains"),
        ("/api/v1/system/permissions", "/api/v1/app/permissions"),
        ("/api/v1/auth/refresh", "/api/v1/global/auth/refresh"),
        ("/api/v1/account/linked-accounts", "/api/v1/global/account/linked-accounts"),
        ("/api/v1/version", "/api/v1/global/version"),
        (
            "/api/v1/plugins/notes/frontend.js",
            "/api/v1/global/plugins/notes/frontend.js",
        ),
        ("/api/v1/system/clubs/fc-test/logo", "/api/v1/global/clubs/fc-test/logo"),
        ("/api/v1/system/tenant-requests/mine", "/api/v1/global/tenant-requests/mine"),
        ("/api/v1/system/tenant-requests", "/api/v1/platform/system/tenant-requests"),
        ("/api/v1/system/tenants/3", "/api/v1/platform/system/tenants/3"),
        ("/api/v1/manager/platform/settings", "/api/v1/platform/settings"),
        ("/api/v1/manager/platform/backups", "/api/v1/platform/backups"),
        ("/api/v1/manager/plugins/updates", "/api/v1/platform/plugins/updates"),
        ("/api/v1/manager/support/cases", "/api/v1/platform/support/cases"),
        # New paths, plugin paths and look-alikes stay as they are.
        ("/api/v1/app/members", "/api/v1/app/members"),
        ("/api/v1/platform/system", "/api/v1/platform/system"),
        ("/api/v1/keys/3", "/api/v1/keys/3"),
        ("/api/v1/membersx", "/api/v1/membersx"),
        ("/health", "/health"),
    ],
)
def test_canonical_path(old, new):
    assert canonical_path(old) == new


def test_every_new_path_is_already_canonical():
    for _old, new in api_areas.LEGACY:
        assert canonical_path(api_areas.V1 + new) == api_areas.V1 + new, new


def test_every_core_route_lives_in_an_area(app):
    areas = (api_areas.APP, api_areas.GLOBAL, api_areas.PLATFORM)
    outside = sorted(
        r.rule
        for r in app.url_map.iter_rules()
        if r.rule.startswith("/api/")
        and not r.rule.startswith(areas)
        # Test plugins (tests/plugins/bundled) keep their own prefix.
        and not r.endpoint.startswith(("notes", "badges"))
    )
    assert outside == []


def test_old_and_new_paths_answer_the_same(client):
    old = client.get("/api/v1/version")
    new = client.get("/api/v1/global/version")
    assert old.status_code == new.status_code == 200
    assert old.get_json() == new.get_json()
    # Signed-in routes: 401, not 404, on both.
    assert client.get("/api/v1/members").status_code == 401
    assert client.get("/api/v1/app/members").status_code == 401
    assert client.get("/api/some-club/v1/members").status_code == 401


# Paths to check the proxies with: every old prefix, its new one, and a few
# more under each.
def _sample_paths() -> list[str]:
    out = []
    for old, new in api_areas.LEGACY:
        for p in (old, new):
            out += [api_areas.V1 + p, api_areas.V1 + p + "/x/1"]
    out += [
        "/api/v1/keys/1",
        "/api/v1/platform",
        "/api/v1/global",
        "/api/v1/systemx",
        "/api/v1/globalx",
    ]
    return out


SERVICE = {"platform": "platform-backend", "global": "global-backend", "app": "backend"}


@pytest.mark.parametrize("area", ["platform", "global"])
def test_nginx_routes_the_area_paths(area):
    script = (REPO / "app/deploy/nginx/40-hubra-runtime.sh").read_text()
    pattern = re.search(rf"^{area}_paths='([^']+)'", script, re.M).group(1)
    regex = re.compile(pattern)
    for path in _sample_paths():
        assert bool(regex.search(path)) is (area_of(path) == area), path


@pytest.mark.parametrize(
    "ingress",
    [
        "deploy/app/ingress.yaml",
        "deploy/clusters/contabo/ingress.yaml",
        "deploy/vollbuild-ch/ingress.yaml",
    ],
)
def test_ingress_routes_the_platform_paths(ingress):
    doc = yaml.safe_load((REPO / ingress).read_text())
    rule = next(r for r in doc["spec"]["rules"] if r["host"].startswith("api."))
    paths = [
        (p["path"], p["backend"]["service"]["name"]) for p in rule["http"]["paths"]
    ]

    def service(path: str) -> str:
        # Kubernetes Prefix matching: whole segments, the longest path wins.
        best = max(
            (
                p
                for p in paths
                if p[0] == "/" or path == p[0] or path.startswith(p[0] + "/")
            ),
            key=lambda p: len(p[0]),
        )
        return best[1]

    for path in _sample_paths():
        assert service(path) == SERVICE[area_of(path)], path
