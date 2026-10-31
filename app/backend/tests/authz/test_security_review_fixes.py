"""Fixes from the security review of 28 Oct 2026 (C1, H1-H4).

Each test first shows the attack that used to work, now refused.
"""

from __future__ import annotations

import pytest

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
        boss = _user(db, "boss@platform.ch", is_superadmin=True)
        db.session.commit()
        client.post(
            "/api/v1/members/",
            json={"email": "boss@platform.ch", "first_name": "x", "last_name": "y"},
        )
        # Adding only ever invites: no member until the person accepts.
        assert db.session.query(Member).filter_by(user_id=boss.id).one_or_none() is None

    def test_members_are_not_added_by_account_id(self, client, auth_headers, db):
        victim = _user(db, "someone@test.ch")
        db.session.commit()
        resp = client.post(
            "/api/v1/members/",
            json={"user_id": victim.id, "first_name": "x", "last_name": "y"},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("elsewhere", [False, True])
    def test_club_never_sets_passwords_or_changes_accounts(
        self, client, auth_headers, db, seeded_db, elsewhere
    ):
        person = _user(db, "person@test.ch")
        if elsewhere:
            other = Tenant(name="Other", slug="other", plan="starter", status="active")
            db.session.add(other)
            db.session.flush()
            db.session.add(UserTenant(user_id=person.id, tenant_id=other.id))
        member = _member(db, person, seeded_db)
        db.session.commit()
        before = db.session.get(User, person.id).password_hash

        resp = client.post(
            f"/api/v1/members/{member.id}/set-password",
            json={"password": "Attacker-Chosen-9!x"},
        )
        assert resp.status_code in (404, 405)
        resp = client.post(f"/api/v1/members/{member.id}/verify-email")
        assert resp.status_code in (404, 405)
        assert db.session.get(User, person.id).password_hash == before

        for change in (
            {"email": "attacker@evil.ch"},
            {"first_name": "Mallory"},
            {"address_city": "Elsewhere"},
        ):
            resp = client.patch(f"/api/v1/members/{member.id}", json=change)
            assert resp.status_code == 403
            assert resp.get_json()["error"] == "ACCOUNT_FIELDS_READ_ONLY"
        assert db.session.get(User, person.id).email == "person@test.ch"

        # Club-only fields still work.
        resp = client.patch(f"/api/v1/members/{member.id}", json={"notes": "hi"})
        assert resp.status_code == 200

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
            json={"reason": "ticket", "user_id": target.id, "allow_changes": True},
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
        boss = db.session.query(GlobalRole).filter_by(name="Platform admin").one()
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

    def test_general_writer_cannot_create_the_finance_contact(self, client, seeded_db, db):
        """Club.Contact.FinanceEmail is printed on QR bills: a new one lands
        in the club namespace, not the one the request names."""
        _settings_writer(db, seeded_db)
        _login(client, "ed@test.ch")
        resp = client.put(
            "/api/v1/settings/Club.Contact.FinanceEmail",
            json={"value": "pay@evil.example", "namespace": "general"},
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


# ── M1: repeated wrong passwords lock the account ────────────────────────────


class TestLoginLockout:
    def test_sso_login_locks_after_five_failures(self, client, db, seeded_db):
        for _ in range(5):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "admin@test.ch", "password": "wrong"},
            )
            assert resp.status_code == 401
        # The right password no longer helps until the lock runs out.
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "ACCOUNT_LOCKED"

        user = db.session.get(User, seeded_db["user"].id)
        user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        assert resp.status_code == 200

    def test_a_good_login_resets_the_count(self, client, db, seeded_db):
        for _ in range(4):
            client.post(
                "/api/v1/auth/login",
                json={"email": "admin@test.ch", "password": "wrong"},
            )
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "admin@test.ch", "password": "password123"},
            ).status_code
            == 200
        )
        assert db.session.get(User, seeded_db["user"].id).failed_login_count == 0


# ── Roles: nobody hands out more than they have ──────────────────────────────


def _member_by_email(db, email):
    return (
        db.session.query(Member)
        .join(User, Member.user_id == User.id)
        .filter(User.email == email)
        .one()
    )


class TestNoRoleEscalation:
    def test_update_holder_cannot_make_themselves_admin(
        self, client, db, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(
            ["members.members.update", "members.members.read"], email="climber@test.ch"
        )
        me = _member_by_email(db, "climber@test.ch")
        own = [r.id for r in me.roles]
        resp = client.patch(
            f"/api/v1/members/{me.id}",
            json={"role_ids": [*own, seeded_db["role"].id], "tool_hours": 0},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "ADMIN_ONLY"

    def test_only_roles_within_your_own_permissions(
        self, client, db, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(
            ["members.members.update", "members.members.read"], email="giver@test.ch"
        )
        me = _member_by_email(db, "giver@test.ch")
        target = _member(db, _user(db, "target2@test.ch"), seeded_db)

        from tests.authz.conftest import _seed_permissions

        def role_with(name, keys):
            _seed_permissions(
                [k for k in keys if not db.session.query(Permission).filter_by(key=k).count()]
            )
            role = Role(name=name, is_default=False, is_admin=False)
            db.session.add(role)
            db.session.flush()
            for key in keys:
                perm = db.session.query(Permission).filter_by(key=key).one()
                db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
            db.session.commit()
            return role

        bigger = role_with("Treasurer", ["finance.invoices.create"])
        smaller = role_with("Reader", ["members.members.read"])

        resp = client.patch(
            f"/api/v1/members/{target.id}",
            json={"role_ids": [bigger.id], "tool_hours": 0},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "BEYOND_OWN_PERMISSIONS"

        resp = client.patch(
            f"/api/v1/members/{target.id}",
            json={"role_ids": [smaller.id], "tool_hours": 0},
            headers=headers,
        )
        assert resp.status_code == 200
        assert me.id != target.id

    def test_role_editor_cannot_add_permissions_they_lack(
        self, client, db, seeded_db, permissioned_member_factory
    ):
        headers = permissioned_member_factory(
            ["roles.roles.set_permissions", "roles.roles.create"]
        )
        role = Role(name="Helpers", is_default=False, is_admin=False)
        db.session.add(role)
        db.session.commit()
        from tests.authz.conftest import _seed_permissions

        _seed_permissions(["finance.invoices.create"])
        resp = client.put(
            f"/api/v1/roles/{role.id}/permissions",
            json={"permissions": ["finance.invoices.create"]},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "BEYOND_OWN_PERMISSIONS"
