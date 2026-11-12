"""Step-up for risky club actions (account_token.ensure_club_step_up,
POST /auth/step-up): bank details, deleting a member for good, giving
admin rights."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from hubra.core.models.role import Role
from tests.test_bank_settings_api import ADDRESS, IBAN, admin, tenant_ctx  # noqa: F401


@pytest.fixture
def enforced(app):
    app.config["STEP_UP_ENFORCED"] = True
    yield
    app.config["STEP_UP_ENFORCED"] = False


def test_bank_details_need_a_fresh_confirmation(
    enforced,
    tenant_ctx,  # noqa: F811
    admin,  # noqa: F811
):
    url = "/api/v1/admin/bank-settings"
    resp = admin.put(url, json={"iban": IBAN, **ADDRESS})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "STEP_UP_REQUIRED"

    status = admin.get("/api/v1/auth/step-up").get_json()
    assert status["sudoUntil"] is None and status["code"] is False

    bad = admin.post("/api/v1/auth/step-up", json={"password": "wrong"})
    assert bad.status_code == 400
    ok = admin.post("/api/v1/auth/step-up", json={"password": "password123"})
    assert ok.status_code == 200, ok.get_json()
    assert admin.get("/api/v1/auth/step-up").get_json()["sudoUntil"]

    assert admin.put(url, json={"iban": IBAN, **ADDRESS}).status_code == 200


def test_making_a_role_admin_needs_it(enforced, client, db, seeded_db):
    role = Role(name="Board", is_default=False, is_admin=False)
    db.session.add(role)
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    url = f"/api/v1/roles/{role.id}"
    # Renaming is not risky.
    assert client.patch(url, json={"name": "Vorstand"}).status_code == 200
    resp = client.patch(url, json={"is_admin": True})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "STEP_UP_REQUIRED"
    assert db.session.scalar(select(Role.is_admin).where(Role.id == role.id)) is False

    client.post("/api/v1/auth/step-up", json={"password": "password123"})
    assert client.patch(url, json={"is_admin": True}).status_code == 200


def test_off_in_tests_and_needs_a_sign_in(client, db, seeded_db, app):
    assert client.get("/api/v1/auth/step-up").status_code == 401
    assert client.post("/api/v1/auth/step-up", json={}).status_code == 401


def test_giving_a_member_an_admin_role_and_deleting_need_it(
    enforced, client, db, seeded_db
):
    from tests.helpers import add_member

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    member = add_member(
        client, {}, first_name="Ada", last_name="L", email="ada@test.ch"
    )
    member_id = member.get_json()["id"]
    admin_role = Role(name="Co-Admin", is_default=False, is_admin=True)
    plain_role = Role(name="Helper", is_default=False, is_admin=False)
    db.session.add_all([admin_role, plain_role])
    db.session.commit()
    url = f"/api/v1/members/{member_id}"
    # A role without admin rights: no confirmation.
    assert client.patch(url, json={"role_ids": [plain_role.id]}).status_code == 200
    resp = client.patch(url, json={"role_ids": [plain_role.id, admin_role.id]})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "STEP_UP_REQUIRED"
    assert client.delete(url).status_code == 403

    client.post("/api/v1/auth/step-up", json={"password": "password123"})
    resp = client.patch(url, json={"role_ids": [plain_role.id, admin_role.id]})
    assert resp.status_code == 200, resp.get_json()
