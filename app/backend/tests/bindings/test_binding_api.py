"""Tests for the Bindings API — key CRUD, binding CRUD, toggle, registry, validators."""

from hubra.core.models.internal_key import InternalKey
from hubra.core.models.member import Member
from hubra.core.models.user import User


def _make_member(db, name="Test Member", email="test@example.ch"):
    parts = name.split()
    user = User(email=email, first_name=parts[0], last_name=parts[-1])
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    m = Member(user_id=user.id)
    db.session.add(m)
    db.session.flush()
    return m


def _make_key(db, key="test.key", **kwargs):
    ik = InternalKey(key=key, **kwargs)
    db.session.add(ik)
    db.session.flush()
    return ik


# ── Internal Keys CRUD ────────────────────────────────────────────────────────


def test_list_keys_empty(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/bindings/keys", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_key(client, seeded_db, auth_headers):
    resp = client.post(
        "/api/v1/bindings/keys",
        headers=auth_headers,
        json={"key": "test.new", "label": "Test Key"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["key"] == "test.new"
    assert body["label"] == "Test Key"
    assert body["allow_multiple"] is False
    assert body["is_protected"] is False
    assert body["has_value"] is False
    assert body["masked_value"] is None


def test_create_key_duplicate(client, seeded_db, auth_headers, db):
    _make_key(db, "test.dup")
    db.session.commit()
    resp = client.post(
        "/api/v1/bindings/keys",
        headers=auth_headers,
        json={"key": "test.dup"},
    )
    assert resp.status_code == 409


def test_create_array_key(client, seeded_db, auth_headers):
    resp = client.post(
        "/api/v1/bindings/keys",
        headers=auth_headers,
        json={"key": "test.array", "allow_multiple": True},
    )
    assert resp.status_code == 201
    assert resp.get_json()["allow_multiple"] is True


def test_update_key_label(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.update", label="Old")
    db.session.commit()
    resp = client.put(
        f"/api/v1/bindings/keys/{ik.id}",
        headers=auth_headers,
        json={"label": "New"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["label"] == "New"


def test_delete_key(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.delete")
    db.session.commit()
    resp = client.delete(f"/api/v1/bindings/keys/{ik.id}", headers=auth_headers)
    assert resp.status_code == 204


def test_delete_protected_key_rejected(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.protected", is_protected=True)
    db.session.commit()
    resp = client.delete(f"/api/v1/bindings/keys/{ik.id}", headers=auth_headers)
    assert resp.status_code == 409


def test_delete_key_with_bindings_rejected(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.has_bindings")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "name",
            "key_id": ik.id,
        },
    )
    resp = client.delete(f"/api/v1/bindings/keys/{ik.id}", headers=auth_headers)
    assert resp.status_code == 409


def test_key_value_masked(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.masked")
    ik.value = "encrypted_foo"
    db.session.commit()
    resp = client.get("/api/v1/bindings/keys", headers=auth_headers)
    body = resp.get_json()
    match = next(k for k in body if k["key"] == "test.masked")
    assert match["has_value"] is True
    assert match["masked_value"] is not None
    assert match["masked_value"] != "encrypted_foo"


# ── Bindings CRUD ─────────────────────────────────────────────────────────────


def test_list_bindings_empty(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/bindings/", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_binding(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.binding")
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
            "validator": "none",
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["type"] == "member"
    assert body["source_attribute"] == "name"
    assert body["key_id"] == ik.id
    assert body["enabled"] is True
    assert body["validation_status"] == "ok"
    assert body["source_label"] is not None


def test_create_binding_invalid_attribute(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.bad_attr")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    resp = client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "nonexistent_attr",
            "key_id": ik.id,
        },
    )
    assert resp.status_code == 400


def test_create_binding_scalar_conflict(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.scalar_conflict")
    m1 = _make_member(db, "Alice", "alice@example.ch")
    m2 = _make_member(db, "Bob", "bob@example.ch")
    db.session.commit()
    client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m1.id),
            "source_attribute": "name",
            "key_id": ik.id,
        },
    )
    resp = client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m2.id),
            "source_attribute": "name",
            "key_id": ik.id,
        },
    )
    assert resp.status_code == 409


def test_toggle_binding(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.toggle")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    create_resp = client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "name",
            "key_id": ik.id,
        },
    )
    binding_id = create_resp.get_json()["id"]
    resp = client.post(
        f"/api/v1/bindings/{binding_id}/toggle",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert resp.status_code == 200
    assert resp.get_json()["enabled"] is False


def test_delete_binding(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.del_binding")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    create_resp = client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "name",
            "key_id": ik.id,
        },
    )
    binding_id = create_resp.get_json()["id"]
    resp = client.delete(f"/api/v1/bindings/{binding_id}", headers=auth_headers)
    assert resp.status_code == 204


def test_update_binding_validator(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.update_binding")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    create_resp = client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "name",
            "key_id": ik.id,
        },
    )
    binding_id = create_resp.get_json()["id"]
    resp = client.put(
        f"/api/v1/bindings/{binding_id}",
        headers=auth_headers,
        json={"validator": "non_empty"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["validator"] == "non_empty"


def test_update_binding_protection(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.protect_binding")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    binding_id = client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "name",
            "key_id": ik.id,
        },
    ).get_json()["id"]

    resp = client.put(
        f"/api/v1/bindings/{binding_id}",
        headers=auth_headers,
        json={"is_protected": True},
    )
    assert resp.status_code == 200
    assert resp.get_json()["is_protected"] is True
    assert client.delete(f"/api/v1/bindings/{binding_id}", headers=auth_headers).status_code == 409

    client.put(
        f"/api/v1/bindings/{binding_id}",
        headers=auth_headers,
        json={"is_protected": False},
    )
    assert client.delete(f"/api/v1/bindings/{binding_id}", headers=auth_headers).status_code in (200, 204)


def test_list_bindings_filtered_by_key(client, seeded_db, auth_headers, db):
    ik1 = _make_key(db, "test.filter1")
    ik2 = _make_key(db, "test.filter2")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "name",
            "key_id": ik1.id,
        },
    )
    client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "primary_mail_address",
            "key_id": ik2.id,
        },
    )
    resp = client.get(f"/api/v1/bindings/?key_id={ik1.id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["key_id"] == ik1.id


# ── Registry & Validators ────────────────────────────────────────────────────


def test_get_registry(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/bindings/registry", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    types = [r["type"] for r in body]
    assert "member" in types
    assert "group" in types
    assert "function" in types
    assert "setting" in types
    assert "mail_address" in types

    member_entry = next(r for r in body if r["type"] == "member")
    attr_names = [a["name"] for a in member_entry["attributes"]]
    assert "name" in attr_names
    assert "primary_mail_address" in attr_names


def test_get_validators(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/bindings/validators", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body, list)
    assert "email" in body
    assert "none" not in body
    assert "non_empty" in body


# ── Sources ───────────────────────────────────────────────────────────────────


def test_get_sources_member(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/bindings/sources?type=member", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["id"] == str(seeded_db["admin"].id)
    assert body[0]["label"] == "Test Admin"
    assert "name" in body[0]["preview"]
    assert "email" in body[0]["preview"]


def test_get_sources_group_empty(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/bindings/sources?type=group", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_get_sources_invalid_type(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/bindings/sources?type=bogus", headers=auth_headers)
    assert resp.status_code == 400


def test_get_sources_missing_type(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/bindings/sources", headers=auth_headers)
    assert resp.status_code == 400


# ── Preview endpoint ──────────────────────────────────────────────────────────


def test_preview_non_sensitive(client, seeded_db, auth_headers):
    """Member name attribute → plain text, not masked."""
    admin = seeded_db["admin"]
    resp = client.get(
        f"/api/v1/bindings/preview?type=member&source_id={admin.id}&source_attribute=name",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["value"] == "Test Admin"
    assert body["masked"] is False
    assert body["sensitive"] is False


def test_preview_sensitive_setting(client, seeded_db, auth_headers, db):
    """Sensitive setting value → masked."""
    from hubra.core.models.setting import Setting

    db.session.add(Setting(key="test.secret", value="my-secret-value", sensitive=True))
    db.session.commit()
    resp = client.get(
        "/api/v1/bindings/preview?type=setting&source_id=test.secret&source_attribute=value",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["value"] != "my-secret-value"
    assert body["masked"] is True
    assert body["sensitive"] is True


def test_preview_non_sensitive_setting(client, seeded_db, auth_headers, db):
    """Non-sensitive setting value → plain text."""
    from hubra.core.models.setting import Setting

    db.session.add(Setting(key="test.public", value="hello-world", sensitive=False))
    db.session.commit()
    resp = client.get(
        "/api/v1/bindings/preview?type=setting&source_id=test.public&source_attribute=value",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["value"] == "hello-world"
    assert body["masked"] is False
    assert body["sensitive"] is False


def test_preview_null_value(client, seeded_db, auth_headers, db):
    """Attribute that resolves to None → value: null."""

    m = _make_member(db, "No Public", "nopub@example.ch")
    m.public_email = None
    db.session.commit()
    resp = client.get(
        f"/api/v1/bindings/preview?type=member&source_id={m.id}&source_attribute=primary_mail_address",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["value"] is None
    assert body["masked"] is False


def test_preview_invalid_type(client, seeded_db, auth_headers):
    resp = client.get(
        "/api/v1/bindings/preview?type=bogus&source_id=1&source_attribute=name",
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_preview_invalid_attribute(client, seeded_db, auth_headers):
    admin = seeded_db["admin"]
    resp = client.get(
        f"/api/v1/bindings/preview?type=member&source_id={admin.id}&source_attribute=nonexistent",
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_preview_missing_source_id(client, seeded_db, auth_headers):
    resp = client.get(
        "/api/v1/bindings/preview?type=member&source_attribute=name",
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ── Sensitivity-aware binding serialization ───────────────────────────────────


def test_binding_resolved_value_non_sensitive(client, seeded_db, auth_headers, db):
    """Binding with name attribute → resolved_value is plain text."""
    ik = _make_key(db, "test.resolved_plain")
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
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["resolved_value"] == "Alice Smith"
    assert body["resolved_sensitive"] is False


def test_binding_resolved_value_sensitive_setting(client, seeded_db, auth_headers, db):
    """Binding with sensitive setting → resolved_value is masked."""
    from hubra.core.models.setting import Setting

    db.session.add(
        Setting(key="test.binding_secret", value="hidden-val", sensitive=True)
    )
    ik = _make_key(db, "test.resolved_masked")
    db.session.commit()
    resp = client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "setting",
            "source_id": "test.binding_secret",
            "source_attribute": "value",
            "key_id": ik.id,
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["resolved_value"] != "hidden-val"
    assert body["resolved_sensitive"] is True


# ── Sensitivity-aware key serialization ───────────────────────────────────────


def test_key_value_non_sensitive(client, seeded_db, auth_headers, db):
    """Key with non-sensitive enabled binding → masked_value is plain text."""
    ik = _make_key(db, "test.key_plain")
    m = _make_member(db, "Bob Jones", "bob@example.ch")
    db.session.commit()
    client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(m.id),
            "source_attribute": "name",
            "key_id": ik.id,
        },
    )
    resp = client.get("/api/v1/bindings/keys", headers=auth_headers)
    body = resp.get_json()
    match = next(k for k in body if k["key"] == "test.key_plain")
    assert match["has_value"] is True
    assert match["masked_value"] == "Bob Jones"
    assert match["sensitive"] is False


def test_key_value_sensitive(client, seeded_db, auth_headers, db):
    """Key with sensitive enabled binding → masked_value is _MASK."""
    from hubra.core.models.setting import Setting

    db.session.add(Setting(key="test.key_secret", value="secret-data", sensitive=True))
    ik = _make_key(db, "test.key_masked")
    db.session.commit()
    client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "setting",
            "source_id": "test.key_secret",
            "source_attribute": "value",
            "key_id": ik.id,
        },
    )
    resp = client.get("/api/v1/bindings/keys", headers=auth_headers)
    body = resp.get_json()
    match = next(k for k in body if k["key"] == "test.key_masked")
    assert match["has_value"] is True
    assert match["masked_value"] != "secret-data"
    assert match["sensitive"] is True


def test_key_value_no_bindings_masked(client, seeded_db, auth_headers, db):
    """Key with value but no bindings → masked (conservative default)."""
    ik = _make_key(db, "test.key_nobindings")
    ik.value = "encrypted_data"
    db.session.commit()
    resp = client.get("/api/v1/bindings/keys", headers=auth_headers)
    body = resp.get_json()
    match = next(k for k in body if k["key"] == "test.key_nobindings")
    assert match["has_value"] is True
    assert match["masked_value"] != "encrypted_data"
    assert match["sensitive"] is True


# ── Projected MMA fallbacks ───────────────────────────────────────────────────


def test_preview_group_primary_alias_no_mma(client, seeded_db, auth_headers, db):
    """Group without MMA → projected address from name."""
    from hubra.core.models.group import Group
    from hubra.core.models.setting import Setting

    db.session.add(Setting(key="mail.domain", value="test.ch"))
    g = Group(name="TestGroup")
    db.session.add(g)
    db.session.flush()
    db.session.commit()
    resp = client.get(
        f"/api/v1/bindings/preview?type=group&source_id={g.id}&source_attribute=primary_alias",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["value"] == "testgroup@test.ch"
    assert body["sensitive"] is False


def test_preview_function_mma_local_part_no_mma(client, seeded_db, auth_headers, db):
    """Function without MMA → projected local_part."""
    from hubra.core.models.function import Function
    from hubra.core.models.setting import Setting

    db.session.add(Setting(key="mail.domain", value="test.ch"))
    fn = Function(name="Kassier")
    db.session.add(fn)
    db.session.flush()
    db.session.commit()
    resp = client.get(
        f"/api/v1/bindings/preview?type=function&source_id={fn.id}&source_attribute=mma.local_part",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["value"] == "kassier"


def _bind(client, auth_headers, member, key, enabled=True):
    return client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": str(member.id),
            "source_attribute": "name",
            "key_id": key.id,
            "enabled": enabled,
        },
    )


def test_update_cannot_enable_onto_taken_scalar_key(
    client, seeded_db, auth_headers, db
):
    ik = _make_key(db, "test.put_enable")
    m1 = _make_member(db, "Alice", "alice@example.ch")
    m2 = _make_member(db, "Bob", "bob@example.ch")
    db.session.commit()
    assert _bind(client, auth_headers, m1, ik).status_code == 201
    second = _bind(client, auth_headers, m2, ik, enabled=False)
    assert second.status_code == 201

    resp = client.put(
        f"/api/v1/bindings/{second.get_json()['id']}",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "SCALAR_KEY_OCCUPIED"


def test_update_disable_clears_the_key(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.put_disable")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    binding_id = _bind(client, auth_headers, m, ik).get_json()["id"]
    db.session.refresh(ik)
    assert ik.value

    resp = client.put(
        f"/api/v1/bindings/{binding_id}", headers=auth_headers, json={"enabled": False}
    )
    assert resp.status_code == 200
    db.session.refresh(ik)
    assert not ik.value


def test_update_checks_the_attribute_alone(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.put_attr")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    db.session.commit()
    binding_id = _bind(client, auth_headers, m, ik).get_json()["id"]

    for body in ({"source_attribute": "not_an_attribute"}, {"source_id": "abc"}):
        resp = client.put(
            f"/api/v1/bindings/{binding_id}", headers=auth_headers, json=body
        )
        assert resp.status_code == 400, body


def test_non_numeric_source_id_is_a_400(client, seeded_db, auth_headers, db):
    ik = _make_key(db, "test.bad_source")
    db.session.commit()
    resp = client.post(
        "/api/v1/bindings/",
        headers=auth_headers,
        json={
            "type": "member",
            "source_id": "abc",
            "source_attribute": "name",
            "key_id": ik.id,
        },
    )
    assert resp.status_code == 400
    resp = client.get(
        "/api/v1/bindings/preview?type=member&source_id=abc&source_attribute=name",
        headers=auth_headers,
    )
    assert resp.status_code == 400
