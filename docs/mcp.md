# Claude connector (MCP server)

`app/mcp` is a small [MCP](https://modelcontextprotocol.io) server that lets
Claude read Hubra. It runs as its own image (`ghcr.io/hubra-app/hubra/mcp`)
at `https://mcp.hubra.club/mcp`, speaks the streamable HTTP transport, and
turns a hand-picked set of Hubra API reads into tools.

It has **no database access, no Secret and no credentials of its own**.
Every request brings the person's own API token (docs/api-tokens.md), and
every tool call is a `GET` to the Hubra API with exactly that token. So
Claude can never see more than the token may, and the backend's usual
checks decide every answer: the person's current rights, the token's
scopes, the club's switches, rate limits and the audit log.

## Connecting

Make a token first: platform tokens in manage › Zugriff & Sicherheit ›
API-Tokens, club tokens through the club API for now (docs/api-tokens.md).
Manage shows the command with the secret filled in.

Claude Code:

```
claude mcp add --transport http hubra https://mcp.hubra.club/mcp \
  --header "Authorization: Bearer hbr_plat_…"
```

Anything else that can send a fixed `Authorization` header to a remote MCP
server works the same way (Claude Desktop through its config, the Claude
API's MCP connector). claude.ai custom connectors sign in with OAuth, which
Hubra doesn't offer yet; see "Not built yet".

## Tools

All tools only read (`readOnlyHint`); there is no tool that writes, sends,
deletes or changes anything. The tool list depends on the token:

| Token | Tools |
| --- | --- |
| any | `whoami` (kind, name, club, scopes, expiry), `hubra_get` (any `GET` on the token's side of the API) |
| platform (`hbr_plat_`) | `platform_health`, `platform_alerts`, `platform_performance` (routes and slow queries), `platform_errors`, `platform_error`, `platform_jobs`, `platform_events`, `platform_mail`, `platform_discord`, `platform_maintenance` (mode and windows) |
| club or personal (`hbr_club_`, `hbr_pat_`) | `club_members`, `club_member`, `club_events`, `club_event`, `club_attendance`, `club_groups`, `club_invoices`, `club_finance_summary`, `club_transactions`, `club_polls`, `club_inventory`, `club_audit` |

Platform tools need the platform token's default scope
`platform.diagnostics`. Club tools need the matching `*.read` keys on the
token; without one, Hubra answers `403 API_TOKEN_SCOPE` and Claude says so.

## Club data needs the club's consent

A club's data only reaches the connector when a club admin switches on
**AI assistants** (`PUT /api/v1/app/api-tokens/settings {"aiAllowed": true}`,
off by default; the club page for it is not built yet). The connector sends
`X-Hubra-Client: mcp` on every call, and the backend refuses a club or
personal token with that header while the switch is off
(`403 API_TOKEN_AI_OFF`). Platform tools never return member data, so the
switch doesn't apply to platform tokens.

The header is the connector's own statement, not a proof: a person who
holds a token can always read the same data with a script. The switch keeps
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
- **Caller's address.** With `MCP_FORWARDED=pass` (set in deploy/app and the
  Traefik Compose file) the connector hands the `X-Forwarded-For` of the
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

- **k3s:** `deploy/app/mcp.yaml` (Deployment + Service, read-only root
  filesystem, no service account token) and the `mcp.hubra.club` host in
  `ingress.yaml`, on its own certificate. It calls `backend` and
  `platform-backend` inside the cluster.
- **Compose:** `docker compose --profile mcp up -d mcp`, on
  `127.0.0.1:${MCP_PORT:-8090}`. With `docker-compose.traefik.yml` it gets
  the host `${MCP_HOST:-mcp.hubra.club}`.
- Set the platform setting **Claude connector address** (`mcp.url`, in
  manage on the API tokens page) so manage shows the right command.
- `GET /healthz` answers without a token.

Tests: `cd app/mcp && pytest` (the server against a fake Hubra API) and
`tests/auth/test_api_tokens.py` in the backend (the self route and the AI
switch).

## Not built yet

OAuth on SSO for claude.ai custom connectors, the club pages for club and
personal tokens and the AI switch, write tools (they would answer with a
preview the person confirms).
