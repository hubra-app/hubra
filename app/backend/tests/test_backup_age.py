"""Backups encrypted to public keys: the server writes them, only the
private key (from the operator, or a club's own) opens them."""

import shutil
import subprocess
import uuid
from unittest.mock import MagicMock, patch

import pytest

from hubra.core.services import backup_crypto

pytestmark = pytest.mark.skipif(
    shutil.which("age") is None, reason="needs the age command"
)

_real_run = subprocess.run


def _keypair() -> tuple[str, str]:
    out = _real_run(["age-keygen"], capture_output=True, check=True).stdout.decode()
    private = next(line for line in out.splitlines() if line.startswith("AGE-SECRET"))
    public = _real_run(
        ["age-keygen", "-y"], input=private.encode(), capture_output=True, check=True
    ).stdout.decode()
    return public.strip(), private


INSTALL_PUB, INSTALL_PRIV = _keypair() if shutil.which("age") else ("", "")
CLUB_PUB, CLUB_PRIV = _keypair() if shutil.which("age") else ("", "")
OTHER_PUB, OTHER_PRIV = _keypair() if shutil.which("age") else ("", "")


@pytest.fixture
def age_config(app):
    keys = (
        "BACKUP_PUBLIC_KEY",
        "BACKUP_PRIVATE_KEY",
        "BACKUP_ENCRYPTION_KEY",
        "BACKUP_S3_ENDPOINT",
        "BACKUP_S3_BUCKET",
        "BACKUP_S3_ACCESS_KEY",
        "BACKUP_S3_SECRET_KEY",
    )
    saved = {k: app.config.get(k) for k in keys}
    app.config.update(
        BACKUP_PUBLIC_KEY=INSTALL_PUB,
        BACKUP_PRIVATE_KEY="",
        BACKUP_ENCRYPTION_KEY="old-passphrase",
        BACKUP_S3_ENDPOINT="https://s3.test",
        BACKUP_S3_BUCKET="b",
        BACKUP_S3_ACCESS_KEY="a",
        BACKUP_S3_SECRET_KEY="s",
    )
    yield app
    app.config.update(saved)


