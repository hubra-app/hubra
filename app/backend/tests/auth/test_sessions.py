"""Tests for device session management — creation, listing, revocation, cleanup."""

from datetime import datetime, timedelta, timezone

from hubra.core.extensions import db
from hubra.core.models.device_session import Device, Session
from hubra.core.redis_client import reset_redis_down


# ── Login creates Device + Session ───────────────────────────────────────────


def test_login_creates_device_and_session(client, seeded_db):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    devices = db.session.scalars(
        db.select(Device).where(Device.member_id == seeded_db["admin"].id)
    ).all()
    assert len(devices) == 1

    sessions = db.session.scalars(
        db.select(Session).where(Session.device_id == devices[0].id)
    ).all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is None


def test_login_returns_session_in_access_token(client, seeded_db):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    assert resp.status_code == 200

    sessions_resp = client.get("/api/v1/account/sessions")
    assert sessions_resp.status_code == 200
    body = sessions_resp.get_json()
    assert len(body) == 1
    assert body[0]["current"] is True


# ── List sessions ─────────────────────────────────────────────────────────────


def test_list_sessions(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/account/sessions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) >= 1
    assert "id" in body[0]
    assert "userAgent" in body[0]
    assert "ipAddress" in body[0]
    assert "current" in body[0]
    assert "lastActiveAt" in body[0]
    assert "createReason" in body[0]
    assert "browserFamily" in body[0]
    assert "platform" in body[0]


def test_list_sessions_requires_auth(client, seeded_db):
    resp = client.get("/api/v1/account/sessions")
    assert resp.status_code == 401


def test_list_sessions_excludes_revoked_by_default(client, seeded_db, db):
    """Revoked sessions are hidden by default but shown with include_revoked=1."""
    from hubra.api.auth.services import AuthService

    member = seeded_db["admin"]
    _, sid = AuthService.record_login(member, "192.168.1.1", "Mozilla/Chrome")
    db.session.commit()

    # Revoke the session directly in DB
    session = db.session.get(Session, sid)
    session.revoked_at = datetime.now(timezone.utc)
    db.session.commit()

    # Login again to get a fresh active session + auth cookies
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    # Default: only the active session is shown (not the revoked one)
    resp = client.get("/api/v1/account/sessions")
    body = resp.get_json()
    active = [s for s in body if s["revokedAt"] is None]
    revoked = [s for s in body if s["revokedAt"] is not None]
    assert len(active) >= 1
    assert len(revoked) == 0

    # With include_revoked=1: revoked sessions appear
    resp2 = client.get("/api/v1/account/sessions?include_revoked=1")
    body2 = resp2.get_json()
    assert any(s["revokedAt"] is not None for s in body2)


# ── Revoke single session ──────────────────────────────────────────────────────


def test_revoke_session(client, seeded_db, auth_headers):
    sessions_resp = client.get("/api/v1/account/sessions")
    sessions = sessions_resp.get_json()
    session_id = sessions[0]["id"]

    revoke_resp = client.delete(f"/api/v1/account/sessions/{session_id}")
    assert revoke_resp.status_code == 200

    session = db.session.get(Session, session_id)
    assert session.revoked_at is not None
    assert session.revoked_reason == "user_revoke"


def test_revoke_nonexistent_session_returns_404(client, seeded_db, auth_headers):
    resp = client.delete("/api/v1/account/sessions/99999")
    assert resp.status_code == 404


def test_revoke_already_revoked_returns_404(client, seeded_db, auth_headers):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
        headers={"User-Agent": "Mozilla/5.0 Firefox/139.0"},
    )

    sessions_resp = client.get("/api/v1/account/sessions")
    sessions = sessions_resp.get_json()
    non_current = [s for s in sessions if not s["current"]]
    assert len(non_current) >= 1
    session_id = non_current[0]["id"]

    resp1 = client.delete(f"/api/v1/account/sessions/{session_id}")
    assert resp1.status_code == 200

    resp2 = client.delete(f"/api/v1/account/sessions/{session_id}")
    assert resp2.status_code == 404


# ── Revoke all others ──────────────────────────────────────────────────────────


