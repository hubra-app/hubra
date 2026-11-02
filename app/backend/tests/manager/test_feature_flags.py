"""Early-access flags per club."""

from __future__ import annotations

import pytest

from hubra.core.errors import ApiError
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.services import feature_flags as ff

PLATFORM = "/api/v1/manager/platform/features"


@pytest.fixture(autouse=True)
def flags():
    ff.register(ff.Flag("new_calendar", "Neuer Kalender", "New calendar"))
    ff.register(ff.Flag("bank_sync", "Bankabgleich", "Bank sync", default="early"))
    yield
    ff.unregister("new_calendar")
    ff.unregister("bank_sync")


def test_stages_and_groups(db, tenant_pair):
    a, b = tenant_pair["tenant_a"], tenant_pair["tenant_b"]
    assert ff.stages() == {"new_calendar": "off", "bank_sync": "early"}
    assert not ff.is_on("new_calendar", a)
    assert not ff.is_on("bank_sync", a)  # early, but a isn't in the group

    ff.set_club(a, early_access=True)
    assert ff.is_on("bank_sync", a) and not ff.is_on("bank_sync", b)

    ff.set_stage("new_calendar", "early")
    assert ff.is_on("new_calendar", a) and not ff.is_on("new_calendar", b)
    ff.set_stage("new_calendar", "all")
    assert ff.is_on("new_calendar", b)

    # A club's own choice wins over the stage, both ways.
    ff.set_club(b, features={"new_calendar": False, "bank_sync": True})
    assert not ff.is_on("new_calendar", b) and ff.is_on("bank_sync", b)
    ff.set_club(b, features={"new_calendar": None})
    assert ff.is_on("new_calendar", b)

    assert not ff.is_on("does_not_exist", a)


def test_bad_values(db, tenant_pair):
    a = tenant_pair["tenant_a"]
    with pytest.raises(ApiError):
        ff.set_stage("new_calendar", "half")
    with pytest.raises(ApiError):
        ff.set_stage("nope", "all")
    with pytest.raises(ApiError):
        ff.set_club(a, early_access="yes")
    with pytest.raises(ApiError):
        ff.set_club(a, features={"nope": True})
    with pytest.raises(ApiError):
        ff.set_club(a, features={"new_calendar": "on"})


def test_manage_stage_and_club(client, db, staff_headers, tenant_pair):
    a = tenant_pair["tenant_a"]
    body = client.get(PLATFORM).get_json()
    assert [f["key"] for f in body["flags"]] == ["new_calendar", "bank_sync"]
    assert body["early_access"] == []

    resp = client.put(f"{PLATFORM}/new_calendar", json={"stage": "early"})
    assert resp.status_code == 200, resp.get_json()
    assert (
        client.put(f"{PLATFORM}/new_calendar", json={"stage": "x"}).status_code == 400
    )
    assert client.put(f"{PLATFORM}/nope", json={"stage": "all"}).status_code == 404

    url = f"/api/v1/system/tenants/{a.id}/early-access"
    resp = client.put(
        url, json={"early_access": True, "features": {"bank_sync": False}}
    )
    assert resp.status_code == 200, resp.get_json()
    club = resp.get_json()
    assert club["early_access"] is True
    on = {f["key"]: f["on"] for f in club["features"]}
    assert on == {"new_calendar": True, "bank_sync": False}
    assert client.put(url, json={}).status_code == 400

    body = client.get(PLATFORM).get_json()
    assert [c["name"] for c in body["early_access"]] == ["Tenant A"]
    cal = next(f for f in body["flags"] if f["key"] == "new_calendar")
    assert cal["stage"] == "early" and cal["clubs_on"] == 1
    sync = next(f for f in body["flags"] if f["key"] == "bank_sync")
    assert sync["forced_off"] == [a.id] and sync["clubs_on"] == 0

    actions = {e.action for e in db.session.query(GlobalAuditEntry).all()}
    assert {"platform.feature.stage", "tenant.early_access"} <= actions


def test_club_app_reads_its_flags(app, db, tenant_pair):
    a = tenant_pair["tenant_a"]
    ff.set_club(a, early_access=True)
    db.session.commit()
    from flask import g

    with app.test_request_context("/api/v1/features"):
        g.tenant = a
        assert ff.for_club(a) == {"new_calendar": False, "bank_sync": True}
        assert ff.is_on("bank_sync")  # the current club


def test_features_endpoint_without_club(client, db):
    assert client.get("/api/v1/features").get_json() == {"features": {}}


def test_require_feature(app, db, tenant_pair):
    a = tenant_pair["tenant_a"]
    from flask import g

    @ff.require_feature("new_calendar")
    def view():
        return "ok"

    with app.test_request_context("/"):
        g.tenant = a
        with pytest.raises(ApiError) as err:
            view()
        assert err.value.status == 404
        ff.set_stage("new_calendar", "all")
        assert view() == "ok"


def test_rights(client, auth_headers, tenant_pair):
    assert client.get(PLATFORM, headers=auth_headers).status_code == 403
    a = tenant_pair["tenant_a"]
    url = f"/api/v1/system/tenants/{a.id}/early-access"
    assert client.get(url, headers=auth_headers).status_code == 403