class FakeS3:
    """Keeps uploaded objects in memory."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def upload_file(self, path, bucket, key):
        with open(path, "rb") as f:
            self.objects[key] = f.read()

    def download_file(self, bucket, key, path):
        with open(path, "wb") as f:
            f.write(self.objects[key])

    def head_bucket(self, Bucket):
        return {}


def _tools(cmd, *args, **kwargs):
    """Real age; fake pg_dump and pg_restore."""
    if cmd[0] == "pg_dump":
        return MagicMock(returncode=0, stdout=b"PGDMP-club-data", stderr=b"")
    if cmd[0] == "pg_restore":
        listing = b"; TABLE DATA public.codes\n; TABLE DATA public.members\n"
        return MagicMock(returncode=0, stdout=listing, stderr=b"")
    return _real_run(cmd, *args, **kwargs)


@pytest.fixture
def s3():
    fake = FakeS3()
    with (
        patch("hubra.core.services.backup._get_s3_client", return_value=fake),
        patch("hubra.core.services.backup.subprocess.run", side_effect=_tools),
    ):
        yield fake


def _club(db, key=None):
    from hubra.core.models.tenant import Tenant

    slug = f"club-{uuid.uuid4().hex[:8]}"
    tenant = Tenant(name=slug, slug=slug, plan="starter", backup_public_key=key)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def _open(blob: bytes, private_key: str, tmp_path) -> bytes:
    src = tmp_path / "x.dump.age"
    src.write_bytes(blob)
    dst = tmp_path / "x.dump"
    backup_crypto.decrypt(str(src), str(dst), private_key)
    return dst.read_bytes()


def test_club_backup_opens_with_install_or_club_key_only(age_config, db, s3, tmp_path):
    from hubra.core.services.backup import BackupService

    club = _club(db, CLUB_PUB)
    record = BackupService.create_backup("manual", "t", club.id)
    assert record.status == "completed", record.error_message
    assert record.s3_key.endswith(".dump.age")
    blob = s3.objects[record.s3_key]
    assert b"PGDMP" not in blob

    assert _open(blob, INSTALL_PRIV, tmp_path) == b"PGDMP-club-data"
    assert _open(blob, CLUB_PRIV, tmp_path) == b"PGDMP-club-data"
    with pytest.raises(RuntimeError, match="age decryption failed"):
        _open(blob, OTHER_PRIV, tmp_path)
    with pytest.raises(backup_crypto.MissingPrivateKey):
        _open(blob, "", tmp_path)


def test_global_backup_is_not_encrypted_to_club_keys(age_config, db, s3, tmp_path):
    from hubra.core.services.backup import BackupService

    _club(db, CLUB_PUB)
    record = BackupService.create_backup("manual", "t")
    with pytest.raises(RuntimeError):
        _open(s3.objects[record.s3_key], CLUB_PRIV, tmp_path)


def test_verify_without_private_key_checks_the_file_only(age_config, db, s3):
    from hubra.core.services.backup import BackupService

    record = BackupService.create_backup("manual", "t")
    checked = BackupService.verify_backup(record.id)
    assert checked.verified_ok is True and checked.table_count is None

    full = BackupService.verify_backup(record.id, INSTALL_PRIV)
    assert full.verified_ok is True and full.table_count == 2


def test_verify_notices_a_changed_file(age_config, db, s3):
    from hubra.core.services.backup import BackupService

    record = BackupService.create_backup("manual", "t")
    s3.objects[record.s3_key] += b"tampered"
    checked = BackupService.verify_backup(record.id)
    assert checked.verified_ok is False
    assert "checksum" in checked.verify_error


def test_private_key_on_server_opens_without_asking(age_config, db, s3):
    from hubra.core.services.backup import BackupService

    record = BackupService.create_backup("manual", "t")
    age_config.config["BACKUP_PRIVATE_KEY"] = INSTALL_PRIV
    assert not backup_crypto.needs_private_key(record.s3_key)
    assert BackupService.verify_backup(record.id).table_count == 2


def test_old_gpg_backups_still_open_with_the_passphrase(age_config, db, s3):
    from hubra.core.services.backup import BackupService

    age_config.config["BACKUP_PUBLIC_KEY"] = ""
    record = BackupService.create_backup("manual", "t")
    assert record.s3_key.endswith(".dump.gpg")
    age_config.config["BACKUP_PUBLIC_KEY"] = INSTALL_PUB
    assert not backup_crypto.needs_private_key(record.s3_key)
    assert BackupService.verify_backup(record.id).table_count == 2


class TestRestoreApi:
    URL = "/api/v1/manager/platform/backups/"

    @pytest.fixture(autouse=True)
    def _platform_staff(self, seeded_db, db):
        seeded_db["user"].is_superadmin = True
        db.session.commit()
        yield
        seeded_db["user"].is_superadmin = False
        db.session.commit()

    def test_restore_asks_for_the_private_key(
        self, client, auth_headers, age_config, db, s3
    ):
        from hubra.core.services.backup import BackupService

        club = _club(db)
        record = BackupService.create_backup("manual", "t", club.id)
        resp = client.post(
            f"{self.URL}{record.id}/restore",
            json={"confirm": club.slug},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "PRIVATE_KEY_REQUIRED"

    def test_restore_rejects_something_that_is_not_a_key(
        self, client, auth_headers, age_config, db, s3
    ):
        from hubra.core.services.backup import BackupService

        club = _club(db)
        record = BackupService.create_backup("manual", "t", club.id)
        resp = client.post(
            f"{self.URL}{record.id}/restore",
            json={"confirm": club.slug, "private_key": "hunter2"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_restore_passes_the_key_through(
        self, client, auth_headers, age_config, db, s3
    ):
        from hubra.core.services.backup import BackupService

        club = _club(db)
        record = BackupService.create_backup("manual", "t", club.id)
        with patch.object(
            BackupService, "restore_club", return_value=record
        ) as restore:
            resp = client.post(
                f"{self.URL}{record.id}/restore",
                json={
                    "confirm": club.slug,
                    "private_key": f"# created: today\n{CLUB_PRIV}\n",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert CLUB_PRIV in restore.call_args.args[1]

    def test_backup_lists_say_when_a_key_is_needed(
        self, client, auth_headers, age_config, db, s3
    ):
        from hubra.core.services.backup import BackupService

        BackupService.create_backup("manual", "t")
        rows = client.get(self.URL, headers=auth_headers).get_json()
        assert rows[0]["needs_private_key"] is True
        cfg = client.get(f"{self.URL}config", headers=auth_headers).get_json()
        assert cfg["encryption_mode"] == "age"
        assert cfg["private_key_on_server"] is False


def test_sealed_key_expires(app):
    from hubra.core.crypto import InvalidToken, seal, unseal

    token = seal(CLUB_PRIV)
    assert unseal(token) == CLUB_PRIV
    with patch("cryptography.fernet.time.time", return_value=10**10):
        with pytest.raises(InvalidToken):
            unseal(token)


def test_club_key_cli(app, db):
    club = _club(db)
    runner = app.test_cli_runner()
    bad = runner.invoke(args=["backups", "club-key", club.slug, "nope"])
    assert bad.exit_code != 0
    ok = runner.invoke(args=["backups", "club-key", club.slug, CLUB_PUB])
    assert ok.exit_code == 0
    db.session.refresh(club)
    assert club.backup_public_key == CLUB_PUB
    runner.invoke(args=["backups", "club-key", club.slug, "--clear"])
    db.session.refresh(club)
    assert club.backup_public_key is None


def test_production_rejects_a_malformed_backup_key(monkeypatch):
    from cryptography.fernet import Fernet

    from hubra.core.config import ProductionConfig

    monkeypatch.setenv("SECRET_KEY", "s" * 64)
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 64)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("BACKUP_PUBLIC_KEY", INSTALL_PUB)
    ProductionConfig.validate()
    monkeypatch.setenv("BACKUP_PUBLIC_KEY", "age1short")
    with pytest.raises(RuntimeError, match="BACKUP_PUBLIC_KEY"):
        ProductionConfig.validate()
