"""Fixes from the security review of 28 Oct 2026 (C1, H1-H4).

Each test first shows the attack that used to work, now refused.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask_jwt_extended import decode_token

from hubra.core.models.member import Member
from hubra.core.models.role import Permission, Role, RolePermission
from hubra.core.models.setting import Setting
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant


def _user(db, email: str, **kw) -> User:
    user = User(
        email=email, first_name="A", last_name="B", private_email_verified=True, **kw
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    return user


def _member(db, user: User, seeded_db, roles=()) -> Member:
    member = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    member.roles = list(roles)
    db.session.add(member)
    db.session.flush()
    return member


def _login(client, email: str, password: str = "password123"):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


# ── C1: a club can't take over accounts it doesn't own ───────────────────────


class TestClubCannotTakeOverAccounts:
    def test_existing_account_is_not_pulled_into_the_club(
        self, client, auth_headers, db
    ):
        _user(db, "boss@platform.ch", is_superadmin=True)
        db.session.commit()
        resp = client.post(
            "/api/v1/members/",
            json={"email": "boss@platform.ch", "first_name": "x", "last_name": "y"},
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "ACCOUNT_EXISTS"

    def test_members_are_not_added_by_account_id(self, client, auth_headers, db):
        victim = _user(db, "someone@test.ch")
        db.session.commit()
        resp = client.post(
            "/api/v1/members/",
            json={"user_id": victim.id, "first_name": "x", "last_name": "y"},
        )
        assert resp.status_code == 400

    def test_no_password_or_email_change_for_an_account_used_elsewhere(
        self, client, auth_headers, db, seeded_db
    ):
        other = Tenant(name="Other", slug="other", plan="starter", status="active")
        db.session.add(other)
        db.session.flush()
        shared = _user(db, "shared@test.ch")
        db.session.add(UserTenant(user_id=shared.id, tenant_id=other.id))
        member = _member(db, shared, seeded_db)
        db.session.commit()

        resp = client.post(
            f"/api/v1/members/{member.id}/set-password",
            json={"password": "Attacker-Chosen-9!x"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "ACCOUNT_NOT_MANAGED"

        resp = client.patch(
            f"/api/v1/members/{member.id}", json={"email": "attacker@evil.ch"}
        )
        assert resp.status_code == 403
        assert db.session.get(User, shared.id).email == "shared@test.ch"

        # Club-only fields still work.
        resp = client.patch(f"/api/v1/members/{member.id}", json={"notes": "hi"})
        assert resp.status_code == 200

    def test_platform_staff_account_is_never_managed_by_a_club(
        self, client, auth_headers, db, seeded_db
    ):
        staff = _user(db, "staff@test.ch", is_superadmin=True)
        member = _member(db, staff, seeded_db)
        db.session.commit()
        resp = client.post(
            f"/api/v1/members/{member.id}/set-password",
            json={"password": "Attacker-Chosen-9!x"},
        )
        assert resp.status_code == 403

    def test_own_accounts_can_still_get_a_password(
        self, client, auth_headers, db, seeded_db
    ):
        own = _user(db, "own@test.ch")
        member = _member(db, own, seeded_db)
        db.session.commit()
        resp = client.post(
            f"/api/v1/members/{member.id}/set-password",
            json={"password": "New-Passw0rd-123!"},
        )
        assert resp.status_code == 200
        assert db.session.get(User, own.id).tokens_valid_after is not None

    def test_disabling_is_per_club(self, client, auth_headers, db, seeded_db):
        person = _user(db, "person@test.ch")
        member = _member(db, person, seeded_db)
        db.session.commit()
        resp = client.post(f"/api/v1/members/{member.id}/disable")
        assert resp.status_code == 200
        assert db.session.get(User, person.id).is_disabled is False
        assert db.session.get(Member, member.id).disabled_at is not None

    def test_enabling_does_not_undo_a_platform_block(
        self, client, auth_headers, db, seeded_db
    ):
        blocked = _user(db, "blocked@test.ch", is_superadmin=True, is_disabled=True)
        member = _member(db, blocked, seeded_db)
        db.session.commit()
        client.post(f"/api/v1/members/{member.id}/enable")
        assert db.session.get(User, blocked.id).is_disabled is True


# ── H1: impersonation stays in one club and ends on time ─────────────────────


class TestImpersonationIsBounded:
    def _setup(self, client, db, seeded_db):
        from hubra.api.global_rbac_seed import seed_global_rbac
        from hubra.core.models.global_role import GlobalRole, UserGlobalRole

        seed_global_rbac()
        club = Tenant(name="C", slug="club-c", plan="starter", status="active")
        db.session.add(club)
        db.session.flush()
        support_role = db.session.query(GlobalRole).filter_by(name="Support").one()
        db.session.add(
            UserGlobalRole(user_id=seeded_db["user"].id, role_id=support_role.id)
        )
        target = _user(db, "target@test.ch")
        db.session.add(UserTenant(user_id=target.id, tenant_id=club.id))
        _member(db, target, seeded_db)
        db.session.commit()
        _login(client, "admin@test.ch")
        return club, target

    def test_token_is_the_member_in_that_club_only(self, client, db, seeded_db):
        club, target = self._setup(client, db, seeded_db)
        resp = client.post(
            f"/api/v1/system/tenants/{club.id}/impersonate",
            json={"reason": "ticket", "user_id": target.id},
        )
        assert resp.status_code == 200
        claims = decode_token(client.get_cookie("refresh_token_cookie").value)
        assert "user_id" not in claims
        assert not str(claims["sub"]).startswith("user:")
        assert claims["exp"] - claims["iat"] <= 30 * 60

        # No club switch out of it.
        resp = client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "club-c"})
        assert resp.status_code == 401

        # Stopping gives the support user their own session back.
        resp = client.post("/api/v1/system/impersonation/stop")
        assert resp.status_code == 200
        claims = decode_token(client.get_cookie("access_token_cookie").value)
        assert claims["sub"] == f"user:{seeded_db['user'].id}"

    def test_platform_staff_cannot_be_impersonated(self, client, db, seeded_db):
        from hubra.core.models.global_role import GlobalRole, UserGlobalRole

        club, target = self._setup(client, db, seeded_db)
        boss = db.session.query(GlobalRole).filter_by(name="Superadmin").one()
        db.session.add(UserGlobalRole(user_id=target.id, role_id=boss.id))
        db.session.commit()
        resp = client.post(
            f"/api/v1/system/tenants/{club.id}/impersonate",
            json={"reason": "ticket", "user_id": target.id},
        )
        assert resp.status_code == 403

    def test_expired_impersonation_is_refused(self, app, client, seeded_db, db):
        from flask_jwt_extended import create_access_token

        member = seeded_db["admin"]
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        with app.test_request_context():
            token = create_access_token(
                identity=str(member.id),
                additional_claims={
                    "impersonator_id": 99,
                    "impersonator_user_id": 99,
                    "impersonation_expires_at": past,
                },
            )
        client.set_cookie("access_token_cookie", token)
        assert client.get("/api/v1/members/").status_code == 401


# ── H2: settings are checked in the namespace they live in ───────────────────


def _settings_writer(db, seeded_db, namespace: str = "general") -> None:
    role = Role(name="Editor", is_admin=False)
    perm = Permission(
        key=f"settings.{namespace}.write",
        display_name="w",
        resource=namespace,
        action="write",
        blueprint="settings",
    )
    db.session.add_all([role, perm])
    db.session.flush()
    db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    _member(db, _user(db, "ed@test.ch"), seeded_db, roles=[role])
    db.session.commit()


class TestSettingsNamespace:
    def test_general_writer_cannot_change_the_iban(self, client, seeded_db, db):
        db.session.add(
            Setting(
                key="Club.Banking.Iban",
                value="CH9300762011623852957",
                namespace="finance",
            )
        )
        _settings_writer(db, seeded_db)
        _login(client, "ed@test.ch")
        resp = client.put(
            "/api/v1/settings/Club.Banking.Iban",
            json={"value": "CH5604835012345678009", "namespace": "general"},
        )
        assert resp.status_code == 403
        assert db.session.get(Setting, "Club.Banking.Iban").value.startswith("CH93")

    def test_general_writer_cannot_create_the_iban(self, client, seeded_db, db):
        _settings_writer(db, seeded_db)
        _login(client, "ed@test.ch")
        resp = client.put(
            "/api/v1/settings/Club.Banking.Iban",
            json={"value": "CH5604835012345678009", "namespace": "general"},
        )
        assert resp.status_code == 403

    def test_writer_cannot_lock_a_setting(self, client, seeded_db, db):
        db.session.add(Setting(key="club.name", value="Club", namespace="general"))
        _settings_writer(db, seeded_db)
        _login(client, "ed@test.ch")
        resp = client.put(
            "/api/v1/settings/club.name", json={"value": "New", "restricted": True}
        )
        assert resp.status_code == 200
        assert db.session.get(Setting, "club.name").restricted is not True


# ── H3: removing someone ends their sessions ─────────────────────────────────


class TestSessionsEnd:
    def _signed_in(self, app, db, seeded_db):
        person = _user(db, "t@test.ch")
        member = _member(db, person, seeded_db, roles=[seeded_db["role"]])
        db.session.commit()
        other = app.test_client()
        assert _login(other, "t@test.ch").status_code == 200
        return other, person, member

    def test_disabled_member_is_signed_out(self, app, db, seeded_db):
        other, _person, member = self._signed_in(app, db, seeded_db)
        member.disabled_at = datetime.now(timezone.utc)
        db.session.commit()
        assert other.get("/api/v1/members/").status_code == 401
        assert other.post("/api/v1/auth/refresh").status_code == 401

    def test_archived_member_is_signed_out(self, app, db, seeded_db):
        other, _person, member = self._signed_in(app, db, seeded_db)
        member.archived_at = datetime.now(timezone.utc)
        db.session.commit()
        assert other.get("/api/v1/members/").status_code == 401

    def test_ended_sessions_are_refused(self, app, db, seeded_db):
        other, person, _member_ = self._signed_in(app, db, seeded_db)
        person.tokens_valid_after = datetime.now(timezone.utc) + timedelta(seconds=2)
        db.session.commit()
        assert other.get("/api/v1/members/").status_code == 401

    def test_logout_blocks_the_refresh_cookie(self, app, db, seeded_db):
        other, _person, _member_ = self._signed_in(app, db, seeded_db)
        refresh = other.get_cookie("refresh_token_cookie").value
        assert other.post("/api/v1/auth/logout").status_code == 204
        other.set_cookie("refresh_token_cookie", refresh)
        assert other.post("/api/v1/auth/refresh").status_code == 401


# ── H4: translations are cached per club ─────────────────────────────────────


def test_translation_cache_is_per_club(app, db):
    from unittest.mock import patch

    from hubra.api.i18n import services as i18n_services
    from hubra.core.models.translation import Translation

    i18n_services._mem_translations.clear()
    db.session.add(Translation(locale="de-CH", key="greeting", value="Club A"))
    db.session.commit()

    class _T:
        def __init__(self, tid):
            self.id = tid

    with patch("hubra.core.tenant.context.current_tenant", return_value=_T(1)):
        assert i18n_services.get_translations_dict("de-CH")["greeting"] == "Club A"
    db.session.query(Translation).delete()
    db.session.add(Translation(locale="de-CH", key="greeting", value="Club B"))
    db.session.commit()
    with patch("hubra.core.tenant.context.current_tenant", return_value=_T(2)):
        assert i18n_services.get_translations_dict("de-CH")["greeting"] == "Club B"
    i18n_services._mem_translations.clear()
