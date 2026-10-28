"""Tests for the FeatureFlag system — model, service, endpoint, and mail gating."""

from __future__ import annotations

from vollbuild.core.models.feature_flag import FeatureFlag


def _enable_mail(db, enabled: bool = True):
    flag = db.session.get(FeatureFlag, "mail")
    if flag is None:
        flag = FeatureFlag(key="mail", enabled=enabled, label="Mail")
        db.session.add(flag)
    else:
        flag.enabled = enabled
    db.session.commit()
    return flag


# ── Model / Service ───────────────────────────────────────────────────────────


def test_is_enabled_returns_false_when_no_flag(db):
    from vollbuild.api.features.services import FeatureFlagService

    assert FeatureFlagService.is_enabled("mail") is False


def test_is_enabled_returns_true_when_enabled(db):
    from vollbuild.api.features.services import FeatureFlagService

    _enable_mail(db, True)
    assert FeatureFlagService.is_enabled("mail") is True


def test_is_enabled_returns_false_when_disabled(db):
    from vollbuild.api.features.services import FeatureFlagService

    _enable_mail(db, False)
    assert FeatureFlagService.is_enabled("mail") is False


def test_set_enabled_updates_flag(db):
    from vollbuild.api.features.services import FeatureFlagService

    _enable_mail(db, False)
    flag = FeatureFlagService.set_enabled("mail", True)
    db.session.commit()
    assert flag.enabled is True
    assert FeatureFlagService.is_enabled("mail") is True


# ── Endpoint ──────────────────────────────────────────────────────────────────


def test_get_features_requires_auth(client):
    resp = client.get("/api/v1/features/")
    assert resp.status_code == 401


def test_get_features_returns_list(client, db, seeded_db, auth_headers):
    _enable_mail(db, True)
    resp = client.get("/api/v1/features/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert any(f["key"] == "mail" and f["enabled"] is True for f in data)


def test_put_feature_toggles_flag(client, db, seeded_db, auth_headers):
    _enable_mail(db, False)
    resp = client.put(
        "/api/v1/features/mail",
        json={"enabled": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["enabled"] is True
    flag = db.session.get(FeatureFlag, "mail")
    assert flag.enabled is True


def test_put_feature_rejects_missing_enabled(client, db, seeded_db, auth_headers):
    _enable_mail(db, False)
    resp = client.put(
        "/api/v1/features/mail",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ── Mail blueprint gating ─────────────────────────────────────────────────────


def test_mail_endpoints_return_409_when_disabled(client, db, seeded_db, auth_headers):
    _enable_mail(db, False)
    resp = client.get("/api/v1/mail/mailboxes", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "FEATURE_DISABLED"


def test_mail_endpoints_work_when_enabled(client, db, seeded_db, auth_headers):
    from unittest.mock import patch

    _enable_mail(db, True)
    with patch(
        "vollbuild.api.mail.services.MailboxesService.list",
        return_value=[],
    ):
        resp = client.get("/api/v1/mail/mailboxes", headers=auth_headers)
        assert resp.status_code == 200


# ── Account mail-settings gating ──────────────────────────────────────────────


def test_account_mail_settings_reports_disabled(client, db, seeded_db, auth_headers):
    _enable_mail(db, False)
    resp = client.get("/api/v1/account/mail-settings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mail_disabled"] is True
    assert data["mailbox_enabled"] is False


def test_account_mail_settings_patch_returns_409_when_disabled(
    client, db, seeded_db, auth_headers
):
    _enable_mail(db, False)
    resp = client.patch(
        "/api/v1/account/mail-settings",
        json={"forwarding_enabled": True},
        headers=auth_headers,
    )
    assert resp.status_code == 409


# ── requiresConfiguration + per-feature settings endpoints ───────────────────

_BACKUP_KEYS = [
    "backup.s3_endpoint",
    "backup.s3_bucket",
    "backup.s3_access_key",
    "backup.s3_secret_key",
    "backup.s3_region",
]


def _seed_backup(db, configured: bool = False) -> FeatureFlag:
    """Create the backup feature flag + its 5 required setting rows."""
    from vollbuild.core.models.setting import Setting

    flag = db.session.get(FeatureFlag, "backup")
    if flag is None:
        flag = FeatureFlag(key="backup", enabled=False, label="Backup")
        db.session.add(flag)
    else:
        flag.enabled = False

    meta = {
        "backup.s3_endpoint": ("url", "S3 endpoint URL"),
        "backup.s3_bucket": (None, "S3 bucket name"),
        "backup.s3_access_key": (None, "S3 access key"),
        "backup.s3_secret_key": (None, "S3 secret key"),
        "backup.s3_region": (None, "S3 region"),
    }
    for skey in _BACKUP_KEYS:
        existing = db.session.get(Setting, skey)
        v = f"value-{skey}" if configured else ""
        if existing is None:
            vtype, label = meta[skey]
            db.session.add(
                Setting(
                    key=skey,
                    value=v,
                    namespace="backup",
                    sensitive=skey in ("backup.s3_access_key", "backup.s3_secret_key"),
                    validation_type=vtype,
                    label=label,
                )
            )
        else:
            existing.value = v
    db.session.commit()
    return flag


# ── Toggle (requires auth) ────────────────────────────────────────────────────


def test_toggle_requires_auth(client):
    resp = client.put("/api/v1/features/mail", json={"enabled": True})
    assert resp.status_code == 401
