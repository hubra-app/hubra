"""Standard roles, functions and module access (docs/roles.md).

* ``standardise`` gives a club Vorstand, Aktuar/in and the board functions,
  and keeps every role's modules on its first run.
* A person without a module's access key gets ``403 MODULE_ACCESS`` from its
  API, except on routes for their own data, and only once the club enforces
  module access.
* A function gives several roles.
"""

from sqlalchemy import select

from tests.settings.test_settings_kv import _login, _make_role_and_member


def _sync(app):
    app.test_cli_runner().invoke(args=["sync-permissions"])


def _standardise(db, **kw):
    from hubra.core.services.standard_roles import standardise

    report = standardise(**kw)
    db.session.commit()
    return report


def _keys(role):
    from hubra.core.services.roles import RoleService

    return set(RoleService.get_permissions(role.id))


def test_standardise_adds_the_board_roles_and_functions(app, db, seeded_db):
    from hubra.core.models.function import Function
    from hubra.core.models.role import Role

    _sync(app)
    report = _standardise(db)
    assert {"Board", "Secretary", "Member", "Treasurer"} <= set(report["roles"])

    by_key = {r.key: r for r in db.session.scalars(select(Role)).all() if r.key}
    # The seeded Admin/Owner roles are adopted by name, not made again.
    assert by_key["admin"].id == seeded_db["role"].id
    assert by_key["owner"].id == seeded_db["owner_role"].id
    assert "members.members.read" in _keys(by_key["board"])
    assert "module.events.access" in _keys(by_key["board"])
    assert "events.events.create" in _keys(by_key["board"])
    assert "applications.applications.approve" in _keys(by_key["secretary"])
    # Giving roles stays with admins.
    assert "members.members.update.role_ids" not in _keys(by_key["secretary"])
    assert "finance.invoices.delete" in _keys(by_key["treasurer"])

    fns = {f.key: f for f in db.session.scalars(select(Function)).all() if f.key}
    assert {r.key for r in fns["president"].roles} == {"admin", "board"}
    assert {r.key for r in fns["vice_president"].roles} == {"admin", "board"}
    assert {r.key for r in fns["secretary"].roles} == {"board", "secretary"}
    assert {r.key for r in fns["treasurer"].roles} == {"board", "treasurer"}

    # A second run adds nothing.
    again = _standardise(db)
    assert again["roles"] == [] and again["functions"] == [] and not again["first"]


def test_a_club_function_is_adopted_and_gets_the_missing_roles(app, db, seeded_db):
    from hubra.core.models.function import Function

    _sync(app)
    own = _make_role_and_member(db, seeded_db["tier"], name="Kasse", permission_keys=[])
    kassier = Function(name="Kassier", roles=[own.roles[0]])
    praesidium = Function(name="Präsidium")
    db.session.add_all([kassier, praesidium])
    db.session.commit()

    _standardise(db)
    db.session.refresh(kassier)
    assert kassier.key == "treasurer"
    assert {r.name for r in kassier.roles} == {"Kasse", "Board", "Treasurer"}

    # A Präsidium the club had doesn't make its holders admins on upgrade.
    db.session.refresh(praesidium)
    assert praesidium.key == "president"
    assert {r.name for r in praesidium.roles} == {"Board"}
    names = set(db.session.scalars(select(Function.name)).all())
    assert "Kassier/in" not in names  # not made twice


def test_the_first_run_keeps_what_every_role_could_use(app, db, seeded_db):
    from hubra.core import module_access

    _sync(app)
    member = _make_role_and_member(
        db, seeded_db["tier"], name="Helfer", permission_keys=["events.events.read"]
    )
    role = member.roles[0]
    assert "module.events.access" not in _keys(role)

    report = _standardise(db)
    assert report["first"] and report["backfilled"] >= 1
    assert "module.events.access" in _keys(role)
    assert "module.finance.access" not in _keys(role)
    assert module_access.enforced()


def test_no_access_hides_the_module_api(app, client, db, seeded_db):
    _sync(app)
    _make_role_and_member(
        db, seeded_db["tier"], name="Leser", permission_keys=["events.events.read"]
    )
    _standardise(db)
    _login(client, "leser@test.ch")

    # Finance had a sidebar entry only for those with finance keys, so the
    # first run gave no one else its access key.
    r = client.get("/api/v1/finance/invoices")
    assert r.status_code == 403
    assert r.get_json()["error"] == "MODULE_ACCESS"
    # Polls had an entry everyone saw: every role kept it.
    assert (client.get("/api/v1/polls/").get_json() or {}).get("error") != "MODULE_ACCESS"
    # The module they may use answers.
    assert client.get("/api/v1/events/").status_code == 200
    # Their own invoices stay open without finance access (D4).
    r = client.get("/api/v1/finance/invoices/mine")
    assert r.status_code != 403 or r.get_json()["error"] != "MODULE_ACCESS"


