"""``replaces:``: a plugin that took another one over.

Installing or updating it retires the old plugin like an uninstall that
keeps the data: the tables stay for the new plugin's migrations to adopt,
and the clubs' module switches carry over because the new plugin offers the
same module codes. The old plugin can't come back while the new one is
installed, and the loader never loads both.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from hubra.core.models.plugin import InstalledPlugin, PluginArchive
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.plugins import installer, loader
from hubra.core.plugins.installer import InstallError
from hubra.core.plugins.spec import Spec, validate

from .test_plugins import (  # noqa: F401  (fixtures)
    key,
    make_plugin,
    plugin_dir,
    signed_zip,
    trust_key,
)


def _install(d: Path, pem: bytes) -> dict:
    info = installer.stage(signed_zip(d, pem))
    return installer.confirm(info["token"], accept_unsigned=False)


def test_validate_checks_replaces(tmp_path):
    good = {"id": "books", "name": "Books", "version": "1"}
    assert validate({**good, "replaces": ["budgets"]}) == ""
    assert "replaces" in validate({**good, "replaces": "budgets"})
    assert "replaces" in validate({**good, "replaces": ["Not An Id"]})
    assert "replaces" in validate({**good, "replaces": ["books"]})
    assert "depends on" in validate(
        {**good, "replaces": ["budgets"], "depends": {"budgets": ">=1"}}
    )


def test_installing_the_new_plugin_retires_the_old_and_keeps_its_data(
    tmp_path,
    key,  # noqa: F811
    db,
    seeded_db,
    plugin_dir,  # noqa: F811
):
    pem, pub = key
    trust_key(db, pub)
    _install(make_plugin(tmp_path / "a", pid="old"), pem)
    db.session.execute(text("INSERT INTO hello_notes (text) VALUES ('kept')"))
    db.session.commit()
    try:
        _replace_and_check(tmp_path, pem, db)
    finally:  # the table outlives this test's database rows
        db.session.execute(text("DELETE FROM hello_notes"))
        db.session.commit()


def _replace_and_check(tmp_path, pem, db):

    # Same module and table, now in another plugin that took "old" over.
    new = make_plugin(tmp_path / "b", pid="merged", version="2.0.0", replaces=["old"])
    result = _install(new, pem)

    assert result["replaced"] == ["old"]
    assert db.session.get(InstalledPlugin, "old") is None
    assert db.session.get(InstalledPlugin, "merged") is not None
    assert db.session.query(PluginArchive).filter_by(plugin_id="old").count() == 0
    assert db.session.execute(text("SELECT text FROM hello_notes")).scalars().all() == [
        "kept"
    ]
    entry = (
        db.session.query(GlobalAuditEntry)
        .filter_by(action="replace_plugin", target_id="old")
        .one()
    )
    assert entry.details["replacedBy"] == "merged"


def test_the_old_plugin_cannot_come_back(
    tmp_path,
    key,  # noqa: F811
    db,
    seeded_db,
    plugin_dir,  # noqa: F811
):
    pem, pub = key
    trust_key(db, pub)
    _install(make_plugin(tmp_path / "b", pid="merged", replaces=["old"]), pem)
    with pytest.raises(InstallError, match="part of Hello now"):
        _install(make_plugin(tmp_path / "a", pid="old"), pem)
    assert db.session.get(InstalledPlugin, "old") is None


def test_refused_while_another_plugin_depends_on_the_old_one(
    tmp_path,
    key,  # noqa: F811
    db,
    seeded_db,
    plugin_dir,  # noqa: F811
):
    pem, pub = key
    trust_key(db, pub)
    _install(make_plugin(tmp_path / "a", pid="old"), pem)
    db.session.add(
        InstalledPlugin(
            id="extra", name="Extra", version="1", source="archive", trust="official"
        )
    )
    db.session.commit()
    extra = Spec(
        id="extra",
        path=tmp_path,
        manifest={"id": "extra", "name": "Extra", "depends": {"old": ">=1"}},
    )
    real = installer._installed_spec
    installer._installed_spec = lambda pid: extra if pid == "extra" else real(pid)
    try:
        with pytest.raises(InstallError, match="Extra needs the plugin"):
            _install(make_plugin(tmp_path / "b", pid="merged", replaces=["old"]), pem)
    finally:
        installer._installed_spec = real
    assert db.session.get(InstalledPlugin, "old") is not None


def _spec(pid: str, **manifest) -> Spec:
    return Spec(
        id=pid, path=Path("/x"), manifest={"id": pid, "name": pid.title(), **manifest}
    )


def test_the_loader_never_loads_both():
    found = loader.PluginSet(
        specs={
            "old": _spec("old"),
            "merged": _spec("merged", replaces=["old"]),
            "other": _spec("other"),
        },
        wanted={"old", "merged", "other"},
    )
    loader._drop_replaced(found)
    assert found.specs["old"].error == "replaced by Merged"
    assert not found.specs["merged"].error and not found.specs["other"].error


def test_a_broken_replacement_keeps_the_old_plugin():
    broken = _spec("merged", replaces=["old"])
    broken.error = "signature: bad"
    found = loader.PluginSet(
        specs={"old": _spec("old"), "merged": broken}, wanted={"old", "merged"}
    )
    loader._drop_replaced(found)
    assert not found.specs["old"].error


def test_the_catalogue_offers_the_new_plugin_instead():
    out = {
        "old": {"id": "old", "name": "Old", "installed": True},
        "merged": {
            "id": "merged",
            "name": "Merged",
            "installed": True,
            "replaces": ["old"],
        },
        "gone": {"id": "gone", "name": "Gone", "installed": False},
        "next": {
            "id": "next",
            "name": "Next",
            "installed": False,
            "replaces": ["gone"],
        },
    }
    installer._add_replaced(out)
    assert out["old"]["replacedBy"] == "merged"
    assert out["old"]["replacedByName"] == "Merged"
    assert out["old"]["replacedByInstalled"] is True
    assert out["merged"]["takesOver"] == ["Old"]
    assert out["gone"]["replacedByInstalled"] is False
    assert out["next"]["takesOver"] == []
