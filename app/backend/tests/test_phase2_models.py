"""Tests for Phase 2 identity & tenancy model extensions.

Verifies new columns and defaults on:
- UserTenant (status, is_owner, updated_at)
- TenantRequest (purpose, rejection_reason, created_tenant_id, reviewed_by FK)
- Tenant (locale, timezone)
- Role (is_system, is_owner)
- Function (grants_tenant_role_id, mailbox_ref, is_singleton)
- FunctionHolder (term_start, term_end)
"""

from datetime import date

from hubra.core.models.function import Function, FunctionHolder
from hubra.core.models.role import Role
from hubra.core.models.tenant import Tenant
from hubra.core.models.tenant_request import TenantRequest
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant


# ── UserTenant ────────────────────────────────────────────────────────────────


def test_user_tenant_status_defaults_active(db):
    user = User(email="test@example.com", first_name="Test", last_name="User")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    tenant = Tenant(name="Test Club", slug="test-club")
    db.session.add(tenant)
    db.session.flush()

    ut = UserTenant(user_id=user.id, tenant_id=tenant.id)
    db.session.add(ut)
    db.session.commit()

    assert ut.status == "active"
    assert ut.is_owner is False
    assert ut.updated_at is not None


def test_user_tenant_is_owner_can_be_true(db):
    user = User(email="owner@example.com", first_name="Owner", last_name="User")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    tenant = Tenant(name="Owner Club", slug="owner-club")
    db.session.add(tenant)
    db.session.flush()

    ut = UserTenant(user_id=user.id, tenant_id=tenant.id, is_owner=True)
    db.session.add(ut)
    db.session.commit()

    assert ut.is_owner is True


# ── TenantRequest ─────────────────────────────────────────────────────────────


def test_tenant_request_has_purpose_field(db):
    user = User(email="requester@example.com", first_name="Req", last_name="User")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    req = TenantRequest(
        user_id=user.id,
        name="My Club",
        slug="my-club",
        purpose="A makerspace for Zurich",
    )
    db.session.add(req)
    db.session.commit()

    assert req.purpose == "A makerspace for Zurich"


def test_tenant_request_has_rejection_reason(db):
    user = User(email="reject@example.com", first_name="Rej", last_name="User")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    req = TenantRequest(
        user_id=user.id,
        name="Bad Club",
        slug="bad-club",
        rejection_reason="Slug too similar to existing tenant",
    )
    db.session.add(req)
    db.session.commit()

    assert req.rejection_reason == "Slug too similar to existing tenant"


def test_tenant_request_purpose_nullable(db):
    user = User(email="nopurpose@example.com", first_name="No", last_name="Purpose")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    req = TenantRequest(user_id=user.id, name="No Purpose Club", slug="no-purpose")
    db.session.add(req)
    db.session.commit()

    assert req.purpose is None


# ── Tenant ────────────────────────────────────────────────────────────────────


def test_tenant_locale_defaults_de_ch(db):
    tenant = Tenant(name="Swiss Club", slug="swiss-club")
    db.session.add(tenant)
    db.session.commit()

    assert tenant.locale == "de-CH"


def test_tenant_timezone_defaults_europe_zurich(db):
    tenant = Tenant(name="TZ Club", slug="tz-club")
    db.session.add(tenant)
    db.session.commit()

    assert tenant.timezone == "Europe/Zurich"


def test_tenant_locale_can_be_overridden(db):
    tenant = Tenant(name="English Club", slug="english-club", locale="en-GB")
    db.session.add(tenant)
    db.session.commit()

    assert tenant.locale == "en-GB"


# ── Role ──────────────────────────────────────────────────────────────────────


def test_role_is_system_defaults_false(db):
    role = Role(name="Custom Role")
    db.session.add(role)
    db.session.commit()

    assert role.is_system is False
    assert role.is_owner is False


def test_role_is_system_can_be_true(db):
    role = Role(name="System Role", is_system=True)
    db.session.add(role)
    db.session.commit()

    assert role.is_system is True


def test_role_is_owner_can_be_true(db):
    role = Role(name="Owner", is_system=True, is_owner=True, is_admin=True)
    db.session.add(role)
    db.session.commit()

    assert role.is_owner is True
    assert role.is_system is True


# ── Function ──────────────────────────────────────────────────────────────────


def test_function_is_singleton_defaults_false(db):
    fn = Function(name="Test Function")
    db.session.add(fn)
    db.session.commit()

    assert fn.is_singleton is False
    assert fn.mailbox_ref is None
    assert fn.grants_tenant_role_id is None


def test_function_mailbox_ref_can_be_set(db):
    fn = Function(name="Mail Function", mailbox_ref="function@club.ch")
    db.session.add(fn)
    db.session.commit()

    assert fn.mailbox_ref == "function@club.ch"


def test_function_grants_tenant_role_id_nullable(db):
    fn = Function(name="No Grant Function")
    db.session.add(fn)
    db.session.commit()

    assert fn.grants_tenant_role_id is None


# ── FunctionHolder ────────────────────────────────────────────────────────────


def test_function_holder_term_dates_nullable(db):
    fn = Function(name="Term Function")
    db.session.add(fn)
    db.session.flush()

    holder = FunctionHolder(function_id=fn.id, member_id=1)
    db.session.add(holder)
    db.session.commit()

    assert holder.term_start is None
    assert holder.term_end is None


def test_function_holder_term_dates_can_be_set(db):
    fn = Function(name="Dated Function")
    db.session.add(fn)
    db.session.flush()

    holder = FunctionHolder(
        function_id=fn.id,
        member_id=1,
        term_start=date(2026, 1, 1),
        term_end=date(2026, 12, 31),
    )
    db.session.add(holder)
    db.session.commit()

    assert holder.term_start == date(2026, 1, 1)
    assert holder.term_end == date(2026, 12, 31)
