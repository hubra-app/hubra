"""Tests for new mail features: toggle, prefix change, MailAlias CRUD, system addresses."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from sqlalchemy import select

from vollbuild.core.models.group import Group
from vollbuild.core.models.managed_mail import ManagedMailAddress


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_group(db, *, name: str = "Test Group", **overrides) -> Group:
    g = Group(name=name, **overrides)
    db.session.add(g)
    db.session.commit()
    return g


def _make_mma(
    db, *, address: str, address_type: str = "alias", **overrides
) -> ManagedMailAddress:
    addr = ManagedMailAddress(
        address=address,
        address_type=address_type,
        **overrides,
    )
    db.session.add(addr)
    db.session.commit()
    return addr


# ── PATCH /mail/groups/<id>/toggle ────────────────────────────────────────────


def test_toggle_group_mail_disable(client, db, seeded_db, auth_headers):
    """PATCH /mail/groups/<id>/toggle disables mail via ensure_absent."""
    group = _make_group(db, name="ToggleDisableGroup")
    addr = _make_mma(
        db,
        address="toggledisable@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        is_enabled=True,
        kind="group",
        enabled=True,
        wildduck_id="wd-user-001",
        provisioning_status="provisioned",
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = {"id": "wd-user-001"}
    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.patch(
            f"/api/v1/mail/groups/{group.id}/toggle",
            json={"enabled": False},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["isEnabled"] is False

    db.session.refresh(addr)
    assert addr.is_enabled is False
    assert addr.enabled is False
    mock_wd.safe_delete_user.assert_called_once_with("wd-user-001")


def test_toggle_group_mail_enable(client, db, seeded_db, auth_headers):
    """PATCH /mail/groups/<id>/toggle enables mail via ensure_mailbox+ensure_forwarding."""
    group = _make_group(db, name="ToggleEnableGroup")
    addr = _make_mma(
        db,
        address="toggleenable@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        is_enabled=False,
        kind="group",
        enabled=False,
        provisioning_status="pending",
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = None
    mock_wd.create_user.return_value = {"id": "wd-user-002"}
    mock_wd.list_user_addresses.return_value = {"results": []}
    mock_wd.add_address_to_user.return_value = {"id": "addr-001"}
    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        with patch(
            "vollbuild.core.services.mail_provisioning._resolve_group_member_targets",
            return_value=["member@example.ch"],
        ):
            resp = client.patch(
                f"/api/v1/mail/groups/{group.id}/toggle",
                json={"enabled": True},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["isEnabled"] is True

    db.session.refresh(addr)
    assert addr.is_enabled is True
    assert addr.enabled is True
    mock_wd.create_user.assert_called_once()
    mock_wd.update_user_attributes.assert_called_once()


def test_toggle_group_mail_not_found(client, db, seeded_db, auth_headers):
    """PATCH /mail/groups/9999/toggle returns 404."""
    resp = client.patch(
        "/api/v1/mail/groups/9999/toggle",
        json={"enabled": True},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_toggle_group_mail_missing_enabled(client, db, seeded_db, auth_headers):
    """PATCH /mail/groups/<id>/toggle returns 400 without enabled field."""
    group = _make_group(db, name="NoEnabledGroup")
    _make_mma(
        db,
        address="noenabled@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        kind="group",
    )

    resp = client.patch(
        f"/api/v1/mail/groups/{group.id}/toggle",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ── PATCH /mail/groups/<id>/prefix ────────────────────────────────────────────


def test_change_group_mail_prefix(client, db, seeded_db, auth_headers):
    """PATCH /mail/groups/<id>/prefix changes the mail prefix for a group mailbox."""
    group = _make_group(db, name="PrefixChangeGroup")
    addr = _make_mma(
        db,
        address="oldprefix@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        is_enabled=True,
        kind="group",
        wildduck_id="wd-user-old",
        provisioning_status="provisioned",
        mail_prefix="oldprefix",
        local_part="oldprefix",
        domain="club.ch",
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = None
    mock_wd.create_user.return_value = {"id": "wd-user-new"}
    mock_wd.list_user_addresses.return_value = {"results": []}
    mock_wd.add_address_to_user.return_value = {"id": "addr-new"}
    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        with patch(
            "vollbuild.core.services.mail_provisioning._resolve_group_member_targets",
            return_value=["target@example.ch"],
        ):
            with patch(
                "vollbuild.api.settings.service.SettingsService.get",
                return_value="club.ch",
            ):
                resp = client.patch(
                    f"/api/v1/mail/groups/{group.id}/prefix",
                    json={"prefix": "newprefix"},
                    headers=auth_headers,
                )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["address"] == "newprefix@club.ch"

    db.session.refresh(addr)
    assert addr.address == "newprefix@club.ch"
    assert addr.mail_prefix == "newprefix"
    assert addr.local_part == "newprefix"
    mock_wd.safe_delete_user.assert_called_once_with("wd-user-old")
    mock_wd.create_user.assert_called_once()


def test_change_group_mail_prefix_normalizes(client, db, seeded_db, auth_headers):
    """PATCH /mail/groups/<id>/prefix normalizes invalid-looking prefix via resolve_local_part."""
    group = _make_group(db, name="InvalidPrefixGroup")
    _make_mma(
        db,
        address="valid@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        kind="group",
        local_part="valid",
        domain="club.ch",
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = None
    mock_wd.create_user.return_value = {"id": "wd-normalized"}
    mock_wd.list_user_addresses.return_value = {"results": []}
    with patch(
        "vollbuild.api.settings.service.SettingsService.get",
        return_value="club.ch",
    ):
        with patch(
            "vollbuild.core.services.mail_provisioning.try_get_client",
            return_value=mock_wd,
        ):
            with patch(
                "vollbuild.core.services.mail_provisioning._resolve_group_member_targets",
                return_value=[],
            ):
                resp = client.patch(
                    f"/api/v1/mail/groups/{group.id}/prefix",
                    json={"prefix": "INVALID UPPER!"},
                    headers=auth_headers,
                )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["address"] == "invalid.upper@club.ch"


def test_change_group_mail_prefix_duplicate(client, db, seeded_db, auth_headers):
    """PATCH /mail/groups/<id>/prefix returns 400 when address already exists."""
    group = _make_group(db, name="DupPrefixGroup")
    _make_mma(
        db,
        address="first@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        kind="group",
        local_part="first",
        domain="club.ch",
    )
    _make_mma(db, address="taken@club.ch", local_part="taken", domain="club.ch")

    with patch(
        "vollbuild.api.settings.service.SettingsService.get",
        return_value="club.ch",
    ):
        resp = client.patch(
            f"/api/v1/mail/groups/{group.id}/prefix",
            json={"prefix": "taken"},
            headers=auth_headers,
        )
    assert resp.status_code == 400


# ── Additional group alias CRUD (MMA-based) ────────────────────────────────────


def test_create_group_alias(client, db, seeded_db, auth_headers):
    """POST /mail/groups/<id>/aliases creates an additional alias MMA."""
    group = _make_group(db, name="AliasCreateGroup")
    _make_mma(
        db,
        address="main@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        kind="group",
    )

    with patch(
        "vollbuild.api.settings.service.SettingsService.get",
        return_value="club.ch",
    ):
        with patch(
            "vollbuild.core.services.wildduck.try_get_client", return_value=MagicMock()
        ):
            resp = client.post(
                f"/api/v1/mail/groups/{group.id}/aliases",
                json={"prefix": "extra"},
                headers=auth_headers,
            )

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["address"] == "extra@club.ch"
    assert body["kind"] == "group"
    assert body["mailboxBacked"] is False

    alias = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == "extra@club.ch")
    )
    assert alias is not None
    assert alias.owner_id == group.id
    assert alias.owner_type == "group"
    assert alias.address_type == "alias"
    assert alias.kind == "group"


def test_list_group_aliases(client, db, seeded_db, auth_headers):
    """GET /mail/groups/<id>/aliases lists additional alias MMAs."""
    group = _make_group(db, name="AliasListGroup")
    _make_mma(
        db,
        address="listmain@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        kind="group",
    )
    _make_mma(
        db,
        address="listextra1@club.ch",
        address_type="alias",
        owner_type="group",
        owner_id=group.id,
        kind="group",
        fixed_forward_targets=json.dumps(["listmain@club.ch"]),
    )
    _make_mma(
        db,
        address="listextra2@club.ch",
        address_type="alias",
        owner_type="group",
        owner_id=group.id,
        kind="group",
        fixed_forward_targets=json.dumps(["listmain@club.ch"]),
    )

    resp = client.get(
        f"/api/v1/mail/groups/{group.id}/aliases",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 2
    addresses = [d["address"] for d in data]
    assert "listextra1@club.ch" in addresses
    assert "listextra2@club.ch" in addresses


def test_delete_group_alias(client, db, seeded_db, auth_headers):
    """DELETE /mail/groups/<id>/aliases/<alias_id> removes an additional alias MMA."""
    group = _make_group(db, name="AliasDeleteGroup")
    _make_mma(
        db,
        address="delmain@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        kind="group",
    )
    alias = _make_mma(
        db,
        address="delextra@club.ch",
        address_type="alias",
        owner_type="group",
        owner_id=group.id,
        kind="group",
        wildduck_id="wd-del-001",
        fixed_forward_targets=json.dumps(["delmain@club.ch"]),
    )

    mock_wd = MagicMock()
    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.delete(
            f"/api/v1/mail/groups/{group.id}/aliases/{alias.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 204
    assert db.session.get(ManagedMailAddress, alias.id) is None
    mock_wd.safe_delete_address.assert_called_once_with("wd-del-001")


def test_delete_group_alias_of_protected_parent(client, db, seeded_db, auth_headers):
    """Additional aliases are deletable even when parent is protected."""
    group = _make_group(db, name="ProtectedParentGroup")
    _make_mma(
        db,
        address="protected@club.ch",
        address_type="mailbox",
        owner_type="group",
        owner_id=group.id,
        kind="group",
        is_protected=True,
    )
    alias = _make_mma(
        db,
        address="protected-extra@club.ch",
        address_type="alias",
        owner_type="group",
        owner_id=group.id,
        kind="group",
        fixed_forward_targets=json.dumps(["protected@club.ch"]),
    )

    mock_wd = MagicMock()
    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.delete(
            f"/api/v1/mail/groups/{group.id}/aliases/{alias.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 204
    assert db.session.get(ManagedMailAddress, alias.id) is None


# ── System addresses ──────────────────────────────────────────────────────────


def test_list_system_addresses(client, db, seeded_db, auth_headers):
    """GET /mail/system-addresses returns only is_system addresses."""
    _make_mma(
        db,
        address="sysinfo@club.ch",
        address_type="alias",
        is_system=True,
        display_name="Info",
    )
    _make_mma(
        db,
        address="nonsys@club.ch",
        address_type="alias",
        is_system=False,
    )

    resp = client.get("/api/v1/mail/system-addresses", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["address"] == "sysinfo@club.ch"
    assert data[0]["isSystem"] is True
    assert data[0]["displayName"] == "Info"


def test_create_system_address(client, db, seeded_db, auth_headers):
    """POST /mail/system-addresses creates a new system address."""
    mock_wd = MagicMock()
    mock_wd.create_forwarding_alias.return_value = {"id": "wd-sys-001"}
    with patch("vollbuild.core.services.wildduck.try_get_client", return_value=mock_wd):
        with patch(
            "vollbuild.api.settings.service.SettingsService.get",
            return_value="club.ch",
        ):
            resp = client.post(
                "/api/v1/mail/system-addresses",
                json={
                    "address": "newsys",
                    "addressType": "alias",
                    "displayName": "New System",
                    "forwardTargets": ["target@example.ch"],
                    "isProtected": False,
                },
                headers=auth_headers,
            )

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["address"] == "newsys@club.ch"
    assert body["isSystem"] is True
    assert body["displayName"] == "New System"
    assert body["isProtected"] is False


def test_delete_protected_system_address_returns_403(
    client, db, seeded_db, auth_headers
):
    """DELETE /mail/system-addresses/<id> returns 403 for protected addresses."""
    addr = _make_mma(
        db,
        address="protectedsys@club.ch",
        is_protected=True,
        is_system=True,
    )

    resp = client.delete(
        f"/api/v1/mail/system-addresses/{addr.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_delete_unprotected_system_address(client, db, seeded_db, auth_headers):
    """DELETE /mail/system-addresses/<id> succeeds for non-protected addresses."""
    addr = _make_mma(
        db,
        address="unprotectedsys@club.ch",
        is_protected=False,
        is_system=True,
        address_type="alias",
        wildduck_id="wd-del-002",
    )
    addr_id = addr.id

    mock_wd = MagicMock()
    with patch("vollbuild.core.services.wildduck.try_get_client", return_value=mock_wd):
        resp = client.delete(
            f"/api/v1/mail/system-addresses/{addr_id}",
            headers=auth_headers,
        )

    assert resp.status_code == 204
    assert db.session.get(ManagedMailAddress, addr_id) is None


def test_toggle_system_address(client, db, seeded_db, auth_headers):
    """PATCH /mail/system-addresses/<id>/toggle toggles the address."""
    addr = _make_mma(
        db,
        address="togglesys@club.ch",
        is_system=True,
        is_protected=True,
        is_enabled=True,
        address_type="alias",
        wildduck_id="wd-toggle-001",
        provisioning_status="provisioned",
    )

    mock_wd = MagicMock()
    with patch("vollbuild.core.services.wildduck.try_get_client", return_value=mock_wd):
        with patch(
            "vollbuild.core.services.managed_mail.resolve_alias_targets",
            return_value=["target@example.ch"],
        ):
            resp = client.patch(
                f"/api/v1/mail/system-addresses/{addr.id}/toggle",
                json={"enabled": False},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    db.session.refresh(addr)
    assert addr.is_enabled is False


# ── Function mail toggle / prefix / aliases ───────────────────────────────────


def test_toggle_function_mail(client, db, seeded_db, auth_headers):
    """PATCH /mail/functions/<id>/toggle toggles function mail."""
    from vollbuild.core.models.function import Function

    fn = Function(name="TestToggleFn")
    db.session.add(fn)
    db.session.commit()

    addr = _make_mma(
        db,
        address="togglefn@club.ch",
        address_type="mailbox",
        owner_type="function",
        owner_id=fn.id,
        is_enabled=True,
        kind="function",
        enabled=True,
        wildduck_id="wd-user-001",
        provisioning_status="provisioned",
    )

    mock_wd = MagicMock()
    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        resp = client.patch(
            f"/api/v1/mail/functions/{fn.id}/toggle",
            json={"enabled": False},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    db.session.refresh(addr)
    assert addr.is_enabled is False
    assert addr.enabled is False


def test_create_function_alias(client, db, seeded_db, auth_headers):
    """POST /mail/functions/<id>/aliases creates an additional MMA alias."""
    from vollbuild.core.models.function import Function

    fn = Function(name="TestAliasFn")
    db.session.add(fn)
    db.session.commit()

    _make_mma(
        db,
        address="fnmain@club.ch",
        address_type="mailbox",
        owner_type="function",
        owner_id=fn.id,
        kind="function",
        enabled=True,
    )

    mock_wd = MagicMock()
    mock_wd.create_forwarding_alias.return_value = {"id": "wd-fn-alias-001"}
    with patch(
        "vollbuild.core.services.mail_provisioning.try_get_client", return_value=mock_wd
    ):
        with patch(
            "vollbuild.api.settings.service.SettingsService.get",
            return_value="club.ch",
        ):
            resp = client.post(
                f"/api/v1/mail/functions/{fn.id}/aliases",
                json={"prefix": "fnextra"},
                headers=auth_headers,
            )

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["address"] == "fnextra@club.ch"
    assert body["kind"] == "function"
    assert body["mailboxBacked"] is False


# ── Service-layer unit tests ──────────────────────────────────────────────────


def test_validate_mail_prefix_valid():
    from vollbuild.core.services.managed_mail import validate_mail_prefix

    assert validate_mail_prefix("vorstand") == "vorstand"
    assert validate_mail_prefix("  Info  ") == "info"
    assert validate_mail_prefix("my-alias") == "my-alias"
    assert validate_mail_prefix("a.b.c") == "a.b.c"


def test_validate_mail_prefix_invalid():
    from vollbuild.core.services.managed_mail import validate_mail_prefix

    import pytest as _pytest

    for bad in ["", "   ", "with space", "ümlaut", "a" * 65, "-leading", "trailing-"]:
        with _pytest.raises(ValueError):
            validate_mail_prefix(bad)


def test_normalize_prefix_from_name():
    from vollbuild.core.services.managed_mail import normalize_prefix_from_name

    assert normalize_prefix_from_name("Vorstand") == "vorstand"
    assert normalize_prefix_from_name("IT & Technik") == "ittechnik"
    assert normalize_prefix_from_name("Café") == "caf"
    assert normalize_prefix_from_name("") == "mail"


def test_serialize_includes_new_fields():
    from vollbuild.core.services.managed_mail import serialize

    addr = ManagedMailAddress(
        address="test@club.ch",
        address_type="alias",
        is_protected=True,
        is_enabled=False,
        is_system=True,
        mail_prefix="test",
        display_name="Test",
        cached_forward_targets='["a@b.ch"]',
        fixed_forward_targets='["c@d.ch"]',
        provisioning_status="provisioned",
    )
    data = serialize(addr)
    assert data["isEnabled"] is False
    assert data["isSystem"] is True
    assert data["mailPrefix"] == "test"
    assert data["displayName"] == "Test"
    assert data["cachedForwardTargets"] == ["a@b.ch"]
    assert data["fixedForwardTargets"] == ["c@d.ch"]


# ── Seed tests ────────────────────────────────────────────────────────────────


def test_seed_creates_system_addresses(db):
    """Seed function creates system addresses: noreply, postmaster, info, abuse."""
    from vollbuild.core.models.setting import Setting
    from vollbuild.core.seeds import run_seeds

    db.session.add(Setting(key="mail.domain", value="club.ch"))
    db.session.commit()

    run_seeds(db)

    for prefix in ["noreply", "postmaster", "info", "abuse"]:
        addr = db.session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.address == f"{prefix}@club.ch"
            )
        )
        assert addr is not None, f"{prefix}@club.ch should be seeded"
        assert addr.is_system is True

    catchall = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == "*@club.ch")
    )
    assert catchall is not None, "*@club.ch catch-all should be seeded"
    assert catchall.is_system is True

    noreply = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.address == "noreply@club.ch"
        )
    )
    assert noreply.is_system is True
    assert noreply.display_name == "No-Reply"

    info = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == "info@club.ch")
    )
    assert info.is_system is True
    assert info.display_name == "Info"

    abuse = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == "abuse@club.ch")
    )
    assert abuse.is_system is True
    assert abuse.fixed_forward_targets is not None
    fixed = json.loads(abuse.fixed_forward_targets)
    assert "postmaster@club.ch" in fixed


def test_seed_system_aliases_forward_to_postmaster(db):
    """Seed creates info@, abuse@, *@ aliases that forward to postmaster@."""
    from vollbuild.core.models.setting import Setting
    from vollbuild.core.seeds import run_seeds

    db.session.add(Setting(key="mail.domain", value="club.ch"))
    db.session.commit()

    run_seeds(db)

    for prefix in ["info", "abuse", "*"]:
        alias = db.session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.address == f"{prefix}@club.ch"
            )
        )
        assert alias is not None, f"{prefix}@club.ch should be seeded"
        assert alias.is_system is True
        assert alias.address_type == "alias"

    # Verify info@ forwards to postmaster@ (not "hub")
    info_mma = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == "info@club.ch")
    )
    assert info_mma is not None
    import json as _json

    fixed = _json.loads(info_mma.fixed_forward_targets)
    assert "postmaster@club.ch" in fixed
    assert "hub" not in fixed
