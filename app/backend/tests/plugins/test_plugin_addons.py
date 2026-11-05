"""Add-ons: plugins that need another plugin (its parent).

The Marketplace and the index name each plugin's parent, so both can show
add-ons under it.  An install or update whose ``depends:`` range the
installed parent misses stops with the version it needs, unless the
platform lets updates bring their required plugins along.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hubra.core.models.plugin import InstalledPlugin
from hubra.core.plugins import installer, publish, updates
from hubra.core.plugins.installer import InstallError
from hubra.core.plugins.spec import parents

from .test_plugins import (  # noqa: F401  (fixtures)
    _served,
    key,
    make_plugin,
    plugin_dir,
    superadmin,
)


def test_parent_comes_from_depends_then_from_a_required_plugin_module():
    entries = [
        {"id": "inventory", "modules": ["inventory"], "requires": ["members"]},
        {"id": "guides", "modules": ["inventory.guides"], "requires": ["inventory"]},
        {"id": "keys", "modules": ["inventory.keys"], "depends": {"inventory": ">=2"}},
        {"id": "books", "modules": ["books"], "depends": {"finance": ">=2"}},
        {"id": "solo", "modules": ["solo"], "requires": ["members"]},
    ]
    assert parents(entries) == {
        "inventory": "",  # members is a core module
        "guides": "inventory",
        "keys": "inventory",
        "books": "finance",  # named even when the catalogue doesn't offer it
        "solo": "",
    }


def test_a_loop_does_not_nest_both_ways():
    out = parents(
        [
            {"id": "a", "modules": ["a"], "depends": {"b": ""}},
            {"id": "b", "modules": ["b"], "depends": {"a": ""}},
        ]
    )
    assert "" in (out["a"], out["b"])


def make_addon(root: Path, version: str, needs: str) -> Path:
    d = root / "addon"
    if d.exists():
        m = yaml.safe_load((d / "plugin.yaml").read_text())
        m.update(version=version, depends={"hello": needs})
        (d / "plugin.yaml").write_text(yaml.safe_dump(m))
        (d / "CHANGELOG.md").write_text(f"# Add-on\n\n## {version}\n\nNew.\n")
        return d
    pkg = d / "hubra_addon"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        "from hubra.core.modules import Module\n"
        'module = Module(code="addon", name="Add-on")\n'
    )
    (d / "CHANGELOG.md").write_text(f"# Add-on\n\n## {version}\n\nNew.\n")
    (d / "plugin.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "addon",
                "name": "Add-on",
                "version": version,
                "hubra": ">=0.1,<1",
                "description": "Adds to Hello",
                "author": "Test",
                "package": "hubra_addon",
                "modules": ["addon"],
                "depends": {"hello": needs},
            }
        )
    )
    return d


def set_version(d: Path, version: str) -> None:
    m = yaml.safe_load((d / "plugin.yaml").read_text())
    m["version"] = version
    (d / "plugin.yaml").write_text(yaml.safe_dump(m))
    (d / "CHANGELOG.md").write_text(f"# Hello\n\n## {version}\n\nNew.\n")


@pytest.fixture
def repo_with_addon(tmp_path, key, db, seeded_db, plugin_dir, monkeypatch):  # noqa: F811
    """Hello 1.0.0 and Add-on 1.0.0 (needs Hello >=1.0), both installed."""
    pem, _pub = key
    src, out = tmp_path / "src", tmp_path / "public"
    src.mkdir()
    hello = make_plugin(src)
    make_addon(src, "1.0.0", ">=1.0,<2")
    publish.build_repository(src, out, pem, "Test plugins")
    monkeypatch.setattr(
        installer,
        "http_get",
        lambda url, timeout=30, limit=0: _served(out, url).read_bytes(),
    )
    url = "https://plugins.example/index.json"
    repo = installer.add_repository(url, installer.preview_repository(url)["keyId"])
    for pid in ("hello", "addon"):
        info = installer.install_from_repository(repo, pid)
        installer.confirm(info["token"], accept_unsigned=False, repository_id=repo.id)

    def release(hello_version: str | None, addon_version: str, needs: str):
        if hello_version:
            set_version(hello, hello_version)
        make_addon(src, addon_version, needs)
        publish.build_repository(src, out, pem, "Test plugins")
        installer._index_cache.clear()

    return repo, release, out


def _entry(pid: str) -> dict:
    return next(p for p in installer.marketplace()["plugins"] if p["id"] == pid)


def test_the_index_and_the_marketplace_name_the_parent(repo_with_addon):
    _repo, _release, out = repo_with_addon
    import json

    index = json.loads((out / "index.json").read_text())
    by_id = {p["id"]: p for p in index["plugins"]}
    assert by_id["addon"]["parent"] == "hello" and by_id["hello"]["parent"] == ""

    addon = _entry("addon")
    assert addon["parent"] == "hello" and addon["parentName"] == "Hello"
    assert addon["parentInstalled"] is True and addon["unmet"] == []


def test_an_update_that_needs_a_newer_parent_stops_by_default(repo_with_addon, db):
    repo, release, _out = repo_with_addon
    release("1.1.0", "1.1.0", ">=1.1,<2")
    addon = _entry("addon")
    assert addon["update"] is True
    assert addon["unmet"] == [
        {"id": "hello", "name": "Hello", "range": ">=1.1,<2", "installed": "1.0.0"}
    ]

    info = installer.install_from_repository(repo, "addon", "1.1.0")
    with pytest.raises(InstallError, match=r"needs Hello >=1.1,<2; 1.0.0 is installed"):
        installer.confirm(info["token"], accept_unsigned=False, repository_id=repo.id)
    db.session.rollback()
    assert db.session.get(InstalledPlugin, "addon").version == "1.0.0"
    assert db.session.get(InstalledPlugin, "hello").version == "1.0.0"


def test_with_the_setting_on_the_parent_is_updated_first(repo_with_addon, db):
    repo, release, _out = repo_with_addon
    release("1.1.0", "1.1.0", ">=1.1,<2")
    assert updates.follow_dependencies() is False
    updates.set_follow_dependencies(True)

    info = installer.install_from_repository(repo, "addon", "1.1.0")
    out = installer.confirm(info["token"], accept_unsigned=False, repository_id=repo.id)
    assert [d["id"] for d in out["dependencies"]] == ["hello"]
    assert db.session.get(InstalledPlugin, "hello").version == "1.1.0"
    assert db.session.get(InstalledPlugin, "addon").version == "1.1.0"


def test_a_held_parent_is_not_updated_along(repo_with_addon, db):
    repo, release, _out = repo_with_addon
    release("1.1.0", "1.1.0", ">=1.1,<2")
    updates.set_follow_dependencies(True)
    installer.hold("hello", "1.0.0")

    info = installer.install_from_repository(repo, "addon", "1.1.0")
    with pytest.raises(InstallError, match="held at 1.0.0"):
        installer.confirm(info["token"], accept_unsigned=False, repository_id=repo.id)


def test_a_parent_update_the_addon_does_not_allow_stops(repo_with_addon, db):
    repo, release, _out = repo_with_addon
    release("2.0.0", "1.0.0", ">=1.0,<2")
    info = installer.install_from_repository(repo, "hello", "2.0.0")
    with pytest.raises(InstallError, match="update Add-on first"):
        installer.confirm(info["token"], accept_unsigned=False, repository_id=repo.id)


def test_the_setting_over_the_api(client, superadmin):  # noqa: F811
    base = "/api/v1/manager/plugins/"
    assert client.get(base + "?fetch=0").get_json()["updateDependencies"] is False
    resp = client.put(base + "updates", json={"dependencies": True})
    assert resp.status_code == 200
    assert resp.get_json() == {"mode": "notify", "dependencies": True}
    assert client.get(base + "?fetch=0").get_json()["updateDependencies"] is True
    assert client.put(base + "updates", json={"dependencies": "yes"}).status_code == 400
    assert client.put(base + "updates", json={}).status_code == 400
