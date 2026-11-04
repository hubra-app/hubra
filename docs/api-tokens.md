# API tokens

Bearer tokens for scripts, integrations and (later) the Claude connector.
The design and the open decisions are in the concept doc
(https://claude.ai/artifact/UJBF3LBZfBPrs9ZHfjKrse); this page describes what
the backend does today. There is no UI yet: tokens are made through the API
below, from a signed-in browser session.

```
curl -H "Authorization: Bearer hbr_pat_…" https://api.hubra.club/api/v1/events/
```

## Kinds

| Kind | Prefix | Made by | Acts as | Opens |
| --- | --- | --- | --- | --- |
| Personal | `hbr_pat_` | a member (admins always; others only if the club allows it) | that member, in that one club | club routes |
| Club | `hbr_club_` | a club admin | that admin's membership (so capped by the admin's rights) | club routes |
| Platform | `hbr_plat_` | a platform admin | that platform admin | platform routes, **GET only** |

Personal tokens are always bound to one club. A platform token never opens
a club, and a club token never opens the platform API.

## Rules

- **Rights.** A request passes only if the person may do it right now
  (roles, functions, group roles, object rules, club two-factor rule,
  archived/blocked) **and** the derived permission key is in the token's
  scopes. Admins are limited by scopes too. Scopes are permission keys
  (`events.events.read`) for club tokens and global keys
  (`platform.diagnostics`) for platform tokens.
- **Making a token** needs two-factor sign-in on the account, a fresh
  step-up (`POST /account/step-up`, 10 minutes) and no support session.
  Scopes must be keys the maker holds; `{"preset": "read"}` takes every read
  key they hold. Lifetimes: 7, 30, 90 (default) or 365 days; platform tokens
  7 or 30. Optional `allowedIps` (CIDR list).
- **Never with a token:** routes without `permission_required`, `can_update`
  or `require_global_permission` (account, sign-in, notifications …), the
  blueprints in `api_tokens._NEVER_BLUEPRINTS` (auth, account, linked
  accounts, token management, club switching/impersonation, plugins,
  backups), every `require_step_up` route, routes marked `no_api_tokens`, and
  plugin routes. `tests/auth/test_api_tokens.py` walks every registered route
  to keep this true.
- **One credential per request.** `ApiTokenWsgi` drops every cookie and the
  `X-CSRF-Token`, `X-Account-CSRF` and `X-Tenant-Slug` headers of a request
  that carries `Bearer hbr_…`, and every `Set-Cookie` of its answer. The
  request then runs on a 5-minute JWT for the token's person that exists
  only inside the request, so all existing checks apply unchanged.
- **Not for browsers.** A token request with an `Origin` header is refused
  (`API_TOKEN_BROWSER`); CORS doesn't allow the `Authorization` header.
- **Storage.** Only `HMAC-SHA256(pepper, secret)` is stored; the pepper is
  derived from `FERNET_KEY` (old keys still verify, so `flask crypto rotate`
  doesn't end tokens). The secret is returned once at creation.
- **Per-token permissions.** Every token has its own scope list.
  `PATCH` renames a token or changes its scopes: narrowing needs nothing
  more, adding a key needs the same two-factor + step-up as making one, and
  only keys the person holds now.
- **Rolling.** `POST …/roll` gives a token a new secret: a new token with
  the same name, kind, person, club and IP list, and the old secret keeps
  working for `graceHours` (0, 1, 24 default, or 168) so scripts switch
  without downtime. Needs two-factor + step-up. Scopes the person no longer
  holds are dropped on the way. The new lifetime defaults to the old one's.
  Admins roll and edit club tokens only, never a member's own token (the
  new secret would reach someone else).
- **Ending.** Revoked by the owner, by the club's admins (any token of their
  club) or by platform admins (any token). Ends on its own when it expires,
  after 60 days unused, after 10 wrong secrets in 10 minutes, when the
  account is disabled or its sessions are reset (password reset, sign out
  everywhere), when the club is no longer active, or for personal tokens of
  non-admins when the club switches member tokens off.
- **Rate limits.** 120 reads and 30 writes per minute per token, 600 per
  minute per club, 30 invalid tokens per minute per IP (`429 RATE_LIMITED`).
- **Audit.** Writes through a token appear in the club audit log as
  "Name (Token «token name»)", which the Discord audit channel shows too.
  Making and revoking tokens is audited (club audit log, or the platform
  audit log for platform tokens).

## Endpoints

Club (`/api/v1/app/api-tokens`, club session):

| Method | Path | Who | What |
| --- | --- | --- | --- |
| GET | `/scopes` | member | keys I may put on a token, the read preset, the club switch |
| GET | `/mine` | member | my personal tokens in this club |
| POST | `/mine` | member | make one: `{name, scopes \| preset, days, allowedIps?}` |
| DELETE | `/mine/<id>` | member | revoke mine |
| PATCH | `/mine/<id>` | member | rename, change scopes |
| POST | `/mine/<id>/roll` | member | roll: `{graceHours?, days?}` |
| GET | `/` | admin | every token of the club |
| POST | `/club` | admin | make a club token |
| DELETE | `/<id>` | admin | revoke any token of the club |
| PATCH | `/<id>` | admin | change a club token (not a member's own) |
| POST | `/<id>/roll` | admin | roll a club token (not a member's own) |
| PUT | `/settings` | admin | `{membersAllowed: bool}` (off by default) |

Platform (`/api/v1/platform/api-tokens`, account sign-in):

| Method | Path | Who | What |
| --- | --- | --- | --- |
| GET | `/mine` | platform admin | my tokens and the keys I may grant |
| POST | `/mine` | platform admin | make one: `{name, scopes?, days}` (default scope `platform.diagnostics`) |
| DELETE | `/mine/<id>` | platform admin | revoke mine |
| PATCH | `/mine/<id>` | platform admin | rename, change scopes |
| POST | `/mine/<id>/roll` | platform admin | roll mine |
| GET | `/` | `platform.settings` | every token |
| DELETE | `/<id>` | `platform.settings` | revoke any token |

## Errors

`API_TOKEN_INVALID` (401), `API_TOKEN_EXPIRED` (401), `API_TOKEN_REVOKED`
(401), `API_TOKEN_NOT_ALLOWED` (403, route takes no tokens),
`API_TOKEN_READ_ONLY` (403), `API_TOKEN_SCOPE` (403), `API_TOKEN_WRONG_CLUB`
(403), `API_TOKEN_DISABLED_BY_CLUB` (403), `API_TOKEN_BROWSER` (403),
`API_TOKEN_IP` (403), `API_TOKEN_LIMIT` (409, too many active tokens),
`RATE_LIMITED` (429).

## Not built yet

UI (SSO/club app/manage pages), mails for new and ended tokens, pausing a
club token and mailing the club's admins when its admin leaves (today it
just stops working), opt-in for plugin routes, the MCP server.
