"""Connected apps: connect round trip, confirm, settings, disconnect, and
secret module settings stored encrypted."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from hubra.core import apps
from hubra.core.models.audit import AuditEntry
from hubra.core.models.connected_app import ConnectedApp
from hubra.core.models.feature import TenantFeature
from hubra.core.models.tenant import Tenant
from hubra.core.modules import AppProvider, AppScope, Module, SettingField, registry
from hubra.core.modules.state import invalidate, seal_secrets
from tests.apps import fake_provider
from tests.helpers import set_modules

H = {"X-Tenant-Slug": "club-a"}


@pytest.fixture
def fake_module(app):
    registry.load()
    registry._modules["fakeapp"] = Module(
        code="fakeapp",
        name="Fake",
        depends_on=("members",),
        settings=(SettingField("token", "secret"), SettingField("note", "str")),
        apps=(
            AppProvider(
                code="fake",
                name="Fake",
                handler="tests.apps.fake_provider:handler",
                scopes=(AppScope("announce", "Announce"), AppScope("roles", "Roles")),
            ),
        ),
    )
    fake_provider.calls.clear()
    fake_provider.handler.fail_complete = False
    fake_provider.handler.fail_revoke = False
    yield
    registry._modules.pop("fakeapp", None)


@pytest.fixture
def tenant(db, seeded_db, fake_module):
    t = Tenant(name="Club A", slug="club-a", status="active")
    db.session.add(t)
    db.session.commit()
    set_modules(True, "fakeapp")
    return t


@pytest.fixture
def club_auth(client, tenant):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
        headers=H,
    )
    return {}


def _connect(client, guild="g1", scopes=None):
    body = {} if scopes is None else {"scopes": scopes}
    resp = client.post("/api/v1/apps/fake/connect", json=body, headers=H)
    assert resp.status_code == 200, resp.get_json()
    state = parse_qs(urlparse(resp.get_json()["url"]).query)["state"][0]
    return client.get(f"/api/v1/apps/callback/fake?state={state}&guild_id={guild}")


def _query(resp):
    return parse_qs(urlparse(resp.headers["Location"]).query)


def test_list_shows_providers_of_enabled_modules(client, club_auth):
    resp = client.get("/api/v1/apps/", headers=H)
    assert resp.status_code == 200
    data = resp.get_json()
    fake = next(p for p in data["providers"] if p["code"] == "fake")
    assert [s["key"] for s in fake["scopes"]] == ["announce", "roles"]
    assert fake["unavailable"] is None
    assert data["connections"] == []


def test_list_needs_sign_in(client, tenant):
    assert client.get("/api/v1/apps/", headers=H).status_code == 401


def test_connect_round_trip_creates_a_pending_connection(client, db, club_auth, tenant):
    resp = _connect(client, scopes=["announce"])
    assert resp.status_code == 302
    location = urlparse(resp.headers["Location"])
    assert location.path == "/club-a/app/settings/apps"
    conn = db.session.get(ConnectedApp, int(_query(resp)["confirm"][0]))
    assert conn.status == "pending"
    assert conn.tenant_id == tenant.id
    assert conn.external_id == "g1"
    assert conn.scopes == ["announce"]
    # The secret is stored encrypted, and readable through core only.
    assert "s3cret" not in (conn.secret_encrypted or "")
    assert apps.secret(conn) == "s3cret"
    # A pending connection does nothing yet.
    assert apps.active("fake", "g1") is None


def test_callback_needs_the_browser_that_started_it(client, db, club_auth):
    resp = client.post("/api/v1/apps/fake/connect", json={}, headers=H)
    state = parse_qs(urlparse(resp.get_json()["url"]).query)["state"][0]
    client.delete_cookie(apps.NONCE_COOKIE)
    resp = client.get(f"/api/v1/apps/callback/fake?state={state}&guild_id=g1")
    assert _query(resp)["error"] == ["expired"]
    assert db.session.query(ConnectedApp).count() == 0


def test_callback_refuses_a_tampered_state(client, db, club_auth):
    client.post("/api/v1/apps/fake/connect", json={}, headers=H)
    resp = client.get("/api/v1/apps/callback/fake?state=forged&guild_id=g1")
    assert _query(resp)["error"] == ["expired"]
    assert db.session.query(ConnectedApp).count() == 0


def test_connect_refuses_unknown_scopes(client, club_auth):
    resp = client.post(
        "/api/v1/apps/fake/connect", json={"scopes": ["admin"]}, headers=H
    )
    assert resp.status_code == 400


def test_cancelled_on_the_service(client, db, club_auth):
    resp = client.post("/api/v1/apps/fake/connect", json={}, headers=H)
    state = parse_qs(urlparse(resp.get_json()["url"]).query)["state"][0]
    resp = client.get(f"/api/v1/apps/callback/fake?state={state}&error=access_denied")
    assert _query(resp)["error"] == ["cancelled"]


def test_confirm_makes_it_live_and_audits(client, db, club_auth):
    conn_id = int(_query(_connect(client))["confirm"][0])
    resp = client.post(f"/api/v1/apps/connections/{conn_id}/confirm", headers=H)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "active"
    assert apps.active("fake", "g1").id == conn_id
    assert ("confirmed", conn_id) in fake_provider.calls
    entry = db.session.query(AuditEntry).filter_by(action="connect_app").one()
    assert entry.target_id == conn_id


def test_confirm_after_expiry_is_refused(client, db, club_auth):
    conn_id = int(_query(_connect(client))["confirm"][0])
    conn = db.session.get(ConnectedApp, conn_id)
    conn.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.session.commit()
    resp = client.post(f"/api/v1/apps/connections/{conn_id}/confirm", headers=H)
    assert resp.status_code == 409
    assert db.session.get(ConnectedApp, conn_id).status == "pending"


def test_one_outside_id_belongs_to_one_club(client, db, club_auth, tenant):
    other = Tenant(name="Club B", slug="club-b", status="active")
    db.session.add(other)
    db.session.flush()
    db.session.add(
        ConnectedApp(
            tenant_id=other.id, provider="fake", external_id="g1", status="active"
        )
    )
    db.session.commit()
    resp = _connect(client)
    assert _query(resp)["error"] == ["taken"]
    assert apps.active("fake", "g1").tenant_id == other.id


def test_connecting_again_replaces_the_old_link(client, db, club_auth):
    first = int(_query(_connect(client))["confirm"][0])
    client.post(f"/api/v1/apps/connections/{first}/confirm", headers=H)
    second = int(_query(_connect(client))["confirm"][0])
    client.post(f"/api/v1/apps/connections/{second}/confirm", headers=H)
    assert apps.active("fake", "g1").id == second
    old = db.session.get(ConnectedApp, first)
    assert old.status == "revoked" and old.secret_encrypted is None


def test_another_clubs_connection_is_not_found(client, db, club_auth):
    other = Tenant(name="Club B", slug="club-b", status="active")
    db.session.add(other)
    db.session.flush()
    conn = ConnectedApp(
        tenant_id=other.id, provider="fake", external_id="g9", status="active"
    )
    db.session.add(conn)
    db.session.commit()
    assert (
        client.get(f"/api/v1/apps/connections/{conn.id}", headers=H).status_code == 404
    )
    assert (
        client.delete(f"/api/v1/apps/connections/{conn.id}", headers=H).status_code
        == 404
    )
    assert db.session.get(ConnectedApp, conn.id).status == "active"


def test_update_config_audits_changed_keys(client, db, club_auth):
    conn_id = int(_query(_connect(client))["confirm"][0])
    client.post(f"/api/v1/apps/connections/{conn_id}/confirm", headers=H)
    resp = client.patch(
        f"/api/v1/apps/connections/{conn_id}",
        json={"config": {"channel": "c42"}, "scopes": ["roles"]},
        headers=H,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["config"] == {"channel": "c42"}
    assert data["scopes"] == ["roles"]
    entry = db.session.query(AuditEntry).filter_by(action="update_app").one()
    assert "scopes" in entry.target_label and "channel" in entry.target_label
    assert data["events"][0]["action"] == "changed"


def test_update_config_validation_error(client, db, club_auth):
    conn_id = int(_query(_connect(client))["confirm"][0])
    resp = client.patch(
        f"/api/v1/apps/connections/{conn_id}",
        json={"config": {"channel": "bad"}},
        headers=H,
    )
    assert resp.status_code == 400


def test_disconnect_revokes_on_the_service_and_forgets_the_secret(
    client, db, club_auth
):
    conn_id = int(_query(_connect(client))["confirm"][0])
    client.post(f"/api/v1/apps/connections/{conn_id}/confirm", headers=H)
    assert (
        client.delete(f"/api/v1/apps/connections/{conn_id}", headers=H).status_code
        == 200
    )
    conn = db.session.get(ConnectedApp, conn_id)
    assert conn.status == "revoked" and conn.secret_encrypted is None
    assert ("revoke", conn_id) in fake_provider.calls
    assert apps.active("fake", "g1") is None
    assert db.session.query(AuditEntry).filter_by(action="disconnect_app").count() == 1


def test_disconnect_goes_through_when_the_service_fails(client, db, club_auth):
    conn_id = int(_query(_connect(client))["confirm"][0])
    client.post(f"/api/v1/apps/connections/{conn_id}/confirm", headers=H)
    fake_provider.handler.fail_revoke = True
    assert (
        client.delete(f"/api/v1/apps/connections/{conn_id}", headers=H).status_code
        == 200
    )
    assert db.session.get(ConnectedApp, conn_id).status == "revoked"


def test_member_without_the_right_cannot_manage(client, db, tenant):
    from hubra.core.models.member import Member
    from hubra.core.models.role import Role
    from hubra.core.models.user import User

    role = Role(name="Member", is_default=False, is_admin=False)
    user = User(
        email="m@test.ch", first_name="M", last_name="M", private_email_verified=True
    )
    user.set_password("password123")
    db.session.add_all([role, user])
    db.session.flush()
    member = Member(user_id=user.id, status="active")
    member.roles = [role]
    db.session.add(member)
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "m@test.ch", "password": "password123"},
        headers=H,
    )
    assert client.get("/api/v1/apps/", headers=H).status_code == 403
    assert (
        client.post("/api/v1/apps/fake/connect", json={}, headers=H).status_code == 403
    )


def test_activity_list_is_trimmed(db, tenant):
    conn = ConnectedApp(
        tenant_id=tenant.id, provider="fake", external_id="g1", status="active"
    )
    db.session.add(conn)
    db.session.flush()
    for i in range(apps.KEEP_EVENTS + 5):
        apps.record(conn, "sent", i % 2 == 0, f"n{i}")
    db.session.commit()
    from hubra.core.models.connected_app import ConnectedAppEvent

    assert db.session.query(ConnectedAppEvent).count() == apps.KEEP_EVENTS
    assert conn.last_error == f"n{apps.KEEP_EVENTS + 3}"


# ── Secret module settings ───────────────────────────────────────────────────


def test_secret_settings_are_stored_encrypted(db, tenant):
    from hubra.core import modules

    state = modules.set_config("fakeapp", {"token": "abc", "note": "hi"}, tenant.id)
    assert state.config["token"] == "abc"
    raw = db.session.query(TenantFeature).filter_by(feature_code="fakeapp").one().config
    assert raw["token"].startswith("enc:") and "abc" not in raw["token"]
    assert raw["note"] == "hi"
    # Saving without the secret keeps it, still encrypted the same way.
    modules.set_config("fakeapp", {"token": "", "note": "ho"}, tenant.id)
    again = (
        db.session.query(TenantFeature).filter_by(feature_code="fakeapp").one().config
    )
    assert again["token"] == raw["token"]
    assert modules.get_config("fakeapp", tenant.id)["token"] == "abc"


def test_seal_secrets_encrypts_old_plaintext(db, tenant):
    from hubra.core import modules

    db.session.add(
        TenantFeature(
            tenant_id=tenant.id,
            feature_code="fakeapp",
            config={"token": "old", "note": "x"},
        )
    )
    db.session.commit()
    invalidate()
    assert modules.get_config("fakeapp", tenant.id)["token"] == "old"
    assert seal_secrets() == 1
    db.session.commit()
    raw = db.session.query(TenantFeature).filter_by(feature_code="fakeapp").one().config
    assert raw["token"].startswith("enc:")
    assert raw["note"] == "x"
    assert modules.get_config("fakeapp", tenant.id)["token"] == "old"
    assert seal_secrets() == 0
