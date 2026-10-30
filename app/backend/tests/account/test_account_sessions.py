"""Sign-ins to the account itself (SSO portal) are listed and can be ended."""

from __future__ import annotations

PASSWORD = "password123"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"


def _browser(app, ua, email="solo@test.ch"):
    client = app.test_client()
    client.environ_base["HTTP_USER_AGENT"] = ua
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.get_json()
    return client


def _user(db, email="solo@test.ch"):
    from hubra.core.models.user import User

    user = User(email=email, first_name="Solo", last_name="User")
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def _sessions(client):
    resp = client.get("/api/v1/account/all-sessions")
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def test_each_browser_is_listed_once(app, db):
    _user(db)
    chrome = _browser(app, CHROME)
    _browser(app, FIREFOX)
    _browser(app, CHROME)  # the same browser again keeps its row

    sessions = _sessions(chrome)
    assert sorted(s["browserFamily"] for s in sessions) == ["Chrome", "Firefox"]
    assert all(s["club"] is None for s in sessions)
    current = [s for s in sessions if s["current"]]
    assert [s["browserFamily"] for s in current] == ["Chrome"]
    assert current[0]["platform"] == "Windows"


def test_ending_a_sign_in_signs_that_browser_out(app, db):
    _user(db)
    chrome = _browser(app, CHROME)
    firefox = _browser(app, FIREFOX)
    other = next(s for s in _sessions(chrome) if not s["current"])

    resp = chrome.delete(f"/api/v1/account/account-sessions/{other['id']}")
    assert resp.status_code == 200
    assert firefox.get("/api/v1/account/profile").status_code == 401
    assert [s["browserFamily"] for s in _sessions(chrome)] == ["Chrome"]
    # Twice, or someone else's: not found.
    resp = chrome.delete(f"/api/v1/account/account-sessions/{other['id']}")
    assert resp.status_code == 404


def test_cannot_end_another_accounts_sign_in(app, db):
    _user(db)
    _user(db, "other@test.ch")
    mine = _browser(app, CHROME)
    theirs = _browser(app, FIREFOX, "other@test.ch")
    their_id = _sessions(theirs)[0]["id"]

    resp = mine.delete(f"/api/v1/account/account-sessions/{their_id}")
    assert resp.status_code == 404
    assert theirs.get("/api/v1/account/profile").status_code == 200


def test_logout_ends_the_sign_in(app, db):
    _user(db)
    chrome = _browser(app, CHROME)
    firefox = _browser(app, FIREFOX)
    assert firefox.post("/api/v1/auth/logout").status_code == 204
    assert [s["browserFamily"] for s in _sessions(chrome)] == ["Chrome"]


def test_sign_out_everywhere_keeps_this_browser(app, db):
    _user(db)
    chrome = _browser(app, CHROME)
    firefox = _browser(app, FIREFOX)

    resp = chrome.post("/api/v1/account/all-sessions/revoke-all")
    assert resp.status_code == 200
    assert resp.get_json()["revoked"] == 1
    assert firefox.get("/api/v1/account/profile").status_code == 401
    sessions = _sessions(chrome)
    assert [(s["browserFamily"], s["current"]) for s in sessions] == [("Chrome", True)]


def test_password_change_hides_the_other_sign_ins(app, db):
    _user(db)
    chrome = _browser(app, CHROME)
    _browser(app, FIREFOX)

    resp = chrome.post(
        "/api/v1/account/password",
        json={"currentPassword": PASSWORD, "newPassword": "An0ther-Long-Passw0rd!"},
    )
    assert resp.status_code == 200, resp.get_json()
    assert [s["browserFamily"] for s in _sessions(chrome)] == ["Chrome"]


def _join_club(db, user):
    """A club for *user*, added after the sign-in (the tests' clubs share one
    schema, so a member that exists at sign-in turns it into a club login)."""
    from hubra.core.models.member import Member
    from hubra.core.models.tenant import Tenant
    from hubra.core.models.user_tenant import UserTenant

    tenant = Tenant(name="Club A", slug="club-a", plan="starter", status="active")
    db.session.add(tenant)
    db.session.flush()
    db.session.add(UserTenant(user_id=user.id, tenant_id=tenant.id))
    db.session.add(Member(user_id=user.id, status="active"))
    db.session.commit()


def test_a_club_switch_keeps_the_sign_in(app, db):
    user = _user(db)
    chrome = _browser(app, CHROME)
    firefox = _browser(app, FIREFOX)
    account_sid = next(s["id"] for s in _sessions(chrome) if s["current"])
    _join_club(db, user)
    resp = chrome.post("/api/v1/auth/switch-tenant", json={"tenantSlug": "club-a"})
    assert resp.status_code == 200, resp.get_json()

    sessions = _sessions(chrome)
    current = {(s["club"] or {}).get("slug"): s["id"] for s in sessions if s["current"]}
    assert current.get(None) == account_sid
    assert "club-a" in current

    # Ended from another browser: the club token from it stops working too.
    resp = firefox.delete(f"/api/v1/account/account-sessions/{account_sid}")
    assert resp.status_code == 200
    assert chrome.get("/api/v1/account/all-sessions").status_code == 401
