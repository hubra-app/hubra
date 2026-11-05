"""What plugins may extend: uses:, club-only routes, after-commit events and
plugin dependencies (docs/plugins.md)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hubra.core import api_areas
from hubra.core.models.plugin import InstalledPlugin
from hubra.core.modules import Module
from hubra.core.modules import events as events_mod
from hubra.core.modules.base import AppProvider, Blueprint, Schedule
from hubra.core.plugins import installer, limits, loader, publish
from hubra.core.plugins.installer import InstallError
from hubra.core.plugins.limits import LimitError, check, club_prefix
from hubra.core.plugins.spec import Spec, validate, version_matches

from .test_plugins import key, plugin_dir, signed_zip, trust_key  # noqa: F401


def spec(tmp_path: Path, status: str = "community", **manifest) -> Spec:
    m = {"id": "demo", "name": "Demo", "version": "1.0.0", "package": "hubra_demo"}
    m.update(manifest)
    return Spec(
        id="demo",
        path=tmp_path,
        manifest=m,
        trust={"status": status, "signer": "", "key_id": "", "detail": ""},
    )


def bp(prefix: str, path: str = "hubra_demo.routes") -> Blueprint:
    return Blueprint(path, "demo_bp", prefix)


# ── plugin.yaml ─────────────────────────────────────────────────────────────


def test_uses_and_depends_are_validated():
    base = {"id": "demo", "name": "Demo", "version": "1"}
    assert validate({**base, "uses": ["routes", "events"]}) == ""
    assert "unknown area" in validate({**base, "uses": ["routes", "manage"]})
    assert "uses:" in validate({**base, "uses": "routes"})
    assert validate({**base, "depends": {"finance": ">=2.0,<3"}}) == ""
    assert validate({**base, "depends": {"finance": None}}) == ""
    assert "version range" in validate({**base, "depends": {"finance": "two"}})
    assert "another plugin" in validate({**base, "depends": {"demo": ">=1"}})
    assert "depends:" in validate({**base, "depends": ["finance"]})


def test_version_ranges():
    assert version_matches("2.1.0", ">=2.0,<3")
    assert not version_matches("3.0.0", ">=2.0,<3")
    assert version_matches("0.1", "")


# ── Routes: club area only ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("prefix", "served"),
    [
        ("/api/v1/app/bank", "/api/v1/app/bank"),
        ("/api/v1/bank", "/api/v1/app/bank"),
        ("/api/v1/bank/", "/api/v1/app/bank"),
        # An old core path of the club app keeps its new home.
        ("/api/v1/codes", "/api/v1/app/codes"),
    ],
)
def test_club_prefixes(prefix, served):
    assert club_prefix(prefix) == served


@pytest.mark.parametrize(
    "prefix",
    [
        "/api/v1/platform/x",
        "/api/v1/manager/plugins",  # old platform path
        "/api/v1/system/tenants",
        "/api/v1/global/x",
        "/api/v1/auth",  # sign-in
        "/api/v1/account/x",
        "/api/v1/plugins",  # plugin assets (global)
        "/api/v1/app",
        "/api/v1",
        "/somewhere",
    ],
)
def test_platform_and_global_prefixes_are_refused(prefix):
    with pytest.raises(LimitError):
        club_prefix(prefix)


def test_an_old_plugin_path_reaches_the_new_one():
    api_areas.add_plugin_prefix("/api/v1/zzdemo", "/api/v1/app/zzdemo")
    try:
        assert api_areas.canonical_path("/api/v1/zzdemo/items/1") == (
            "/api/v1/app/zzdemo/items/1"
        )
        assert api_areas.canonical_path("/api/v1/zzdemox") == "/api/v1/zzdemox"
    finally:
        api_areas._PLUGIN_PREFIXES.pop("/api/v1/zzdemo", None)


def test_check_moves_routes_into_the_club_area(tmp_path):
    taken: dict[str, str] = {}
    m = check(Module(code="demo", name="Demo", blueprints=(bp("/api/v1/demo"),)),
              spec(tmp_path), taken, set())
    assert m.blueprints[0].url_prefix == "/api/v1/app/demo"
    assert taken == {"/api/v1/app/demo": "demo"}


def test_check_refuses_a_prefix_someone_has(tmp_path):
    taken = {"/api/v1/app/members": "members"}
    for prefix in ("/api/v1/members", "/api/v1/app/members/extra", "/api/v1/app"):
        with pytest.raises(LimitError):
            check(Module(code="demo", name="Demo", blueprints=(bp(prefix),)),
                  spec(tmp_path), dict(taken), set())


def test_a_core_blueprint_on_the_root_does_not_block_plugins(tmp_path):
    """OAuth registers its blueprint without a prefix (/.well-known, /oauth);
    that refused every plugin as overlapping "/"."""
    taken = {"/": "core", "/api/v1/app/members": "members"}
    m = check(
        Module(code="demo", name="Demo", blueprints=(bp("/api/v1/demo"),)),
        spec(tmp_path),
        taken,
        set(),
    )
    assert m.blueprints[0].url_prefix == "/api/v1/app/demo"


def test_hubras_own_blueprints_leave_room_for_plugins(app):
    """Every prefix Hubra itself takes still lets a plugin add a club route."""
    from hubra.core.modules.registry import registry

    with app.app_context():
        taken, _ = loader._taken(registry)
    m = check(
        Module(code="demo", name="Demo", blueprints=(bp("/api/v1/demo"),)),
        spec(Path(".")),
        dict(taken),
        set(),
    )
    assert m.blueprints[0].url_prefix == "/api/v1/app/demo"


def test_check_refuses_code_outside_the_plugin(tmp_path):
    cases = [
        Module(code="demo", name="D", blueprints=(bp("/api/v1/demo", "hubra.api.members.routes"),)),
        Module(code="demo", name="D", events={"invoice.paid": "hubra.api.finance:x"}),
        Module(code="demo", name="D", tasks=("hubra.core.tasks.backup_tasks",)),
        Module(code="demo", name="D", schedule=(Schedule("x", "hubra.core.tasks.backup_tasks.run", 60),)),
        Module(code="demo", name="D", apps=(AppProvider("x", "X", "hubra_demox.app:p"),)),
    ]
    for m in cases:
        with pytest.raises(LimitError, match="outside hubra_demo"):
            check(m, spec(tmp_path), {}, set())


def test_check_refuses_hubras_tables(tmp_path):
    with pytest.raises(LimitError, match="members"):
        check(Module(code="demo", name="D", tables=("demo_items", "members")),
              spec(tmp_path), {}, {"members", "invoices"})


def test_processes_and_in_transaction_events_are_for_official_plugins(tmp_path):
    proc = Module(code="demo", name="D", processes={"gw": "hubra_demo.gw:run"})
    with pytest.raises(LimitError, match="official"):
        check(proc, spec(tmp_path, "community"), {}, set())
    assert check(proc, spec(tmp_path, "official"), {}, set()).processes

    tx = Module(code="demo", name="D", events={"invoice.paid": "hubra_demo.h:on"},
                events_in_transaction=("invoice.paid",))
    assert check(tx, spec(tmp_path, "community"), {}, set()).events_in_transaction == ()
    assert check(tx, spec(tmp_path, "bundled"), {}, set()).events_in_transaction == (
        "invoice.paid",
    )


def test_uses_must_cover_what_the_module_does(tmp_path):
    m = Module(code="demo", name="D", blueprints=(bp("/api/v1/demo"),),
               events={"invoice.paid": "hubra_demo.h:on"})
    # Without the list: loads (plugins released before uses: existed).
    check(m, spec(tmp_path), {}, set())
    check(m, spec(tmp_path, uses=["routes", "events"]), {}, set())
    with pytest.raises(LimitError, match="events"):
        check(m, spec(tmp_path, uses=["routes"]), {}, set())
    assert limits.areas_used(m, spec(tmp_path)) == {"routes", "events"}


# ── Events after the commit ─────────────────────────────────────────────────

CALLS: list[tuple] = []


def on_demo_event(tenant_id, **payload):
    CALLS.append(("plugin", tenant_id, payload))


def on_core_event(tenant_id, **payload):
    CALLS.append(("core", tenant_id, payload))


@pytest.fixture
def demo_subscribers(monkeypatch):
    here = __name__
    plugin_mod = Module(code="demo", name="D", plugin="demo",
                        events={"demo.happened": f"{here}:on_demo_event"})
    core_mod = Module(code="democore", name="C",
                      events={"demo.happened": f"{here}:on_core_event"})
    monkeypatch.setattr(events_mod.registry, "subscribers",
                        lambda event: [(core_mod, core_mod.events[event]),
                                       (plugin_mod, plugin_mod.events[event])])
    monkeypatch.setattr(events_mod, "is_enabled", lambda code, tenant_id=None: True)
    monkeypatch.setattr("hubra.core.modules.state.is_enabled",
                        lambda code, tenant_id=None: True)
    CALLS.clear()
    yield
    CALLS.clear()


def test_plugin_handlers_run_after_the_commit(app, db, demo_subscribers):
    from hubra.core.models.plugin import PluginState

    with app.app_context():
        db.session.merge(PluginState(key="demo-flag", value="1"))  # opens a transaction
        called = events_mod.emit("demo.happened", tenant_id=None, thing_id=7)
        assert called == ["democore", "demo"]
        assert CALLS == [("core", None, {"thing_id": 7})]  # the plugin waits
        db.session.commit()
        assert CALLS[1] == ("plugin", None, {"thing_id": 7})


def test_plugin_handlers_never_hear_of_a_rollback(app, db, demo_subscribers):
    from hubra.core.models.plugin import PluginState

    with app.app_context():
        db.session.merge(PluginState(key="demo-flag", value="2"))
        events_mod.emit("demo.happened", tenant_id=None, thing_id=8)
        db.session.rollback()
        db.session.commit()
        assert [c[0] for c in CALLS] == ["core"]


def test_official_plugins_can_ask_for_in_transaction_handlers(
    app, db, demo_subscribers, monkeypatch
):
    here = __name__
    mod = Module(code="demo", name="D", plugin="demo",
                 events={"demo.happened": f"{here}:on_demo_event"},
                 events_in_transaction=("demo.happened",))
    monkeypatch.setattr(events_mod.registry, "subscribers",
                        lambda event: [(mod, mod.events[event])])
    from hubra.core.models.plugin import PluginState

    with app.app_context():
        db.session.merge(PluginState(key="demo-flag", value="3"))
        events_mod.emit("demo.happened", tenant_id=None, thing_id=9)
        assert CALLS == [("plugin", None, {"thing_id": 9})]
        db.session.rollback()


# ── Plugin dependencies ─────────────────────────────────────────────────────


def make(root: Path, pid: str, version: str = "1.0.0", **extra) -> Path:
    pkg_name = "hubra_" + pid.replace("-", "_")
    d = root / pid
    (d / pkg_name).mkdir(parents=True)
    (d / pkg_name / "__init__.py").write_text(
        "from hubra.core.modules import Module\n"
        f'module = Module(code="{pid}", name="{pid}", depends_on=("members",))\n'
    )
    manifest = {
        "id": pid, "name": pid.title(), "version": version, "hubra": ">=0.1,<1",
        "package": pkg_name, "modules": [pid], "requires": ["members"],
        "uses": [], **extra,
    }
    (d / "plugin.yaml").write_text(yaml.safe_dump(manifest))
    (d / "CHANGELOG.md").write_text(f"# {pid}\n\n## {version}\n\nFirst.\n")
    return d


def test_install_refuses_a_missing_or_wrong_dependency(
    tmp_path, key, db, seeded_db, plugin_dir  # noqa: F811
):
    trust_key(db, key[1])
    child = make(tmp_path / "a", "zzchild", depends={"zzbase": ">=2.0"})
    info = installer.stage(signed_zip(child, key[0]))
    assert info["depends"] == {"zzbase": ">=2.0"} and info["uses"] == []
    with pytest.raises(InstallError, match="needs the plugin zzbase >=2.0"):
        installer.confirm(info["token"], accept_unsigned=False)

    base = make(tmp_path / "b", "zzbase", "1.5.0")
    installer.confirm(installer.stage(signed_zip(base, key[0]))["token"], False)
    with pytest.raises(InstallError, match="needs zzbase >=2.0; 1.5.0 is installed"):
        installer.confirm(installer.stage(signed_zip(child, key[0]))["token"], False)
    assert db.session.get(InstalledPlugin, "zzchild") is None


def test_dependencies_install_first_from_the_same_repository(
    tmp_path, key, db, seeded_db, plugin_dir, monkeypatch  # noqa: F811
):
    pem, _pub = key
    src = tmp_path / "src"
    src.mkdir()
    make(src, "zzbase", "2.1.0")
    make(src, "zzchild", depends={"zzbase": ">=2.0,<3"})
    out = tmp_path / "public"
    publish.build_repository(src, out, pem, "Test plugins")
    monkeypatch.setattr(
        installer, "http_get",
        lambda url, timeout=30, limit=0: (out / url.split("?", 1)[0].rsplit("/", 1)[-1]).read_bytes(),
    )
    url = "https://plugins.example/index.json"
    repo = installer.add_repository(url, installer.preview_repository(url)["keyId"])

    info = installer.install_from_repository(repo, "zzchild")
    result = installer.confirm(info["token"], False, repository_id=repo.id)
    assert [d["id"] for d in result["dependencies"]] == ["zzbase"]
    assert db.session.get(InstalledPlugin, "zzbase").version == "2.1.0"
    assert db.session.get(InstalledPlugin, "zzchild") is not None


def test_an_update_that_breaks_a_dependant_is_refused(
    tmp_path, key, db, seeded_db, plugin_dir, monkeypatch  # noqa: F811
):
    trust_key(db, key[1])
    installer.confirm(
        installer.stage(signed_zip(make(tmp_path / "b", "zzbase", "2.0.0"), key[0]))["token"],
        False,
    )
    child = make(tmp_path / "a", "zzchild", depends={"zzbase": "<3"})
    installer.confirm(installer.stage(signed_zip(child, key[0]))["token"], False)
    # This process didn't load zzchild; the check reads the loaded specs.
    from hubra.core.plugins.spec import scan

    child_spec = next(s for s in scan(tmp_path / "a", bundled=False) if s.id == "zzchild")
    monkeypatch.setitem(loader.current().specs, "zzchild", child_spec)
    newer = make(tmp_path / "c", "zzbase", "3.0.0")
    with pytest.raises(InstallError, match="Zzchild needs zzbase <3"):
        installer.confirm(installer.stage(signed_zip(newer, key[0]))["token"], False)
    assert db.session.get(InstalledPlugin, "zzbase").version == "2.0.0"
    assert "Zzchild" in installer.dependents("zzbase")
