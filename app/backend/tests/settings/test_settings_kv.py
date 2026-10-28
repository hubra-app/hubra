"""Tests for the Settings KV API (M003/S01)."""

import pytest

from vollbuild.core.models.setting import Setting


def test_get_settings_returns_list(client, db, auth_headers):
    db.session.add(Setting(key="club.name", value="Test Club", namespace="club"))
    db.session.add(Setting(key="club.currency", value="CHF", namespace="club"))
    db.session.commit()

    resp = client.get("/api/v1/settings/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 2
    keys = [item["key"] for item in data]
    assert "club.name" in keys
    assert "club.currency" in keys


def test_put_settings_creates_entry(client, db, auth_headers):
    resp = client.put(
        "/api/v1/settings/club.name",
        json={"value": "Test Club"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    list_resp = client.get("/api/v1/settings/", headers=auth_headers)
    assert list_resp.status_code == 200
    items = list_resp.get_json()
    match = next((i for i in items if i["key"] == "club.name"), None)
    assert match is not None
    assert match["value"] == "Test Club"


def test_put_settings_with_validation_type(client, db, auth_headers):
    resp = client.put(
        "/api/v1/settings/mail.domain",
        json={"value": "example.org", "validation_type": "domain"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["key"] == "mail.domain"
    assert data["value"] == "example.org"
    assert data["validation_type"] == "domain"


def test_put_settings_rejects_invalid_email(client, db, auth_headers):
    resp = client.put(
        "/api/v1/settings/mail.smtp_user",
        json={"value": "not-an-email", "validation_type": "email"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_put_settings_accepts_valid_email(client, db, auth_headers):
    resp = client.put(
        "/api/v1/settings/mail.smtp_user",
        json={"value": "user@example.com", "validation_type": "email"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_put_settings_rejects_invalid_url(client, db, auth_headers):
    resp = client.put(
        "/api/v1/settings/club.website",
        json={"value": "not a url", "validation_type": "url"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_put_settings_accepts_valid_url(client, db, auth_headers):
    resp = client.put(
        "/api/v1/settings/club.website",
        json={"value": "https://example.com", "validation_type": "url"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_put_settings_rejects_invalid_port(client, db, auth_headers):
    resp = client.put(
        "/api/v1/settings/mail.smtp_port",
        json={"value": "999999", "validation_type": "port"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_put_settings_accepts_valid_port(client, db, auth_headers):
    resp = client.put(
        "/api/v1/settings/mail.smtp_port",
        json={"value": "587", "validation_type": "port"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_put_settings_updates_existing(client, db, auth_headers):
    db.session.add(Setting(key="club.name", value="Old", namespace="club"))
    db.session.commit()

    resp = client.put(
        "/api/v1/settings/club.name",
        json={"value": "New Name"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["value"] == "New Name"


def test_delete_required_setting_returns_409(client, db, auth_headers):
    db.session.add(
        Setting(
            key="system.initialized", value="true", namespace="system", required=True
        )
    )
    db.session.commit()

    resp = client.delete("/api/v1/settings/system.initialized", headers=auth_headers)
    assert resp.status_code == 409


def test_delete_optional_setting_returns_204(client, db, auth_headers):
    db.session.add(
        Setting(key="club.currency", value="CHF", namespace="club", required=False)
    )
    db.session.commit()

    resp = client.delete("/api/v1/settings/club.currency", headers=auth_headers)
    assert resp.status_code == 204


# ── Basic settings tests (from S01 foundation) ────────────────────────────────


def test_get_settings_returns_array(client, auth_headers):
    """GET /api/v1/settings returns a JSON array."""
    resp = client.get("/api/v1/settings/", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_get_settings_requires_auth(client):
    """GET /api/v1/settings without JWT returns 401."""
    resp = client.get("/api/v1/settings/")
    assert resp.status_code == 401


def test_put_setting_upserts(client, auth_headers, db):
    """PUT /api/v1/settings/<key> creates a new entry."""
    resp = client.put(
        "/api/v1/settings/test.key",
        json={"value": "hello"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["key"] == "test.key"
    assert data["value"] == "hello"


def test_put_setting_missing_value_returns_400(client, auth_headers):
    """PUT /api/v1/settings/<key> without 'value' field returns 400."""
    resp = client.put(
        "/api/v1/settings/test.key",
        json={"namespace": "general"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_delete_setting_not_found_returns_404(client, auth_headers):
    """DELETE /api/v1/settings/<key> for a non-existent key returns 404."""
    resp = client.delete("/api/v1/settings/nonexistent.key", headers=auth_headers)
    assert resp.status_code == 404


# ── Label field tests ──────────────────────────────────────────────────────────


def test_put_setting_with_label(client, auth_headers, db):
    """PUT with a label field persists it and returns it in the response."""
    resp = client.put(
        "/api/v1/settings/test.label",
        json={"value": "hello", "label": "Test Label"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["label"] == "Test Label"


def test_get_settings_returns_label(client, db, auth_headers):
    """GET /settings returns the label field for each setting."""
    db.session.add(
        Setting(key="test.labeled", value="x", namespace="test", label="My Label")
    )
    db.session.commit()

    resp = client.get("/api/v1/settings/", headers=auth_headers)
    assert resp.status_code == 200
    match = next((i for i in resp.get_json() if i["key"] == "test.labeled"), None)
    assert match is not None
    assert match["label"] == "My Label"


# ── Sensitive value masking tests ─────────────────────────────────────────────


def test_get_settings_masks_sensitive_value(client, db, auth_headers):
    """Sensitive settings have their value masked as '****' in GET responses."""
    db.session.add(
        Setting(
            key="test.secret",
            value="super-secret-password",
            namespace="test",
            sensitive=True,
        )
    )
    db.session.commit()

    resp = client.get("/api/v1/settings/", headers=auth_headers)
    assert resp.status_code == 200
    match = next((i for i in resp.get_json() if i["key"] == "test.secret"), None)
    assert match is not None
    assert match["value"] == "****"


def test_put_setting_response_masks_sensitive_value(client, db, auth_headers):
    """PUT response masks the value when sensitive=True."""
    db.session.add(
        Setting(
            key="test.secret2",
            value="old-secret",
            namespace="test",
            sensitive=True,
        )
    )
    db.session.commit()

    resp = client.put(
        "/api/v1/settings/test.secret2",
        json={"value": "new-secret"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["value"] == "****"


# ── QR-IBAN validation tests ──────────────────────────────────────────────────


def test_put_setting_accepts_valid_qr_iban(client, db, auth_headers):
    """A valid Swiss QR-IBAN passes qr_iban validation."""
    db.session.add(
        Setting(
            key="Club.Banking.Iban",
            value="",
            namespace="club",
            validation_type="qr_iban",
        )
    )
    db.session.commit()

    # CH73 QR-IBAN: IID=30, valid mod-97 checksum
    resp = client.put(
        "/api/v1/settings/Club.Banking.Iban",
        json={"value": "CH73 3000 0012 3456 7890 1"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_put_setting_accepts_any_ch_iban(client, db, auth_headers):
    """Any valid Swiss IBAN (any IID) passes validation."""
    db.session.add(
        Setting(
            key="Club.Banking.Iban",
            value="",
            namespace="club",
            validation_type="qr_iban",
        )
    )
    db.session.commit()

    # CH46 IBAN — valid checksum, IID is 99 (was rejected before IID check was relaxed)
    resp = client.put(
        "/api/v1/settings/Club.Banking.Iban",
        json={"value": "CH4699000012345678901"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_put_setting_rejects_non_swiss_iban(client, db, auth_headers):
    """A non-CH IBAN is rejected by qr_iban validation."""
    db.session.add(
        Setting(
            key="Club.Banking.Iban",
            value="",
            namespace="club",
            validation_type="qr_iban",
        )
    )
    db.session.commit()

    resp = client.put(
        "/api/v1/settings/Club.Banking.Iban",
        json={"value": "DE3107300000123456789"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_put_setting_rejects_qr_iban_bad_checksum(client, db, auth_headers):
    """An IBAN with wrong mod-97 checksum is rejected."""
    db.session.add(
        Setting(
            key="Club.Banking.Iban",
            value="",
            namespace="club",
            validation_type="qr_iban",
        )
    )
    db.session.commit()

    # Valid IID (30) but wrong checksum (should be 73, we use 71)
    resp = client.put(
        "/api/v1/settings/Club.Banking.Iban",
        json={"value": "CH7130000012345678901"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ── Namespace Permission Auto-Creation ──────────────────────────────────────


def test_put_creates_namespace_permissions(client, db, auth_headers):
    """PUT with a namespace creates settings.{ns}.{read,write,delete} Permission rows."""
    from vollbuild.core.models.role import Permission
    from sqlalchemy import select

    resp = client.put(
        "/api/v1/settings/custom.test",
        json={"value": "hello", "namespace": "custom"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    for action in ("read", "write", "delete"):
        perm = db.session.scalar(
            select(Permission).where(Permission.key == f"settings.custom.{action}")
        )
        assert perm is not None, f"Missing permission settings.custom.{action}"
        assert perm.resource == "custom"
        assert perm.action == action
        assert perm.blueprint == "settings"
        assert perm.is_active is True


def test_put_creates_key_permissions(client, db, auth_headers):
    """PUT creates per-key settings.{ns}.{key}.{read,write,delete} Permission rows."""
    from vollbuild.core.models.role import Permission
    from sqlalchemy import select

    resp = client.put(
        "/api/v1/settings/mykey",
        json={"value": "hello", "namespace": "custom"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    for action in ("read", "write", "delete"):
        perm = db.session.scalar(
            select(Permission).where(
                Permission.key == f"settings.custom.mykey.{action}"
            )
        )
        assert perm is not None, f"Missing permission settings.custom.mykey.{action}"
        assert perm.resource == "custom"
        assert perm.action == action
        assert perm.blueprint == "settings"


def test_put_does_not_duplicate_namespace_permissions(client, db, auth_headers):
    """PUT twice with the same namespace does not create duplicate Permission rows."""
    from vollbuild.core.models.role import Permission
    from sqlalchemy import select

    client.put(
        "/api/v1/settings/dup.first",
        json={"value": "a", "namespace": "dupns"},
        headers=auth_headers,
    )
    client.put(
        "/api/v1/settings/dup.second",
        json={"value": "b", "namespace": "dupns"},
        headers=auth_headers,
    )

    for action in ("read", "write", "delete"):
        results = db.session.scalars(
            select(Permission).where(Permission.key == f"settings.dupns.{action}")
        ).all()
        assert len(results) == 1, (
            f"Duplicate Permission row for settings.dupns.{action}"
        )


# ── Add-with-Namespace ──────────────────────────────────────────────────────


def test_put_with_namespace_persists(client, db, auth_headers):
    """PUT with a namespace field creates a setting in that namespace."""
    client.put(
        "/api/v1/settings/custom.key",
        json={"value": "val", "namespace": "myns"},
        headers=auth_headers,
    )

    resp = client.get("/api/v1/settings/", headers=auth_headers)
    match = next((i for i in resp.get_json() if i["key"] == "custom.key"), None)
    assert match is not None
    assert match["namespace"] == "myns"


def test_put_defaults_to_general_namespace(client, db, auth_headers):
    """PUT without a namespace defaults to 'general'."""
    client.put(
        "/api/v1/settings/general.key",
        json={"value": "val"},
        headers=auth_headers,
    )

    resp = client.get("/api/v1/settings/", headers=auth_headers)
    match = next((i for i in resp.get_json() if i["key"] == "general.key"), None)
    assert match is not None
    assert match["namespace"] == "general"


# ── Metadata Field Persistence ──────────────────────────────────────────────


def test_put_with_description(client, db, auth_headers):
    """PUT with description persists it."""
    resp = client.put(
        "/api/v1/settings/meta.desc",
        json={"value": "x", "description": "A description"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["description"] == "A description"


def test_put_with_sensitive_masks_value(client, db, auth_headers):
    """PUT with sensitive=True returns masked value and stores real value."""
    resp = client.put(
        "/api/v1/settings/meta.secret",
        json={"value": "s3cret", "sensitive": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["value"] == "****"

    # Verify real value is stored
    from vollbuild.core.models.setting import Setting

    setting = db.session.get(Setting, "meta.secret")
    assert setting is not None
    assert setting.value == "s3cret"


def test_put_with_required_prevents_delete(client, db, auth_headers):
    """PUT with required=True prevents deletion (409)."""
    client.put(
        "/api/v1/settings/meta.required",
        json={"value": "x", "required": True},
        headers=auth_headers,
    )
    resp = client.delete("/api/v1/settings/meta.required", headers=auth_headers)
    assert resp.status_code == 409


def test_put_with_restricted_prevents_modification(client, db, auth_headers):
    """PUT with restricted=True prevents subsequent PUT (409)."""
    client.put(
        "/api/v1/settings/meta.restricted",
        json={"value": "first", "restricted": True},
        headers=auth_headers,
    )
    resp = client.put(
        "/api/v1/settings/meta.restricted",
        json={"value": "second"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_put_updates_metadata_in_place(client, db, auth_headers):
    """PUT on an existing setting updates metadata fields."""
    client.put(
        "/api/v1/settings/meta.update",
        json={"value": "x", "label": "Old Label"},
        headers=auth_headers,
    )
    resp = client.put(
        "/api/v1/settings/meta.update",
        json={"value": "x", "label": "New Label"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["label"] == "New Label"


# ── Namespace-Scoped Permission Enforcement ─────────────────────────────────


def _make_role_and_member(db, tier, *, name, is_admin=False, permission_keys=None):
    """Create a role + member, optionally granting permission keys. Returns auth headers."""
    from vollbuild.extensions import db as _db
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.role import Role, RolePermission, Permission
    from vollbuild.core.models.user import User
    from sqlalchemy import select

    role = Role(name=name, is_default=False, is_admin=is_admin)
    _db.session.add(role)
    _db.session.flush()

    if permission_keys:
        for key in permission_keys:
            perm = _db.session.scalar(select(Permission).where(Permission.key == key))
            if perm is None:
                perm = Permission(
                    key=key,
                    display_name=key,
                    resource=key.split(".")[1] if "." in key else key,
                    action=key.split(".")[2]
                    if "." in key and len(key.split(".")) > 2
                    else key,
                    blueprint=key.split(".")[0] if "." in key else "",
                )
                _db.session.add(perm)
                _db.session.flush()
            _db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

    user = User(
        email=f"{name.lower()}@test.ch",
        first_name="Test",
        last_name=name,
    )
    user.set_password("password123")
    _db.session.add(user)
    _db.session.flush()

    member = Member(
        user_id=user.id,
        status="active",
        tier_id=tier.id,
    )
    member.roles = [role]
    _db.session.add(member)
    _db.session.commit()
    return member


def _login(client, email):
    """Log in and return auth headers (empty dict — cookies stored on client)."""
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    return {}


@pytest.fixture
def ns_perm_headers(request, client, seeded_db, app, db):
    """Fixture factory for non-admin headers with specific permission keys.

    Usage: pass ``permission_keys=[...]`` as an indirect param or use one of
    the named fixtures below.

    Must sync permissions first so base Permission rows exist.
    """
    from vollbuild.extensions import db as _db

    app.test_cli_runner().invoke(args=["sync-permissions"])
    keys = getattr(request, "param", None) or []
    _make_role_and_member(
        _db, seeded_db["tier"], name="NsPermMember", permission_keys=keys
    )
    return _login(client, "nspermmember@test.ch")


@pytest.fixture
def ns_read_headers(client, seeded_db, app, db):
    """Non-admin with only settings.custom.read."""
    from vollbuild.extensions import db as _db

    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        _db,
        seeded_db["tier"],
        name="NsRead",
        permission_keys=["settings.custom.read"],
    )
    return _login(client, "nsread@test.ch")


@pytest.fixture
def wildcard_read_headers(client, seeded_db, app, db):
    """Non-admin with settings.settings.read (wildcard)."""
    from vollbuild.extensions import db as _db

    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        _db,
        seeded_db["tier"],
        name="WildcardRead",
        permission_keys=["settings.settings.read"],
    )
    return _login(client, "wildcardread@test.ch")


@pytest.fixture
def ns_write_headers(client, seeded_db, app, db):
    """Non-admin with settings.custom.write."""
    from vollbuild.extensions import db as _db

    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        _db,
        seeded_db["tier"],
        name="NsWrite",
        permission_keys=["settings.custom.write"],
    )
    return _login(client, "nswrite@test.ch")


@pytest.fixture
def ns_delete_headers(client, seeded_db, app, db):
    """Non-admin with settings.custom.delete."""
    from vollbuild.extensions import db as _db

    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        _db,
        seeded_db["tier"],
        name="NsDelete",
        permission_keys=["settings.custom.delete"],
    )
    return _login(client, "nsdelete@test.ch")


def test_non_admin_with_namespace_read_sees_only_that_namespace(
    client,
    db,
    seeded_db,
    ns_read_headers,
):
    """Non-admin with settings.custom.read sees only custom-namepace settings in GET."""
    from vollbuild.core.models.setting import Setting

    db.session.add(Setting(key="general.a", value="1", namespace="general"))
    db.session.add(Setting(key="custom.a", value="2", namespace="custom"))
    db.session.add(Setting(key="other.b", value="3", namespace="other"))
    db.session.commit()

    resp = client.get("/api/v1/settings/", headers=ns_read_headers)
    assert resp.status_code == 200
    keys = [i["key"] for i in resp.get_json()]
    assert "custom.a" in keys
    assert "general.a" not in keys
    assert "other.b" not in keys


def test_non_admin_with_wildcard_read_sees_all(
    client,
    db,
    seeded_db,
    wildcard_read_headers,
):
    """Non-admin with settings.settings.read sees all settings regardless of namespace."""
    from vollbuild.core.models.setting import Setting

    db.session.add(Setting(key="general.a", value="1", namespace="general"))
    db.session.add(Setting(key="custom.b", value="2", namespace="custom"))
    db.session.commit()

    resp = client.get("/api/v1/settings/", headers=wildcard_read_headers)
    assert resp.status_code == 200
    keys = [i["key"] for i in resp.get_json()]
    assert "general.a" in keys
    assert "custom.b" in keys


def test_non_admin_without_write_gets_403_on_put(
    client,
    db,
    seeded_db,
    ns_read_headers,
):
    """Non-admin with only read permission gets 403 on PUT."""
    client.put(
        "/api/v1/settings/general.test",
        json={"value": "x"},
        headers=ns_read_headers,
    )
    # The route-level @permission_required("settings", "write") kicks in first
    # but our test user doesn't have any write permission, so 403.
    # Actually, the route-level decorator checks for "settings.settings.write"
    # (or whatever sync-permissions defined). Let's verify.
    resp = client.put(
        "/api/v1/settings/custom.test",
        json={"value": "x"},
        headers=ns_read_headers,
    )
    assert resp.status_code == 403


def test_non_admin_with_namespace_write_can_put(
    client,
    db,
    seeded_db,
    ns_write_headers,
):
    """Non-admin with settings.custom.write can PUT a setting in custom namespace."""
    resp = client.put(
        "/api/v1/settings/custom.test",
        json={"value": "hello", "namespace": "custom"},
        headers=ns_write_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["value"] == "hello"


def test_non_admin_with_namespace_write_cannot_put_other_namespace(
    client,
    db,
    seeded_db,
    ns_write_headers,
):
    """Non-admin with settings.custom.write gets 403 on a general setting."""
    resp = client.put(
        "/api/v1/settings/general.test",
        json={"value": "hello", "namespace": "general"},
        headers=ns_write_headers,
    )
    assert resp.status_code == 403


def test_non_admin_with_key_write_can_put_specific_key(
    client,
    db,
    seeded_db,
    app,
):
    """Non-admin with settings.custom.my.key.write can PUT that key but not another."""
    from vollbuild.extensions import db as _db

    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        _db,
        seeded_db["tier"],
        name="KeyWrite",
        permission_keys=["settings.custom.custom.specific.key.write"],
    )
    headers = _login(client, "keywrite@test.ch")

    resp = client.put(
        "/api/v1/settings/custom.specific.key",
        json={"value": "ok", "namespace": "custom"},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = client.put(
        "/api/v1/settings/custom.other.key",
        json={"value": "nok", "namespace": "custom"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_non_admin_without_delete_gets_403_on_delete(
    client,
    db,
    seeded_db,
    ns_read_headers,
):
    """Non-admin without delete permission gets 403 on DELETE."""
    from vollbuild.core.models.setting import Setting

    db.session.add(
        Setting(key="custom.todelete", value="x", namespace="custom", required=False)
    )
    db.session.commit()

    resp = client.delete("/api/v1/settings/custom.todelete", headers=ns_read_headers)
    assert resp.status_code == 403


def test_non_admin_with_namespace_delete_can_delete(
    client,
    db,
    seeded_db,
    ns_delete_headers,
):
    """Non-admin with settings.custom.delete can delete a custom setting."""
    from vollbuild.core.models.setting import Setting

    db.session.add(
        Setting(key="custom.todelete", value="x", namespace="custom", required=False)
    )
    db.session.commit()

    resp = client.delete("/api/v1/settings/custom.todelete", headers=ns_delete_headers)
    assert resp.status_code == 204


def test_non_admin_read_key_level_only_sees_that_key(
    client,
    db,
    seeded_db,
    app,
):
    """Non-admin with per-key read permission sees only that key's setting."""
    from vollbuild.extensions import db as _db
    from vollbuild.core.models.setting import Setting

    db.session.add(Setting(key="custom.my.visible", value="1", namespace="custom"))
    db.session.add(Setting(key="custom.my.hidden", value="2", namespace="custom"))
    db.session.commit()

    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        _db,
        seeded_db["tier"],
        name="KeyRead",
        permission_keys=["settings.custom.custom.my.visible.read"],
    )
    headers = _login(client, "keyread@test.ch")

    resp = client.get("/api/v1/settings/", headers=headers)
    assert resp.status_code == 200
    keys = [i["key"] for i in resp.get_json()]
    assert "custom.my.visible" in keys
    assert "custom.my.hidden" not in keys
