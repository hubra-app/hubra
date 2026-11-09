# Sign in with Hubra (OpenID Connect)

A club's website, forum or any other app can sign people in with their
Hubra account. It is OpenID Connect on top of Hubra's OAuth server
(docs/oauth.md): the app sends the person to Hubra, they agree once, and
the app gets a signed ID token that says who they are. It reads nothing
else in Hubra.

Code: `hubra/core/auth/oidc.py` (ID tokens, keys, claims, userinfo), the
OAuth rules in `hubra/core/auth/oauth.py`, the endpoints in
`hubra/api/oauth/routes.py`, the consent page
`app/sso-frontend/src/screens/OAuthAuthorize.tsx`, the club page
`app/frontend/src/screens/private/settings/SignInAppsSection.tsx`.

## Setting it up for a club

Club app › Einstellungen › API & Webhooks › **Anmelden mit Hubra** (club
admins):

1. "Neue Anmelde-App": a name members will see ("Vereinswebsite"), the
   website, and the return addresses the plugin uses (https; one per line,
   exact).
2. Hubra shows the **client ID**, the **client secret** (once; it can be
   replaced later) and the **discovery address**
   `https://api.hubra.club/.well-known/openid-configuration`.
3. Enter those three in the site's OpenID Connect plugin (WordPress
   "OpenID Connect Generic", Discourse OIDC, Nextcloud "user_oidc",
   Keycloak as an identity provider, …). Scopes: `openid profile email club`.

A club has at most 10 such apps. Switching one off stops every sign-in at
once; deleting it removes them. An app without a secret (browser or phone
apps) must use PKCE.

Platform admins can also register sign-in apps that aren't tied to a club
(manage › API-Tokens › Apps (OAuth), "Anmelden mit Hubra"), for example a
Hubra community forum. Any Hubra account may sign in there, and the `club`
scope gives nothing.

## Who may sign in

* A club's app: active members of that club only, not archived or blocked.
  Checked when they sign in, on every refresh and on every userinfo call;
  someone who leaves the club is signed out of the app (the grant ends with
  reason `left_club`).
* An app without a club: every Hubra account.
* Disabled accounts, a password reset and "sign out everywhere" end the
  sign-in like every other token (docs/api-tokens.md).

## What the app learns

| Scope | Claims |
| --- | --- |
| `openid` (required) | `sub`, a person id that is different for every app (pairwise, an HMAC of the app and the account with the platform's secret `oauth.subject_salt`) |
| `profile` | `name`, `given_name`, `family_name`, `locale`; with `club` also `preferred_username` (the club user name, if set) |
| `email` | `email`, `email_verified` |
| `club` (a club's app only) | `hubra_club`: `slug`, `name`, `member_status`, `admin` (owner or admin role), `groups` (names of the groups the member is in) |

The consent page lists exactly these before the person agrees. The same
claims come in the ID token and from userinfo; userinfo always answers
with the current values.

A sign-in-only app holds an `identity` grant (an `api_tokens` row, kind
`identity`, access token `hbr_oai_…`). That token opens userinfo and
nothing else: every API route answers `401 API_TOKEN_AUDIENCE`. The grant
lasts 90 days and is renewed by signing in again.

An app registered with both the API and `openid` (manage only) gets an
ID token next to its normal access (docs/oauth.md). The Claude connector
never signs people in: it ignores `openid`.

## The flow

1. Discovery: `GET /.well-known/openid-configuration` (on the API host,
   every backend answers it).
2. `https://sso.hubra.club/oauth/authorize?response_type=code&client_id=…&redirect_uri=…&scope=openid%20profile%20email%20club&state=…&nonce=…`
   (and `code_challenge`/`code_challenge_method=S256`; see below).
   * The person signs in if needed, then sees what the app learns and
     either "Anmelden" or "Ablehnen".
   * Signed in to the same app before with the same scopes, they are sent
     straight back (no question), unless `prompt=consent`.
   * `prompt=none`: never shows a page; an app not allowed yet gets
     `error=consent_required`, a person not signed in `login_required`.
3. `POST /api/v1/global/oauth/token` with the code: `access_token`,
   `refresh_token`, `id_token`, `scope`. Each refresh also returns a new
   `id_token` (without `nonce`).
4. `GET` or `POST /api/v1/global/oauth/userinfo` with
   `Authorization: Bearer <access_token>`.
5. `POST /api/v1/global/oauth/revoke` ends the sign-in.

**PKCE** is required, except for an app with a secret that sends a
`nonce` with `openid` (OAuth 2.1 §7.5.1): many website plugins don't do
PKCE. Such a code can only be redeemed with the app's secret.

## ID tokens and keys

* RS256, `kid` in the header; `iss` is `API_PUBLIC_URL`, `aud` and `azp`
  the client ID, an hour long, with `auth_time` (when the person signed in
  to Hubra), `nonce` and `at_hash`.
* Keys: `GET /api/v1/global/oauth/jwks`. The first key is made the first
  time one is needed and kept encrypted in the platform setting
  `oauth.signing_keys` (never shown in manage). manage › API-Tokens ›
  Apps (OAuth) › "Neuer Schlüssel" makes a new one; the one before stays
  in the JWKS so tokens signed just before still check out, older ones are
  dropped.
* Changing `oauth.subject_salt` gives every person a new `sub` in every
  app, which signs them up as new users there. Don't.

## Audit

Every sign-in and its end is a platform audit entry (`oauth.grant`,
`oauth.revoke`), a key change `oauth.key_rotate`; club apps are in the
club's audit log (`oauth_app.create`, `.update`, `.secret`, `.delete`).

## After deploying

`flask db upgrade` (migration `d3a7e5b9c1f4`). Nothing else: keys and the
subject secret are made on first use.

## Not built yet

Front-channel or back-channel logout, `max_age` and `prompt=login`
(ignored), the `claims` and `request` parameters, CORS on the token
endpoint (browser-only apps need a small backend), a mail when someone
signs in to a new app.
