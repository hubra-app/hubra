"""The club's own backup key, set from the club app's settings guide.

Only the public key reaches the server: a private key is refused so it is
never stored or logged by mistake.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from hubra.core.models.backup import BackupRecord
from hubra.core.models.tenant import Tenant

# A valid age X25519 public key and its private key (made for these tests).
PUB = "age1msg3zx2y4vaq4y7fjp0kcm30xvzkdd4crwreclncz0fr5kf7xgwstzvt0m"
PRIV = "AGE-SECRET-KEY-1ZHCYVF9YQEQH3E40GU8R6ZUJSV0V4WUMQC5NSWKQJDZS4PJP40HSNVMC6W"
URL = "/api/v1/admin/backup-key"


@pytest.fixture
def tenant(db, seeded_db):
    club = Tenant(name="Key Club", slug="key-club", plan="starter")
    db.session.add(club)
    db.session.commit()
    with (
        patch("hubra.api.admin.routes.current_tenant", return_value=club),
        patch("hubra.core.tenant.context.set_search_path"),
    ):
        yield club


@pytest.fixture
def admin(client, seeded_db):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )


def test_no_key_yet(tenant, client, admin):
    body = client.get(URL).get_json()
    assert body["public_key"] is None
    assert body["set_at"] is None
    assert body["last_backup_with_key"] is None


def test_set_and_remove_key(tenant, client, admin, db):
    resp = client.put(URL, json={"public_key": f"  {PUB}\n"})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["public_key"] == PUB
    assert body["set_at"]
    db.session.refresh(tenant)
    assert tenant.backup_public_key == PUB

    resp = client.delete(URL)
    assert resp.status_code == 200
    assert resp.get_json()["public_key"] is None
    db.session.refresh(tenant)
    assert tenant.backup_public_key is None
    assert "backup_key" not in (tenant.settings or {})


@pytest.mark.parametrize(
    "value",
    [PRIV, f"# public key: {PUB}\n{PRIV}", PRIV.lower()],
)
def test_private_key_is_refused(tenant, client, admin, db, value):
    resp = client.put(URL, json={"public_key": value})
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "PRIVATE_KEY_SENT"
    db.session.refresh(tenant)
    assert tenant.backup_public_key is None


@pytest.mark.parametrize("value", ["", "nope", f"{PUB} {PUB}", PUB[:-1], None, 5])
def test_bad_key_is_refused(tenant, client, admin, value):
    resp = client.put(URL, json={"public_key": value})
    assert resp.status_code == 422


def test_last_backup_counts_only_age_backups_after_the_key(tenant, client, admin, db):
    client.put(URL, json={"public_key": PUB})
    now = datetime.now(UTC)
    db.session.add_all(
        [
            BackupRecord(
                type="scheduled",
                status="completed",
                scope="club",
                tenant_id=tenant.id,
                s3_key="clubs/x/old.dump.age",
                created_at=now - timedelta(days=2),
            ),
            BackupRecord(
                type="scheduled",
                status="completed",
                scope="club",
                tenant_id=tenant.id,
                s3_key="clubs/x/new.dump.gpg",
                created_at=now + timedelta(minutes=1),
            ),
        ]
    )
    db.session.commit()
    assert client.get(URL).get_json()["last_backup_with_key"] is None

    db.session.add(
        BackupRecord(
            type="scheduled",
            status="completed",
            scope="club",
            tenant_id=tenant.id,
            s3_key="clubs/x/new.dump.age",
            created_at=now + timedelta(minutes=2),
        )
    )
    db.session.commit()
    assert client.get(URL).get_json()["last_backup_with_key"]


def test_key_set_elsewhere_has_no_stale_note(tenant, client, admin, db):
    client.put(URL, json={"public_key": PUB})
    other = "age1" + "q" * 58
    tenant.backup_public_key = other  # e.g. from manage › Encryption
    db.session.commit()
    body = client.get(URL).get_json()
    assert body["public_key"] == other
    assert body["set_at"] is None


def test_members_cannot_set_the_key(tenant, client, seeded_db):
    resp = client.put(URL, json={"public_key": PUB})
    assert resp.status_code in (401, 403)
