# Claude connector (MCP server)

`app/mcp` is a small [MCP](https://modelcontextprotocol.io) server that lets
Claude read Hubra. It runs as its own image (`ghcr.io/hubra-app/hubra/mcp`)
at `https://mcp.hubra.club/mcp`, speaks the streamable HTTP transport, and
turns a hand-picked set of Hubra API reads into tools.

It has **no database access, no Secret and no credentials of its own**.
Every request brings the person's own token: one Claude got by signing in
(OAuth, docs/oauth.md) or an API token pasted in (docs/api-tokens.md), and
every tool call is a `GET` to the Hubra API with exactly that token. So
Claude can never see more than the token may, and the backend's usual
checks decide every answer: the person's current rights, the token's
scopes, the club's switches, rate limits and the audit log.

## Connecting

**Sign in (claude.ai, Claude Desktop, Claude Code).** Add a custom
connector with the URL `https://mcp.hubra.club/mcp` and nothing else, or in
Claude Code:

```
claude mcp add --transport http hubra https://mcp.hubra.club/mcp
```

Claude finds the sign-in by itself (OAuth, docs/oauth.md), registers itself
as an app, and opens Hubra's sign-in page: pick the club (platform admins
can also pick the platform) and how long. A club only appears when it
allows AI assistants. End the access any time under SSO › Mein Konto ›
Apps.

**With a pasted token** (scripts, or clients without OAuth): make a token
first: platform tokens in manage › Zugriff & Sicherheit › API-Tokens, club
tokens through the club API for now (docs/api-tokens.md). Manage shows the
command with the secret filled in:

```
claude mcp add --transport http hubra https://mcp.hubra.club/mcp \
  --header "Authorization: Bearer hbr_plat_…"
```

## Tools

All tools only read (`readOnlyHint`); there is no tool that writes, sends,
deletes or changes anything. The tool list depends on the token:

| Token | Tools |
| --- | --- |
| any (also the OAuth ones, `hbr_oam_` club and `hbr_oap_` platform) | `whoami` (kind, name, club, scopes, expiry), `hubra_get` (any `GET` on the token's side of the API) |
| platform (`hbr_plat_`, `hbr_oap_`) | `platform_health`, `platform_alerts`, `platform_performance` (routes and slow queries), `platform_errors`, `platform_error`, `platform_jobs`, `platform_events`, `platform_mail`, `platform_discord`, `platform_maintenance` (mode and windows) |
| club or personal (`hbr_club_`, `hbr_pat_`) | `club_members`, `club_member`, `club_events`, `club_event`, `club_attendance`, `club_groups`, `club_invoices`, `club_finance_summary`, `club_transactions`, `club_polls`, `club_inventory`, `club_audit` |

Platform tools need the platform token's default scope
`platform.diagnostics`. Club tools need the matching `*.read` keys on the
token; without one, Hubra answers `403 API_TOKEN_SCOPE` and Claude says so.

## Club data needs the club's consent

A club's data only reaches the connector when a club admin switches on
**AI assistants** (Einstellungen › API & Apps in the club app, or
`PUT /api/v1/app/api-tokens/settings {"aiAllowed": true}`; off by default). The connector sends
`X-Hubra-Client: mcp` on every call, and the backend refuses a club or
personal token with that header while the switch is off
(`403 API_TOKEN_AI_OFF`). Platform tools never return member data, so the
switch doesn't apply to platform tokens.

For a pasted token the header is the connector's own statement, not a
proof: a person who holds a token can always read the same data with a
script. A token Claude got by signing in is made for the connector
(RFC 8707): it works only with that header and the switch always applies. The switch keeps
the club's decision for Hubra's own connector; the token rules keep the data
safe either way.

## Security

- **Only the caller's token, only to Hubra.** The connector sends the token
  only to `HUBRA_API_URL` / `HUBRA_PLATFORM_API_URL`, never to a URL from a
  tool argument, and never follows a redirect. `hubra_get` takes paths on
  the token's own side only (`/api/v1/app/…` for club tokens,
  `/api/v1/platform/…` for platform tokens), plain segments, no `..`.
- **No browsers.** A request with an `Origin` header is refused, the `Host`
  header must be one of `MCP_ALLOWED_HOSTS` (DNS rebinding guard), and a
  request without a well-formed `hbr_` token gets 401 before any tool runs.
- **No state.** Stateless HTTP with JSON answers: no MCP sessions, nothing
  kept between calls, any replica answers any call.
- **Prompt injection.** Club data contains text anyone may have written. The
  server's instructions tell Claude that tool results are data and never
  instructions, and since no tool writes, a planted instruction has nothing
  to act with. Long answers are cut at 60 000 characters.
- **Caller's address.** With `MCP_FORWARDED=pass` (set in the Traefik Compose file;
  set it too in a cluster's manifests) the connector hands the `X-Forwarded-For` of the
  proxies in front of it to the backend, which reads it with its own
  `PROXY_FIX_X_FOR`. A token's IP allowlist and last-used address then see
  the address Claude connects from. Without it (local Compose) the
  connector sends the address that connected to it.

## Running it

| Setting | Default | |
| --- | --- | --- |
| `HUBRA_API_URL` | `http://localhost:5000` | the club app backend |
| `HUBRA_PLATFORM_API_URL` | `HUBRA_API_URL` | the platform backend |
| `MCP_ALLOWED_HOSTS` | `localhost`, `127.0.0.1` (any port) | allowed `Host` headers, comma-separated, `host:*` for any port |
| `MCP_FORWARDED` | off | `pass`: forward the proxies' `X-Forwarded-For` (see above) |
| `MCP_PORT` | `8000` | |

- **Kubernetes:** a Deployment and Service for the `mcp` image (read-only root
  filesystem, no service account token) and the `mcp.hubra.club` host in the
  Ingress, on its own certificate. It calls `backend` and `platform-backend`
  inside the cluster.
- **Compose:** `docker compose --profile mcp up -d mcp`, on
  `127.0.0.1:${MCP_PORT:-8090}`. With `docker-compose.traefik.yml` it gets
  the host `${MCP_HOST:-mcp.hubra.club}`.
- Set the platform setting **Claude connector address** (`mcp.url`, in
  manage on the API tokens page) so manage shows the right command.
- `GET /healthz` answers without a token.
- `GET /.well-known/oauth-protected-resource` (and `…/mcp`): where to sign
  in (RFC 9728), from Hubra's `GET /api/v1/global/oauth/resource`, which
  follows the platform setting `mcp.url`. Without a token `/mcp` answers 401
  with `WWW-Authenticate: Bearer resource_metadata="…"`. An OAuth token is
  checked with Hubra before the call (cached 30 s), so an expired one gets
  HTTP 401 and Claude renews it.

Tests: `cd app/mcp && pytest` (the server against a fake Hubra API) and
`tests/auth/test_api_tokens.py` in the backend (the self route and the AI
switch).

## Not built yet

Making club and personal tokens in the club app (the API can), write tools
(they would answer with a preview the person confirms).
