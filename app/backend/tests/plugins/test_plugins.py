"""The plugin system: manifests, signatures, repositories, install and removal."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from hubra.core.models.plugin import InstalledPlugin, PluginArchive, PluginRepository
from hubra.core.plugins import installer, loader, publish, trust
from hubra.core.plugins.installer import InstallError
from hubra.core.plugins.spec import compatibility, scan, validate

MIGRATION = '''"""hello_notes"""
from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import has_table

revision = "aaaaaaaaaaaa"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if not has_table("hello_notes"):
        op.create_table(
            "hello_notes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("text", sa.Text()),
        )


def downgrade():
    op.drop_table("hello_notes")
'''


def make_plugin(
    root: Path, pid: str = "hello", version: str = "1.0.0", **extra
) -> Path:
    d = root / pid
    pkg = d / "hubra_hello"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        "from hubra.core.modules import Module\n"
        'module = Module(code="hello", name="Hello", depends_on=("members",))\n'
    )
    (d / "migrations").mkdir()
    (d / "migrations" / "aaaaaaaaaaaa_hello.py").write_text(MIGRATION)
    (d / "frontend" / "dist").mkdir(parents=True)
    (d / "frontend" / "dist" / "plugin.js").write_text(
        "HubraPluginHost.register({id:'hello'})"
    )
    (d / "tests").mkdir()
    (d / "tests" / "test_x.py").write_text("")
    (d / ".releaseignore").write_text("tests/\n")
    (d / "CHANGELOG.md").write_text(f"# Hello\n\n## {version}\n\nSays hello.\n")
    manifest = {
        "id": pid,
        "name": "Hello",
        "version": version,
        "hubra": ">=0.1,<1",
        "description": "A test plugin",
        "author": "Test",
        "package": "hubra_hello",
        "modules": ["hello"],
        "requires": ["members"],
        "migrations": "migrations",
        "frontend": "frontend/dist/plugin.js",
        **extra,
    }
    import yaml

    (d / "plugin.yaml").write_text(yaml.safe_dump(manifest))
    return d


@pytest.fixture
def key():
    pem, pub = trust.keygen()
    return pem, pub


@pytest.fixture
def plugin_dir(app, tmp_path):
    app.config["PLUGIN_DIR"] = str(tmp_path / "installed")
    return tmp_path


def signed_zip(src: Path, pem: bytes) -> bytes:
    _m, blob = publish.release(src, pem, "Tester")
    return blob


def trust_key(db, pub: str, name: str = "tester"):
    from hubra.core.models.plugin import TrustedKey

    k = trust.load_public(pub)
    db.session.add(
        TrustedKey(name=name, key_id=trust.key_id(k), public_key=trust.public_b64(k))
    )
    db.session.commit()


# ── Manifests ────────────────────────────────────────────────────────────────


def test_validate_rejects_bad_manifests(tmp_path):
    d = make_plugin(tmp_path)
    good = {"id": "hello", "name": "Hello", "version": "1", "package": "hubra_hello"}
    assert validate(good, d) == ""
    assert "id" in validate({**good, "id": "Bad Id"})
    assert "package" in validate({**good, "package": "os"})
    assert "version" in validate({**good, "version": ""})
    assert "hubra" in validate({**good, "hubra": "not a range"})
    assert "frontend" in validate({**good, "frontend": "../x.js"}, d)
    assert "modules" in validate(
        {"id": "x1", "name": "X", "version": "1", "modules": ["a"]}
    )


def test_compatibility_uses_the_hubra_range():
    assert compatibility({})[0]
    assert compatibility({"hubra": ">=0.1,<1"})[0]
    ok, why = compatibility({"hubra": ">=99"})
    assert not ok and "needs Hubra >=99" in why


def test_bundled_plugins_are_valid():
    root = Path(__file__).resolve().parent / "bundled"
    specs = scan(root, bundled=True)
    assert {s.id for s in specs} == {"notes", "badges"}
    for s in specs:
        assert s.error == "", f"{s.id}: {s.error}"


def test_bundled_plugins_load_in_tests(app):
    from hubra.core.modules import registry

    loaded = {s.id for s in loader.current().loaded()}
    assert {"notes", "badges"} <= loaded
    notes = registry.get("notes")
    assert notes is not None and notes.plugin == "notes"


# ── Signatures ───────────────────────────────────────────────────────────────


def test_sign_and_verify(tmp_path, key):
    pem, pub = key
    d = make_plugin(tmp_path)
    doc = trust.sign(d, pem, "Tester")
    keys = {doc["key_id"]: ("tester", trust.load_public(pub))}
    m = {"id": "hello", "version": "1.0.0"}
    assert trust.verify(d, m, keys)["status"] == "community"
    assert trust.verify(d, m, {})["status"] == "invalid"
    (d / "hubra_hello" / "__init__.py").write_text("import os  # changed")
    result = trust.verify(d, m, keys)
    assert result["status"] == "invalid" and "files differ" in result["detail"]


def test_release_prunes_and_leaves_source_alone(tmp_path, key):
    pem, _pub = key
    d = make_plugin(tmp_path)
    blob = signed_zip(d, pem)
    names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    assert "hello/SIGNATURE.json" in names
    assert "hello/frontend/dist/plugin.js" in names
    assert not any("/tests/" in n for n in names)
    assert not (d / "SIGNATURE.json").exists()


def test_release_needs_the_built_frontend(tmp_path, key):
    d = make_plugin(tmp_path)
    (d / "frontend" / "dist" / "plugin.js").unlink()
    with pytest.raises(InstallError, match="build the frontend"):
        publish.release(d, key[0], "Tester")


def test_safe_extract_refuses_path_traversal(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.py", "x")
    with pytest.raises(InstallError, match="unsafe path"):
        installer.safe_extract(buf.getvalue(), tmp_path / "x")


@pytest.mark.parametrize(
    "name",
    [
        "hello/hello_pkg/__pycache__/__init__.cpython-313.pyc",
        "hello/hello_pkg/extra.pyc",
        "hello/node_modules/x/index.js",
        "hello/.git/config",
    ],
)
def test_safe_extract_refuses_files_the_signature_skips(tmp_path, name):
    """A .pyc next to a signed .py would run instead of it, unsigned."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello/plugin.yaml", "id: hello\n")
        zf.writestr(name, "x")
    with pytest.raises(InstallError, match="compiled or tooling"):
        installer.safe_extract(buf.getvalue(), tmp_path / "x")


