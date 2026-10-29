"""Changing an internal key: a protected key or one in use keeps its shape."""

from tests.bindings.test_binding_api import _make_key, _make_member

URL = "/api/v1/bindings/keys"


def test_label_and_protection_can_change(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "door.code")
    db.session.commit()
    resp = client.put(
        f"{URL}/{ik.id}",
        json={"label": "Türcode", "is_protected": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(ik)
    assert ik.label == "Türcode" and ik.is_protected is True


def test_a_protected_key_keeps_allow_multiple(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "door.code", is_protected=True)
    db.session.commit()
    resp = client.put(
        f"{URL}/{ik.id}", json={"allow_multiple": True}, headers=auth_headers
    )
    assert resp.status_code == 409 and resp.get_json()["error"] == "PROTECTED"
    # Sending the value it already has is fine (the edit form does).
    resp = client.put(
        f"{URL}/{ik.id}", json={"allow_multiple": False}, headers=auth_headers
    )
    assert resp.status_code == 200


def test_a_key_in_use_keeps_allow_multiple(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "member.name")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    resp = client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "name",
            "key_id": ik.id,
        },
    )
    assert resp.status_code == 201, resp.get_json()
    resp = client.put(
        f"{URL}/{ik.id}", json={"allow_multiple": True}, headers=auth_headers
    )
    assert resp.status_code == 409 and resp.get_json()["error"] == "CONFLICT"


def test_unknown_key(client, seeded_db, auth_headers):
    assert (
        client.put(f"{URL}/999", json={"label": "x"}, headers=auth_headers).status_code
        == 404
    )
