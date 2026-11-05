"""scripts/role_files.py: the files each backend role's image holds.

The images leave out the hubra modules their role doesn't import, so a
module a role does import but the list misses would fail only in production.
These tests start every role and compare.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("role_files", BACKEND / "scripts" / "role_files.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


role_files = _script()

# Starts the role as gunicorn, the worker and beat would (the app, Celery
# with its task modules, the CLI) and prints the hubra modules it imported.
_PROBE = """
import json, sys
from hubra import create_app
app = create_app("testing")
from hubra.core.tasks import celery_app
celery_app.loader.import_default_modules()
with app.app_context():
    app.cli.list_commands(None)
print(json.dumps(sorted(m for m in sys.modules if m == "hubra" or m.startswith("hubra."))))
"""


@pytest.mark.parametrize("role", ["app", "global", "platform"])
def test_a_role_imports_only_modules_its_image_has(role):
    env = {**os.environ, "HUBRA_ROLE": role, "HUBRA_PLATFORM_QUEUE": "platform"}
    out = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    imported = set(json.loads(out.strip().splitlines()[-1]))
    allowed = role_files.role_modules(role, BACKEND)
    assert imported - allowed == set()


def test_roles_pick_the_blueprints_the_backend_registers():
    """role_files reads the manifests without importing them; it must pick
    the same blueprints as hubra.core.roles.registers at start-up."""
    from hubra.core import roles
    from hubra.core.modules import registry

    registry.load()
    declared = [
        bp for m in registry.all() if not m.plugin for bp in m.blueprints
    ]
    listed = role_files.manifest_blueprints(BACKEND)
    assert sorted((b.import_path, b.attr) for b in declared) == sorted(
        (b[0], b[1]) for b in listed
    )
    for role in ("app", "global", "platform", "all"):
        picked = {(b[0], b[1]) for b in role_files.role_blueprints(role, BACKEND)}
        expected = {(b.import_path, b.attr) for b in declared if roles.registers(b, role)}
        assert picked == expected, role


def test_each_role_leaves_out_the_other_areas_routes():
    app = role_files.role_modules("app", BACKEND)
    platform = role_files.role_modules("platform", BACKEND)
    glob = role_files.role_modules("global", BACKEND)
    assert "hubra.api.members.routes" in app
    assert "hubra.api.members.routes" not in platform | glob
    assert "hubra.api.backups.routes" in platform
    assert "hubra.api.backups.routes" not in app | glob
    assert "hubra.api.auth.routes" in glob
    assert "hubra.api.auth.routes" not in app | platform
    # Hubra's core is in every image.
    assert "hubra.core.tasks.backup_tasks" in app & platform & glob
    assert role_files.role_modules("all", BACKEND) >= app | platform | glob


def test_listed_files_and_prune_agree(tmp_path):
    """--prune leaves exactly the listed hubra modules (the Dockerfile uses
    it, images.yml compares the list)."""
    import shutil

    copy = tmp_path / "backend"
    shutil.copytree(
        BACKEND,
        copy,
        ignore=shutil.ignore_patterns("__pycache__", ".venv", ".pytest_cache", ".ruff_cache"),
    )
    listed = set(role_files.role_files("platform", copy))
    role_files.prune("platform", copy)
    left = {
        p.relative_to(copy).as_posix()
        for p in (copy / "hubra").rglob("*.py")
    }
    assert left == {f for f in listed if f.startswith("hubra/") and f.endswith(".py")}
    assert "migrations/env.py" in listed
    assert not any(f.startswith("tests/") for f in listed)


def test_images_build_each_role_from_its_file_list():
    """images.yml has one role image per role, built from the Dockerfile's
    role target, and the Dockerfile prunes with role_files.py."""
    import yaml

    workflow = yaml.safe_load((BACKEND.parents[1] / ".github/workflows/images.yml").read_text())
    entries = workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
    roles = {e["image"]: e.get("role") for e in entries if e.get("target") == "role"}
    assert roles == {"app-backend": "app", "global-backend": "global", "platform-backend": "platform"}
    dockerfile = (BACKEND / "Dockerfile").read_text()
    assert "scripts/role_files.py \"$ROLE\" --root /src --prune" in dockerfile
    assert "ENV HUBRA_ROLE=${ROLE}" in dockerfile
    # The default target (Compose builds without one) is the full image.
    assert dockerfile.rstrip().rsplit("FROM ", 1)[1].startswith("base AS backend")
