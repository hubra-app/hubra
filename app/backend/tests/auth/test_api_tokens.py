"""API tokens (docs/api-tokens.md): ``Authorization: Bearer hbr_…``.

A token acts as its person and passes only what they may do now AND what
its scopes allow. It never opens account, token, step-up or plugin routes,
never carries a cookie session along, and is bound to one club (personal and
club tokens) or to the platform API (read-only platform tokens).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hubra.core.auth import api_tokens, mfa
from hubra.core.models.api_token import ApiToken
from hubra.core.models.audit import AuditEntry
from hubra.core.models.role import Permission, Role, RolePermission

PASSWORD = "password123"
READ = "events.events.read"
CREATE = "events.events.create"


@pytest.fixture(autouse=True)
def _clean_limits():
    api_tokens.reset_rate_limits()
    yield
    api_tokens.reset_rate_limits()


@pytest.fixture
def catalog(db):
    rows = [
        Permission(
            key=k,
            display_name=k,
            resource="events",
            action=k.rsplit(".", 1)[-1],
            blueprint="events_bp",
        )
        for k in (READ, CREATE)
    ]
    db.session.add_all(rows)
    db.session.commit()
    return rows


_RECOVERY: list[str] = []


def _two_factor(db, user) -> None:
    user.totp_secret = mfa._seal(mfa._new_secret(), mfa._SECRET)
    user.totp_enabled_at = datetime.now(timezone.utc)
    _RECOVERY[:] = mfa.new_recovery_codes(user)
    db.session.commit()


def _login(client, email="user@test.ch"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json() or {}
    if body.get("mfaRequired"):
        resp = client.post(
            "/api/v1/auth/login/mfa",
            json={"mfaToken": body["mfaToken"], "code": _RECOVERY.pop()},
        )
        assert resp.status_code == 200, resp.get_json()
    return resp


def _sign_in(client, slug="tenant-a", email="user@test.ch"):
    _login(client, email)
    resp = client.post("/api/v1/auth/switch-tenant", json={"tenantSlug": slug})
    assert resp.status_code == 200, resp.get_json()


def _bearer(token: str, **extra) -> dict:
    return {"Authorization": f"Bearer {token}", **extra}


def _make(client, path="/api/v1/app/api-tokens/mine", **body):
    payload = {"name": "Script", "scopes": [READ], "days": 30, **body}
    return client.post(path, json=payload)


@pytest.fixture
def made(app, db, tenant_pair, catalog):
    """A personal read token of user@test.ch (admin) in tenant-a."""
    client = app.test_client()
    _sign_in(client)
    _two_factor(db, tenant_pair["user"])
    resp = _make(client)
    assert resp.status_code == 201, resp.get_json()
    return {"token": resp.get_json()["token"], "id": resp.get_json()["id"], **tenant_pair}


# ── Making tokens ───────────────────────────────────────────────────────────


def test_secret_is_shown_once_and_stored_as_hash(app, db, made, client):
    token = made["token"]
    assert token.startswith("hbr_pat_")
    row = db.session.get(ApiToken, made["id"])
    assert token not in (row.secret_hash, row.public_id)
    assert row.last4 == token[-4:]
    assert row.scopes == [READ]
    # Listing never shows the secret again.
    other = app.test_client()
    _sign_in(other)
    listed = other.get("/api/v1/app/api-tokens/mine").get_json()["items"]
    assert [i["id"] for i in listed] == [made["id"]]
    assert "token" not in listed[0]
    assert token not in str(listed)


def test_needs_two_factor(client, db, tenant_pair, catalog):
    _sign_in(client)
    resp = _make(client)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MFA_SETUP_FIRST"


def test_needs_a_fresh_step_up(app, client, db, tenant_pair, catalog):
    _sign_in(client)
    _two_factor(db, tenant_pair["user"])
    with patch.dict(app.config, {"STEP_UP_ENFORCED": True}):
        resp = _make(client)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "STEP_UP_REQUIRED"


def test_scopes_cannot_exceed_the_makers_rights(client, db, tenant_pair, catalog):
    member = tenant_pair["member_a"]
    reader = Role(name="Reader")
    db.session.add(reader)
    db.session.flush()
    reader.permissions = [RolePermission(permission_id=catalog[0].id)]  # READ only
    member.roles = [reader]
    tenant = tenant_pair["tenant_a"]
    tenant.settings = {"api_tokens": {"members": True}}
    _sign_in(client)
    _two_factor(db, tenant_pair["user"])

    assert _make(client, scopes=[CREATE]).status_code == 400
    assert _make(client, scopes=["admin.everything"]).status_code == 400
    ok = _make(client, scopes=[READ])
    assert ok.status_code == 201, ok.get_json()


def test_members_need_the_club_switch(client, db, tenant_pair, catalog):
    member = tenant_pair["member_a"]
    reader = Role(name="Reader")
    db.session.add(reader)
    db.session.flush()
    reader.permissions = [RolePermission(permission_id=catalog[0].id)]
    member.roles = [reader]
    db.session.commit()
    _sign_in(client)
    _two_factor(db, tenant_pair["user"])
    resp = _make(client)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "API_TOKEN_DISABLED_BY_CLUB"


def test_read_preset_takes_only_read_keys(client, db, tenant_pair, catalog):
    _sign_in(client)
    _two_factor(db, tenant_pair["user"])
    resp = client.post(
        "/api/v1/app/api-tokens/mine", json={"name": "R", "preset": "read", "days": 7}
    )
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["scopes"] == [READ]


def test_lifetime_has_a_maximum(client, db, tenant_pair, catalog):
    _sign_in(client)
    _two_factor(db, tenant_pair["user"])
    assert _make(client, days=3650).status_code == 400
    assert _make(client, days=365).status_code == 201


# ── Using tokens ────────────────────────────────────────────────────────────


def test_token_reads_within_scope(app, made):
    c = app.test_client()
    resp = c.get("/api/v1/events/", headers=_bearer(made["token"]))
    assert resp.status_code == 200, resp.get_json()


def test_admin_token_is_still_limited_to_its_scopes(app, made):
    c = app.test_client()
    resp = c.post(
        "/api/v1/events/",
        json={"title": "X", "date": "2030-06-06", "type": "Social"},
        headers=_bearer(made["token"]),
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "API_TOKEN_SCOPE"


def test_write_scope_writes_and_is_audited(app, db, tenant_pair, catalog):
    maker = app.test_client()
    _sign_in(maker)
    _two_factor(db, tenant_pair["user"])
    token = _make(maker, name="Website", scopes=[READ, CREATE]).get_json()["token"]

    c = app.test_client()
    resp = c.post(
        "/api/v1/events/",
        json={"title": "Via token", "date": "2030-06-06", "type": "Social"},
        headers=_bearer(token),
    )
    assert resp.status_code in (200, 201), resp.get_json()
    names = [e.actor_name or "" for e in db.session.query(AuditEntry).all()]
    assert any("(Token «Website»)" in n for n in names), names


def test_live_rights_cap_the_token(app, db, tenant_pair, catalog):
    """Scopes only narrow: losing the role ends what the token could do."""
    member = tenant_pair["member_a"]
    tenant_pair["tenant_a"].settings = {"api_tokens": {"members": True}}
    reader = Role(name="Reader")
    db.session.add(reader)
    db.session.flush()
    reader.permissions = [RolePermission(permission_id=catalog[0].id)]
    member.roles = [reader]
    db.session.commit()
    maker = app.test_client()
    _sign_in(maker)
    _two_factor(db, tenant_pair["user"])
    token = _make(maker).get_json()["token"]
    c = app.test_client()
    assert c.get("/api/v1/events/", headers=_bearer(token)).status_code == 200

    member.roles = []
    db.session.commit()
    from hubra.core.permissions import invalidate_member_permissions

    invalidate_member_permissions(member.id)
    resp = c.get("/api/v1/events/", headers=_bearer(token))
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "FORBIDDEN"


def test_switching_member_tokens_off_stops_them(app, db, tenant_pair, catalog):
    member = tenant_pair["member_a"]
    tenant = tenant_pair["tenant_a"]
    tenant.settings = {"api_tokens": {"members": True}}
    reader = Role(name="Reader")
    db.session.add(reader)
    db.session.flush()
    reader.permissions = [RolePermission(permission_id=catalog[0].id)]
    member.roles = [reader]
    db.session.commit()
    maker = app.test_client()
    _sign_in(maker)
    _two_factor(db, tenant_pair["user"])
    token = _make(maker).get_json()["token"]
    c = app.test_client()
    assert c.get("/api/v1/events/", headers=_bearer(token)).status_code == 200

    tenant.settings = {"api_tokens": {"members": False}}
    db.session.commit()
    resp = c.get("/api/v1/events/", headers=_bearer(token))
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "API_TOKEN_DISABLED_BY_CLUB"


def test_bad_tokens_are_401(app, made):
    c = app.test_client()
    # The last character is changed, never kept (a token may end in "x").
    wrong = made["token"][:-1] + ("x" if made["token"][-1] != "x" else "y")
    for raw in ("hbr_pat_nonsense", wrong, "hbr_club" + made["token"][7:]):
        resp = c.get("/api/v1/events/", headers=_bearer(raw))
        assert resp.status_code == 401, raw
        assert resp.get_json()["error"] == "API_TOKEN_INVALID"


def test_repeated_wrong_secrets_revoke_the_token(app, db, made):
    c = app.test_client()
    wrong = made["token"][:-4] + ("aaaa" if made["token"][-4:] != "aaaa" else "bbbb")
    for _ in range(api_tokens.MAX_FAILURES):
        c.get("/api/v1/events/", headers=_bearer(wrong))
    row = db.session.get(ApiToken, made["id"])
    db.session.refresh(row)
    assert row.revoked_reason == "failed_attempts"
    assert c.get("/api/v1/events/", headers=_bearer(made["token"])).status_code == 401


def test_revoked_and_expired_tokens_stop(app, db, made):
    c = app.test_client()
    row = db.session.get(ApiToken, made["id"])
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    resp = c.get("/api/v1/events/", headers=_bearer(made["token"]))
    assert resp.get_json()["error"] == "API_TOKEN_EXPIRED"

    row.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    row.revoked_at = datetime.now(timezone.utc)
    db.session.commit()
    resp = c.get("/api/v1/events/", headers=_bearer(made["token"]))
    assert resp.get_json()["error"] == "API_TOKEN_REVOKED"


def test_revoke_from_the_club_app(app, db, made):
    owner = app.test_client()
    _sign_in(owner)
    assert owner.delete(f"/api/v1/app/api-tokens/mine/{made['id']}").status_code == 200
    c = app.test_client()
    assert c.get("/api/v1/events/", headers=_bearer(made["token"])).status_code == 401


def test_password_reset_ends_tokens(app, db, made):
    user = made["user"]
    user.tokens_valid_after = datetime.now(timezone.utc) + timedelta(seconds=1)
    db.session.commit()
    c = app.test_client()
    resp = c.get("/api/v1/events/", headers=_bearer(made["token"]))
    assert resp.status_code == 401


def test_unused_tokens_end(app, db, made):
    row = db.session.get(ApiToken, made["id"])
    row.created_at = datetime.now(timezone.utc) - timedelta(days=api_tokens.UNUSED_DAYS + 1)
    row.last_used_at = None
    db.session.commit()
    c = app.test_client()
    assert c.get("/api/v1/events/", headers=_bearer(made["token"])).status_code == 401


def test_token_is_bound_to_its_club(app, made):
    c = app.test_client()
    resp = c.get("/api/tenant-b/v1/events/", headers=_bearer(made["token"]))
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "API_TOKEN_WRONG_CLUB"


def test_club_header_is_ignored(app, made, db):
    """X-Tenant-Slug can't move a token to another club."""
    c = app.test_client()
    resp = c.get(
        "/api/v1/events/", headers=_bearer(made["token"], **{"X-Tenant-Slug": "tenant-b"})
    )
    assert resp.status_code == 200


