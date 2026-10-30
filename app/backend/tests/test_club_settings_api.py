"""Tests for club settings (branding) API.

Club settings are stored in ``Tenant.settings['branding']`` and managed
via the admin blueprint at ``/api/v1/admin/club-settings``.
"""

from unittest.mock import patch

import pytest

from hubra.core.models.tenant import Tenant


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def tenant_ctx(db, seeded_db):
    """Create a tenant and patch current_tenant to return it."""
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


# ── Club settings tests ─────────────────────────────────────────────────────


def test_get_club_settings_empty(tenant_ctx, client, auth_headers):
    """A new tenant has no branding yet; the form still shows the club's name."""
    resp = client.get("/api/v1/admin/club-settings", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["settings"] == {"club_name": "Test Club"}


def test_update_club_settings_basic(tenant_ctx, client, auth_headers, db):
    """Updating club name and description persists in Tenant.settings."""
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={
            "club_name": "My Awesome Club",
            "club_description": "The best club ever",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["settings"]["club_name"] == "My Awesome Club"
    assert body["settings"]["club_description"] == "The best club ever"

    tenant = db.session.get(Tenant, tenant_ctx.id)
    assert tenant.settings["branding"]["club_name"] == "My Awesome Club"
    # The club list, invites and the manager portal read tenant.name.
    assert tenant.name == "My Awesome Club"


def test_blank_club_name_keeps_the_tenant_name(tenant_ctx, client, auth_headers, db):
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={"club_name": "  "},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert db.session.get(Tenant, tenant_ctx.id).name == "Test Club"


def test_update_club_settings_colors(tenant_ctx, client, auth_headers):
    """Updating brand colors works with valid hex values."""
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={
            "primary_color": "#6366f1",
            "secondary_color": "#2596be",
            "accent_color": "#f59e0b",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["settings"]["primary_color"] == "#6366f1"


def test_update_club_settings_invalid_color(tenant_ctx, client, auth_headers):
    """Invalid hex color returns 422."""
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={"primary_color": "not-a-color"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_update_club_settings_invalid_timezone(tenant_ctx, client, auth_headers):
    """Invalid timezone returns 422."""
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={"timezone": "Mars/Olympus"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_update_club_settings_valid_timezone(tenant_ctx, client, auth_headers):
    """Valid timezone persists."""
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={"timezone": "Europe/Zurich"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["settings"]["timezone"] == "Europe/Zurich"


def test_update_club_settings_locale(tenant_ctx, client, auth_headers):
    """Valid locale persists."""
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={"locale": "de-CH"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["settings"]["locale"] == "de-CH"


def test_update_club_settings_privacy(tenant_ctx, client, auth_headers, db):
    """Privacy toggles persist as booleans."""
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={
            "member_directory_visible": True,
            "public_group_listing": False,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["settings"]["member_directory_visible"] is True
    assert body["settings"]["public_group_listing"] is False


def test_update_club_settings_announcement(tenant_ctx, client, auth_headers):
    """Announcement banner settings persist."""
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={
            "announcement_banner_text": "Annual meeting on Friday!",
            "announcement_banner_active": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["settings"]["announcement_banner_text"] == "Annual meeting on Friday!"
    assert body["settings"]["announcement_banner_active"] is True


def test_update_club_settings_merges(tenant_ctx, client, auth_headers):
    """Partial update merges with existing settings."""
    client.patch(
        "/api/v1/admin/club-settings",
        json={"club_name": "First Update"},
        headers=auth_headers,
    )
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={"club_description": "Second Update"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["settings"]["club_name"] == "First Update"
    assert body["settings"]["club_description"] == "Second Update"


def test_update_club_settings_creates_audit_entry(tenant_ctx, client, auth_headers, db):
    from sqlalchemy import select

    from hubra.core.models.tenant import GlobalAuditEntry

    client.patch(
        "/api/v1/admin/club-settings",
        json={"club_name": "Audited Club"},
        headers=auth_headers,
    )

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(
            GlobalAuditEntry.action == "club_settings.update"
        )
    )
    assert entry is not None
    assert "club_name" in entry.details["fields"]


def test_get_club_settings_after_update(tenant_ctx, client, auth_headers):
    """GET returns the previously saved settings."""
    client.patch(
        "/api/v1/admin/club-settings",
        json={"club_name": "Persisted Club", "primary_color": "#ff0000"},
        headers=auth_headers,
    )

    resp = client.get("/api/v1/admin/club-settings", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["settings"]["club_name"] == "Persisted Club"
    assert body["settings"]["primary_color"] == "#ff0000"


def test_membership_rules_persist_and_are_checked(tenant_ctx, client, auth_headers):
    """Invite-only and invite validity are club settings; validity is 1-60 days."""
    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={"join_requests_open": False, "invite_valid_days": 30},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["settings"]["join_requests_open"] is False
    assert resp.get_json()["settings"]["invite_valid_days"] == 30

    resp = client.patch(
        "/api/v1/admin/club-settings",
        json={"invite_valid_days": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_club_profile_for_members(tenant_ctx, client, auth_headers, db):
    """Members read the club's name, look and active banner, not its rules."""
    tenant_ctx.settings = {
        "branding": {
            "primary_color": "#123456",
            "announcement_banner_text": "  GV am Freitag  ",
            "announcement_banner_active": True,
            "join_requests_open": False,
        }
    }
    db.session.commit()
    with patch("hubra.core.tenant.context.current_tenant", return_value=tenant_ctx):
        body = client.get("/api/v1/settings/club-profile").get_json()
    assert body["club_name"] == "Test Club"
    assert body["primary_color"] == "#123456"
    assert body["banner"] == "GV am Freitag"
    assert "join_requests_open" not in body
    assert body["logo_version"] is None


def test_club_profile_links_the_logo_instead_of_embedding_it(
    tenant_ctx, client, auth_headers, db
):
    logo = "data:image/png;base64," + "A" * 4000
    tenant_ctx.settings = {"branding": {"logo": logo}}
    db.session.commit()
    with patch("hubra.core.tenant.context.current_tenant", return_value=tenant_ctx):
        body = client.get("/api/v1/settings/club-profile").get_json()
    assert "logo" not in body
    assert body["slug"] == tenant_ctx.slug
    assert len(body["logo_version"]) == 12

    tenant_ctx.settings = {
        "branding": {
            "announcement_banner_text": "Old news",
            "announcement_banner_active": False,
        }
    }
    db.session.commit()
    with patch("hubra.core.tenant.context.current_tenant", return_value=tenant_ctx):
        body = client.get("/api/v1/settings/club-profile").get_json()
    assert body["banner"] is None


def test_club_profile_needs_sign_in(client, db):
    assert client.get("/api/v1/settings/club-profile").status_code == 401


# ── Logo ────────────────────────────────────────────────────────────────────

# A 1×1 transparent PNG.
_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
_PNG_URL = f"data:image/png;base64,{_PNG_B64}"


def test_logo_must_be_an_image_data_url(tenant_ctx, client, auth_headers):
    for bad in (
        "https://example.com/logo.png",
        "data:text/html;base64,PHNjcmlwdD4=",
        "data:image/png,not-base64",
    ):
        resp = client.patch("/api/v1/admin/club-settings", json={"logo": bad})
        assert resp.status_code == 422, bad

    resp = client.patch("/api/v1/admin/club-settings", json={"logo": _PNG_URL})
    assert resp.status_code == 200
    assert resp.get_json()["settings"]["logo"] == _PNG_URL


def test_null_clears_a_setting(tenant_ctx, client, auth_headers, db):
    client.patch(
        "/api/v1/admin/club-settings",
        json={"logo": _PNG_URL, "primary_color": "#123456"},
    )
    resp = client.patch(
        "/api/v1/admin/club-settings", json={"logo": None, "club_name": "Neu"}
    )
    assert resp.status_code == 200
    settings = resp.get_json()["settings"]
    assert "logo" not in settings
    assert settings["primary_color"] == "#123456"
    assert db.session.get(Tenant, tenant_ctx.id).settings["branding"].get("logo") is None


def test_logo_is_served_as_an_image(client, db):
    tenant = Tenant(
        name="Logo Club",
        slug="logo-club",
        plan="starter",
        settings={"branding": {"logo": _PNG_URL}},
    )
    db.session.add(tenant)
    db.session.add(Tenant(name="Plain Club", slug="plain-club", plan="starter"))
    db.session.commit()

    resp = client.get("/api/v1/system/clubs/logo-club/logo")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert "sandbox" in resp.headers["Content-Security-Policy"]

    assert client.get("/api/v1/system/clubs/plain-club/logo").status_code == 404
    assert client.get("/api/v1/system/clubs/nope/logo").status_code == 404
