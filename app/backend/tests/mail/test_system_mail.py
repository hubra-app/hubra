"""Tests for system mail addresses — provisioning, reconciliation, and API."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.models.setting import Setting


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_system_mma(
    db,
    *,
    local_part: str,
    domain: str = "hubra.club",
    is_mailbox: bool = True,
    wildduck_id: str | None = None,
    fixed_forward_targets: list[str] | None = None,
    display_name: str | None = None,
    owner_type: str | None = None,
    owner_id: int | None = None,
    quota_bytes: int | None = None,
    retention_days: int | None = None,
) -> ManagedMailAddress:
    addr = ManagedMailAddress(
        address=f"{local_part}@{domain}",
        address_type="mailbox" if is_mailbox else "alias",
        is_protected=True,
        is_enabled=True,
        is_system=True,
        kind="system",
        local_part=local_part,
        domain=domain,
        wildduck_id=wildduck_id,
        display_name=display_name,
        fixed_forward_targets=json.dumps(fixed_forward_targets)
        if fixed_forward_targets
        else None,
        owner_type=owner_type,
        owner_id=owner_id,
        provisioning_status="pending",
        quota_bytes=quota_bytes,
        retention=retention_days * 86400000 if retention_days else None,
    )
    db.session.add(addr)
    db.session.commit()
    return addr


def _ensure_settings(db, domain: str = "hubra.club"):
    """Ensure mail.domain setting exists."""
    existing = db.session.get(Setting, "mail.domain")
    if existing is None:
        db.session.add(Setting(key="mail.domain", value=domain))
    else:
        existing.value = domain
    db.session.commit()


# ── Hub resolver tests ────────────────────────────────────────────────────────


def test_get_hub_address_default(app, db):
    """_get_hub_address returns postmaster@domain by default."""
    from hubra.core.services.mail_provisioning import _get_hub_address

    _ensure_settings(db)
    assert _get_hub_address() == "postmaster@hubra.club"


# ── System alias target resolver tests ────────────────────────────────────────


def test_resolve_system_alias_targets_hub_marker(app, db):
    """_resolve_system_alias_targets replaces 'hub' with the hub address."""
    from hubra.core.services.mail_provisioning import _resolve_system_alias_targets

    _ensure_settings(db)
    mma = _make_system_mma(
        db, local_part="abuse", is_mailbox=False, fixed_forward_targets=["hub"]
    )
    targets = _resolve_system_alias_targets(mma)
    assert targets == ["postmaster@hubra.club"]


def test_resolve_system_alias_targets_passthrough(app, db):
    """_resolve_system_alias_targets passes through non-hub targets."""
    from hubra.core.services.mail_provisioning import _resolve_system_alias_targets

    _ensure_settings(db)
    mma = _make_system_mma(
        db,
        local_part="info",
        is_mailbox=False,
        fixed_forward_targets=["external@example.com", "hub"],
    )
    targets = _resolve_system_alias_targets(mma)
    assert targets == ["external@example.com", "postmaster@hubra.club"]


def test_resolve_system_alias_targets_no_fixed_falls_back_to_hub(app, db):
    """_resolve_system_alias_targets falls back to hub when no fixed targets."""
    from hubra.core.services.mail_provisioning import _resolve_system_alias_targets

    _ensure_settings(db)
    mma = _make_system_mma(db, local_part="info", is_mailbox=False)
    targets = _resolve_system_alias_targets(mma)
    assert targets == ["postmaster@hubra.club"]


# ── System forward target resolver tests ──────────────────────────────────────


def test_resolve_system_forward_targets_with_fixed(app, db):
    """_resolve_system_forward_targets resolves 'hub' markers in fixed targets."""
    from hubra.core.services.mail_provisioning import (
        _resolve_system_forward_targets,
    )

    _ensure_settings(db)
    mma = _make_system_mma(
        db,
        local_part="postmaster",
        is_mailbox=True,
        fixed_forward_targets=["hub", "external@example.com"],
    )
    targets = _resolve_system_forward_targets(mma)
    assert targets == ["postmaster@hubra.club", "external@example.com"]


def test_resolve_system_forward_targets_empty_when_no_fixed_no_group(app, db):
    """_resolve_system_forward_targets returns empty list when no fixed targets and no group."""
    from hubra.core.services.mail_provisioning import (
        _resolve_system_forward_targets,
    )

    _ensure_settings(db)
    mma = _make_system_mma(
        db, local_part="noreply", is_mailbox=True, fixed_forward_targets=None
    )
    targets = _resolve_system_forward_targets(mma)
    assert targets == []


# ── ensure_catchall tests ─────────────────────────────────────────────────────


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_catchall_adds_wildcard_to_hub(mock_tgc, app, db):
    """ensure_catchall adds *@domain to hub user with allowWildcard=True."""
    from hubra.core.services.mail_provisioning import ensure_catchall

    _ensure_settings(db)
    _make_system_mma(
        db,
        local_part="postmaster",
        is_mailbox=True,
        wildduck_id="wd-hub",
        display_name="Postmaster",
        quota_bytes=500 * 1024 * 1024,
        retention_days=90,
    )
    catchall_mma = _make_system_mma(
        db, local_part="*", is_mailbox=False, display_name="Catch-All"
    )

    mock_wd = MagicMock()
    mock_wd.list_user_addresses.return_value = {"results": []}
    mock_tgc.return_value = mock_wd

    ensure_catchall(catchall_mma)

    mock_wd.add_address_to_user.assert_called_once_with(
        "wd-hub", "*@hubra.club", allow_wildcard=True
    )
    assert catchall_mma.sync_state == "ok"


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_catchall_skips_when_hub_not_provisioned(mock_tgc, app, db):
    """ensure_catchall marks error when hub is not yet provisioned."""
    from hubra.core.services.mail_provisioning import ensure_catchall

    _ensure_settings(db)
    _make_system_mma(db, local_part="postmaster", is_mailbox=True, wildduck_id=None)
    catchall_mma = _make_system_mma(
        db, local_part="*", is_mailbox=False, display_name="Catch-All"
    )

    mock_wd = MagicMock()
    mock_tgc.return_value = mock_wd

    ensure_catchall(catchall_mma)

    mock_wd.add_address_to_user.assert_not_called()
    assert catchall_mma.sync_state == "error"


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_catchall_noop_when_already_present(mock_tgc, app, db):
    """ensure_catchall is a no-op when *@domain already exists on hub user."""
    from hubra.core.services.mail_provisioning import ensure_catchall

    _ensure_settings(db)
    _make_system_mma(db, local_part="postmaster", is_mailbox=True, wildduck_id="wd-hub")
    catchall_mma = _make_system_mma(
        db, local_part="*", is_mailbox=False, display_name="Catch-All"
    )

    mock_wd = MagicMock()
    mock_wd.list_user_addresses.return_value = {
        "results": [{"address": "*@hubra.club"}]
    }
    mock_tgc.return_value = mock_wd

    ensure_catchall(catchall_mma)

    mock_wd.add_address_to_user.assert_not_called()
    assert catchall_mma.sync_state == "ok"


# ── set_system_mailbox_password tests ─────────────────────────────────────────


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_set_system_mailbox_password_pushes_plaintext(mock_tgc, app, db):
    """set_system_mailbox_password pushes plaintext password to WildDuck."""
    from hubra.core.services.mail_provisioning import set_system_mailbox_password

    mma = _make_system_mma(
        db, local_part="postmaster", is_mailbox=True, wildduck_id="wd-pm"
    )

    mock_wd = MagicMock()
    mock_tgc.return_value = mock_wd

    set_system_mailbox_password(mma, "newpass123")

    mock_wd.update_user_password.assert_called_once_with("wd-pm", "newpass123")
    assert mma.sync_state == "ok"


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_set_system_mailbox_password_no_wildduck_id(mock_tgc, app, db):
    """set_system_mailbox_password marks error when no wildduck_id."""
    from hubra.core.services.mail_provisioning import set_system_mailbox_password

    mma = _make_system_mma(
        db, local_part="postmaster", is_mailbox=True, wildduck_id=None
    )

    mock_wd = MagicMock()
    mock_tgc.return_value = mock_wd

    set_system_mailbox_password(mma, "newpass123")

    mock_wd.update_user_password.assert_not_called()
    assert mma.sync_state == "error"


# ── ensure_alias for system aliases tests ─────────────────────────────────────


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_alias_system_resolves_hub_targets(mock_tgc, app, db):
    """ensure_alias for a system alias resolves 'hub' marker to hub address."""
    from hubra.core.services.mail_provisioning import ensure_alias

    _ensure_settings(db)
    mma = _make_system_mma(
        db,
        local_part="abuse",
        is_mailbox=False,
        fixed_forward_targets=["hub"],
        display_name="Abuse",
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_address.return_value = None
    mock_wd.create_forwarding_alias.return_value = {"id": "wd-alias-abuse"}
    mock_tgc.return_value = mock_wd

    ensure_alias(mma)

    mock_wd.create_forwarding_alias.assert_called_once_with(
        "abuse@hubra.club",
        targets=["postmaster@hubra.club"],
        name="Abuse",
    )
    assert mma.wildduck_id == "wd-alias-abuse"


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_alias_system_updates_targets_when_different(mock_tgc, app, db):
    """ensure_alias updates forwarding alias targets when they differ."""
    from hubra.core.services.mail_provisioning import ensure_alias

    _ensure_settings(db)
    mma = _make_system_mma(
        db,
        local_part="abuse",
        is_mailbox=False,
        fixed_forward_targets=["hub"],
        wildduck_id="wd-alias-abuse",
        display_name="Abuse",
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_address.return_value = {
        "id": "wd-alias-abuse",
        "targets": ["old@example.com"],
    }
    mock_tgc.return_value = mock_wd

    ensure_alias(mma)

    mock_wd.update_forwarding_alias.assert_called_once_with(
        "wd-alias-abuse", ["postmaster@hubra.club"]
    )
    mock_wd.create_forwarding_alias.assert_not_called()


# ── ensure_forwarding for alias MMAs tests ────────────────────────────────────


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_forwarding_alias_updates_targets(mock_tgc, app, db):
    """ensure_forwarding on an alias MMA calls update_forwarding_alias."""
    from hubra.core.services.mail_provisioning import ensure_forwarding

    mma = _make_system_mma(
        db,
        local_part="abuse",
        is_mailbox=False,
        wildduck_id="wd-alias-abuse",
    )

    mock_wd = MagicMock()
    mock_tgc.return_value = mock_wd

    ensure_forwarding(mma, ["target@example.com"])

    mock_wd.update_forwarding_alias.assert_called_once_with(
        "wd-alias-abuse", ["target@example.com"]
    )


# ── reconcile_mail system tests ───────────────────────────────────────────────


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_catchall(mock_wd_tgc, mock_mp_tgc, app, db):
    """reconcile_mail calls ensure_catchall for local_part='*' rows."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    _ensure_settings(db)
    _make_system_mma(
        db,
        local_part="postmaster",
        is_mailbox=True,
        wildduck_id="wd-hub",
        display_name="Postmaster",
    )
    _make_system_mma(db, local_part="*", is_mailbox=False, display_name="Catch-All")

    mock_wd = MagicMock()
    mock_wd.list_user_addresses.return_value = {"results": []}
    mock_wd.list_users.return_value = {"results": []}
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    result = reconcile_mail.run()

    assert result["provisioned"] >= 1
    mock_wd.add_address_to_user.assert_any_call(
        "wd-hub", "*@hubra.club", allow_wildcard=True
    )


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_system_mailbox_forwarding(mock_wd_tgc, mock_mp_tgc, app, db):
    """reconcile_mail reconciles forwarding targets for system mailboxes."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    _ensure_settings(db)
    _make_system_mma(
        db,
        local_part="postmaster",
        is_mailbox=True,
        wildduck_id="wd-pm",
        fixed_forward_targets=["hub"],
        display_name="Postmaster",
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = {"id": "wd-pm"}
    mock_wd.list_users.return_value = {"results": []}
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    reconcile_mail.run()

    mock_wd.update_user_attributes.assert_any_call(
        "wd-pm", targets=["postmaster@hubra.club"]
    )


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_system_alias_with_hub_targets(
    mock_wd_tgc, mock_mp_tgc, app, db
):
    """reconcile_mail provisions system alias and resolves hub targets."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    _ensure_settings(db)
    _make_system_mma(
        db,
        local_part="abuse",
        is_mailbox=False,
        fixed_forward_targets=["hub"],
        display_name="Abuse",
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_address.return_value = None
    mock_wd.create_forwarding_alias.return_value = {"id": "wd-alias-abuse"}
    mock_wd.list_users.return_value = {"results": []}
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    reconcile_mail.run()

    mock_wd.create_forwarding_alias.assert_called_once_with(
        "abuse@hubra.club",
        targets=["postmaster@hubra.club"],
        name="Abuse",
    )


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_recreates_postmaster_if_removed(
    mock_wd_tgc, mock_mp_tgc, app, db
):
    """reconcile_mail recreates postmaster mailbox if removed in WildDuck."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    _ensure_settings(db)
    mma = _make_system_mma(
        db,
        local_part="postmaster",
        is_mailbox=True,
        wildduck_id="wd-pm-gone",
        display_name="Postmaster",
    )

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = None  # user not found
    mock_wd.create_user.return_value = {"id": "wd-pm-recreated"}
    mock_wd.list_users.return_value = {"results": []}
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    reconcile_mail.run()

    mock_wd.create_user.assert_called_once()
    db.session.refresh(mma)
    assert mma.wildduck_id == "wd-pm-recreated"


# ── API tests ─────────────────────────────────────────────────────────────────


def test_api_delete_protected_system_address_403(
    client, app, db, seeded_db, auth_headers
):
    """Deleting a protected system address returns 403."""
    mma = _make_system_mma(db, local_part="postmaster", is_mailbox=True)

    resp = client.delete(
        f"/api/v1/mail/system-addresses/{mma.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_api_get_system_addresses_returns_new_fields(
    client, app, db, seeded_db, auth_headers
):
    """GET /system-addresses returns new fields (kind, mailboxBacked, etc.)."""
    mma = _make_system_mma(
        db,
        local_part="postmaster",
        is_mailbox=True,
        display_name="Postmaster",
        quota_bytes=500 * 1024 * 1024,
        retention_days=90,
    )

    resp = client.get(
        "/api/v1/mail/system-addresses",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert any(d["id"] == mma.id for d in data)
    item = next(d for d in data if d["id"] == mma.id)
    assert item["kind"] == "system"
    assert item["mailboxBacked"] is True
    assert item["quotaBytes"] == 500 * 1024 * 1024
    assert item["retention"] == 90 * 86400000


def test_api_reset_password_user_supplied_returns_200(
    client, app, db, seeded_db, auth_headers
):
    """reset-password with a user-supplied password returns 200 with password."""

    mma = _make_system_mma(
        db,
        local_part="postmaster",
        is_mailbox=True,
        wildduck_id="wd-pm",
        display_name="Postmaster",
    )

    with patch("hubra.core.services.mail_provisioning.set_system_mailbox_password"):
        resp = client.post(
            f"/api/v1/mail/system-addresses/{mma.id}/reset-password",
            json={"password": "userpass123"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.get_json()["password"] == "userpass123"


def test_api_reset_password_auto_generated_returns_password(
    client, app, db, seeded_db, auth_headers
):
    """reset-password without a password auto-generates and returns it."""
    mma = _make_system_mma(
        db,
        local_part="postmaster",
        is_mailbox=True,
        wildduck_id="wd-pm",
        display_name="Postmaster",
    )

    with patch("hubra.core.services.mail_provisioning.set_system_mailbox_password"):
        resp = client.post(
            f"/api/v1/mail/system-addresses/{mma.id}/reset-password",
            json={},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert "password" in data
    assert len(data["password"]) >= 8


def test_api_reset_password_alias_returns_400(client, app, db, seeded_db, auth_headers):
    """reset-password on an alias-type system address returns 400."""
    mma = _make_system_mma(
        db,
        local_part="abuse",
        is_mailbox=False,
        display_name="Abuse",
    )

    resp = client.post(
        f"/api/v1/mail/system-addresses/{mma.id}/reset-password",
        json={"password": "testpass123"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_api_update_forwarding(client, app, db, seeded_db, auth_headers):
    """PUT /system-addresses/<id>/forwarding updates targets."""
    _ensure_settings(db)
    mma = _make_system_mma(
        db,
        local_part="postmaster",
        is_mailbox=True,
        wildduck_id="wd-pm",
        display_name="Postmaster",
    )

    with patch("hubra.core.services.mail_provisioning.ensure_forwarding"):
        resp = client.put(
            f"/api/v1/mail/system-addresses/{mma.id}/forwarding",
            json={"targets": ["admin@example.com", "user@example.com"]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["targets"] == ["admin@example.com", "user@example.com"]

    db.session.refresh(mma)
    stored = json.loads(mma.fixed_forward_targets)
    assert stored == ["admin@example.com", "user@example.com"]


def test_api_get_forwarding_fixed_targets(client, app, db, seeded_db, auth_headers):
    """GET /system-addresses/<id>/forwarding returns fixed targets."""
    mma = _make_system_mma(
        db,
        local_part="abuse",
        is_mailbox=False,
        fixed_forward_targets=["hub", "external@example.com"],
        display_name="Abuse",
    )

    resp = client.get(
        f"/api/v1/mail/system-addresses/{mma.id}/forwarding",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["targets"] == ["hub", "external@example.com"]


def test_api_update_forwarding_catchall_400(client, app, db, seeded_db, auth_headers):
    """PUT forwarding on catch-all address returns 400."""
    mma = _make_system_mma(
        db,
        local_part="*",
        is_mailbox=False,
        display_name="Catch-All",
    )

    resp = client.put(
        f"/api/v1/mail/system-addresses/{mma.id}/forwarding",
        json={"targets": ["admin@example.com"]},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ── Seed tests ────────────────────────────────────────────────────────────────


# ── Translation key tests ─────────────────────────────────────────────────────


def test_translations_contain_system_mail_keys():
    """en-GB and de-CH translation files contain system mail keys."""
    import json as _json
    import pathlib

    seeds_dir = (
        pathlib.Path(__file__).resolve().parents[2]
        / "hubra"
        / "core"
        / "seed_data"
        / "translations"
    )

    required_keys = [
        "mail.system.title",
        "mail.system.hub",
        "mail.system.catchall",
        "mail.system.forwarding",
        "mail.system.password.set",
        "mail.system.password.reset",
        "mail.system.protected",
        "mail.permission.system.manage",
        "mail.permission.system.read",
    ]

    for locale in ("en-GB", "de-CH"):
        with open(seeds_dir / f"{locale}.json", encoding="utf-8") as f:
            translations = _json.load(f)
        for key in required_keys:
            assert key in translations, f"Missing key {key} in {locale}.json"


# ── Seed noreply binding sync tests ──────────────────────────────────────────


def test_seed_creates_noreply_mma_with_password(app, db):
    """run_seeds creates a noreply system MMA with an encrypted password."""
    from hubra.core.seeds import run_seeds
    from hubra.core.models.managed_mail import ManagedMailAddress
    from sqlalchemy import select

    run_seeds(db)

    noreply = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.address == "noreply@hubra.club"
        )
    )
    assert noreply is not None
    assert noreply.is_system is True
    assert noreply.address_type == "mailbox"
    assert noreply.mailbox_password_encrypted is not None
