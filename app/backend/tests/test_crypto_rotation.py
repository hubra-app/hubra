"""Changing FERNET_KEY keeps every stored secret readable, and
``flask crypto rotate`` moves them all to the new key."""

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

    yield use
    app.config["FERNET_KEY"], app.config["FERNET_OLD_KEYS"] = saved


def _store(db, plaintext: str) -> Code:
    code = Code(name=plaintext, code=crypto.encrypt_code(plaintext))
    db.session.add(code)
    db.session.commit()
    return code


def test_old_key_still_decrypts_after_the_switch(db, keys):
    keys(OLD)
    code = _store(db, "1234")
    keys(NEW, OLD)
    assert code.plain_code == "1234"
    assert not crypto.is_current(code.code)


def test_values_from_before_fernet_key_still_decrypt(db, keys):
    keys("")
    code = _store(db, "legacy")
    keys(NEW)
    assert code.plain_code == "legacy"


def test_rotate_moves_everything_to_the_new_key(app, db, keys):
    keys(OLD)
    code = _store(db, "4321")
    db.session.add(
        PlatformSetting(
            key="mail.relay.password", secret=True, value=crypto.encrypt_code("pw")
        )
    )
    db.session.add(PlatformSetting(key="mail.relay.host", secret=False, value="smtp.x"))
    db.session.commit()

    keys(NEW, OLD)
    before = secret_store.check()
    assert (before.current, before.old_key, before.clean) == (0, 2, False)

    assert secret_store.rotate().rotated == 2
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
    assert report.rotated == 0 and sum(report.unreadable.values()) == 1
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
    value = crypto.encrypt_code("club-code")
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
        assert secret_store.rotate().rotated == 1
        stored = db.session.scalar(text("SELECT code FROM tenant_9901.codes"))
        keys(NEW)
        assert crypto.decrypt_code(stored) == "club-code"
    finally:
        db.session.execute(text("DROP SCHEMA tenant_9901 CASCADE"))
        db.session.commit()