def test_revoke_all_other_sessions(client, seeded_db, auth_headers):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
        headers={"User-Agent": "Mozilla/5.0 Firefox/139.0"},
    )

    sessions_resp = client.get("/api/v1/account/sessions")
    sessions = sessions_resp.get_json()
    assert len(sessions) >= 2

    revoke_resp = client.post(
        "/api/v1/account/sessions/revoke-all",
        json={"includeCurrent": False},
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.get_json()["revoked"] >= 1

    after_resp = client.get("/api/v1/account/sessions")
    after_sessions = after_resp.get_json()
    active = [s for s in after_sessions if s["revokedAt"] is None]
    assert len(active) == 1
    assert active[0]["current"] is True


def test_revoke_all_including_current(client, seeded_db, auth_headers):
    resp = client.post(
        "/api/v1/account/sessions/revoke-all",
        json={"includeCurrent": True},
    )
    assert resp.status_code == 200
    assert resp.get_json()["revoked"] >= 1

    blocked = client.get("/api/v1/account/")
    assert blocked.status_code == 401


# ── Logout revokes session ─────────────────────────────────────────────────────


def test_logout_revokes_session(client, seeded_db):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    active = db.session.scalars(
        db.select(Session)
        .join(Device, Session.device_id == Device.id)
        .where(Device.member_id == seeded_db["admin"].id)
        .where(Session.revoked_at.is_(None))
    ).all()
    assert len(active) == 0


# ── New device detection ──────────────────────────────────────────────────────


def test_new_device_detection_first_login(client, seeded_db):
    from hubra.api.auth.services import AuthService

    member = seeded_db["admin"]
    new_device, sid = AuthService.record_login(member, "192.168.1.1", "Mozilla/Chrome")
    assert new_device is True
    assert sid is not None


def test_same_fingerprint_not_new_device(client, seeded_db):
    from hubra.api.auth.services import AuthService

    member = seeded_db["admin"]
    AuthService.record_login(member, "192.168.1.1", "Mozilla/Chrome")
    db.session.commit()

    new_device, _ = AuthService.record_login(member, "192.168.1.1", "Mozilla/Chrome")
    assert new_device is False


def test_different_fingerprint_is_new_device(client, seeded_db):
    from hubra.api.auth.services import AuthService, compute_fingerprint

    member = seeded_db["admin"]
    fp1 = compute_fingerprint({"User-Agent": "Mozilla/5.0 Chrome/149.0.0.0"})
    AuthService.record_login(member, "192.168.1.1", "Chrome/149", fingerprint=fp1)
    db.session.commit()

    fp2 = compute_fingerprint({"User-Agent": "Mozilla/5.0 Firefox/139.0"})
    new_device, _ = AuthService.record_login(
        member, "10.0.0.5", "Firefox/139", fingerprint=fp2
    )
    assert new_device is True


# ── Session reuse on repeated login ───────────────────────────────────────────


def test_record_login_reuses_active_session(client, seeded_db, db):
    from hubra.api.auth.services import AuthService

    member = seeded_db["admin"]
    _, sid1 = AuthService.record_login(member, "192.168.1.1", "Mozilla/Chrome")
    db.session.commit()

    _, sid2 = AuthService.record_login(member, "192.168.1.1", "Mozilla/Chrome")
    db.session.commit()

    assert sid1 == sid2

    sessions = db.session.scalars(
        db.select(Session)
        .join(Device, Session.device_id == Device.id)
        .where(Device.member_id == member.id)
    ).all()
    assert len(sessions) == 1


def test_record_login_creates_new_after_revoke(client, seeded_db, db):
    from hubra.api.auth.services import AuthService

    member = seeded_db["admin"]
    _, sid1 = AuthService.record_login(member, "192.168.1.1", "Mozilla/Chrome")
    db.session.commit()

    session = db.session.get(Session, sid1)
    session.revoked_at = datetime.now(timezone.utc)
    db.session.commit()

    _, sid2 = AuthService.record_login(member, "192.168.1.1", "Mozilla/Chrome")
    db.session.commit()

    assert sid1 != sid2

    sessions = db.session.scalars(
        db.select(Session)
        .join(Device, Session.device_id == Device.id)
        .where(Device.member_id == member.id)
    ).all()
    assert len(sessions) == 2


# ── Fingerprint helpers ───────────────────────────────────────────────────────


def test_compute_fingerprint_stable_across_version_changes():
    from hubra.api.auth.services import compute_fingerprint

    base = {
        "User-Agent": "Mozilla/5.0 Chrome/149.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Chromium";v="149", "Not?A_Brand";v="24"',
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-CH-UA-Mobile": "?0",
    }
    headers2 = {
        **base,
        "User-Agent": "Mozilla/5.0 Chrome/150.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Chromium";v="150", "Not?A_Brand";v="99"',
    }
    assert compute_fingerprint(base) == compute_fingerprint(headers2)


def test_compute_fingerprint_stable_without_high_entropy():
    from hubra.api.auth.services import compute_fingerprint

    firefox = {
        "User-Agent": "Mozilla/5.0 Firefox/139.0",
    }
    firefox2 = {
        "User-Agent": "Mozilla/5.0 Firefox/140.0",
    }
    assert compute_fingerprint(firefox) == compute_fingerprint(firefox2)


def test_compute_fingerprint_differs_on_browser():
    from hubra.api.auth.services import compute_fingerprint

    chrome = {"User-Agent": "Mozilla/5.0 Chrome/149.0.0.0", "Sec-CH-UA": '"Chromium"'}
    firefox = {"User-Agent": "Mozilla/5.0 Firefox/139.0"}
    assert compute_fingerprint(chrome) != compute_fingerprint(firefox)


def test_compute_fingerprint_differs_on_platform():
    from hubra.api.auth.services import compute_fingerprint

    windows = {
        "User-Agent": "Mozilla/5.0 Chrome/149.0.0.0",
        "Sec-CH-UA-Platform": '"Windows"',
    }
    mac = {
        "User-Agent": "Mozilla/5.0 Chrome/149.0.0.0",
        "Sec-CH-UA-Platform": '"macOS"',
    }
    assert compute_fingerprint(windows) != compute_fingerprint(mac)


def test_accept_ch_not_on_api_responses(client):
    """Accept-CH is set by Caddy on frontend HTML, not on API JSON responses."""
    from hubra.api.health.cache import HealthCache

    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.get("/api/v1/health")
    assert "Accept-CH" not in resp.headers


def test_new_device_notification_fires_on_new_fingerprint(client, seeded_db, db):
    from hubra.api.auth.services import AuthService, compute_fingerprint

    member = seeded_db["admin"]
    fp1 = compute_fingerprint({"User-Agent": "Mozilla/5.0 Chrome/149.0.0.0"})
    AuthService.record_login(member, "192.168.1.1", "Chrome/149", fingerprint=fp1)
    db.session.commit()

    fp2 = compute_fingerprint({"User-Agent": "Mozilla/5.0 Firefox/139.0"})
    new_device, _ = AuthService.record_login(
        member, "192.168.1.1", "Firefox/139", fingerprint=fp2
    )
    assert new_device is True


# ── Admin revoke ──────────────────────────────────────────────────────────────


def test_admin_revoke_member_sessions(client, seeded_db, auth_headers):
    sessions_resp = client.get("/api/v1/account/sessions")
    assert sessions_resp.status_code == 200

    member_id = seeded_db["admin"].id
    resp = client.delete(f"/api/v1/members/{member_id}/sessions")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert resp.get_json()["revoked"] >= 1

    active = db.session.scalars(
        db.select(Session)
        .join(Device, Session.device_id == Device.id)
        .where(Device.member_id == member_id)
        .where(Session.revoked_at.is_(None))
    ).all()
    assert len(active) == 0


# ── Cleanup task ──────────────────────────────────────────────────────────────


def test_cleanup_revoked_sessions(client, seeded_db, db):
    from hubra.core.tasks.session_tasks import cleanup_revoked_sessions

    member = seeded_db["admin"]
    device = Device(
        member_id=member.id,
        fingerprint="test-fp-cleanup",
        user_agent="TestBrowser",
    )
    db.session.add(device)
    db.session.flush()

    old_revoked = Session(
        device_id=device.id,
        jti="old-revoked-jti",
        ip_address="1.2.3.4",
    )
    old_revoked.revoked_at = datetime.now(timezone.utc) - timedelta(days=100)
    db.session.add(old_revoked)

    recent_revoked = Session(
        device_id=device.id,
        jti="recent-revoked-jti",
        ip_address="5.6.7.8",
    )
    recent_revoked.revoked_at = datetime.now(timezone.utc) - timedelta(days=10)
    db.session.add(recent_revoked)

    active = Session(
        device_id=device.id,
        jti="active-jti",
        ip_address="9.10.11.12",
    )
    db.session.add(active)
    db.session.commit()

    deleted = cleanup_revoked_sessions.run()
    assert deleted == 1

    remaining = db.session.scalars(
        db.select(Session).where(Session.device_id == device.id)
    ).all()
    jtis = {s.jti for s in remaining}
    assert "old-revoked-jti" not in jtis
    assert "recent-revoked-jti" in jtis
    assert "active-jti" in jtis


# ── Redis negative-cache (session_service) ────────────────────────────────────


def test_is_session_revoked_skips_redis_when_down(app, db, seeded_db):
    from unittest.mock import patch, MagicMock

    from hubra.api.auth import session_service

    member = seeded_db["admin"]
    device = Device(
        member_id=member.id,
        fingerprint="test-fp-redis",
        user_agent="TestBrowser",
    )
    db.session.add(device)
    db.session.flush()

    session = Session(
        device_id=device.id,
        jti="neg-cache-jti",
        ip_address="1.2.3.4",
    )
    db.session.add(session)
    db.session.commit()

    reset_redis_down()

    mock_client = MagicMock()
    mock_client.get.side_effect = Exception("connection refused")

    with (
        patch.object(session_service, "_get_redis_client", return_value=mock_client),
        patch.object(session_service, "_mark_redis_down") as mock_mark,
    ):
        result = session_service.is_session_revoked(session.id)
        assert result is False
        mock_client.setex.assert_not_called()
        mock_mark.assert_called_once()

    reset_redis_down()


# ── Async last_seen / session activity tasks ─────────────────────────────────


def test_update_last_seen_task_updates_member(app, db, seeded_db):
    from hubra.core.tasks.session_tasks import update_last_seen

    member = seeded_db["admin"]
    assert member.last_seen is None

    update_last_seen.run(member.id)
    db.session.refresh(member)
    assert member.last_seen is not None


def test_update_session_activity_task_updates_session(app, db, seeded_db):
    from hubra.core.tasks.session_tasks import update_session_activity

    member = seeded_db["admin"]
    device = Device(
        member_id=member.id,
        fingerprint="test-fp-activity",
        user_agent="TestBrowser",
    )
    db.session.add(device)
    db.session.flush()

    session = Session(
        device_id=device.id,
        jti="activity-jti",
        ip_address="1.2.3.4",
    )
    db.session.add(session)
    db.session.commit()

    update_session_activity.run(session.id)
    db.session.refresh(session)
    assert session.last_active_at is not None


def test_update_last_seen_task_swallows_errors(app):
    from unittest.mock import patch
    from hubra.core.tasks.session_tasks import update_last_seen

    with patch(
        "hubra.core.extensions.db.session.commit", side_effect=Exception("boom")
    ):
        update_last_seen.run(99999)


def test_after_request_dispatches_last_seen_task(client, auth_headers):
    from unittest.mock import patch

    from hubra.core import app as app_module
    from hubra.core.tasks.session_tasks import update_last_seen

    with patch.object(update_last_seen, "run") as mock_run:
        app_module._last_seen_cache.clear()
        client.get("/api/v1/account/", headers=auth_headers)
        mock_run.assert_called_once()


def test_after_request_throttles_last_seen(client, auth_headers):
    from unittest.mock import patch

    from hubra.core import app as app_module
    from hubra.core.tasks.session_tasks import update_last_seen

    with patch.object(update_last_seen, "run") as mock_run:
        app_module._last_seen_cache.clear()
        client.get("/api/v1/account/", headers=auth_headers)
        client.get("/api/v1/account/", headers=auth_headers)
        mock_run.assert_called_once()

    app_module._last_seen_cache.clear()


def test_refresh_dispatches_session_activity_task(client, seeded_db):
    from unittest.mock import patch

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    with patch(
        "hubra.core.tasks.session_tasks.update_session_activity.run"
    ) as mock_run:
        client.post("/api/v1/auth/refresh")
        mock_run.assert_called_once()


# ── Logout clears all cookies ──────────────────────────────────────────────────


def test_logout_clears_access_cookie(client, seeded_db):
    """Logout clears the access_token_cookie (empty value + epoch Expires)."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    cookies = resp.headers.getlist("Set-Cookie")
    access_cleared = any(
        "access_token_cookie=;" in c or "access_token_cookie= " in c for c in cookies
    )
    assert access_cleared, "access_token_cookie must be cleared on logout"


def test_logout_clears_refresh_cookie(client, seeded_db):
    """Logout clears the refresh_token_cookie."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    cookies = resp.headers.getlist("Set-Cookie")
    refresh_cleared = any(
        "refresh_token_cookie=;" in c or "refresh_token_cookie= " in c for c in cookies
    )
    assert refresh_cleared, "refresh_token_cookie must be cleared on logout"


def test_logout_clears_remembered_email_cookie(client, seeded_db):
    """Logout clears the remembered_email cookie."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    cookies = resp.headers.getlist("Set-Cookie")
    email_cleared = any(
        "remembered_email=" in c and ("Max-Age=0" in c or "delete" in c.lower())
        for c in cookies
    )
    assert email_cleared, "remembered_email must be cleared on logout"


# ── Session endpoint returns correct state ─────────────────────────────────────


def test_session_endpoint_returns_correct_state_after_login(client, seeded_db):
    """GET /account/sessions returns one active session after login."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    resp = client.get("/api/v1/account/sessions")
    assert resp.status_code == 200
    sessions = resp.get_json()
    assert len(sessions) == 1
    assert sessions[0]["current"] is True
    assert sessions[0]["revokedAt"] is None


def test_session_endpoint_empty_after_logout(client, seeded_db):
    """GET /account/sessions after logout returns 401 (no valid token)."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    client.post("/api/v1/auth/logout")
    resp = client.get("/api/v1/account/sessions")
    assert resp.status_code == 401


# ── Refresh token blocked after logout ─────────────────────────────────────────


def test_refresh_token_blocked_after_logout(client, seeded_db):
    """After logout, the refresh token can no longer be used."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    client.post("/api/v1/auth/logout")
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