# ── Repositories ─────────────────────────────────────────────────────────────


def test_repository_index_is_signed_and_pinned(tmp_path, key, db, monkeypatch):
    pem, _pub = key
    src = tmp_path / "src"
    src.mkdir()
    make_plugin(src)
    out = tmp_path / "public"
    doc = publish.build_repository(src, out, pem, "Test plugins")
    assert doc["plugins"][0]["id"] == "hello"
    assert doc["plugins"][0]["hubra"] == ">=0.1,<1"
    assert doc["plugins"][0]["changes"] == "Says hello."

    def fake_get(url, timeout=30, limit=0):
        return (out / url.rsplit("/", 1)[-1]).read_bytes()

    monkeypatch.setattr(installer, "http_get", fake_get)
    url = "https://plugins.example/index.json"
    info = installer.preview_repository(url)
    assert info["name"] == "Test plugins" and info["plugins"] == 1
    with pytest.raises(InstallError, match="now signed with key"):
        installer.add_repository(url, "0" * 16)
    repo = installer.add_repository(url, info["keyId"])

    # Re-signing the index with another key is refused afterwards.
    other, _ = trust.keygen()
    publish.build_repository(src, out, other, "Test plugins")
    installer._index_cache.clear()
    with pytest.raises(InstallError):
        installer.fetch_repository(repo, force=True)
    assert db.session.get(PluginRepository, repo.id).error


