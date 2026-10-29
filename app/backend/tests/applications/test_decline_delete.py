"""Declining or deleting an application leaves a trace in the audit log."""

from __future__ import annotations

import pytest

from hubra.api.applications.services import ApplicationsService
from hubra.core.models.application import Application
from hubra.core.models.audit import AuditEntry


@pytest.fixture
def application(db, seeded_db):
    ApplicationsService.submit("Eva", "Muster", "eva@example.ch")
    db.session.commit()
    return db.session.query(Application).one()


def test_an_application_can_be_read(client, auth_headers, application):
    resp = client.get(f"/api/v1/applications/{application.id}", headers=auth_headers)
    assert resp.status_code == 200 and resp.get_json()["email"] == "eva@example.ch"
    assert (
        client.get("/api/v1/applications/999", headers=auth_headers).status_code == 404
    )


@pytest.mark.parametrize(
    "method, path, action",
    [
        ("post", "/decline", "decline_application"),
        ("delete", "", "delete_application"),
    ],
)
def test_declining_and_deleting_are_audited(
    client, auth_headers, db, seeded_db, application, method, path, action
):
    url = f"/api/v1/applications/{application.id}{path}"
    resp = getattr(client, method)(url, headers=auth_headers)
    assert resp.status_code == 204
    assert db.session.query(Application).count() == 0
    entry = db.session.query(AuditEntry).filter_by(action=action).one()
    assert entry.actor_id == seeded_db["admin"].id
    assert entry.target_label == "Eva Muster"
    assert getattr(client, method)(url, headers=auth_headers).status_code == 404
