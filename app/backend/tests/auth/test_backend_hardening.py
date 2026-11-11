"""Hardening from the backend image security audit (2026-11-11)."""

from unittest.mock import patch


def test_unknown_address_checks_a_password_too(client, seeded_db):
    """An address without an account costs one password check, like a wrong
    password does, so the response time doesn't tell that nobody uses it."""
    from argon2 import PasswordHasher

    from hubra.core.models import user as user_module

    calls = []

    class Counting(PasswordHasher):
        def verify(self, hash, password):  # noqa: A002 (argon2's name)
            calls.append(password)
            return super().verify(hash, password)

    fast = Counting(time_cost=1, memory_cost=1024, parallelism=1)
    with patch.object(user_module, "_ph", fast):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.ch", "password": "wrongpassword"},
        )
    assert resp.status_code == 401
    assert calls == ["wrongpassword"]


def test_burn_password_check_takes_odd_input():
    from hubra.core.models.user import burn_password_check

    burn_password_check(None)
    burn_password_check({"not": "text"})
    burn_password_check("x")

