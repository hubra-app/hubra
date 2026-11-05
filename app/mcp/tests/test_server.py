"""The Claude connector (docs/mcp.md): token gate, tool lists per token
kind, and that each call goes to Hubra with the caller's own token only."""

from __future__ import annotations

import json

import httpx
import pytest
from starlette.testclient import TestClient

from hubra_mcp import hubra, server

PLAT = "hbr_plat_" + "a" * 12 + "_" + "b" * 43
CLUB = "hbr_club_" + "c" * 12 + "_" + "d" * 43
PAT = "hbr_pat_" + "e" * 12 + "_" + "f" * 43
OAM = "hbr_oam_" + "g" * 12 + "_" + "h" * 43
OAP = "hbr_oap_" + "i" * 12 + "_" + "j" * 43
META = {
    "resource": "https://mcp.hubra.club/mcp",
    "authorization_servers": ["https://api.hubra.club"],
    "scopes_supported": ["read"],
}


class FakeHubra:
    def __init__(self):
        self.calls: list[httpx.Request] = []
        self.answer = lambda req: httpx.Response(200, json={"ok": True, "path": req.url.path})

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        return self.answer(req)


@pytest.fixture
def fake():
    fake = FakeHubra()
    server.reset_caches()
    server.set_api(
        hubra.Hubra(
            hubra.Settings("http://app-api", "http://platform-api"),
            transport=httpx.MockTransport(fake),
        )
    )
    yield fake
    server.set_api(None)
    server.reset_caches()


@pytest.fixture
def client(fake):
    with TestClient(server.create_app(), base_url="http://localhost") as c:
        yield c


def _headers(token: str | None = PLAT, **extra) -> dict:
    h = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-06-18",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return {**h, **extra}


def _rpc(client, method, params=None, token=PLAT, **headers):
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return client.post("/mcp", headers=_headers(token, **headers), json=body)


def _call(client, name, arguments=None, token=PLAT):
    resp = _rpc(client, "tools/call", {"name": name, "arguments": arguments or {}}, token)
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    return result["isError"], result["content"][0]["text"]


# ── The gate in front of /mcp ───────────────────────────────────────────────


def test_no_token_is_401(client, fake):
    resp = _rpc(client, "tools/list", token=None)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].startswith("Bearer")
    # Only the sign-in metadata was asked for (not set up here: 200 ok body
    # without "resource" counts as not set up).
    assert [c.url.path for c in fake.calls] == ["/api/v1/global/oauth/resource"]
    assert "resource_metadata" not in resp.headers["www-authenticate"]


def _with_meta(fake, token_status=200):
    def answer(req):
        if req.url.path == "/api/v1/global/oauth/resource":
            return httpx.Response(200, json=META)
        if req.url.path.endswith("/api-tokens/self"):
            return httpx.Response(token_status, json={"error": "API_TOKEN_EXPIRED"})
        return httpx.Response(200, json={"ok": True, "path": req.url.path})

    fake.answer = answer


def test_no_token_points_to_the_sign_in(client, fake):
    _with_meta(fake)
    resp = _rpc(client, "tools/list", token=None)
    assert resp.status_code == 401
    challenge = resp.headers["www-authenticate"]
    assert 'resource_metadata="https://mcp.hubra.club/.well-known/oauth-protected-resource/mcp"' in challenge


@pytest.mark.parametrize("path", ["/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"])
def test_protected_resource_metadata(client, fake, path):
    _with_meta(fake)
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.json()["authorization_servers"] == ["https://api.hubra.club"]


def test_protected_resource_metadata_not_set_up(client, fake):
    fake.answer = lambda req: httpx.Response(404, json={"error": "NOT_SET_UP"})
    assert client.get("/.well-known/oauth-protected-resource").status_code == 404


def test_expired_oauth_token_is_http_401(client, fake):
    _with_meta(fake, token_status=401)
    resp = _rpc(client, "tools/list", token=OAM)
    assert resp.status_code == 401
    assert 'error="invalid_token"' in resp.headers["www-authenticate"]


def test_oauth_token_check_is_cached(client, fake):
    _with_meta(fake)
    assert _rpc(client, "tools/list", token=OAM).status_code == 200
    assert _rpc(client, "tools/list", token=OAM).status_code == 200
    selfs = [c for c in fake.calls if c.url.path.endswith("/self")]
    assert len(selfs) == 1
    assert selfs[0].headers["x-hubra-client"] == "mcp"


