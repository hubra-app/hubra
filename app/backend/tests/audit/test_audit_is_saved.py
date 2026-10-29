"""Audit entries written after a route's commit must be committed too.

In tests the last-seen update runs inline and commits whatever the request
left in the session, which hid entries that production (where it runs on
the worker) silently dropped. These tests throttle that update first.
"""

import pytest

from hubra.core import app as app_module
from hubra.core.models.audit import AuditEntry


@pytest.fixture
def no_last_seen(monkeypatch):
    monkeypatch.setattr(app_module, "_maybe_dispatch_last_seen", lambda member_id: None)


def _actions(db):
    db.session.remove()
    return [e.action for e in db.session.query(AuditEntry).all()]


def test_function_create_update_delete_are_saved(client, auth_headers, db, no_last_seen):
    fn = client.post("/api/v1/functions/", json={"name": "Kassier"}, headers=auth_headers)
    assert fn.status_code == 201
    fn_id = fn.get_json()["id"]
    client.patch(f"/api/v1/functions/{fn_id}", json={"name": "Kasse"}, headers=auth_headers)
    client.delete(f"/api/v1/functions/{fn_id}", headers=auth_headers)

    assert {"create_function", "update_function", "delete_function"} <= set(_actions(db))


def test_tier_update_is_saved(client, auth_headers, db, seeded_db, no_last_seen):
    tier_id = seeded_db["tier"].id
    resp = client.patch(f"/api/v1/tiers/{tier_id}", json={"name": "Neu"}, headers=auth_headers)
    assert resp.status_code == 200

    assert "update" in _actions(db)


def test_setting_change_is_saved(client, auth_headers, db, no_last_seen):
    resp = client.put(
        "/api/v1/settings/club.motto", json={"value": "Hallo"}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.get_json()

    assert "upsert" in _actions(db)