def test_nothing_hides_before_the_club_is_standardised(app, client, db, seeded_db):
    _sync(app)
    _make_role_and_member(
        db, seeded_db["tier"], name="Leser", permission_keys=["events.events.read"]
    )
    _login(client, "leser@test.ch")
    r = client.get("/api/v1/finance/invoices")
    assert (r.get_json() or {}).get("error") != "MODULE_ACCESS"
    perms = client.get("/api/v1/account/permissions").get_json()
    assert perms["module_access"] is False


def test_admins_use_every_module(app, client, db, seeded_db, auth_headers):
    _sync(app)
    _standardise(db)
    assert client.get("/api/v1/polls/").status_code == 200


def test_any_module_key_brings_its_access_key(app, client, db, seeded_db, auth_headers):
    from hubra.core.models.role import Role

    _sync(app)
    role = Role(name="Umfragen")
    db.session.add(role)
    db.session.commit()
    r = client.put(
        f"/api/v1/roles/{role.id}/permissions", json={"permissions": ["polls.polls.read"]}
    )
    assert r.status_code == 200
    assert "module.polls.access" in r.get_json()["permissions"]


def test_role_defaults_apply_once_on_first_enable(app, db, seeded_db, monkeypatch):
    import dataclasses

    from hubra.core import module_access
    from hubra.core.models.role import Role
    from hubra.core.modules import registry
    from hubra.core.modules.state import set_enabled

    _sync(app)
    _standardise(db)
    set_enabled("bindings", False)
    db.session.commit()
    module_access.mark_applied([])  # nothing changes yet
    applied = module_access.applied_modules() - {"bindings"}
    module_access._write_setting(
        module_access.APPLIED_SETTING, __import__("json").dumps(sorted(applied))
    )

    real = registry.get("bindings")
    patched = dataclasses.replace(real, role_defaults={"board": "view"})
    original_get = registry.get
    monkeypatch.setattr(
        registry, "get", lambda code: patched if code == "bindings" else original_get(code)
    )

    board = db.session.scalar(select(Role).where(Role.key == "board"))
    assert "bindings.bindings.read" not in _keys(board)
    set_enabled("bindings", True)
    db.session.commit()
    assert {"bindings.bindings.read", "module.bindings.access"} <= _keys(board)
    assert "bindings.bindings.write" not in _keys(board)

    # Taken away by the club, not given again on the next switch-on.
    from hubra.core.services.roles import RoleService

    RoleService.set_permissions(board, [], actor_id=None, _internal=True)
    set_enabled("bindings", False)
    set_enabled("bindings", True)
    db.session.commit()
    assert "bindings.bindings.read" not in _keys(board)


def test_bad_role_defaults_are_refused():
    import pytest

    from hubra.core.modules.base import Module
    from hubra.core.modules.registry import ModuleRegistry, ModuleRegistryError

    reg = ModuleRegistry()
    reg.add(Module(code="x", name="X", role_defaults={"president": "view"}))
    with pytest.raises(ModuleRegistryError):
        reg.validate()


def test_a_function_gives_several_roles(app, client, db, seeded_db, auth_headers):
    from hubra.core.models.role import Role

    _sync(app)
    _standardise(db)
    board = db.session.scalar(select(Role).where(Role.key == "board"))
    treasurer = db.session.scalar(select(Role).where(Role.key == "treasurer"))
    r = client.post(
        "/api/v1/functions/",
        json={"name": "Revisor/in", "grantsRoleIds": [board.id, treasurer.id]},
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert sorted(body["grantsRoleIds"]) == sorted([board.id, treasurer.id])

    holder = _make_role_and_member(db, seeded_db["tier"], name="Revi", permission_keys=[])
    r = client.post(f"/api/v1/functions/{body['id']}/holders", json={"memberId": holder.id})
    assert r.status_code in (200, 201), r.get_json()

    from hubra.core.permissions import held_roles

    db.session.expire_all()
    assert {"board", "treasurer"} <= {r.key for r in held_roles(holder)}

    r = client.patch(f"/api/v1/functions/{body['id']}", json={"grantsRoleIds": [board.id]})
    assert r.status_code == 200
    assert r.get_json()["grantsRoleIds"] == [board.id]