def test_check_repository_downloads_and_verifies_every_archive(
    tmp_path, key, monkeypatch
):
    pem, _pub = key
    src = tmp_path / "src"
    src.mkdir()
    d = make_plugin(src)
    out = tmp_path / "public"
    publish.build_repository(src, out, pem, "Test plugins")
    m = (d / "plugin.yaml").read_text().replace("version: 1.0.0", "version: 1.1.0")
    (d / "plugin.yaml").write_text(m)
    doc = publish.build_repository(src, out, pem, "Test plugins")

    def fake_get(url, timeout=30, limit=0):
        return (out / url.split("?")[0].rsplit("/", 1)[-1]).read_bytes()

    monkeypatch.setattr(installer, "http_get", fake_get)
    monkeypatch.setattr(publish, "http_get", fake_get)
    url = "https://plugins.example/index.json?v=1"
    assert publish.check_repository(url, doc["key_id"]) == (doc, [])
    _, problems = publish.check_repository(url)
    assert problems == [
        f"the index is signed with key {doc['key_id']}, not b84edc01a8b17490"
    ]

    # An archive changed after signing: re-zipped with a new checksum in a re-signed index.
    with zipfile.ZipFile(out / "hello-1.0.0.zip") as zf:
        files = {n: zf.read(n) for n in zf.namelist()}
    init = next(n for n in files if n.endswith("hubra_hello/__init__.py"))
    files[init] += b"# changed\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n, b in files.items():
            zf.writestr(n, b)
    (out / "hello-1.0.0.zip").write_bytes(buf.getvalue())
    idx = json.loads((out / "index.json").read_text())
    import hashlib

    for v in idx["plugins"][0]["versions"]:
        if v["version"] == "1.0.0":
            v["sha256"] = hashlib.sha256(buf.getvalue()).hexdigest()
    for k in ("signature", "key_id", "public_key"):
        idx.pop(k)
    (out / "index.json").write_text(json.dumps(trust.sign_index(idx, pem)))
    _, problems = publish.check_repository(url, doc["key_id"])
    assert problems == [
        "hello 1.0.0: files differ from what was signed: hubra_hello/__init__.py"
    ]


def test_build_index_leaves_out_repositories_without_a_release(tmp_path, key):
    pem, _pub = key
    src = tmp_path / "src"
    src.mkdir()
    make_plugin(src)
    built = tmp_path / "built"
    publish.build_repository(src, built, pem, "Test plugins")
    asset = "https://github.com/o/hubra-plugin-hello/releases/download/v1.0.0/hello-1.0.0.zip"
    answers = {
        "https://api.github.com/repos/o/hubra-plugin-hello/releases?per_page=100": [
            {
                "body": "",
                "published_at": "2026-10-30T00:00:00Z",
                "assets": [{"name": "hello-1.0.0.zip", "browser_download_url": asset}],
            }
        ],
        "https://api.github.com/repos/o/hubra-plugin-new/releases?per_page=100": [],
        asset: (built / "hello-1.0.0.zip").read_bytes(),
    }
    sources = {
        "plugins": [{"repo": "o/hubra-plugin-hello"}, {"repo": "o/hubra-plugin-new"}]
    }

    def get(url, headers):
        return answers[url]

    out = tmp_path / "site"
    doc = publish.build_index_from_sources(sources, out, pem, get=get)
    assert [p["id"] for p in doc["plugins"]] == ["hello"]
    assert doc["skipped"] == ["o/hubra-plugin-new"]
    assert doc["problems"] == []

    # Nothing released yet: an empty, signed index rather than an error.
    del sources["plugins"][0]
    doc = publish.build_index_from_sources(sources, out, pem, get=get)
    assert doc["plugins"] == [] and doc["problems"] == []
    assert json.loads((out / "index.json").read_text())["signature"]


def test_an_older_index_than_seen_is_refused(tmp_path, key, db, monkeypatch):
    """L7: a mirror can't roll the index back to an older signed one."""
    pem, _pub = key
    src = tmp_path / "src"
    src.mkdir()
    make_plugin(src)
    out = tmp_path / "public"
    doc = publish.build_repository(src, out, pem, "Test plugins")
    monkeypatch.setattr(
        installer,
        "http_get",
        lambda url, timeout=30, limit=0: (out / url.rsplit("/", 1)[-1]).read_bytes(),
    )
    url = "https://plugins.example/index.json"
    repo = installer.add_repository(url, installer.preview_repository(url)["keyId"])
    installer._index_cache.clear()
    installer.fetch_repository(repo, force=True)
    assert repo.index_generated == doc["generated"]

    # As if a newer index had been seen: the one served now is older.
    repo.index_generated = "2099-01-01T00:00:00+00:00"
    db.session.commit()
    with pytest.raises(InstallError, match="older"):
        installer.fetch_repository(repo, force=True)


