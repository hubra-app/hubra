"""Tests for tenant admin API — CRUD, authorization, search, soft-delete.

Tests use cookie-based JWT auth. A superadmin User is created and linked
to a Member so login works via the standard auth flow.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.tenant import Tenant, GlobalAuditEntry


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def superadmin_db(seeded_db, db):
    """Mark the seeded User as superadmin."""
    user = seeded_db["user"]
    user.is_superadmin = True
    db.session.add(user)
    db.session.commit()
    return {**seeded_db, "user": user}


@pytest.fixture
def superadmin_headers(client, superadmin_db):
    """Login as superadmin and return auth cookies (stored on client)."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    return {}


@pytest.fixture
def normal_headers(client, seeded_db):
    """Login as a regular (non-superadmin) admin."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    return {}


@pytest.fixture
def sample_tenants(db):
    """Create sample tenants for list/search/pagination tests."""
    tenants = [
        Tenant(name="Acme Corp", slug="acme-corp", plan="growth"),
        Tenant(name="Beta Club", slug="beta-club", plan="starter"),
        Tenant(name="Gamma Org", slug="gamma-org", plan="enterprise"),
    ]
    db.session.add_all(tenants)
    db.session.commit()
    return tenants


# ── Authorization tests ─────────────────────────────────────────────────────


def test_list_tenants_unauthenticated(client):
    """Unauthenticated request is rejected."""
    resp = client.get("/api/v1/system/tenants")
    assert resp.status_code == 401


def test_list_tenants_non_superadmin(client, normal_headers):
    """Non-superadmin gets 403."""
    resp = client.get("/api/v1/system/tenants", headers=normal_headers)
    assert resp.status_code == 403


def test_list_tenants_superadmin(client, superadmin_headers):
    """Superadmin can list tenants."""
    resp = client.get("/api/v1/system/tenants", headers=superadmin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "tenants" in body
    assert "total" in body
    assert "page" in body
    assert "per_page" in body


# ── CRUD tests ──────────────────────────────────────────────────────────────


def test_create_tenant_success(client, superadmin_headers, db):
    """Create a new tenant via the API."""
    with (
        patch("hubra.core.tenant.service.create_tenant_schema"),
        patch("hubra.core.tenant.service._seed_tenant"),
    ):
        resp = client.post(
            "/api/v1/system/tenants",
            json={
                "name": "New Club",
                "slug": "new-club",
                "plan": "starter",
            },
            headers=superadmin_headers,
        )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["tenant"]["name"] == "New Club"
    assert body["tenant"]["slug"] == "new-club"
    assert body["tenant"]["plan"] == "starter"
    assert "provisioning_status_url" in body


def test_create_tenant_validation_error(client, superadmin_headers):
    """Missing fields returns 422."""
    resp = client.post(
        "/api/v1/system/tenants",
        json={"slug": "test"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 422


def test_create_tenant_invalid_plan(client, superadmin_headers):
    """Invalid plan returns 422."""
    resp = client.post(
        "/api/v1/system/tenants",
        json={"name": "Test", "slug": "test-club", "plan": "invalid"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 422


def test_get_tenant_success(client, superadmin_headers, sample_tenants):
    """Get a single tenant by ID."""
    resp = client.get(
        f"/api/v1/system/tenants/{sample_tenants[0].id}",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["tenant"]["name"] == "Acme Corp"
    assert "usage" in body["tenant"]


def test_get_tenant_not_found(client, superadmin_headers):
    resp = client.get(
        "/api/v1/system/tenants/99999",
        headers=superadmin_headers,
    )
    assert resp.status_code == 404


def test_update_tenant(client, superadmin_headers, sample_tenants, db):
    """Patch tenant name and plan."""
    tid = sample_tenants[0].id
    resp = client.patch(
        f"/api/v1/system/tenants/{tid}",
        json={"name": "Updated Name", "plan": "enterprise"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["tenant"]["name"] == "Updated Name"
    assert body["tenant"]["plan"] == "enterprise"

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.update")
    )
    assert entry is not None
    assert entry.details["name"] == "Updated Name"


def test_update_tenant_invalid_plan(client, superadmin_headers, sample_tenants):
    resp = client.patch(
        f"/api/v1/system/tenants/{sample_tenants[0].id}",
        json={"plan": "invalid"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 422


def test_update_tenant_not_found(client, superadmin_headers):
    resp = client.patch(
        "/api/v1/system/tenants/99999",
        json={"name": "Nope"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 404


# ── Soft-delete tests ───────────────────────────────────────────────────────


def test_soft_delete_tenant(client, superadmin_headers, sample_tenants, db):
    """DELETE without force=true performs a soft-delete."""
    tid = sample_tenants[0].id
    resp = client.delete(
        f"/api/v1/system/tenants/{tid}",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200

    tenant = db.session.get(Tenant, tid)
    assert tenant is not None
    assert tenant.deleted_at is not None
    assert tenant.status == "archived"

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "tenant.soft_delete")
    )
    assert entry is not None


def test_soft_delete_excludes_from_list(client, superadmin_headers, sample_tenants, db):
    """Soft-deleted tenants are excluded from list by default."""
    tid = sample_tenants[0].id
    client.delete(
        f"/api/v1/system/tenants/{tid}",
        headers=superadmin_headers,
    )

    resp = client.get(
        "/api/v1/system/tenants",
        headers=superadmin_headers,
    )
    body = resp.get_json()
    slugs = [t["slug"] for t in body["tenants"]]
    assert "acme-corp" not in slugs
    assert body["total"] == 2


def test_include_deleted_param(client, superadmin_headers, sample_tenants):
    """include_deleted=1 shows soft-deleted tenants."""
    tid = sample_tenants[0].id
    client.delete(
        f"/api/v1/system/tenants/{tid}",
        headers=superadmin_headers,
    )

    resp = client.get(
        "/api/v1/system/tenants?include_deleted=1",
        headers=superadmin_headers,
    )
    body = resp.get_json()
    assert body["total"] == 3


@patch("hubra.core.tenant.service.drop_tenant_schema")
def test_force_delete_tenant(mock_drop, client, superadmin_headers, sample_tenants, db):
    """DELETE with force=true permanently deletes the tenant."""
    tid = sample_tenants[0].id
    resp = client.delete(
        f"/api/v1/system/tenants/{tid}?force=1",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    assert db.session.get(Tenant, tid) is None
    mock_drop.assert_called_once_with(tid)


def test_delete_tenant_not_found(client, superadmin_headers):
    resp = client.delete(
        "/api/v1/system/tenants/99999",
        headers=superadmin_headers,
    )
    assert resp.status_code == 404


# ── Status transition tests ─────────────────────────────────────────────────


def test_disable_tenant(client, superadmin_headers, sample_tenants):
    resp = client.post(
        f"/api/v1/system/tenants/{sample_tenants[0].id}/disable",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["tenant"]["status"] == "suspended"


def test_enable_tenant(client, superadmin_headers, sample_tenants, db):
    tid = sample_tenants[0].id
    tenant = db.session.get(Tenant, tid)
    tenant.status = "suspended"
    db.session.commit()

    resp = client.post(
        f"/api/v1/system/tenants/{tid}/enable",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["tenant"]["status"] == "active"


def test_archive_tenant(client, superadmin_headers, sample_tenants):
    resp = client.post(
        f"/api/v1/system/tenants/{sample_tenants[0].id}/archive",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["tenant"]["status"] == "archived"


def test_disable_tenant_not_found(client, superadmin_headers):
    resp = client.post(
        "/api/v1/system/tenants/99999/disable",
        headers=superadmin_headers,
    )
    assert resp.status_code == 404


# ── Search and pagination tests ─────────────────────────────────────────────


def test_list_tenants_search(client, superadmin_headers, sample_tenants):
    resp = client.get(
        "/api/v1/system/tenants?search=acme",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 1
    assert body["tenants"][0]["slug"] == "acme-corp"


def test_list_tenants_filter_by_plan(client, superadmin_headers, sample_tenants):
    resp = client.get(
        "/api/v1/system/tenants?plan=starter",
        headers=superadmin_headers,
    )
    body = resp.get_json()
    assert body["total"] == 1
    assert body["tenants"][0]["plan"] == "starter"


def test_list_tenants_filter_by_status(client, superadmin_headers, sample_tenants):
    resp = client.get(
        "/api/v1/system/tenants?status=active",
        headers=superadmin_headers,
    )
    body = resp.get_json()
    assert body["total"] == 3


def test_list_tenants_sort_by_name_desc(client, superadmin_headers, sample_tenants):
    resp = client.get(
        "/api/v1/system/tenants?sort_by=name&sort_dir=desc",
        headers=superadmin_headers,
    )
    body = resp.get_json()
    names = [t["name"] for t in body["tenants"]]
    assert names == sorted(names, reverse=True)


def test_list_tenants_pagination(client, superadmin_headers, sample_tenants):
    resp = client.get(
        "/api/v1/system/tenants?per_page=2&page=1",
        headers=superadmin_headers,
    )
    body = resp.get_json()
    assert len(body["tenants"]) == 2
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["per_page"] == 2

    resp2 = client.get(
        "/api/v1/system/tenants?per_page=2&page=2",
        headers=superadmin_headers,
    )
    body2 = resp2.get_json()
    assert len(body2["tenants"]) == 1
    assert body2["page"] == 2


# ── Stats and provisioning status ───────────────────────────────────────────


def test_get_tenant_stats(client, superadmin_headers, sample_tenants):
    resp = client.get(
        f"/api/v1/system/tenants/{sample_tenants[0].id}/stats",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    stats = resp.get_json()["stats"]
    assert "member_count" in stats
    assert "domain_count" in stats
    assert "plan" in stats


def test_get_tenant_stats_not_found(client, superadmin_headers):
    resp = client.get(
        "/api/v1/system/tenants/99999/stats",
        headers=superadmin_headers,
    )
    assert resp.status_code == 404


def test_get_provisioning_status(client, superadmin_headers, sample_tenants):
    resp = client.get(
        f"/api/v1/system/tenants/{sample_tenants[0].id}/provisioning-status",
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "complete"
    assert body["tenant_id"] == sample_tenants[0].id


def test_global_audit_pages_entries_of_one_moment_in_order(
    client, db, superadmin_headers
):
    """Entries with one timestamp neither repeat nor go missing across pages."""
    from datetime import datetime, timezone

    same = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for _ in range(5):
        db.session.add(GlobalAuditEntry(action="tie.test", time=same))
    db.session.commit()

    seen = []
    for page in (1, 2, 3):
        resp = client.get(
            f"/api/v1/system/audit?action=tie.test&page={page}&per_page=2",
            headers=superadmin_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total"] == 5  # what the filter leaves, not the whole table
        seen += [e["id"] for e in body["entries"]]
    assert seen == sorted(seen, reverse=True)
    assert len(set(seen)) == 5

    resp = client.get(
        "/api/v1/system/audit?page=x&per_page=0", headers=superadmin_headers
    )
    assert resp.status_code == 200


def test_user_search_counts_only_matching_users(client, db, superadmin_headers):
    from hubra.core.models.user import User

    user = User(email="findme@test.ch", first_name="F", last_name="M")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    body = client.get(
        "/api/v1/system/users?search=findme", headers=superadmin_headers
    ).get_json()
    assert [u["email"] for u in body["users"]] == ["findme@test.ch"]
    assert body["total"] == 1
