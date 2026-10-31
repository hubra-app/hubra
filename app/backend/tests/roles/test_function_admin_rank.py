"""An admin role held through a function (Präsident gives Admin) protects
its holder like one given directly: someone without admin rights can't
switch them off, sign them out, or delete the function to take it away."""

import pytest
from sqlalchemy import select

from tests.settings.test_settings_kv import _login, _make_role_and_member


@pytest.fixture
def boss(app, db, seeded_db):
    """A member who is admin only through the function Praesident."""
    from hubra.core.models.function import Function, FunctionHolder
    from hubra.core.models.role import Role

    app.test_cli_runner().invoke(args=["sync-permissions"])
    admin_role = db.session.scalar(
        select(Role).where(Role.is_admin.is_(True), Role.is_owner.is_(False))
    )
    member = _make_role_and_member(db, seeded_db["tier"], name="Boss", permission_keys=[])
    fn = Function(name="Praesident", grants_tenant_role_id=admin_role.id, max_holders=1)
    db.session.add(fn)
    db.session.flush()
    db.session.add(FunctionHolder(function_id=fn.id, member_id=member.id))
    db.session.commit()
    return {"member": member, "function": fn}


def _clerk(db, seeded_db, *keys):
    _make_role_and_member(db, seeded_db["tier"], name="Clerk", permission_keys=list(keys))


@pytest.mark.parametrize(
    "key,call",
    [
        ("members.members.disable", lambda c, mid: c.post(f"/api/v1/members/{mid}/disable")),
        ("members.members.archive", lambda c, mid: c.post(f"/api/v1/members/{mid}/archive")),
        ("members.members.update", lambda c, mid: c.delete(f"/api/v1/members/{mid}/sessions")),
        (
            "members.members.update",
            lambda c, mid: c.patch(f"/api/v1/members/{mid}", json={"status": "suspended"}),
        ),
    ],
)
def test_a_function_admin_is_out_of_reach(client, db, seeded_db, boss, key, call):
    _clerk(db, seeded_db, key, "members.members.read")
    _login(client, "clerk@test.ch")
    r = call(client, boss["member"].id)
    assert r.status_code in (403, 409), r.get_json()
    db.session.refresh(boss["member"])
    assert not boss["member"].is_disabled
    assert boss["member"].archived_at is None


def test_deleting_the_function_needs_the_right_to_take_its_role(client, db, seeded_db, boss):
    from hubra.core.models.function import Function

    _clerk(db, seeded_db, "functions.functions.delete")
    _login(client, "clerk@test.ch")
    r = client.delete(f"/api/v1/functions/{boss['function'].id}")
    assert r.status_code == 403
    assert r.get_json()["error"] == "ADMIN_ONLY"
    assert db.session.get(Function, boss["function"].id) is not None

    _login(client, "admin@test.ch")
    assert client.delete(f"/api/v1/functions/{boss['function'].id}").status_code == 200


def test_an_admin_still_signs_a_member_out(client, db, seeded_db):
    member = _make_role_and_member(db, seeded_db["tier"], name="Plain", permission_keys=[])
    _login(client, "admin@test.ch")
    assert client.delete(f"/api/v1/members/{member.id}/sessions").status_code == 200


def test_role_managers_only_take_away_rights_they_hold(client, db, seeded_db, app):
    from hubra.core.models.role import Role

    app.test_cli_runner().invoke(args=["sync-permissions"])
    treasurer = _make_role_and_member(
        db, seeded_db["tier"], name="Kassier", permission_keys=["finance.invoices.read"]
    )
    role_id = treasurer.roles[0].id
    _clerk(db, seeded_db, "roles.roles.set_permissions", "members.members.read")
    _login(client, "clerk@test.ch")
    url = f"/api/v1/roles/{role_id}/permissions"
    r = client.put(url, json={"permissions": []})
    assert r.status_code == 403
    assert r.get_json()["error"] == "BEYOND_OWN_PERMISSIONS"
    r = client.put(url, json={"permissions": ["finance.invoices.read", "members.members.read"]})
    assert r.status_code == 200
    r = client.put(url, json={"permissions": ["finance.invoices.read"]})
    assert r.status_code == 200
    assert db.session.get(Role, role_id) is not None