def test_install_from_repository_then_update_and_rollback(
    tmp_path, key, db, seeded_db, plugin_dir, monkeypatch
):
    pem, _pub = key
    src = tmp_path / "src"
    src.mkdir()
    d = make_plugin(src)
    out = tmp_path / "public"
    publish.build_repository(src, out, pem, "Test plugins")

    monkeypatch.setattr(
        installer,
        "http_get",
        lambda url, timeout=30, limit=0: (out / url.rsplit("/", 1)[-1]).read_bytes(),
    )
    url = "https://plugins.example/index.json"
    repo = installer.add_repository(url, installer.preview_repository(url)["keyId"])

    market = installer.marketplace()
    entry = next(p for p in market["plugins"] if p["id"] == "hello")
    assert entry["installed"] is False and entry["repositoryId"] == repo.id

    info = installer.install_from_repository(repo, "hello")
    assert info["trust"]["status"] == "community" and info["installable"]
    result = installer.confirm(
        info["token"], accept_unsigned=False, repository_id=repo.id
    )
    assert result["version"] == "1.0.0"
    row = db.session.get(InstalledPlugin, "hello")
    assert row.source == "archive" and row.origin == "Test plugins"
    assert db.session.execute(db.text("SELECT COUNT(*) FROM hello_notes")).scalar() == 0
    assert (Path(plugin_dir) / "installed" / "hello" / "plugin.yaml").is_file()

    # A new version shows up as an update, installs, and can be rolled back.
    import yaml

    m = yaml.safe_load((d / "plugin.yaml").read_text())
    m["version"] = "1.1.0"
    (d / "plugin.yaml").write_text(yaml.safe_dump(m))
    (d / "CHANGELOG.md").write_text(
        "# Hello\n\n## 1.1.0\n\nLouder.\n\n## 1.0.0\n\nSays hello.\n"
    )
    publish.build_repository(src, out, pem, "Test plugins")
    installer._index_cache.clear()
    entry = next(p for p in installer.marketplace()["plugins"] if p["id"] == "hello")
    assert entry["update"] is True and entry["repoVersion"] == "1.1.0"
    assert [v["version"] for v in entry["versions"]] == ["1.1.0", "1.0.0"]

    installer.hold("hello", "1.0.0")
    entry = next(p for p in installer.marketplace()["plugins"] if p["id"] == "hello")
    assert entry["update"] is False and entry["held"] == "1.0.0"
    installer.hold("hello", None)

    info = installer.install_from_repository(repo, "hello", "1.1.0")
    installer.confirm(info["token"], accept_unsigned=False, repository_id=repo.id)
    assert db.session.get(InstalledPlugin, "hello").version == "1.1.0"
    back = installer.rollback("hello")
    assert back == {**back, "version": "1.0.0", "previous": "1.1.0"}
    assert db.session.get(InstalledPlugin, "hello").version == "1.0.0"


def test_unsigned_upload_needs_confirmation(tmp_path, db, seeded_db, plugin_dir):
    d = make_plugin(tmp_path)
    info = installer.stage(publish.pack(d))
    assert info["trust"]["status"] == "unsigned" and info["needsConfirmation"]
    with pytest.raises(InstallError, match="isn't signed"):
        installer.confirm(info["token"], accept_unsigned=False)
    installer.confirm(info["token"], accept_unsigned=True)
    assert db.session.get(InstalledPlugin, "hello").trust == "unsigned"


def test_upload_with_an_unknown_key_is_refused(
    tmp_path, key, db, seeded_db, plugin_dir
):
    info = installer.stage(signed_zip(make_plugin(tmp_path), key[0]))
    assert info["trust"]["status"] == "invalid" and not info["installable"]
    with pytest.raises(InstallError, match="refused"):
        installer.confirm(info["token"], accept_unsigned=True)


