"""Sign-in and password reset answer wrong JSON types with a 4xx, not a 500."""

import pytest


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/v1/auth/login", {"email": 5, "password": "x"}),
        ("/api/v1/auth/login", {"email": "a@b.ch", "password": 5}),
        ("/api/v1/auth/login", [1]),
        ("/api/v1/auth/forgot-password", {"email": ["a@b.ch"]}),
        ("/api/v1/auth/reset-password", {"token": 5, "password": "x"}),
        ("/api/v1/auth/reset-password", {"token": "abc", "password": 5}),
        ("/api/v1/auth/switch-tenant", {"tenantSlug": {"a": 1}}),
    ],
)
def test_wrong_types_are_refused(client, seeded_db, path, body):
    resp = client.post(path, json=body)
    assert resp.status_code < 500, (path, body, resp.get_json())
