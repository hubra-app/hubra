"""A club that requires two-factor sign-in (Settings › Verein › Mitgliedschaft).

"admins" asks it of owners and admins (also through a function), "all" of
every member. Without it the club does not open: /auth/switch-tenant and a
club sign-in answer 403 MFA_REQUIRED_BY_CLUB, and a club session from before
the rule ends.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from hubra.api.auth import mfa
from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant

PASSWORD = "password123"


def _require(db, tenant: Tenant, scope: str) -> None:
    settings = dict(tenant.settings or {})
    settings["branding"] = {**settings.get("branding", {}), "mfa_required": scope}
    tenant.settings = settings
    db.session.commit()


def _turn_on_app(db, user) -> None:
    user.totp_secret = mfa._seal(mfa._new_secret(), mfa._SECRET)
    user.totp_enabled_at = datetime.now(timezone.utc)
    db.session.commit()


def _sign_in(client, email="user@test.ch"):
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.get_json()


def _switch(client, slug):
    return client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": slug})


def test_off_by_default(client, tenant_pair):
    _sign_in(client)
    assert _switch(client, "tenant-b").status_code == 200


def test_a_club_that_requires_it_does_not_open_without_it(client, db, tenant_pair):
    _require(db, tenant_pair["tenant_b"], "all")
    _sign_in(client)

    resp = _switch(client, "tenant-b")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MFA_REQUIRED_BY_CLUB"
    # Another club without the rule still opens.
    assert _switch(client, "tenant-a").status_code == 200


def test_a_passkey_counts(db, tenant_pair):
    from hubra.core.models.passkey import Passkey

    tenant, member, user = (
        tenant_pair["tenant_b"],
        tenant_pair["member_b"],
        tenant_pair["user"],
    )
    _require(db, tenant, "all")
    assert mfa.club_blocks(tenant, member, user) is True
    db.session.add(
        Passkey(
            user_id=user.id,
            credential_id="cred-1",
            public_key=b"k",
            sign_count=0,
            name="Key",
        )
    )
    db.session.commit()
    assert mfa.club_blocks(tenant, member, user) is False


def test_with_the_app_the_club_opens(client, db, tenant_pair):
    _require(db, tenant_pair["tenant_b"], "all")
    _turn_on_app(db, tenant_pair["user"])

    token = client.post(
        "/api/v1/auth/login", json={"email": "user@test.ch", "password": PASSWORD}
    ).get_json()["mfaToken"]
    with patch.object(mfa, "verify", return_value="totp"):
        resp = client.post(
            "/api/v1/auth/login/mfa", json={"mfaToken": token, "code": "1"}
        )
    assert resp.status_code == 200, resp.get_json()
    assert _switch(client, "tenant-b").status_code == 200


def test_admins_scope_asks_only_admins(db, tenant_pair):
    tenant = tenant_pair["tenant_b"]
    _require(db, tenant, "admins")
    plain = Member(user_id=tenant_pair["user"].id, status="active")
    db.session.add(plain)
    db.session.commit()

    assert mfa.club_requires(tenant, tenant_pair["member_b"]) is True
    assert mfa.club_requires(tenant, plain) is False
    _require(db, tenant, "all")
    assert mfa.club_requires(tenant, plain) is True


def test_an_unknown_value_counts_as_off(db, tenant_pair):
    _require(db, tenant_pair["tenant_b"], "sometimes")
    assert mfa.club_scope(tenant_pair["tenant_b"]) == "off"


def test_a_session_from_before_the_rule_ends(client, db, tenant_pair):
    _sign_in(client)
    assert _switch(client, "tenant-b").status_code == 200
    headers = {"X-Tenant-Slug": "tenant-b"}
    assert client.get("/api/v1/account/", headers=headers).status_code == 200

    _require(db, tenant_pair["tenant_b"], "all")
    resp = client.get("/api/v1/account/", headers=headers)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MFA_REQUIRED_BY_CLUB"

    # Out of the club, still signed in to the account (SSO works).
    status = client.get("/api/v1/account/mfa")
    assert status.status_code == 200, status.get_json()
    assert status.get_json()["clubsRequiring"] == [
        {"slug": "tenant-b", "name": "Tenant B"}
    ]


def test_the_club_list_and_account_page_name_the_clubs(client, db, tenant_pair):
    _require(db, tenant_pair["tenant_b"], "admins")
    _sign_in(client)

    tenants = client.get("/api/v1/account/my-tenants").get_json()["tenants"]
    flags = {t["tenant_slug"]: t["mfa_required"] for t in tenants}
    assert flags == {"tenant-a": False, "tenant-b": True}

    status = client.get("/api/v1/account/mfa").get_json()
    assert status["clubsRequiring"] == [{"slug": "tenant-b", "name": "Tenant B"}]


# ── Turning it on in the club settings ───────────────────────────────────────


@pytest.fixture
def club(db, seeded_db):
    tenant = Tenant(name="Test Club", slug="test-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()
    with (
        patch("hubra.api.admin.routes.current_tenant", return_value=tenant),
        patch("hubra.core.tenant.context.set_search_path"),
    ):
        yield tenant


def test_turning_it_on_needs_it_on_your_own_account(client, db, club, seeded_db):
    _sign_in(client, "admin@test.ch")
    resp = client.patch("/api/v1/admin/club-settings", json={"mfa_required": "all"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "MFA_SETUP_FIRST"

    # Off is always allowed.
    resp = client.patch("/api/v1/admin/club-settings", json={"mfa_required": "off"})
    assert resp.status_code == 200


def test_turning_it_on_with_two_factor(client, db, club, seeded_db):
    _sign_in(client, "admin@test.ch")
    _turn_on_app(db, seeded_db["user"])

    resp = client.patch("/api/v1/admin/club-settings", json={"mfa_required": "admins"})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["settings"]["mfa_required"] == "admins"

    resp = client.patch("/api/v1/admin/club-settings", json={"mfa_required": "maybe"})
    assert resp.status_code == 422


def test_settings_show_who_still_lacks_it(client, db, club, seeded_db):
    _sign_in(client, "admin@test.ch")
    body = client.get("/api/v1/admin/club-settings").get_json()
    assert body["mfa"]["membersWithout"] >= 1
    assert body["mfa"]["adminsWithout"] >= 1

    _turn_on_app(db, seeded_db["user"])
    after = client.get("/api/v1/admin/club-settings").get_json()["mfa"]
    assert after["membersWithout"] == body["mfa"]["membersWithout"] - 1