def test_install_checks_required_modules(tmp_path, key, db, seeded_db, plugin_dir):
    trust_key(db, key[1])
    d = make_plugin(tmp_path, requires=["nothing.here"])
    info = installer.stage(signed_zip(d, key[0]))
    with pytest.raises(InstallError, match="needs nothing.here"):
        installer.confirm(info["token"], accept_unsigned=False)
    assert db.session.get(InstalledPlugin, "hello") is None


def test_incompatible_plugin_is_refused(tmp_path, db, plugin_dir):
    d = make_plugin(tmp_path, hubra=">=99")
    with pytest.raises(InstallError, match="needs Hubra"):
        installer.stage(publish.pack(d))


def test_uninstall_keeps_or_deletes_data(
    tmp_path, key, db, seeded_db, plugin_dir, monkeypatch
):
    trust_key(db, key[1])
    d = make_plugin(tmp_path)
    info = installer.stage(signed_zip(d, key[0]))
    installer.confirm(info["token"], accept_unsigned=False)
    # This process didn't load it; give the uninstall the files it needs.
    spec = scan(Path(plugin_dir) / "installed", bundled=False)[0]
    monkeypatch.setitem(loader.current().specs, "hello", spec)

    installer.uninstall("hello", delete_data=True)
    assert db.session.get(InstalledPlugin, "hello") is None
    assert db.session.query(PluginArchive).filter_by(plugin_id="hello").count() == 0
    insp = db.inspect(db.engine)
    assert not insp.has_table("hello_notes")


def test_uninstall_refuses_while_another_plugin_needs_it(db, seeded_db):
    installer.install_bundled("notes") if db.session.get(
        InstalledPlugin, "notes"
    ) is None else None
    db.session.add(
        InstalledPlugin(
            id="badges", name="Badges", version="1", source="bundled", trust="bundled"
        )
    )
    db.session.commit()
    spec = loader.current().get("badges")
    spec.manifest = {**spec.manifest, "requires": ["notes"]}
    try:
        with pytest.raises(InstallError, match="need"):
            installer.uninstall("notes")
    finally:
        spec.manifest = {**spec.manifest, "requires": ["members"]}


def test_materialize_unpacks_from_the_database(
    tmp_path, key, db, seeded_db, plugin_dir
):
    trust_key(db, key[1])
    info = installer.stage(signed_zip(make_plugin(tmp_path / "src"), key[0]))
    installer.confirm(info["token"], accept_unsigned=False)
    root = tmp_path / "other-pod"
    root.mkdir()
    row = db.session.get(InstalledPlugin, "hello")
    pdir = loader.materialize(row, root)
    assert (pdir / "plugin.yaml").is_file()
    assert loader.stamp_file(root, "hello").read_text() == row.archive_sha256
    # The signature still checks out after the round trip.
    spec = scan(root, bundled=False)[0]
    assert (
        trust.verify(pdir, spec.manifest, installer.community_keys())["status"]
        == "community"
    )


def test_uninstalled_plugin_modules_disappear_before_reload(db, seeded_db):
    from hubra.core.modules import states
    from hubra.core.models.plugin import InstalledPlugin as Row
    from hubra.core.plugins import current

    plugins = current()
    plugins.autoinstalled.discard("badges")
    try:
        assert "badges" not in states()
        db.session.add(
            Row(
                id="badges",
                name="Badges",
                version="1",
                source="bundled",
                trust="bundled",
            )
        )
        db.session.commit()
        from hubra.core.modules.state import invalidate

        invalidate()
        assert "badges" in states()
    finally:
        plugins.autoinstalled.add("badges")


# ── API ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def superadmin(client, seeded_db, db):
    seeded_db["user"].is_superadmin = True
    db.session.commit()
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )


def test_marketplace_needs_the_permission(client, auth_headers):
    assert client.get("/api/v1/manager/plugins/?fetch=0").status_code == 403


def test_marketplace_lists_bundled_plugins(client, superadmin):
    body = client.get("/api/v1/manager/plugins/?fetch=0").get_json()
    notes = next(p for p in body["plugins"] if p["id"] == "notes")
    assert notes["bundled"] and notes["installed"] and notes["autoinstalled"]
    assert body["updateMode"] == "notify"


