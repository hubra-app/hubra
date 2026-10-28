"""Tests for ExternalParty CRUD (/api/v1/finance/external-parties)."""


def _party_payload(**overrides):
    payload = {
        "name": "Acme Corp",
        "email": "billing@acme.example",
        "address_street": "Bahnhofstrasse",
        "address_house_no": "42",
        "address_postal_code": "8001",
        "address_city": "Zürich",
        "address_country": "CH",
    }
    payload.update(overrides)
    return payload


def test_list_external_parties_empty(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/finance/external-parties", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_external_party(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/finance/external-parties",
        json=_party_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Acme Corp"
    assert body["email"] == "billing@acme.example"
    assert body["address_city"] == "Zürich"
    assert "id" in body


def test_create_external_party_minimal(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/finance/external-parties",
        json={"name": "Minimal Party"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Minimal Party"
    assert body["email"] is None
    assert body["address_country"] == "CH"


def test_create_external_party_missing_name(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/finance/external-parties",
        json={"email": "no@name.example"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_update_external_party(client, auth_headers, seeded_db):
    created = client.post(
        "/api/v1/finance/external-parties",
        json=_party_payload(),
        headers=auth_headers,
    )
    party_id = created.get_json()["id"]

    resp = client.patch(
        f"/api/v1/finance/external-parties/{party_id}",
        json={"name": "Acme AG", "email": "new@acme.example"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == "Acme AG"
    assert body["email"] == "new@acme.example"


def test_update_external_party_not_found(client, auth_headers, seeded_db):
    resp = client.patch(
        "/api/v1/finance/external-parties/99999",
        json={"name": "Ghost"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_delete_external_party(client, auth_headers, seeded_db):
    created = client.post(
        "/api/v1/finance/external-parties",
        json=_party_payload(),
        headers=auth_headers,
    )
    party_id = created.get_json()["id"]

    resp = client.delete(
        f"/api/v1/finance/external-parties/{party_id}", headers=auth_headers
    )
    assert resp.status_code == 204

    resp = client.get("/api/v1/finance/external-parties", headers=auth_headers)
    assert all(p["id"] != party_id for p in resp.get_json())


def test_delete_external_party_not_found(client, auth_headers, seeded_db):
    resp = client.delete("/api/v1/finance/external-parties/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_list_external_parties_search(client, auth_headers, seeded_db):
    client.post(
        "/api/v1/finance/external-parties",
        json=_party_payload(name="Zenith GmbH"),
        headers=auth_headers,
    )
    client.post(
        "/api/v1/finance/external-parties",
        json=_party_payload(name="Acme Corp"),
        headers=auth_headers,
    )

    resp = client.get(
        "/api/v1/finance/external-parties?search=Acme", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["name"] == "Acme Corp"
