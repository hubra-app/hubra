"""Tests for domain CRUD API and DNS verification.

Domain routes are tenant-scoped (require tenant admin). DNS lookups
are mocked so tests run without network access. The tenant context is
injected via patching ``current_tenant`` directly.
"""

from unittest.mock import patch, MagicMock

import pytest

from hubra.core.models.domain import Domain
from hubra.core.models.tenant import Tenant


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def tenant_ctx(db, seeded_db):
    """Create a tenant and provide a context manager that patches current_tenant.

    Yields the tenant. Use within tests that call admin routes — the
    ``current_tenant`` function in the admin routes module is patched
    to return this tenant, and the middleware's search_path is bypassed.
    """
    tenant = Tenant(name="Test Club", slug="test-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()

    with (
        patch(
            "hubra.api.admin.routes.current_tenant",
            return_value=tenant,
        ),
        patch("hubra.core.tenant.context.set_search_path"),
    ):
        yield tenant


@pytest.fixture
def auth_headers(client, seeded_db):
    """Login as admin."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    return {}


# ── Domain CRUD tests ───────────────────────────────────────────────────────


def test_list_domains_empty(tenant_ctx, client, auth_headers):
    """Listing domains on a new tenant returns empty list."""
    resp = client.get("/api/v1/admin/domains", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["domains"] == []


def test_add_domain_success(tenant_ctx, client, auth_headers, db):
    """Adding a domain creates it with a verification token."""
    resp = client.post(
        "/api/v1/admin/domains",
        json={"domain": "example.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["domain"]["domain"] == "example.com"
    assert body["domain"]["verification_status"] == "pending"
    assert body["domain"]["verified"] is False
    # Only a verified domain can be the primary one.
    assert body["domain"]["is_primary"] is False
    assert body["domain"]["verification_token"] is not None
    assert body["txt_record"]["name"] == "_hubra-verify.example.com"
    assert body["txt_record"]["value"].startswith("hubra-verify=")
    assert body["domain"]["txt_record"] == body["txt_record"]


def test_add_domain_validation_error(tenant_ctx, client, auth_headers):
    """Invalid domain returns 422."""
    resp = client.post(
        "/api/v1/admin/domains",
        json={"domain": "notadomain"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_add_domain_duplicate(tenant_ctx, client, auth_headers, db):
    """Duplicate domain returns 409."""
    db.session.add(
        Domain(
            tenant_id=tenant_ctx.id,
            domain="example.com",
            verification_token="existingtoken",
        )
    )
    db.session.commit()

    resp = client.post(
        "/api/v1/admin/domains",
        json={"domain": "example.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.parametrize(
    "age_hours,verified,status",
    [(1, False, 409), (100, False, 201), (100, True, 409)],
)
def test_another_clubs_claim_is_held_only_while_fresh(
    tenant_ctx, client, auth_headers, db, age_hours, verified, status
):
    """An unproven claim by another club blocks others for 72 hours, then lapses."""
    from datetime import datetime, timedelta, timezone

    other = Tenant(name="Other", slug="other-club", plan="starter")
    db.session.add(other)
    db.session.flush()
    db.session.add(
        Domain(
            tenant_id=other.id,
            domain="claimed.example",
            verification_token="theirs",
            verified=verified,
            created_at=datetime.now(timezone.utc) - timedelta(hours=age_hours),
        )
    )
    db.session.commit()

    resp = client.post(
        "/api/v1/admin/domains",
        json={"domain": "claimed.example"},
        headers=auth_headers,
    )
    assert resp.status_code == status
    if status == 201:
        row = db.session.query(Domain).filter_by(domain="claimed.example").one()
        assert row.tenant_id == tenant_ctx.id


def test_add_domain_second_not_primary(tenant_ctx, client, auth_headers, db):
    """Second domain added is not primary by default."""
    client.post(
        "/api/v1/admin/domains",
        json={"domain": "first.com"},
        headers=auth_headers,
    )
    resp = client.post(
        "/api/v1/admin/domains",
        json={"domain": "second.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.get_json()["domain"]["is_primary"] is False


def test_verify_domain_success(tenant_ctx, client, auth_headers, db):
    """DNS verification succeeds when TXT record matches."""
    domain = Domain(
        tenant_id=tenant_ctx.id,
        domain="example.com",
        verification_token="abc123",
        verification_status="pending",
    )
    db.session.add(domain)
    db.session.commit()

    mock_answer = MagicMock()
    mock_answer.strings = [b"verevia-verify=abc123"]
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = [mock_answer]

    with patch("dns.resolver.Resolver", return_value=mock_resolver):
        resp = client.post(
            f"/api/v1/admin/domains/{domain.id}/verify",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["verified"] is True
    assert body["domain"]["verification_status"] == "verified"
    assert body["domain"]["verified"] is True
    assert body["domain"]["verified_at"] is not None


def test_verify_domain_not_found(tenant_ctx, client, auth_headers):
    """Verifying a non-existent domain returns 404."""
    resp = client.post(
        "/api/v1/admin/domains/99999/verify",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_verify_domain_wrong_token(tenant_ctx, client, auth_headers, db):
    """DNS verification fails when TXT record doesn't match."""
    domain = Domain(
        tenant_id=tenant_ctx.id,
        domain="example.com",
        verification_token="correcttoken",
        verification_status="pending",
    )
    db.session.add(domain)
    db.session.commit()

    mock_answer = MagicMock()
    mock_answer.strings = [b"verevia-verify=wrongtoken"]
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = [mock_answer]

    with patch("dns.resolver.Resolver", return_value=mock_resolver):
        resp = client.post(
            f"/api/v1/admin/domains/{domain.id}/verify",
            headers=auth_headers,
        )

    assert resp.status_code == 202
    body = resp.get_json()
    assert body["verified"] is False
    assert body["domain"]["verification_status"] == "pending"


def test_remove_domain(tenant_ctx, client, auth_headers, db):
    """Removing a domain deletes it."""
    domain = Domain(
        tenant_id=tenant_ctx.id,
        domain="example.com",
        verification_token="abc123",
    )
    db.session.add(domain)
    db.session.commit()
    did = domain.id

    resp = client.delete(
        f"/api/v1/admin/domains/{did}",
        headers=auth_headers,
    )
    assert resp.status_code == 204
    assert db.session.get(Domain, did) is None


def test_remove_domain_not_found(tenant_ctx, client, auth_headers):
    resp = client.delete(
        "/api/v1/admin/domains/99999",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_remove_primary_promotes_next(tenant_ctx, client, auth_headers, db):
    """Removing the primary domain promotes the next verified one to primary."""
    d1 = Domain(
        tenant_id=tenant_ctx.id, domain="first.com", verification_token="t1",
        verified=True, verification_status="verified", is_primary=True,
    )
    pending = Domain(
        tenant_id=tenant_ctx.id, domain="pending.com", verification_token="tp"
    )
    d2 = Domain(
        tenant_id=tenant_ctx.id, domain="second.com", verification_token="t2",
        verified=True, verification_status="verified",
    )
    db.session.add_all([d1, pending, d2])
    db.session.commit()
    d1_id = d1.id
    d2_id = d2.id
    pending_id = pending.id

    client.delete(
        f"/api/v1/admin/domains/{d1_id}",
        headers=auth_headers,
    )

    d2_refresh = db.session.get(Domain, d2_id)
    assert d2_refresh.is_primary is True
    assert db.session.get(Domain, pending_id).is_primary is False


def test_set_primary_domain(tenant_ctx, client, auth_headers, db):
    """Setting a verified domain as primary works."""
    d1 = Domain(
        tenant_id=tenant_ctx.id,
        domain="first.com",
        verification_token="t1",
        is_primary=True,
        verified=True,
        verification_status="verified",
    )
    d2 = Domain(
        tenant_id=tenant_ctx.id,
        domain="second.com",
        verification_token="t2",
        verified=True,
        verification_status="verified",
    )
    db.session.add_all([d1, d2])
    db.session.commit()

    resp = client.patch(
        f"/api/v1/admin/domains/{d2.id}/primary",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["domain"]["is_primary"] is True

    d1_refresh = db.session.get(Domain, d1.id)
    assert d1_refresh.is_primary is False


def test_set_primary_unverified_domain(tenant_ctx, client, auth_headers, db):
    """Setting an unverified domain as primary returns 422."""
    domain = Domain(
        tenant_id=tenant_ctx.id,
        domain="unverified.com",
        verification_token="t1",
        verified=False,
        verification_status="pending",
    )
    db.session.add(domain)
    db.session.commit()

    resp = client.patch(
        f"/api/v1/admin/domains/{domain.id}/primary",
        headers=auth_headers,
    )
    assert resp.status_code == 422