def test_upload_and_confirm_over_the_api(client, superadmin, tmp_path, plugin_dir):
    blob = publish.pack(make_plugin(tmp_path))
    resp = client.post(
        "/api/v1/manager/plugins/upload",
        data={"file": (io.BytesIO(blob), "hello-1.0.0.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.get_json()
    token = resp.get_json()["token"]
    resp = client.post(f"/api/v1/manager/plugins/stage/{token}/confirm", json={})
    assert resp.status_code == 400 and "signed" in resp.get_json()["message"]
    resp = client.post(
        f"/api/v1/manager/plugins/stage/{token}/confirm", json={"acceptUnsigned": True}
    )
    assert resp.status_code == 200 and resp.get_json()["version"] == "1.0.0"


def test_trusted_keys_api(client, superadmin, key):
    _pem, pub = key
    resp = client.post(
        "/api/v1/manager/plugins/keys", json={"name": "Ana", "publicKey": pub}
    )
    assert resp.status_code == 201
    kid = resp.get_json()["keyId"]
    assert (
        client.post(
            "/api/v1/manager/plugins/keys", json={"name": "Ana 2", "publicKey": pub}
        ).status_code
        == 409
    )
    keys = client.get("/api/v1/manager/plugins/keys").get_json()
    assert any(k["keyId"] == kid for k in keys)


def test_frontend_asset_is_served_for_loaded_plugins(client, monkeypatch, tmp_path):
    spec = loader.current().get("notes")
    dist = tmp_path / "plugin.js"
    dist.write_text("/* notes */")
    monkeypatch.setattr(type(spec), "frontend_file", property(lambda self: dist))
    resp = client.get("/api/v1/plugins/notes/frontend.js")
    assert resp.status_code == 200 and b"notes" in resp.data
    assert resp.mimetype == "text/javascript"
    assert client.get("/api/v1/plugins/nope/frontend.js").status_code == 404


def test_module_list_says_which_plugin(client, auth_headers, db):
    from tests.helpers import set_modules

    set_modules(True)
    mods = {m["code"]: m for m in client.get("/api/v1/modules/").get_json()}
    assert mods["notes"]["plugin"]["id"] == "notes"
    assert mods["members"]["plugin"] is None


def test_index_json_round_trips(tmp_path, key):
    src = tmp_path / "src"
    src.mkdir()
    make_plugin(src)
    out = tmp_path / "public"
    publish.build_repository(src, out, key[0], "Mine")
    doc = json.loads((out / "index.json").read_text())
    trust.verify_index(doc, trust.load_public(key[1]))
    publish.yank(out, key[0], "hello", "1.0.0", "broken")
    doc = json.loads((out / "index.json").read_text())
    assert doc["plugins"][0]["yanked"] == "broken"
    trust.verify_index(doc, trust.load_public(key[1]))


@pytest.mark.parametrize(
    "url",
    [
        "http://plugins.example/index.json",
        "https://127.0.0.1/index.json",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/index.json",
        "file:///etc/passwd",
    ],
)
def test_downloads_only_go_to_public_https_hosts(url, monkeypatch):
    monkeypatch.delenv("HUBRA_PLUGINS_ALLOW_PRIVATE", raising=False)
    with pytest.raises(InstallError):
        installer.http_get(url)


def test_a_plugin_cannot_shadow_another_package(tmp_path):
    """M3: a plugin's directory comes last on sys.path, and its package must be its own."""
    import sys

    import yaml

    src = make_plugin(tmp_path / "src")
    (src / "hubra_hello").rename(src / "json")
    manifest = yaml.safe_load((src / "plugin.yaml").read_text())
    manifest["package"] = "json"
    (src / "plugin.yaml").write_text(yaml.safe_dump(manifest))
    spec = scan(tmp_path / "src", bundled=False)[0]
    try:
        with pytest.raises(ValueError, match="not the plugin's own"):
            loader._import(spec)
        assert sys.path[0] != str(spec.path)
        assert json.__file__ and str(spec.path) not in json.__file__
    finally:
        if str(spec.path) in sys.path:
            sys.path.remove(str(spec.path))
