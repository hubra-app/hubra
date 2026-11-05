# OAuth: apps that act for a person

Hubra is an OAuth 2.1 authorization server. An outside app (the first one is
Claude, through the Claude connector, docs/mcp.md) sends the person to
Hubra's sign-in page, the person says which club (or the platform) the app
may use and for how long, and the app gets tokens that act as that person.
No token is ever copied by hand.

Code: `hubra/core/auth/oauth.py` (the rules), `hubra/api/oauth/routes.py`
(the endpoints), the consent page `app/sso-frontend/src/screens/OAuthAuthorize.tsx`.

## What an app holds

A sign-in is an `api_tokens` row (docs/api-tokens.md) with
`oauth_client_id` set, kind `member` (one club, as that member) or
`platform` (read-only, for platform admins). So everything an API token goes
through applies on every request: the person's **live** rights AND the
scopes, the club's switches, the rate limits, the audit log, ending with a
password reset or a disabled account, never on account, sign-in, token,
step-up or plugin routes.

| Token | Looks like | Lives |
| --- | --- | --- |
| access, club | `hbr_oam_<id>_<secret>` | 1 hour |
| access, platform | `hbr_oap_<id>_<secret>` | 1 hour |
| refresh | `hbr_ort_<id>_<secret>` | until the sign-in ends: 30 or 90 days (platform 7 or 30), as the person chose |

Each refresh replaces both tokens. The access token before is still
recognised until the next refresh and answered as expired, so a request
already on its way isn't counted as a wrong secret. A refresh token shown again after it was replaced (30 s grace for
two requests at once) ends the sign-in: someone has a copy. A code works
once; shown a second time it ends what it made.

Scopes: an app asks for `read` (default) and/or `write`. `read` becomes
every read permission key of the club catalogue, `write` every key. They
only narrow: the person's rights at the time of each request decide. Platform
sign-ins are always read-only, whatever was asked.

## Resources (RFC 8707)

Every token is for one resource:

* the **Claude connector**, `<mcp.url>/mcp` (platform setting `mcp.url`):
  the token works only with `X-Hubra-Client: mcp` (the connector sends it),
  so the club's "AI assistants" switch always applies; and
* the **Hubra API**, the issuer itself (`API_PUBLIC_URL`): the token is
  refused through the connector.

Either way the other one answers `401 API_TOKEN_AUDIENCE`.

## Apps

* **Club** apps: a club admin registers the club website or forum to sign
  members in (sign-in only, docs/oidc.md).
* **Registered** apps: platform admins add them in manage › Zugriff &
  Sicherheit › API-Tokens › Apps (OAuth): name, return addresses (exact; any
  port on `http://localhost`/`127.0.0.1`), the API and/or the connector,
  read or read+write, with a secret (server app; shown once, can be
  replaced) or without (PKCE only). The consent page shows them as
  "registered with Hubra".
* **Self-registered** apps (RFC 7591, `POST /api/v1/global/oauth/register`):
  how claude.ai and Claude Code sign up on their first connect. Only for
  the connector, only `read`, return addresses only on the hosts of the
  platform setting `oauth.dynamic_redirect_hosts` (default `claude.ai,
  claude.com, localhost, 127.0.0.1`), 10 per hour per address. The consent
  page warns that Hubra hasn't checked the app and names the host it
  returns to. Switch it off with `oauth.dynamic_clients = off`. Apps nobody
  signed in with are removed after a week.

Switching an app off stops all its sign-ins at once; deleting it removes
them.

## Flow

1. The app reads `GET https://api.hubra.club/.well-known/oauth-authorization-server`
   (RFC 8414; the connector points there from
   `/.well-known/oauth-protected-resource`).
2. It opens `https://sso.hubra.club/oauth/authorize?response_type=code&client_id=…&redirect_uri=…&code_challenge=…&code_challenge_method=S256&state=…&resource=…&scope=read`.
   PKCE with S256 is required. The page signs the person in first if
   needed, then shows the app, what it may do, and the clubs: one where the
   club doesn't allow it is greyed out with the reason (members' access off
   for non-admins, AI assistants off for the connector, two-factor missing
   where the club or `write` needs it).
3. Allow → back to the app with `code`, `state` and `iss`. Deny →
   `error=access_denied`. A wrong client or return address is never sent
   back anywhere.
4. The app trades the code at `POST /api/v1/global/oauth/token`
   (`grant_type=authorization_code`, `code_verifier`, `redirect_uri`,
   `resource`; client auth `none`, `client_secret_basic` or
   `client_secret_post`) and later renews with `grant_type=refresh_token`.
5. `POST /api/v1/global/oauth/revoke` (RFC 7009) ends the sign-in.

Signing in again with the same app, person and club replaces the old
sign-in. A person has at most 20 app sign-ins.

## Where people see them

* **SSO › Mein Konto › Apps**: the person's apps, per club, with last use;
  "Beenden" ends one.
* **Club app › Einstellungen › API & Apps** (admins): every token and app
  sign-in of the club, each can be ended; the switches for members' own
  access and for AI assistants.
* **manage › API-Tokens**: "Alle Tokens" lists app sign-ins too (kind
  "App"); "Apps (OAuth)" lists the apps with their number of sign-ins.

Every sign-in and its end is a platform audit entry (`oauth.grant`,
`oauth.revoke`); app changes are `oauth_app.*`.

## Endpoints

| | |
| --- | --- |
| `GET /.well-known/oauth-authorization-server` | server metadata, answered by every backend (roles.SHARED_PATHS) |
| `GET /api/v1/global/oauth/resource` | the connector's resource metadata (RFC 9728), for the connector |
| `POST /api/v1/global/oauth/token`, `/revoke`, `/register` | for apps |
| `GET`/`POST /api/v1/global/oauth/authorize` | for the consent page (account sign-in, `X-Account-CSRF` on POST) |
| `GET /api/v1/global/oauth/grants`, `DELETE …/<id>` | the person's apps |
| `/api/v1/platform/oauth/apps` (`GET`, `POST`, `PATCH /<id>`, `POST /<id>/secret`, `DELETE /<id>`) | manage, `platform.settings` |

## After deploying

`flask db upgrade` (migration `c7f1a9e3b5d2`). `API_PUBLIC_URL` and
`SSO_BASE_URL` must be set (they already are on k3s), and `mcp.url` for the
connector. Nothing else: the metadata path is served by the club backend,
which the API host's `/` already reaches.

## Sign in with Hubra

OpenID Connect (ID tokens, userinfo, keys) and the sign-in apps clubs
register for their own websites are in docs/oidc.md.

## Not built yet

Client ID metadata documents, a mail when an app is connected.