def test_oauth_tokens_see_their_tools(client, fake):
    _with_meta(fake)
    assert "club_members" in _names(client, OAM)
    assert "platform_health" in _names(client, OAP)
    assert "club_members" not in _names(client, OAP)


def test_switched_off_club_still_reaches_the_tools(client, fake):
    """A 403 (club AI switch off) isn't a sign-in problem: the tools say why."""
    _with_meta(fake, token_status=403)
    assert _rpc(client, "tools/list", token=OAM).status_code == 200


def test_pasted_tokens_are_not_checked_up_front(client, fake):
    _with_meta(fake)
    assert _rpc(client, "tools/list", token=CLUB).status_code == 200
    assert not [c for c in fake.calls if c.url.path.endswith("/self")]


@pytest.mark.parametrize("token", ["hbr_plat_short", "ghp_" + "x" * 36, PLAT + "x"])
def test_malformed_tokens_are_401(client, token):
    assert _rpc(client, "tools/list", token=token).status_code == 401


def test_browsers_are_refused(client):
    resp = _rpc(client, "tools/list", Origin="https://evil.example")
    assert resp.status_code == 403


def test_unknown_host_is_refused(fake):
    with TestClient(server.create_app(), base_url="http://evil.example") as c:
        resp = _rpc(c, "tools/list")
    assert resp.status_code in (400, 403, 421)


def test_healthz_needs_no_token(client):
    assert client.get("/healthz").json()["status"] == "ok"


# ── Tools per token kind ────────────────────────────────────────────────────


def _names(client, token):
    resp = _rpc(client, "tools/list", token=token)
    assert resp.status_code == 200, resp.text
    return {t["name"] for t in resp.json()["result"]["tools"]}


def test_platform_token_sees_platform_tools(client):
    names = _names(client, PLAT)
    assert {"whoami", "hubra_get", "platform_performance", "platform_errors"} <= names
    assert not any(n.startswith("club_") for n in names)


@pytest.mark.parametrize("token", [CLUB, PAT])
def test_club_tokens_see_club_tools(client, token):
    names = _names(client, token)
    assert {"whoami", "hubra_get", "club_members", "club_invoices"} <= names
    assert not any(n.startswith("platform_") for n in names)


def test_every_tool_is_read_only(client):
    resp = _rpc(client, "tools/list")
    for tool in resp.json()["result"]["tools"]:
        assert tool["annotations"]["readOnlyHint"] is True, tool["name"]
        assert tool["annotations"]["destructiveHint"] is False, tool["name"]


def test_platform_tool_refuses_a_club_token(client, fake):
    error, text = _call(client, "platform_health", token=CLUB)
    assert error and "platform token" in text
    assert fake.calls == []


# ── Calls to Hubra ──────────────────────────────────────────────────────────


def test_platform_call_carries_the_callers_token(client, fake):
    error, text = _call(client, "platform_performance", {"hours": 6})
    assert not error, text
    (req,) = fake.calls
    assert str(req.url) == "http://platform-api/api/v1/platform/alerts/performance?hours=6"
    assert req.method == "GET"
    assert req.headers["authorization"] == f"Bearer {PLAT}"
    assert req.headers["x-hubra-client"] == "mcp"
    assert "cookie" not in req.headers and "origin" not in req.headers


def test_club_call_goes_to_the_app_api(client, fake):
    error, _ = _call(client, "club_members", {"search": "Muster", "pageSize": 10}, token=CLUB)
    assert not error
    (req,) = fake.calls
    assert req.url.host == "app-api"
    assert req.url.path == "/api/v1/app/members/"
    assert req.url.params["search"] == "Muster"
    assert req.url.params["pageSize"] == "10"
    assert "status" not in req.url.params  # empty filters are left out
    assert req.headers["authorization"] == f"Bearer {CLUB}"


def test_whoami_asks_the_tokens_own_side(client, fake):
    _call(client, "whoami", token=PAT)
    _call(client, "whoami", token=PLAT)
    assert [r.url.path for r in fake.calls] == [
        "/api/v1/app/api-tokens/self",
        "/api/v1/platform/api-tokens/self",
    ]


@pytest.mark.parametrize(
    "path",
    [
        "http://evil.example/api/v1/app/members/",
        "//evil.example/api/v1/app/",
        "/api/v1/app/../platform/settings",
        "/api/v1/auth/login",
        "/api/v1/platform/health",  # the other side for a club token
        "/api/v1/app/members/?search=x",
        "/api/v1/app/members%2F..",
    ],
)
def test_hubra_get_stays_on_the_tokens_side(client, fake, path):
    error, _ = _call(client, "hubra_get", {"path": path}, token=CLUB)
    assert error
    assert fake.calls == []