def test_browser_requests_are_refused(app, made):
    c = app.test_client()
    resp = c.get(
        "/api/v1/events/", headers=_bearer(made["token"], Origin="https://evil.example")
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "API_TOKEN_BROWSER"


def test_cookies_are_ignored_and_never_set(app, made):
    """A request with a token runs only on the token: the browser's club
    session next to it is dropped, and no answer sets a cookie."""
    c = app.test_client()
    _sign_in(c)  # a full club session in the cookie jar
    resp = c.get("/api/v1/account/permissions", headers=_bearer(made["token"]))
    assert resp.status_code == 403  # account routes don't take tokens
    assert not resp.headers.getlist("Set-Cookie")
    resp = c.get("/api/v1/events/", headers=_bearer(made["token"]))
    assert resp.status_code == 200
    assert not resp.headers.getlist("Set-Cookie")


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/app/api-tokens/mine"),
        ("post", "/api/v1/app/api-tokens/mine"),
        ("get", "/api/v1/account/"),
        ("post", "/api/v1/auth/switch-tenant"),
        ("post", "/api/v1/auth/refresh"),
        ("post", "/api/v1/account/step-up"),
        ("get", "/api/v1/account/linked-accounts/"),
    ],
)
def test_account_and_token_routes_refuse_tokens(app, made, method, path):
    c = app.test_client()
    resp = getattr(c, method)(path, json={}, headers=_bearer(made["token"]))
    assert resp.status_code == 403, (path, resp.get_json())
    assert resp.get_json()["error"] == "API_TOKEN_NOT_ALLOWED"


