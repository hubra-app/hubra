"""Tests for the access codes API (/api/v1/codes)."""

from hubra.core.models.audit import AuditEntry
from hubra.core.models.code import Code


def _create(client, auth_headers, **overrides):
    body = {"name": "Haustür", "code": "4711", "description": "Hinten"}
    body.update(overrides)
    return client.post("/api/v1/codes/", json=body, headers=auth_headers)


def test_create_stores_the_code_encrypted(client, auth_headers, db):
    resp = _create(client, auth_headers)
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["code"] == "4711"
    assert body["created_by"]

    stored = db.session.get(Code, body["id"])
    assert stored.code != "4711"
    assert stored.plain_code == "4711"


def test_create_is_audited_with_its_id(client, auth_headers, db):
    code_id = _create(client, auth_headers).get_json()["id"]

    entry = db.session.query(AuditEntry).filter_by(action="create_code").one()
    assert entry.target_id == code_id


def test_create_needs_name_and_code(client, auth_headers):
    assert _create(client, auth_headers, code="").status_code == 400
    assert _create(client, auth_headers, name="").status_code == 400
    assert _create(client, auth_headers, extra=1).status_code == 400


def test_list_get_update_delete(client, auth_headers, db):
    code_id = _create(client, auth_headers).get_json()["id"]
    _create(client, auth_headers, name="Archiv", code="0000")

    listed = client.get("/api/v1/codes/", headers=auth_headers).get_json()
    assert [c["name"] for c in listed] == ["Archiv", "Haustür"]

    resp = client.patch(
        f"/api/v1/codes/{code_id}",
        json={"code": "1234", "is_active": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["code"] == "1234"
    assert resp.get_json()["is_active"] is False

    got = client.get(f"/api/v1/codes/{code_id}", headers=auth_headers)
    assert got.get_json()["code"] == "1234"

    assert client.delete(f"/api/v1/codes/{code_id}", headers=auth_headers).status_code in (200, 204)
    assert client.get(f"/api/v1/codes/{code_id}", headers=auth_headers).status_code == 404
    entry = db.session.query(AuditEntry).filter_by(action="delete_code").one()
    assert (entry.target_id, entry.target_label) == (code_id, "Haustür")


def test_unknown_code_is_404(client, auth_headers):
    assert client.get("/api/v1/codes/999", headers=auth_headers).status_code == 404
    assert (
        client.patch("/api/v1/codes/999", json={"name": "x"}, headers=auth_headers).status_code
        == 404
    )


def test_codes_need_a_sign_in(client):
    # Without a sign-in there is no club, so the module check answers first.
    assert client.get("/api/v1/codes/").status_code in (401, 403)
