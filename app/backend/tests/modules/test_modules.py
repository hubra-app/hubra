"""Tests for the module system: registry, per-club state, gate, API, events."""

from __future__ import annotations

import pytest

from tests.helpers import set_modules
from vollbuild.core import modules
from vollbuild.core.errors import ApiError
from vollbuild.core.models.feature import Feature, TenantFeature
from vollbuild.core.models.tenant import Tenant
from vollbuild.core.modules import Module, ModuleRegistryError, SettingField
from vollbuild.core.modules.registry import ModuleRegistry
from vollbuild.core.modules.state import invalidate


@pytest.fixture
def tenant(db, seeded_db):
    t = Tenant(name="Club A", slug="club-a", status="active")
    db.session.add(t)
    db.session.commit()
    return t


def _grant(db, tenant, code, enabled=True, allowed=True, config=None):
    db.session.add(
        TenantFeature(
            tenant_id=tenant.id,
            feature_code=code,
            enabled=enabled,
            allowed=allowed,
            config=config or {},
        )
    )
    db.session.commit()
    invalidate()


# ── Registry ─────────────────────────────────────────────────────────────────


def test_registry_has_every_section():
    modules.registry.load()
    codes = set(modules.registry.codes())
    assert {"core", "members", "roles", "finance", "inventory", "mail"} <= codes


def test_registry_orders_dependencies_first():
    order = modules.registry.codes()
    for m in modules.registry.all():
        for dep in m.depends_on:
            assert order.index(dep) < order.index(m.code)


def test_registry_rejects_unknown_dependency():
    reg = ModuleRegistry()
    reg.add(Module(code="a", name="A", depends_on=("missing",)))
    with pytest.raises(ModuleRegistryError, match="unknown module"):
        reg.validate()


def test_registry_rejects_cycles():
    reg = ModuleRegistry()
    reg.add(Module(code="a", name="A", depends_on=("b",)))
    reg.add(Module(code="b", name="B", depends_on=("a",)))
    with pytest.raises(ModuleRegistryError, match="cycle"):
        reg.validate()


def test_v2_blueprints_share_v1_permission_keys():
    from vollbuild.api.permissions import _derive_perm_key

    assert (
        _derive_perm_key("members_bp_v2", "members", "read") == "members.members.read"
    )
    assert (
        _derive_perm_key("settings_bp_v2_tenant", "settings", "read")
        == "settings.settings.read"
    )


def test_every_blueprint_belongs_to_a_module(app):
    for name in app.blueprints:
        assert modules.registry.module_for_blueprint(name) is not None, name


# ── Settings schema ──────────────────────────────────────────────────────────


def test_setting_field_coerces_and_validates():
    assert SettingField("n", "int").coerce("5") == 5
    assert SettingField("b", "bool").coerce("yes") is True
    assert SettingField("x", "int", default=3).coerce("") == 3
    with pytest.raises(ValueError):
        SettingField("u", "url").coerce("ftp://x")
    with pytest.raises(ValueError):
        SettingField("r", "str", required=True).coerce("")
    with pytest.raises(ValueError):
        SettingField("c", "choice", choices=("a", "b")).coerce("c")


def test_validate_config_rejects_unknown_keys():
    m = Module(code="x", name="X", settings=(SettingField("a", "int", default=1),))
    assert m.validate_config({}) == {"a": 1}
    with pytest.raises(ValueError, match="Unknown"):
        m.validate_config({"b": 1})


# ── State ────────────────────────────────────────────────────────────────────


def test_required_modules_are_always_on(db, tenant):
    set_modules(False)
    assert modules.is_enabled("core", tenant.id)
    assert modules.is_enabled("members", tenant.id)


def test_without_tenant_catalog_row_is_the_switch(db, seeded_db):
    set_modules(False, "inventory")
    assert not modules.is_enabled("inventory", None)
    set_modules(True, "inventory")
    assert modules.is_enabled("inventory", None)


def test_tenant_grant_overrides_catalog(db, tenant):
    set_modules(True, "inventory")
    _grant(db, tenant, "inventory", enabled=False)
    assert not modules.is_enabled("inventory", tenant.id)
    assert modules.is_enabled("inventory", None)


def test_module_is_off_when_a_dependency_is_off(db, tenant):
    _grant(db, tenant, "groups", enabled=False)
    _grant(db, tenant, "mail", enabled=True)
    state = modules.states(tenant.id)["mail"]
    assert state.enabled and not state.effective
    assert state.missing_dependencies == ["groups"]


def test_blocked_module_is_off(db, tenant):
    _grant(db, tenant, "inventory", enabled=True, allowed=False)
    assert not modules.is_enabled("inventory", tenant.id)


def test_set_enabled_refuses_when_dependency_off(db, tenant):
    _grant(db, tenant, "groups", enabled=False)
    with pytest.raises(ApiError) as exc:
        modules.set_enabled("mail", True, tenant.id)
    assert exc.value.code == "MODULE_DEPENDENCY_OFF"


