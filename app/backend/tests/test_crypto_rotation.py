"""Changing FERNET_KEY keeps every stored secret readable, ``flask crypto
rotate`` moves them all to the new key, and each club's values are
encrypted with that club's own data key."""

import pytest
from cryptography.fernet import Fernet

from hubra.core import crypto
from hubra.core.config import ProductionConfig
from hubra.core.models.code import Code
from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.services import secret_store

OLD = Fernet.generate_key().decode()
NEW = Fernet.generate_key().decode()


@pytest.fixture
def keys(app):
    saved = app.config["FERNET_KEY"], app.config["FERNET_OLD_KEYS"]

    def use(current: str, old: str = "") -> None:
        app.config["FERNET_KEY"], app.config["FERNET_OLD_KEYS"] = current, old
        crypto._unwrapped.clear()  # a fresh process after the restart

    yield use
    app.config["FERNET_KEY"], app.config["FERNET_OLD_KEYS"] = saved


def _store(db, plaintext: str) -> Code:
    code = Code(name=plaintext, code=crypto.encrypt_code(plaintext, "codes.code"))
    db.session.add(code)
    db.session.commit()
    return code


def test_old_key_still_decrypts_after_the_switch(db, keys):
    keys(OLD)
    code = _store(db, "1234")
    keys(NEW, OLD)
    assert code.plain_code == "1234"
    # The value itself did not change: only the data key is wrapped by OLD.
    assert crypto.is_current(code.code, crypto.PLATFORM)
    assert not secret_store.check().clean


def test_values_from_before_fernet_key_still_decrypt(db, keys):
    keys("")
    code = _store(db, "legacy")
    keys(NEW)
    assert code.plain_code == "legacy"


def test_values_from_before_data_keys_still_decrypt_and_move_over(db, keys):
    from cryptography.fernet import Fernet as F

    keys(OLD)
    code = Code(name="x", code=F(OLD.encode()).encrypt(b"plain-fernet").decode())
    db.session.add(code)
    db.session.commit()
    assert code.plain_code == "plain-fernet"
    assert secret_store.rotate().rotated == 1
    db.session.expire_all()
    stored = db.session.get(Code, code.id)
    assert stored.code.startswith("hk1.p.1.")
    assert stored.plain_code == "plain-fernet"


def test_rotate_moves_everything_to_the_new_key(app, db, keys):
    keys(OLD)
    code = _store(db, "4321")
    db.session.add(
        PlatformSetting(
            key="mail.relay.password",
            secret=True,
            value=crypto.encrypt_code("pw", "platform_settings.value"),
        )
    )
    db.session.add(PlatformSetting(key="mail.relay.host", secret=False, value="smtp.x"))
    db.session.commit()

    keys(NEW, OLD)
    before = secret_store.check()
    # Both values sit on the platform data key: one key row to rewrap.
    assert (before.current, before.old_key, before.clean) == (2, 1, False)

    assert secret_store.rotate().rotated == 1
    db.session.expire_all()
    assert secret_store.check().clean

    keys(NEW)  # old key removed
    assert db.session.get(Code, code.id).plain_code == "4321"
    from hubra.core.services import platform_settings

    assert platform_settings.get("mail.relay.password") == "pw"
    assert platform_settings.get("mail.relay.host") == "smtp.x"


def test_rotate_leaves_values_no_key_opens(db, keys):
    keys(OLD)
    code = _store(db, "lost")
    keys(NEW)  # OLD forgotten
    report = secret_store.rotate()
    assert report.rotated == 0
    # The data key under the forgotten master key.
    assert [t.split(".")[-1] for t in report.unreadable] == ['"data_keys"']
    db.session.expire_all()
    keys(NEW, OLD)  # put back: nothing was overwritten
    assert db.session.get(Code, code.id).plain_code == "lost"