def test_hubra_get_passes_query(client, fake):
    error, _ = _call(client, "hubra_get", {"path": "/api/v1/app/groups/", "query": {"page": 2}}, token=CLUB)
    assert not error
    assert str(fake.calls[0].url) == "http://app-api/api/v1/app/groups/?page=2"


def test_hubra_errors_reach_the_model(client, fake):
    fake.answer = lambda req: httpx.Response(
        403, json={"error": "API_TOKEN_SCOPE", "message": "Scope missing"}
    )
    error, text = _call(client, "club_invoices", token=CLUB)
    assert error
    assert "403 API_TOKEN_SCOPE" in text


def test_redirects_are_not_followed(client, fake):
    fake.answer = lambda req: httpx.Response(302, headers={"Location": "http://evil.example/"})
    error, text = _call(client, "platform_health")
    assert error and "redirect" in text
    assert len(fake.calls) == 1


def test_long_answers_are_cut(client, fake):
    fake.answer = lambda req: httpx.Response(200, json={"rows": ["x" * 100] * 2000})
    error, text = _call(client, "platform_jobs")
    assert not error
    assert len(text) < hubra.MAX_CHARS + 300
    assert "cut after" in text


def test_event_with_registrations_is_one_json(client, fake):
    error, text = _call(client, "club_event", {"event_id": 4, "registrations": True}, token=CLUB)
    assert not error
    body = json.loads(text)
    assert body["event"]["path"] == "/api/v1/app/events/4"
    assert body["registrations"]["path"] == "/api/v1/app/events/4/registrations"


def test_query_keys_cannot_clash(client, fake):
    error, _ = _call(
        client, "hubra_get",
        {"path": "/api/v1/app/groups/", "query": {"path": "x", "ctx": "y"}}, token=CLUB,
    )
    assert not error
    assert fake.calls[0].url.params["path"] == "x"


def test_client_ip_is_forwarded(fake):
    app = server.create_app()
    with TestClient(app, base_url="http://localhost", client=("203.0.113.7", 5000)) as c:
        _call(c, "platform_health")
    assert fake.calls[0].headers["x-forwarded-for"] == "203.0.113.7"


def test_no_ip_no_header(client, fake):
    _call(client, "platform_health")  # TestClient's host is "testclient"
    assert "x-forwarded-for" not in fake.calls[0].headers


def test_forwarded_for_is_ignored_by_default(fake):
    app = server.create_app()
    with TestClient(app, base_url="http://localhost", client=("203.0.113.7", 5000)) as c:
        c.post(
            "/mcp",
            headers=_headers(PLAT, **{"X-Forwarded-For": "198.51.100.1"}),
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "platform_health", "arguments": {}}},
        )
    assert fake.calls[0].headers["x-forwarded-for"] == "203.0.113.7"


def test_forwarded_for_passes_behind_the_proxies(fake, monkeypatch):
    monkeypatch.setenv("MCP_FORWARDED", "pass")
    app = server.create_app()
    with TestClient(app, base_url="http://localhost", client=("10.42.0.9", 5000)) as c:
        c.post(
            "/mcp",
            headers=_headers(PLAT, **{"X-Forwarded-For": "198.51.100.1, 203.0.113.7"}),
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "platform_health", "arguments": {}}},
        )
    assert fake.calls[0].headers["x-forwarded-for"] == "198.51.100.1, 203.0.113.7"


def test_forwarded_for_must_be_addresses(fake, monkeypatch):
    monkeypatch.setenv("MCP_FORWARDED", "pass")
    app = server.create_app()
    with TestClient(app, base_url="http://localhost", client=("10.42.0.9", 5000)) as c:
        c.post(
            "/mcp",
            headers=_headers(PLAT, **{"X-Forwarded-For": "evil\r\nX: y"}),
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "platform_health", "arguments": {}}},
        )
    assert "x-forwarded-for" not in fake.calls[0].headers


def test_maintenance_includes_the_windows(client, fake):
    error, text = _call(client, "platform_maintenance")
    assert not error
    body = json.loads(text)
    assert body["mode"]["path"] == "/api/v1/platform/maintenance"
    assert body["windows"]["path"] == "/api/v1/platform/maintenance/windows"


def test_performance_looks_back_past_the_full_hour(client, fake):
    """hours=1 is only since the full hour: a few seconds just after it."""
    error, _ = _call(client, "platform_performance")
    assert not error
    assert fake.calls[0].url.params["hours"] == "2"