def test_club_tokens_never_open_platform_routes(app, made):
    c = app.test_client()
    resp = c.get("/api/v1/manager/platform/health", headers=_bearer(made["token"]))
    assert resp.status_code == 403


def test_rate_limit(app, made):
    c = app.test_client()
    # The limit counts per clock minute: hold the clock still, or five
    # requests that straddle a minute boundary land in two windows.
    with (
        patch.object(api_tokens, "READS_PER_MINUTE", 3),
        patch.object(api_tokens, "time", SimpleNamespace(time=lambda: 1_800_000_030.0)),
    ):
        codes = [
            c.get("/api/v1/events/", headers=_bearer(made["token"])).status_code
            for _ in range(5)
        ]
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]


# ── Club tokens and admin views ─────────────────────────────────────────────


def test_admin_makes_club_token_and_sees_all(app, db, made):
    admin = app.test_client()
    _sign_in(admin)
    resp = _make(admin, path="/api/v1/app/api-tokens/club", name="Website feed")
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["token"].startswith("hbr_club_")
    items = admin.get("/api/v1/app/api-tokens/").get_json()["items"]
    assert {i["kind"] for i in items} == {"member", "club"}
    c = app.test_client()
    assert c.get("/api/v1/events/", headers=_bearer(resp.get_json()["token"])).status_code == 200