def test_set_enabled_refuses_to_switch_off_a_dependency_in_use(db, tenant):
    _grant(db, tenant, "mail", enabled=True)
    with pytest.raises(ApiError) as exc:
        modules.set_enabled("groups", False, tenant.id)
    assert exc.value.code == "MODULE_HAS_DEPENDENTS"


def test_set_enabled_refuses_required(db, tenant):
    with pytest.raises(ApiError) as exc:
        modules.set_enabled("members", False, tenant.id)
    assert exc.value.code == "MODULE_REQUIRED"


def test_set_enabled_refuses_blocked(db, tenant):
    modules.set_allowed("inventory", False, tenant.id)
    with pytest.raises(ApiError) as exc:
        modules.set_enabled("inventory", True, tenant.id)
    assert exc.value.code == "MODULE_NOT_ALLOWED"


def test_set_enabled_creates_grant(db, tenant):
    modules.set_enabled("inventory", False, tenant.id)
    db.session.commit()
    grant = db.session.query(TenantFeature).filter_by(feature_code="inventory").one()
    assert grant.enabled is False and grant.allowed is True


def test_set_config_validates_and_keeps_secrets(db, tenant):
    state = modules.set_config("inventory", {"checkout_max_days": "21"}, tenant.id)
    assert state.config["checkout_max_days"] == 21
    with pytest.raises(ApiError):
        modules.set_config("inventory", {"nope": 1}, tenant.id)


def test_sync_catalog_keeps_existing_default(db):
    db.session.add(Feature(code="mail", name="Old", default_enabled=True))
    db.session.commit()
    modules.sync_catalog()
    row = db.session.get(Feature, "mail")
    assert row.name == "Mail"
    assert row.default_enabled is True


def test_run_for_tenants_only_runs_where_enabled(db, tenant):
    other = Tenant(name="Club B", slug="club-b", status="active")
    db.session.add(other)
    db.session.commit()
    _grant(db, tenant, "inventory", enabled=True)
    _grant(db, other, "inventory", enabled=False)
    seen = []
    result = modules.run_for_tenants("inventory", lambda tid: seen.append(tid) or 1)
    assert seen == [tenant.id]
    assert result == {tenant.id: 1}


def test_per_tenant_job_without_tenants_returns_body_result(db, seeded_db):
    @modules.per_tenant_job("inventory")
    def job():
        return {"ok": True}

    assert job() == {"ok": True}
    set_modules(False, "inventory")
    assert job() == {"skipped": "inventory disabled"}


def test_provisioning_writes_a_switch_per_optional_module(db):
    from unittest.mock import patch

    from vollbuild.core.tenant.service import _seed_tenant

    new = Tenant(name="New", slug="new-club", plan="starter")
    db.session.add(new)
    db.session.flush()
    with (
        patch("vollbuild.core.tenant.context.set_search_path"),
        patch("vollbuild.core.tenant.context.reset_search_path"),
    ):
        _seed_tenant(new.id, None, None)
    db.session.commit()
    grants = {
        g.feature_code: g.enabled
        for g in db.session.query(TenantFeature).filter_by(tenant_id=new.id)
    }
    assert grants["events"] is True
    assert grants["mail"] is False
    assert "members" not in grants


# ── Gate ─────────────────────────────────────────────────────────────────────


