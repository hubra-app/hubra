"""Problem reports carry the session's last request ids (roadmap idea 70):
the report stores them, and staff see the error group a failed one hit."""

from __future__ import annotations

from unittest.mock import patch

from hubra.core.models.error_group import ErrorGroup
from hubra.core.models.support_case import SupportCase
from hubra.core.models.user import User
from hubra.core.services import error_tracker, support

PASSWORD = "password123"


def _staff(client, db) -> User:
    user = User(
        email="staff@test.ch", first_name="S", last_name="T", is_superadmin=True
    )
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    resp = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert resp.status_code == 200
    return user


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    def set(self, key, value, ex=None):
        self.data[key] = value

    def mget(self, keys):
        return [self.data.get(k) for k in keys]


def test_clean_requests_keeps_only_known_fields():
    out = support.clean_requests(
        [
            {
                "id": "abc-1",
                "method": "post",
                "path": "/members/?q=Anna",
                "status": 500,
                "code": "X",
            },
            {"id": "bad id!", "path": "/x"},
            {
                "id": "ok2",
                "method": "TRACE",
                "path": "no-slash",
                "status": True,
                "extra": 1,
            },
            "nope",
        ]
    )
    assert out == [
        {
            "id": "abc-1",
            "method": "POST",
            "path": "/members/",
            "status": 500,
            "code": "X",
        },
        {"id": "ok2"},
    ]
    assert support.clean_requests("x") == []
    assert (
        len(support.clean_requests([{"id": f"r{i}"} for i in range(30)]))
        == support.REQUESTS_MAX
    )


def test_report_stores_requests_and_staff_see_the_error(client, db):
    _staff(client, db)
    group = ErrorGroup(
        fingerprint="f" * 40, exc_type="KeyError", route="POST /api/v1/members/"
    )
    db.session.add(group)
    db.session.commit()
    fake = FakeRedis()
    with (
        patch("hubra.core.redis_client.get_redis_client", lambda *a, **k: fake),
        patch("hubra.core.request_id.current", lambda: "req500"),
    ):
        error_tracker._remember_request("f" * 40)
        resp = client.post(
            "/api/v1/global/support/cases",
            json={
                "kind": "bug",
                "title": "Speichern geht nicht",
                "description": "Fehler beim Speichern",
                "requests": [
                    {
                        "id": "req200",
                        "method": "GET",
                        "path": "/members/",
                        "status": 200,
                    },
                    {
                        "id": "req500",
                        "method": "POST",
                        "path": "/members/",
                        "status": 500,
                    },
                ],
            },
        )
        assert resp.status_code == 201, resp.get_json()
        case = db.session.get(SupportCase, resp.get_json()["id"])
        assert [r["id"] for r in case.details["requests"]] == ["req200", "req500"]
        detail = client.get(f"/api/v1/manager/support/cases/{case.id}").get_json()
    by_id = {r["id"]: r for r in detail["requests"]}
    assert by_id["req200"]["errorGroup"] is None
    assert by_id["req500"]["errorGroup"] == {
        "id": group.id,
        "type": "KeyError",
        "route": "POST /api/v1/members/",
        "status": "open",
    }


def test_errors_list_finds_one_group_by_id(client, db):
    _staff(client, db)
    a = ErrorGroup(fingerprint="a" * 40, exc_type="KeyError", route="GET /a")
    b = ErrorGroup(fingerprint="b" * 40, exc_type="ValueError", route="GET /b")
    db.session.add_all([a, b])
    db.session.commit()
    resp = client.get(f"/api/v1/platform/errors?status=all&q=%23{b.id}")
    assert resp.status_code == 200, resp.get_json()
    assert [g["id"] for g in resp.get_json()["errors"]] == [b.id]
