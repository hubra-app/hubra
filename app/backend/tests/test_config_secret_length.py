"""Production warns about a short signing secret instead of starting quietly."""

import logging

from hubra.core.config import ProductionConfig


def test_short_secret_is_warned_about(monkeypatch, caplog):
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("JWT_SECRET_KEY", "changeme")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("FERNET_KEY", "k")
    with caplog.at_level(logging.WARNING):
        ProductionConfig.validate()
    warned = [r.getMessage() for r in caplog.records if "shorter than 32" in r.getMessage()]
    assert len(warned) == 1 and warned[0].startswith("JWT_SECRET_KEY")