def test_other_clubs_tokens_are_invisible(app, db, made):
    admin_b = app.test_client()
    _sign_in(admin_b, slug="tenant-b")
    assert admin_b.get("/api/v1/app/api-tokens/").get_json()["items"] == []
    assert admin_b.delete(f"/api/v1/app/api-tokens/{made['id']}").status_code == 404


# ── Platform tokens ─────────────────────────────────────────────────────────


@pytest.fixture
def platform_token(app, db, tenant_pair):
    user = tenant_pair["user"]
    user.is_superadmin = True
    db.session.commit()
    c = app.test_client()
    resp = c.post("/api/v1/auth/login", json={"email": "user@test.ch", "password": PASSWORD})
    assert resp.status_code == 200
    _two_factor(db, user)
    resp = c.post(
        "/api/v1/platform/api-tokens/mine",
        json={"name": "Claude diagnostics", "days": 30},
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["token"]


def test_platform_token_reads_diagnostics(app, platform_token):
    c = app.test_client()
    resp = c.get("/api/v1/manager/platform/health", headers=_bearer(platform_token))
    assert resp.status_code == 200, resp.get_json()


def test_platform_token_is_read_only(app, platform_token):
    c = app.test_client()
    resp = c.post("/api/v1/manager/platform/mail/test", json={}, headers=_bearer(platform_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "API_TOKEN_READ_ONLY"


def test_platform_token_scope_is_enforced(app, platform_token):
    """platform.diagnostics by default; settings routes need their own key."""
    c = app.test_client()
    resp = c.get("/api/v1/manager/platform/settings", headers=_bearer(platform_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "API_TOKEN_SCOPE"
    resp = c.get("/api/v1/platform/api-tokens/", headers=_bearer(platform_token))
    assert resp.status_code == 403


def test_platform_token_opens_no_club(app, platform_token):
    c = app.test_client()
    resp = c.get("/api/v1/events/", headers=_bearer(platform_token))
    assert resp.status_code == 403
    resp = c.get("/api/tenant-a/v1/events/", headers=_bearer(platform_token))
    assert resp.status_code == 403


def test_platform_lifetime_max(app, db, tenant_pair):
    user = tenant_pair["user"]
    user.is_superadmin = True
    db.session.commit()
    c = app.test_client()
    c.post("/api/v1/auth/login", json={"email": "user@test.ch", "password": PASSWORD})
    _two_factor(db, user)
    resp = c.post("/api/v1/platform/api-tokens/mine", json={"name": "x", "days": 90})
    assert resp.status_code == 400


# ── Route walk: the deny list holds for every registered route ──────────────


def _sample_path(rule) -> str:
    import re

    path = re.sub(r"<int:[^>]+>", "1", rule.rule)
    path = re.sub(r"<path:[^>]+>", "a/b", path)
    return re.sub(r"<[^>]+>", "a", path)


def test_route_walk_never_routes_refuse_every_token_kind(app):
    """Walks every registered route: a route on the deny list (account,
    sign-in, token management, club switch, step-up, plugins) or without an
    RBAC decorator refuses every kind of token, for every method."""
    from hubra.core.auth.api_tokens import _NEVER_BLUEPRINTS, _route_refusal

    refused = allowed = 0
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        view = app.view_functions[rule.endpoint]
        if getattr(view, "_token_self", False):
            # "Which token is this?": GET only, checked in test_token_self_*.
            assert (rule.methods or set()) <= {"GET", "HEAD", "OPTIONS"}, rule.rule
            continue
        blueprint = rule.endpoint.rsplit(".", 1)[0] if "." in rule.endpoint else ""
        never = (
            blueprint in _NEVER_BLUEPRINTS
            or getattr(view, "_step_up", False)
            or getattr(view, "_api_tokens_never", False)
            or not (getattr(view, "_perm_resource", None) or getattr(view, "_global_perm", None))
        )
        for method in sorted((rule.methods or set()) - {"HEAD", "OPTIONS"}):
            with app.test_request_context(_sample_path(rule), method=method):
                from flask import request

                if request.endpoint != rule.endpoint:
                    continue  # another rule answers this sample path
                for kind in ("member", "club", "platform"):
                    result = _route_refusal(kind)
                    if never:
                        assert result is not None, (kind, method, rule.rule)
                        refused += 1
                    elif result is None:
                        allowed += 1
    assert refused > 200
    assert allowed > 50


def test_step_up_routes_are_marked(app):
    step_up = [
        r.rule
        for r in app.url_map.iter_rules()
        if getattr(app.view_functions[r.endpoint], "_step_up", False)
    ]
    assert any("restore" in p for p in step_up), step_up


# ── Rolling and editing ─────────────────────────────────────────────────────


def test_roll_keeps_the_old_secret_for_the_grace_period(app, db, made):
    owner = app.test_client()
    _sign_in(owner)
    resp = owner.post(f"/api/v1/app/api-tokens/mine/{made['id']}/roll", json={"graceHours": 1})
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    new = body["token"]
    assert new != made["token"] and body["name"] == "Script"
    assert body["scopes"] == [READ]
    assert body["previous"]["revokedReason"] == "rolled"
    c = app.test_client()
    assert c.get("/api/v1/events/", headers=_bearer(new)).status_code == 200
    assert c.get("/api/v1/events/", headers=_bearer(made["token"])).status_code == 200
    # After the grace period only the new one works.
    old = db.session.get(ApiToken, made["id"])
    old.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    assert c.get("/api/v1/events/", headers=_bearer(made["token"])).status_code == 401
    assert c.get("/api/v1/events/", headers=_bearer(new)).status_code == 200


def test_roll_without_grace_ends_the_old_one_now(app, made):
    owner = app.test_client()
    _sign_in(owner)
    resp = owner.post(f"/api/v1/app/api-tokens/mine/{made['id']}/roll", json={"graceHours": 0})
    assert resp.status_code == 201
    c = app.test_client()
    assert c.get("/api/v1/events/", headers=_bearer(made["token"])).status_code == 401


def test_roll_needs_a_fresh_step_up(app, made):
    owner = app.test_client()
    _sign_in(owner)
    with patch.dict(app.config, {"STEP_UP_ENFORCED": True}):
        resp = owner.post(f"/api/v1/app/api-tokens/mine/{made['id']}/roll", json={})
    assert resp.get_json()["error"] == "STEP_UP_REQUIRED"


def test_admin_cannot_roll_or_edit_a_members_token(app, made):
    admin = app.test_client()
    _sign_in(admin)
    assert admin.post(f"/api/v1/app/api-tokens/{made['id']}/roll", json={}).status_code == 404
    assert admin.patch(f"/api/v1/app/api-tokens/{made['id']}", json={"scopes": []}).status_code == 404


def test_edit_narrows_without_step_up_and_widens_with_it(app, db, made):
    owner = app.test_client()
    _sign_in(owner)
    path = f"/api/v1/app/api-tokens/mine/{made['id']}"
    with patch.dict(app.config, {"STEP_UP_ENFORCED": True}):
        widen = owner.patch(path, json={"scopes": [READ, CREATE]})
        assert widen.get_json()["error"] == "STEP_UP_REQUIRED"
        rename = owner.patch(path, json={"name": "Renamed"})
        assert rename.status_code == 200 and rename.get_json()["name"] == "Renamed"
    widen = owner.patch(path, json={"scopes": [READ, CREATE]})
    assert widen.status_code == 200 and widen.get_json()["scopes"] == [CREATE, READ]
    c = app.test_client()
    resp = c.post(
        "/api/v1/events/",
        json={"title": "Now allowed", "date": "2030-06-06", "type": "Social"},
        headers=_bearer(made["token"]),
    )
    assert resp.status_code in (200, 201), resp.get_json()
    assert owner.patch(path, json={"scopes": ["not.a.key"]}).status_code == 400
    with patch.dict(app.config, {"STEP_UP_ENFORCED": True}):
        narrow = owner.patch(path, json={"scopes": [READ]})
    assert narrow.status_code == 200 and narrow.get_json()["scopes"] == [READ]


# ── "Which token is this?" and the club's AI switch ─────────────────────────


def test_token_self_answers_for_a_club_token(app, made):
    c = app.test_client()
    resp = c.get("/api/v1/app/api-tokens/self", headers=_bearer(made["token"]))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["kind"] == "member"
    assert body["scopes"] == [READ]
    assert body["club"]["slug"] == "tenant-a"
    assert body["aiAllowed"] is False
    assert "lastUsedIp" not in body and "token" not in body
    # The other side's self route refuses it.
    resp = c.get("/api/v1/platform/api-tokens/self", headers=_bearer(made["token"]))
    assert resp.status_code == 403


def test_token_self_answers_for_a_platform_token(app, platform_token):
    c = app.test_client()
    resp = c.get("/api/v1/platform/api-tokens/self", headers=_bearer(platform_token))
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["kind"] == "platform"
    assert resp.get_json()["club"] is None
    resp = c.get("/api/v1/app/api-tokens/self", headers=_bearer(platform_token))
    assert resp.status_code == 403


def test_token_self_needs_a_token(app, made):
    c = app.test_client()
    _sign_in(c)
    resp = c.get("/api/v1/app/api-tokens/self")
    assert resp.status_code == 401


def test_ai_client_needs_the_club_switch(app, db, made):
    c = app.test_client()
    mcp = _bearer(made["token"], **{"X-Hubra-Client": "mcp"})
    resp = c.get("/api/v1/events/", headers=mcp)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "API_TOKEN_AI_OFF"
    # "Which token is this?" still answers, so the connector can say why.
    resp = c.get("/api/v1/app/api-tokens/self", headers=mcp)
    assert resp.status_code == 200
    assert resp.get_json()["aiAllowed"] is False
    # The same token without the connector header still works.
    assert c.get("/api/v1/events/", headers=_bearer(made["token"])).status_code == 200

    admin = app.test_client()
    _sign_in(admin)
    resp = admin.put("/api/v1/app/api-tokens/settings", json={"aiAllowed": True})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json() == {"membersAllowed": False, "aiAllowed": True}
    assert admin.get("/api/v1/app/api-tokens/scopes").get_json()["aiAllowed"] is True
    actions = [e.action for e in db.session.query(AuditEntry).all()]
    assert "api_token.ai_on" in actions
    assert c.get("/api/v1/events/", headers=mcp).status_code == 200


def test_ai_switch_does_not_touch_platform_tokens(app, platform_token):
    c = app.test_client()
    headers = _bearer(platform_token, **{"X-Hubra-Client": "mcp"})
    assert c.get("/api/v1/platform/health", headers=headers).status_code == 200


def test_settings_validates_switches(app, made):
    admin = app.test_client()
    _sign_in(admin)
    assert admin.put("/api/v1/app/api-tokens/settings", json={}).status_code == 400
    resp = admin.put("/api/v1/app/api-tokens/settings", json={"aiAllowed": "yes"})
    assert resp.status_code == 400