def test_gate_blocks_disabled_module_for_tenant(client, db, auth_headers, tenant):
    _grant(db, tenant, "inventory", enabled=False)
    resp = client.get("/api/v1/inventory/", headers={"X-Tenant-Slug": "club-a"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MODULE_DISABLED"
    # The same route without the club context still works.
    assert client.get("/api/v1/inventory/").status_code == 200


def test_gate_covers_v2_blueprints(client, db, auth_headers):
    set_modules(False, "polls")
    resp = client.get("/api/v2/tenants/polls/")
    assert resp.status_code == 403


def test_gate_leaves_required_modules_alone(client, db, auth_headers, tenant):
    set_modules(False)
    resp = client.get("/api/v1/members/", headers={"X-Tenant-Slug": "club-a"})
    assert resp.status_code != 403 or resp.get_json()["error"] != "MODULE_DISABLED"


def test_gate_keeps_public_endpoints_open(client, db, seeded_db):
    set_modules(False, "mail")
    resp = client.get("/api/v1/mail/health")
    assert resp.get_json().get("error") != "MODULE_DISABLED"


def test_gate_applies_to_mail_without_tenant(client, db, auth_headers):
    set_modules(False, "mail")
    resp = client.get("/api/v1/mail/mailboxes")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MODULE_DISABLED"


# ── API ──────────────────────────────────────────────────────────────────────


def test_list_modules(client, db, auth_headers, tenant):
    resp = client.get("/api/v1/modules/", headers={"X-Tenant-Slug": "club-a"})
    assert resp.status_code == 200
    data = {m["code"]: m for m in resp.get_json()}
    assert data["members"]["required"] is True
    assert data["finance"]["nav"][0]["path"] == "/app/finance"
    assert "checkout_max_days" in data["inventory"]["config"]


def test_list_modules_requires_auth(client, db):
    assert client.get("/api/v1/modules/").status_code == 401


def test_switch_module(client, db, auth_headers, tenant):
    resp = client.put(
        "/api/v1/modules/inventory",
        json={"enabled": False},
        headers={"X-Tenant-Slug": "club-a"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["enabled"] is False
    assert not modules.is_enabled("inventory", tenant.id)


def test_switch_module_reports_dependency(client, db, auth_headers, tenant):
    _grant(db, tenant, "mail", enabled=True)
    resp = client.put(
        "/api/v1/modules/groups",
        json={"enabled": False},
        headers={"X-Tenant-Slug": "club-a"},
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "MODULE_HAS_DEPENDENTS"


def test_switch_module_validates_body(client, db, auth_headers):
    resp = client.put("/api/v1/modules/inventory", json={"enabled": "yes"})
    assert resp.status_code == 400


def test_switch_unknown_module(client, db, auth_headers):
    resp = client.put("/api/v1/modules/nope", json={"enabled": True})
    assert resp.status_code == 404


def test_update_module_settings(client, db, auth_headers, tenant):
    resp = client.put(
        "/api/v1/modules/inventory/settings",
        json={"config": {"checkout_max_days": 30}},
        headers={"X-Tenant-Slug": "club-a"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["config"]["checkout_max_days"] == 30


def test_update_module_settings_rejects_bad_values(client, db, auth_headers, tenant):
    resp = client.put(
        "/api/v1/modules/inventory/settings",
        json={"config": {"checkout_max_days": "lots"}},
        headers={"X-Tenant-Slug": "club-a"},
    )
    assert resp.status_code == 400


def test_checkout_uses_module_setting_for_due_date(db, seeded_db):
    from datetime import datetime, timezone

    from vollbuild.api.inventory.services import InventoryService
    from vollbuild.core.models.inventory import InventoryItem

    item = InventoryItem(name="Drill", category="Tool", status="available")
    db.session.add(item)
    db.session.commit()
    checkout = InventoryService.checkout(item.id, seeded_db["admin"].id)
    due = checkout.expected_return_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    assert 13 <= (due - datetime.now(timezone.utc)).days <= 14


# ── Events ───────────────────────────────────────────────────────────────────


def test_emit_calls_only_enabled_subscribers(db, tenant, monkeypatch):
    calls: list = []
    monkeypatch.setattr("tests.modules.test_modules._CALLS", calls)
    fake = Module(
        code="fake",
        name="Fake",
        default_enabled=True,
        events={"thing.happened": "tests.modules.test_modules:_record"},
    )
    monkeypatch.setitem(modules.registry._modules, "fake", fake)
    assert modules.emit("thing.happened", tenant_id=tenant.id, x=1) == ["fake"]
    assert calls == [(tenant.id, 1)]

    db.session.add(Feature(code="fake", name="Fake", default_enabled=True))
    db.session.commit()
    _grant(db, tenant, "fake", enabled=False)
    assert modules.emit("thing.happened", tenant_id=tenant.id, x=2) == []


_CALLS: list = []


def _record(tenant_id, x):
    _CALLS.append((tenant_id, x))


def test_emit_survives_failing_handler(db, tenant, monkeypatch):
    fake = Module(
        code="fake2",
        name="Fake",
        default_enabled=True,
        events={"thing.happened": "tests.modules.test_modules:_boom"},
    )
    monkeypatch.setitem(modules.registry._modules, "fake2", fake)
    assert modules.emit("thing.happened", tenant_id=tenant.id) == []


def _boom(tenant_id):
    raise RuntimeError("boom")


# ── Manager ──────────────────────────────────────────────────────────────────


@pytest.fixture
def superadmin(client, seeded_db, db):
    seeded_db["user"].is_superadmin = True
    db.session.commit()
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )


def test_manager_blocks_module_for_club(client, db, superadmin, tenant):
    resp = client.put(
        f"/api/v2/manager/features/tenants/{tenant.id}/inventory",
        json={"allowed": False},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["allowed"] is False and body["enabled"] is False
    resp = client.put(
        "/api/v1/modules/inventory",
        json={"enabled": True},
        headers={"X-Tenant-Slug": "club-a"},
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MODULE_NOT_ALLOWED"


def test_manager_unknown_module(client, db, superadmin, tenant):
    resp = client.put(
        f"/api/v2/manager/features/tenants/{tenant.id}/nope", json={"allowed": True}
    )
    assert resp.status_code == 404


# ── Celery ───────────────────────────────────────────────────────────────────


def test_task_queued_in_a_club_carries_the_club(app, db, tenant):
    from unittest.mock import patch

    from celery import Task
    from flask import g

    from vollbuild.core.tasks.session_tasks import update_last_seen

    with patch.object(Task, "apply_async") as parent:
        with app.test_request_context("/"):
            g.tenant = tenant
            update_last_seen.apply_async((1,))
    assert parent.call_args.kwargs["headers"] == {"tenant_id": tenant.id}