def test_cli_check_fails_until_rotated(app, db, keys):
    keys(OLD)
    _store(db, "9999")
    keys(NEW, OLD)
    runner = app.test_cli_runner()
    first = runner.invoke(args=["crypto", "check"])
    assert first.exit_code == 1 and "1 still on an old key" in first.output
    assert runner.invoke(args=["crypto", "rotate"]).exit_code == 0
    db.session.expire_all()
    last = runner.invoke(args=["crypto", "check"])
    assert last.exit_code == 0 and "OK" in last.output


def _prod_env(monkeypatch, **env):
    monkeypatch.setenv("SECRET_KEY", "s" * 64)
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 64)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.delenv("FERNET_KEY", raising=False)
    monkeypatch.delenv("FERNET_OLD_KEYS", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_production_requires_fernet_key(monkeypatch):
    _prod_env(monkeypatch)
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        ProductionConfig.validate()


def test_production_rejects_a_malformed_old_key(monkeypatch):
    _prod_env(monkeypatch, FERNET_KEY=NEW, FERNET_OLD_KEYS=f"{OLD}, not-a-key")
    with pytest.raises(RuntimeError, match="FERNET_OLD_KEYS"):
        ProductionConfig.validate()


def test_production_accepts_valid_keys(monkeypatch):
    _prod_env(monkeypatch, FERNET_KEY=NEW, FERNET_OLD_KEYS=OLD)
    ProductionConfig.validate()


def test_rotate_covers_every_club_schema(db, keys):
    from sqlalchemy import text

    if db.engine.dialect.name != "postgresql":
        pytest.skip("club schemas need Postgres")
    keys(OLD)
    value = crypto.encrypt_code("club-code", "codes.code", "c9901")
    db.session.execute(text("DROP SCHEMA IF EXISTS tenant_9901 CASCADE"))
    db.session.execute(text("CREATE SCHEMA tenant_9901"))
    db.session.execute(
        text("CREATE TABLE tenant_9901.codes (id int PRIMARY KEY, code text)")
    )
    db.session.execute(
        text("INSERT INTO tenant_9901.codes VALUES (1, :v)"), {"v": value}
    )
    db.session.commit()
    try:
        keys(NEW, OLD)
        assert secret_store.new_keys({"c9901"}).rotated == 1
        stored = db.session.scalar(text("SELECT code FROM tenant_9901.codes"))
        assert stored.startswith("hk1.c9901.2.")
        assert secret_store.rotate().rotated >= 1  # the data keys
        keys(NEW)
        assert crypto.decrypt_code(stored, "codes.code", "c9901") == "club-code"
    finally:
        db.session.execute(text("DROP SCHEMA tenant_9901 CASCADE"))
        db.session.commit()


def test_a_value_only_opens_in_its_own_club_and_column(app, db, keys):
    keys(NEW)
    value = crypto.encrypt_code("4711", "codes.code", "c1")
    assert crypto.decrypt_code(value, "codes.code", "c1") == "4711"
    with pytest.raises(crypto.InvalidToken):
        crypto.decrypt_code(value, "codes.code", "c2")
    with pytest.raises(crypto.InvalidToken):
        crypto.decrypt_code(value, "internal_keys.value", "c1")
    other = crypto.encrypt_code("4711", "codes.code", "c2")
    assert other.split(".")[1] == "c2"
    # Same version number, different key: c1's key cannot open c2's value.
    forged = "hk1.c1." + other.split(".", 2)[2]
    with pytest.raises(crypto.InvalidToken):
        crypto.decrypt_code(forged, "codes.code", "c1")


def test_the_club_comes_from_the_search_path(app, db, keys):
    from flask import g

    keys(NEW)
    g._search_path = "tenant_7, public"
    try:
        value = crypto.encrypt_code("x", "codes.code")
        assert value.startswith("hk1.c7.")
        assert crypto.decrypt_code(value, "codes.code") == "x"
        g._search_path = "tenant_8, public"
        with pytest.raises(crypto.InvalidToken):
            crypto.decrypt_code(value, "codes.code")
    finally:
        g._search_path = "public"
    db.session.rollback()


def test_new_club_key_keeps_old_values_readable(db, keys):
    keys(NEW)
    old_value = crypto.encrypt_code("v1", "codes.code", "c3")
    report = secret_store.new_keys({"c3"})
    assert report.new_keys == 1
    new_value = crypto.encrypt_code("v2", "codes.code", "c3")
    assert new_value.startswith("hk1.c3.2.")
    # A value from a backup made before still opens.
    assert crypto.decrypt_code(old_value, "codes.code", "c3") == "v1"


def test_deleting_a_club_destroys_its_keys(app, db, keys):
    from sqlalchemy import select

    from hubra.core.models.data_key import DataKey
    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.service import TenantService

    keys(NEW)
    tenant = Tenant(name="gone", slug="gone-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()
    scope = f"c{tenant.id}"
    value = crypto.encrypt_code("secret", "codes.code", scope)
    db.session.commit()
    with patch_drop():
        TenantService.delete_tenant(tenant.id, force=True)
    assert not db.session.scalars(select(DataKey).where(DataKey.scope == scope)).all()
    crypto._unwrapped.clear()
    with pytest.raises(crypto.InvalidToken):
        crypto.decrypt_code(value, "codes.code", scope)


def patch_drop():
    from unittest.mock import patch

    return patch("hubra.core.tenant.service.drop_tenant_schema")


class TestEncryptionApi:
    URL = "/api/v1/manager/platform/"

    @pytest.fixture(autouse=True)
    def _platform_staff(self, seeded_db, db):
        seeded_db["user"].is_superadmin = True
        db.session.commit()
        yield
        seeded_db["user"].is_superadmin = False
        db.session.commit()

    def test_status_rotate_and_new_keys(self, client, auth_headers, db, keys):
        from hubra.core.models.tenant import Tenant

        keys(OLD)
        _store(db, "1234")
        club = Tenant(name="Club", slug="enc-club", plan="starter")
        db.session.add(club)
        db.session.commit()
        keys(NEW, OLD)

        status = client.get(f"{self.URL}encryption", headers=auth_headers).get_json()
        assert status["master"] == {"fernet_key_set": True, "old_keys": 1}
        assert status["values"]["clean"] is False
        assert any(c["slug"] == "enc-club" for c in status["clubs"])

        done = client.post(f"{self.URL}encryption/rotate", headers=auth_headers)
        assert done.status_code == 200 and done.get_json()["clean"] is True

        fresh = client.post(
            f"{self.URL}encryption/rotate",
            json={"new_keys": True},
            headers=auth_headers,
        ).get_json()
        assert fresh["new_keys"] == 1 and fresh["rotated"] == 1  # the platform

        club_key = client.post(
            f"{self.URL}encryption/rotate",
            json={"new_keys": True, "tenant_id": club.id},
            headers=auth_headers,
        ).get_json()
        assert club_key["new_keys"] == 1
        status = client.get(f"{self.URL}encryption", headers=auth_headers).get_json()
        assert (
            next(c for c in status["clubs"] if c["slug"] == "enc-club")["key_version"]
            == 1
        )

    def test_club_backup_key(self, client, auth_headers, db):
        from hubra.core.models.tenant import Tenant

        club = Tenant(name="Club", slug="key-club", plan="starter")
        db.session.add(club)
        db.session.commit()
        url = f"{self.URL}clubs/{club.id}/backup-key"
        bad = client.put(url, json={"public_key": "age1nope"}, headers=auth_headers)
        assert bad.status_code == 400
        key = "age1" + "q" * 58
        ok = client.put(url, json={"public_key": key}, headers=auth_headers)
        assert ok.get_json()["backup_public_key"] == key
        cleared = client.put(url, json={"public_key": None}, headers=auth_headers)
        assert cleared.get_json()["backup_public_key"] is None
