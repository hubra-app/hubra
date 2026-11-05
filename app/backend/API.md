# Hubra backend API

Every route of the core backend, by area. Plugin routes are not listed here;
each plugin documents its own (they live under `/api/v1/app/<prefix>`).

- Base URL: `https://api.hubra.club` (production), `http://localhost:5000`
  in development.
- Auth: JWT cookies (`HttpOnly`, `Domain=.hubra.club`, `SameSite=Lax`) plus
  the `X-CSRF-TOKEN` header on writes, or an API token as
  `Authorization: Bearer hbr_…` ([docs/api-tokens.md](../../docs/api-tokens.md)).
- Content type: `application/json`, camelCase field names.
- Old paths from before the area split (`/api/v1/members`,
  `/api/v1/manager/…`) still work: the backend rewrites them
  (`hubra/core/api_areas.py`).

How auth, CSRF, permissions and the areas fit together is in
[docs/api-overview.md](../../docs/api-overview.md).

This list was generated from the Flask URL map. To see the current routes,
including those of installed plugins, run `flask routes --sort rule` in
`app/backend`.

## Pagination envelope

Paginated lists take `page` and `pageSize` and return:

```json
{
  "data": [...],
  "total": 123,
  "page": 1,
  "pageSize": 25,
  "totalPages": 5
}
```

## Error format

```json
{ "error": "NOT_FOUND", "message": "Member 99 does not exist" }
```

| HTTP | Typical error codes |
| ---- | ------------------- |
| 400  | `VALIDATION_ERROR` |
| 401  | `UNAUTHORIZED` |
| 403  | `FORBIDDEN`, `MODULE_DISABLED`, `API_TOKEN_SCOPE` |
| 404  | `NOT_FOUND` |
| 409  | `CONFLICT`, `MODULE_DEPENDENCY_OFF`, `MODULE_HAS_DEPENDENTS` |
| 500  | `INTERNAL_ERROR` |

## Sign-in, account and public (`/api/v1/global`)

132 routes.

### account

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/account/` |  |
| PATCH | `/api/v1/global/account/` |  |
| DELETE | `/api/v1/global/account/account-sessions/<account_sid>` | End one of the account's own sign-ins (`club` null in the list). |
| GET | `/api/v1/global/account/all-sessions` | The account's sessions: its own sign-ins (SSO portal, `club` null) and those in every club, newest first. |
| DELETE | `/api/v1/global/account/all-sessions/<slug>/<session_id>` |  |
| POST | `/api/v1/global/account/all-sessions/revoke-all` | Sign out everywhere except this browser. |
| POST | `/api/v1/global/account/change-password` |  |
| GET | `/api/v1/global/account/deletion` | Whether the account can be deleted now, and what stands in the way. |
| POST | `/api/v1/global/account/deletion` | Delete (anonymise) the account. Body: `currentPassword`. |
| GET | `/api/v1/global/account/devices` |  |
| DELETE | `/api/v1/global/account/devices/<device_id>` |  |
| PATCH | `/api/v1/global/account/devices/<device_id>` |  |
| PATCH | `/api/v1/global/account/email` | Change the address (login and private mail); a new link goes out. |
| GET | `/api/v1/global/account/email-verification` |  |
| GET | `/api/v1/global/account/export` | Everything the account holds, as a JSON download (GDPR / revDSG). |
| GET | `/api/v1/global/account/groups` |  |
| GET | `/api/v1/global/account/invoices` |  |
| GET | `/api/v1/global/account/linked-accounts/` |  |
| DELETE | `/api/v1/global/account/linked-accounts/<code>` |  |
| GET | `/api/v1/global/account/linked-accounts/<code>/callback` |  |
| POST | `/api/v1/global/account/linked-accounts/<code>/start` |  |
| GET | `/api/v1/global/account/mail-settings` |  |
| PATCH | `/api/v1/global/account/mail-settings` |  |
| GET | `/api/v1/global/account/mfa` |  |
| POST | `/api/v1/global/account/mfa/recovery-codes` | New recovery codes; the old ones stop working. |
| POST | `/api/v1/global/account/mfa/totp/disable` |  |
| POST | `/api/v1/global/account/mfa/totp/enable` |  |
| POST | `/api/v1/global/account/mfa/totp/setup` | A new secret for the authenticator app; on only after /enable. |
| GET | `/api/v1/global/account/my-tenants` | Return all tenants the current user belongs to. |
| DELETE | `/api/v1/global/account/notifications` | `?read=1` keeps the unread ones. |
| GET | `/api/v1/global/account/notifications` |  |
| DELETE | `/api/v1/global/account/notifications/<club>/<notification_id>` |  |
| PATCH | `/api/v1/global/account/notifications/<club>/<notification_id>/read` |  |
| POST | `/api/v1/global/account/notifications/read-all` |  |
| POST | `/api/v1/global/account/passkeys` |  |
| PATCH | `/api/v1/global/account/passkeys/<passkey_id>` |  |
| POST | `/api/v1/global/account/passkeys/<passkey_id>/delete` | Remove a passkey; the password confirms it is the owner. |
| POST | `/api/v1/global/account/passkeys/options` | Start adding a passkey; the password confirms it is the owner. |
| POST | `/api/v1/global/account/password` | Change the password of the account, for every club at once. |
| GET | `/api/v1/global/account/permissions` | Return the current user's permission keys (or ['*'] for admins). |
| GET | `/api/v1/global/account/profile` |  |
| PATCH | `/api/v1/global/account/profile` |  |
| DELETE | `/api/v1/global/account/push` |  |
| GET | `/api/v1/global/account/push` | The key a browser subscribes with (made on first use), and whether the browser sending `?endpoint=` … |
| POST | `/api/v1/global/account/push` | Body: the browser's PushSubscription JSON (endpoint, keys.p256dh, keys.auth). |
| POST | `/api/v1/global/account/request-email-verification` |  |
| GET | `/api/v1/global/account/sessions` |  |
| DELETE | `/api/v1/global/account/sessions/<session_id>` |  |
| PATCH | `/api/v1/global/account/sessions/<session_id>` |  |
| POST | `/api/v1/global/account/sessions/revoke-all` |  |
| GET | `/api/v1/global/account/step-up` | What the confirm dialog offers, and whether this sign-in is confirmed right now (manage asks while the … |
| POST | `/api/v1/global/account/step-up` | Confirm the password (and the code, with two-factor on) for the platform actions that run code or open … |
| POST | `/api/v1/global/account/step-up/passkey` | Confirm with a passkey instead of the password. A passkey checks the person (user verification is … |
| POST | `/api/v1/global/account/step-up/passkey/options` | Start confirming a platform action with a passkey of this account. The challenge is tied to this account … |
| POST | `/api/v1/global/account/verify-email` |  |

### apps

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/apps/` |  |
| POST | `/api/v1/global/apps/<code>/connect` | Where to send the admin to sign in on the outside service. |
| GET | `/api/v1/global/apps/callback/<code>` | The outside service sends the admin back here. |
| DELETE | `/api/v1/global/apps/connections/<connection_id>` |  |
| GET | `/api/v1/global/apps/connections/<connection_id>` |  |
| PATCH | `/api/v1/global/apps/connections/<connection_id>` |  |
| POST | `/api/v1/global/apps/connections/<connection_id>/confirm` | The admin's approval: only now does the connection do anything. |
| GET | `/api/v1/global/apps/connections/<connection_id>/options` | What the connection's settings can choose from (provider-specific). |
| POST | `/api/v1/global/apps/connections/<connection_id>/test` |  |

### auth

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/v1/global/auth/forgot-password` |  |
| POST | `/api/v1/global/auth/login` |  |
| POST | `/api/v1/global/auth/login/mfa` | Second step of a sign-in with two-factor: the app or a recovery code. |
| POST | `/api/v1/global/auth/logout` |  |
| POST | `/api/v1/global/auth/passkey/login` | Sign in with a passkey, on its own or as the step after the password. |
| POST | `/api/v1/global/auth/passkey/options` | Start a passkey sign-in: any passkey, or the challenged account's. |
| POST | `/api/v1/global/auth/redirect-loop` |  |
| POST | `/api/v1/global/auth/refresh` |  |
| POST | `/api/v1/global/auth/reset-password` |  |
| POST | `/api/v1/global/auth/signup` | Create a new global User account with no tenant membership. |
| POST | `/api/v1/global/auth/switch-tenant` | Switch the active tenant for the current user. |

### clubs

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/clubs` | Active clubs the signed-in user can ask to join, with their status. |
| GET | `/api/v1/global/clubs/<slug>` | One club for its join page on SSO: name, your status, the tiers. |
| POST | `/api/v1/global/clubs/<slug>/join` | Join a club, or ask to join it. |
| GET | `/api/v1/global/clubs/<slug>/logo` | The club's logo as an image, for <img> tags on every portal. |

### health

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/health` | Minimal liveness check for load balancers — no auth, no infra details. |

### i18n

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/i18n/<locale>` |  |
| PATCH | `/api/v1/global/i18n/<locale>` |  |
| POST | `/api/v1/global/i18n/<locale>` |  |
| DELETE | `/api/v1/global/i18n/<locale>/<key>` |  |
| POST | `/api/v1/global/i18n/<locale>/copy-defaults` |  |
| POST | `/api/v1/global/i18n/<locale>/duplicate` |  |
| GET | `/api/v1/global/i18n/<locale>/export` |  |
| GET | `/api/v1/global/i18n/<locale>/flagged` |  |
| POST | `/api/v1/global/i18n/<locale>/import` |  |
| POST | `/api/v1/global/i18n/<locale>/report` |  |
| GET | `/api/v1/global/i18n/languages` |  |
| GET | `/api/v1/global/i18n/requests` | This club's suggestions, newest first. |
| POST | `/api/v1/global/i18n/requests` | Suggest a new text; a platform admin accepts or rejects it. |

### impersonation

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/v1/global/impersonation/stop` | Stop impersonating and give the platform user back their own session. |

### instance

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/instance` | Tell the SPAs where the SSO portal is, before anyone signs in. |

### invites

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/v1/global/invites/<invite_id>/accept` | Accept one of :func:`my_invites` (no link needed: the address is confirmed). |
| POST | `/api/v1/global/invites/accept` | Accept an invite: the signed-in account with the invited address joins. |
| POST | `/api/v1/global/invites/lookup` | The club and address behind an invite link, for the SSO accept page. |
| GET | `/api/v1/global/invites/mine` | Open invites to the signed-in account's confirmed address. |

### join-requests

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/join-requests/mine` | The clubs the signed-in user asked to join that have not answered yet. |

### maintenance

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/maintenance` |  |

### oauth

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/oauth/authorize` |  |
| POST | `/api/v1/global/oauth/authorize` | `{params: {...the authorize query}, allow: bool, club?: slug, platform?: true, days?: int}` → … |
| GET | `/api/v1/global/oauth/grants` |  |
| DELETE | `/api/v1/global/oauth/grants/<token_id>` |  |
| GET | `/api/v1/global/oauth/jwks` |  |
| POST | `/api/v1/global/oauth/register` | RFC 7591 for the Claude connector: an app registers itself, may only read through the connector, and the … |
| GET | `/api/v1/global/oauth/resource` | For the connector's /.well-known/oauth-protected-resource. |
| POST | `/api/v1/global/oauth/revoke` |  |
| POST | `/api/v1/global/oauth/token` |  |
| GET POST | `/api/v1/global/oauth/userinfo` | OpenID Connect userinfo: the claims of the bearer token's sign-in, as they are now. ApiTokenWsgi leaves … |

### plugins

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/plugins/<plugin_id>/frontend.js` | The plugin's built frontend. Only loaded plugins, only that one file. |

### public

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/public/plugins` |  |
| GET | `/api/v1/global/public/pricing` |  |
| GET | `/api/v1/global/public/roadmap` |  |

### roadmap

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/roadmap` | The public roadmap: titles, descriptions, status and votes only. |
| GET | `/api/v1/global/roadmap/` | The public roadmap: titles, descriptions, status and votes only. |

### status

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/status` |  |

### support

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/support/cases` |  |
| POST | `/api/v1/global/support/cases` | Body: `kind` (bug \| feature \| question), `title`, `description`; bug: `steps`, `expected`, … |
| GET | `/api/v1/global/support/cases/<case_id>` |  |
| POST | `/api/v1/global/support/cases/<case_id>/comments` |  |
| GET | `/api/v1/global/support/roadmap` |  |
| DELETE | `/api/v1/global/support/roadmap/<case_id>/vote` |  |
| POST | `/api/v1/global/support/roadmap/<case_id>/vote` |  |
| DELETE | `/api/v1/global/support/roadmap/items/<item_id>/vote` |  |
| POST | `/api/v1/global/support/roadmap/items/<item_id>/vote` | Vote for a planned item (ROADMAP.yaml `id`). |

### tenant-requests

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/v1/global/tenant-requests` | Submit a request for a new tenant (any authenticated user). |
| GET | `/api/v1/global/tenant-requests/mine` | List the current user's tenant requests. |

### version

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/global/version` | Return the current backend version and the commit it was built from. |
| GET | `/api/v1/global/version/changelog` | The backend version and the changelog entries; `?lang=de` for German. |
| GET | `/api/v1/global/version/roadmap` | The one public roadmap: what is being built now, next, later, what shipped, and the ideas people vote on … |

## Club app (`/api/v1/app`)

280 routes.

### admin

| Method | Path | What it does |
| --- | --- | --- |
| DELETE | `/api/v1/app/admin/backup-key` | Stop encrypting new backups to the club's key. Backups made before still open with it, so the club should … |
| GET | `/api/v1/app/admin/backup-key` | The club's own backup public key and whether backups use it. |
| PATCH | `/api/v1/app/admin/backup-key` | Body `{"club_only": bool}`: whether only the club's own key opens its new backups. Turning it on needs … |
| PUT | `/api/v1/app/admin/backup-key` | Body `{"public_key": "age1..."}`: the club's own backup key. |
| GET | `/api/v1/app/admin/bank-settings` | The account and address the club's QR invoices are paid to. |
| PUT | `/api/v1/app/admin/bank-settings` | Save the club's IBAN and creditor address (Settings > Verein). |
| GET | `/api/v1/app/admin/club-settings` | Return the current tenant's branding settings. |
| PATCH | `/api/v1/app/admin/club-settings` | Update the current tenant's branding settings. |
| GET | `/api/v1/app/admin/domains` | List all domains for the current tenant. |
| POST | `/api/v1/app/admin/domains` | Add a new domain with auto-generated verification token. |
| DELETE | `/api/v1/app/admin/domains/<domain_id>` | Remove a domain. |
| PATCH | `/api/v1/app/admin/domains/<domain_id>/primary` | Set a domain as the primary domain for the tenant. |
| POST | `/api/v1/app/admin/domains/<domain_id>/verify` | Trigger DNS verification for a domain. |

### api-tokens

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/api-tokens/` |  |
| DELETE | `/api/v1/app/api-tokens/<token_id>` |  |
| PATCH | `/api/v1/app/api-tokens/<token_id>` | Admins change club tokens; a member's own token they can only revoke. |
| POST | `/api/v1/app/api-tokens/<token_id>/roll` | Admins roll club tokens only: a member's personal token is theirs, and rolling it would hand its new … |
| POST | `/api/v1/app/api-tokens/club` |  |
| GET | `/api/v1/app/api-tokens/mine` |  |
| POST | `/api/v1/app/api-tokens/mine` |  |
| DELETE | `/api/v1/app/api-tokens/mine/<token_id>` |  |
| PATCH | `/api/v1/app/api-tokens/mine/<token_id>` |  |
| POST | `/api/v1/app/api-tokens/mine/<token_id>/roll` |  |
| GET | `/api/v1/app/api-tokens/scopes` |  |
| GET | `/api/v1/app/api-tokens/self` |  |
| PUT | `/api/v1/app/api-tokens/settings` | `{membersAllowed?, aiAllowed?}`: who may hold personal tokens, and whether AI assistants (the Claude … |

### applications

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/applications/` |  |
| DELETE | `/api/v1/app/applications/<application_id>` |  |
| GET | `/api/v1/app/applications/<application_id>` |  |
| POST | `/api/v1/app/applications/<application_id>/approve` |  |
| POST | `/api/v1/app/applications/<application_id>/decline` |  |

### audit

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/audit/` |  |
| GET | `/api/v1/app/audit/<entry_id>` |  |

### bindings

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/bindings/` |  |
| POST | `/api/v1/app/bindings/` |  |
| DELETE | `/api/v1/app/bindings/<binding_id>` |  |
| PUT | `/api/v1/app/bindings/<binding_id>` |  |
| POST | `/api/v1/app/bindings/<binding_id>/toggle` |  |
| GET | `/api/v1/app/bindings/keys` |  |
| POST | `/api/v1/app/bindings/keys` |  |
| DELETE | `/api/v1/app/bindings/keys/<key_id>` |  |
| PUT | `/api/v1/app/bindings/keys/<key_id>` |  |
| GET | `/api/v1/app/bindings/preview` |  |
| GET | `/api/v1/app/bindings/registry` |  |
| GET | `/api/v1/app/bindings/sources` |  |
| GET | `/api/v1/app/bindings/validators` |  |

### dashboard

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/dashboard/summary` |  |

### events

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/events/` |  |
| POST | `/api/v1/app/events/` |  |
| DELETE | `/api/v1/app/events/<event_id>` |  |
| GET | `/api/v1/app/events/<event_id>` |  |
| PATCH | `/api/v1/app/events/<event_id>` |  |
| POST | `/api/v1/app/events/<event_id>/attend/<member_id>` |  |
| GET | `/api/v1/app/events/<event_id>/attendance` |  |
| PUT | `/api/v1/app/events/<event_id>/attendance` |  |
| DELETE | `/api/v1/app/events/<event_id>/attendees/<member_id>` |  |
| POST | `/api/v1/app/events/<event_id>/attendees/<member_id>` |  |
| POST | `/api/v1/app/events/<event_id>/cancel-registration` |  |
| POST | `/api/v1/app/events/<event_id>/maybe` |  |
| POST | `/api/v1/app/events/<event_id>/register` |  |
| POST | `/api/v1/app/events/<event_id>/register/<member_id>` |  |
| GET | `/api/v1/app/events/<event_id>/registrations` |  |
| POST | `/api/v1/app/events/<event_id>/registrations/<member_id>/<any(approve, decline):decision>` |  |
| GET | `/api/v1/app/events/attendance` | Attendance per member over the events of a period (`?group_id`, `series_id`, `category`, `type`; … |
| GET | `/api/v1/app/events/attendance/groups/<group_id>` | The same for one group's events; a role held for that group is enough (a trainer of the team). |
| GET | `/api/v1/app/events/attendance/me` |  |
| GET | `/api/v1/app/events/attendance/members/<member_id>` |  |
| GET | `/api/v1/app/events/calendar` | Export events as iCal format. |
| GET | `/api/v1/app/events/calendar/<token>.ics` | Public iCalendar feed for calendar apps (token from /calendar/feed). |
| GET | `/api/v1/app/events/calendar/feed` | The member's personal calendar subscription URL. |
| POST | `/api/v1/app/events/calendar/feed/renew` | A new feed URL for the member; every older one stops working. |
| GET | `/api/v1/app/events/public-links` | Where the club's public events can be read (for the events page). |
| GET | `/api/v1/app/events/public/<slug>` | The club's upcoming public events, for its website. |
| GET | `/api/v1/app/events/public/<slug>.ics` | The club's public events as a calendar to subscribe to. |
| GET | `/api/v1/app/events/public/<slug>/trials` | The trainings someone who isn't a member may book to try. |
| POST | `/api/v1/app/events/public/<slug>/trials` | Book a trial training. It counts once the address is confirmed. |
| POST | `/api/v1/app/events/public/<slug>/trials/cancel` | The person can't come after all: the place is free again. |
| POST | `/api/v1/app/events/public/<slug>/trials/confirm` | The link in the mail: the booking counts from now on. |
| GET | `/api/v1/app/events/trials` | Trial bookings: upcoming by default, `?past=1` for the last months. |
| DELETE | `/api/v1/app/events/trials/<signup_id>` | Remove a booking and the person's details (on request, or by mistake). |
| PATCH | `/api/v1/app/events/trials/<signup_id>` | Mark who came (attended, no_show), or cancel a booking. |
| POST | `/api/v1/app/events/trials/<signup_id>/invite` | Invite the person to join as a trial member (the usual invite mail). |

### features

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/features` |  |
| GET | `/api/v1/app/features/catalog` | Every module the platform offers, with its default. |
| GET | `/api/v1/app/features/tenants/<tenant_id>` | Module state for one club, as the club admin sees it plus `allowed`. |
| PUT | `/api/v1/app/features/tenants/<tenant_id>/<feature_code>` | Allow or block a module for a club, and optionally switch it. |

### finance

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/finance/external-parties` |  |
| POST | `/api/v1/app/finance/external-parties` |  |
| DELETE | `/api/v1/app/finance/external-parties/<id>` |  |
| PATCH | `/api/v1/app/finance/external-parties/<id>` |  |
| GET | `/api/v1/app/finance/fee-basis` | How the yearly expenses behind percentage and formula tiers come together; ?source=&extra=&manual= … |
| GET | `/api/v1/app/finance/invoices` |  |
| POST | `/api/v1/app/finance/invoices` |  |
| DELETE | `/api/v1/app/finance/invoices/<id>` |  |
| GET | `/api/v1/app/finance/invoices/<id>` |  |
| PATCH | `/api/v1/app/finance/invoices/<id>` |  |
| GET | `/api/v1/app/finance/invoices/<id>/qr-bill.pdf` | Download a QR-bill invoice PDF for the given invoice. |
| POST | `/api/v1/app/finance/invoices/<id>/remind` |  |
| GET | `/api/v1/app/finance/invoices/<id>/reminders` |  |
| POST | `/api/v1/app/finance/invoices/bulk` |  |
| GET | `/api/v1/app/finance/invoices/mine` |  |

### functions

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/functions/` |  |
| POST | `/api/v1/app/functions/` |  |
| DELETE | `/api/v1/app/functions/<function_id>` |  |
| GET | `/api/v1/app/functions/<function_id>` |  |
| PATCH | `/api/v1/app/functions/<function_id>` |  |
| POST | `/api/v1/app/functions/<function_id>/holders` |  |
| DELETE | `/api/v1/app/functions/<function_id>/holders/<member_id>` |  |

### groups

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/groups/` |  |
| POST | `/api/v1/app/groups/` |  |
| POST | `/api/v1/app/groups/<group_id>/join` |  |
| POST | `/api/v1/app/groups/<group_id>/leave` |  |
| GET | `/api/v1/app/groups/<group_id>/mailing-list` | Return email addresses of all group members for mailing list export. |
| GET | `/api/v1/app/groups/<group_id>/members` |  |
| DELETE | `/api/v1/app/groups/<group_id>/members/<member_id>` |  |
| PATCH | `/api/v1/app/groups/<group_id>/members/<member_id>` |  |
| POST | `/api/v1/app/groups/<group_id>/members/<member_id>` |  |
| DELETE | `/api/v1/app/groups/<id>` |  |
| GET | `/api/v1/app/groups/<id>` |  |
| PATCH | `/api/v1/app/groups/<id>` |  |
| GET | `/api/v1/app/groups/count` | Return total non-archived group count and archived count. |
| GET | `/api/v1/app/groups/joinable` |  |

### mail

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/mail/addresses` |  |
| DELETE | `/api/v1/app/mail/addresses/<address_id>` |  |
| GET | `/api/v1/app/mail/addresses/<address_id>` |  |
| PATCH | `/api/v1/app/mail/addresses/<address_id>` |  |
| GET | `/api/v1/app/mail/addresses/<address_id>/aliases` |  |
| POST | `/api/v1/app/mail/addresses/<address_id>/aliases` |  |
| DELETE | `/api/v1/app/mail/addresses/<address_id>/aliases/<alias_id>` |  |
| PATCH | `/api/v1/app/mail/addresses/<address_id>/aliases/<alias_id>/toggle` |  |
| GET | `/api/v1/app/mail/addresses/<address_id>/from-whitelist` |  |
| PUT | `/api/v1/app/mail/addresses/<address_id>/from-whitelist` |  |
| PATCH | `/api/v1/app/mail/addresses/<address_id>/prefix` |  |
| PATCH | `/api/v1/app/mail/addresses/<address_id>/toggle` |  |
| GET | `/api/v1/app/mail/addresses/all` |  |
| GET | `/api/v1/app/mail/addresses/selectable` |  |
| GET | `/api/v1/app/mail/aliases` |  |
| POST | `/api/v1/app/mail/aliases` |  |
| DELETE | `/api/v1/app/mail/aliases/<wd_id>` |  |
| PATCH | `/api/v1/app/mail/aliases/<wd_id>` |  |
| GET | `/api/v1/app/mail/functions` |  |
| DELETE | `/api/v1/app/mail/functions/<function_id>` |  |
| POST | `/api/v1/app/mail/functions/<function_id>` |  |
| GET | `/api/v1/app/mail/functions/<function_id>/aliases` |  |
| POST | `/api/v1/app/mail/functions/<function_id>/aliases` |  |
| DELETE | `/api/v1/app/mail/functions/<function_id>/aliases/<alias_id>` |  |
| PATCH | `/api/v1/app/mail/functions/<function_id>/aliases/<alias_id>/toggle` |  |
| PATCH | `/api/v1/app/mail/functions/<function_id>/prefix` |  |
| PATCH | `/api/v1/app/mail/functions/<function_id>/toggle` |  |
| GET | `/api/v1/app/mail/groups` |  |
| DELETE | `/api/v1/app/mail/groups/<group_id>` |  |
| POST | `/api/v1/app/mail/groups/<group_id>` |  |
| GET | `/api/v1/app/mail/groups/<group_id>/aliases` |  |
| POST | `/api/v1/app/mail/groups/<group_id>/aliases` |  |
| DELETE | `/api/v1/app/mail/groups/<group_id>/aliases/<alias_id>` |  |
| PATCH | `/api/v1/app/mail/groups/<group_id>/aliases/<alias_id>/toggle` |  |
| PATCH | `/api/v1/app/mail/groups/<group_id>/prefix` |  |
| PATCH | `/api/v1/app/mail/groups/<group_id>/toggle` |  |
| GET | `/api/v1/app/mail/health` | Return WildDuck reachability status. No authentication required. |
| GET | `/api/v1/app/mail/mailboxes` |  |
| POST | `/api/v1/app/mail/mailboxes` |  |
| DELETE | `/api/v1/app/mail/mailboxes/<wd_id>` |  |
| PATCH | `/api/v1/app/mail/mailboxes/<wd_id>` |  |
| GET | `/api/v1/app/mail/members` |  |
| GET | `/api/v1/app/mail/members-mail` |  |
| DELETE | `/api/v1/app/mail/members-mail/<member_id>` |  |
| POST | `/api/v1/app/mail/members-mail/<member_id>` |  |
| PATCH | `/api/v1/app/mail/members-mail/<member_id>/toggle` |  |
| PATCH | `/api/v1/app/mail/members/<member_id>` |  |
| GET | `/api/v1/app/mail/mine` | The club addresses of the groups the member leads and the functions they hold: what they may switch on or … |
| POST | `/api/v1/app/mail/reconcile` |  |
| GET | `/api/v1/app/mail/resolve-local-part` |  |
| GET | `/api/v1/app/mail/system-addresses` |  |
| POST | `/api/v1/app/mail/system-addresses` |  |
| DELETE | `/api/v1/app/mail/system-addresses/<address_id>` |  |
| GET | `/api/v1/app/mail/system-addresses/<address_id>/aliases` |  |
| POST | `/api/v1/app/mail/system-addresses/<address_id>/aliases` |  |
| DELETE | `/api/v1/app/mail/system-addresses/<address_id>/aliases/<alias_id>` |  |
| PATCH | `/api/v1/app/mail/system-addresses/<address_id>/aliases/<alias_id>/toggle` |  |
| GET | `/api/v1/app/mail/system-addresses/<address_id>/forwarding` |  |
| PUT | `/api/v1/app/mail/system-addresses/<address_id>/forwarding` |  |
| POST | `/api/v1/app/mail/system-addresses/<address_id>/reset-password` |  |
| PATCH | `/api/v1/app/mail/system-addresses/<address_id>/toggle` |  |
| POST | `/api/v1/app/mail/test` | Send a test mail the way the club's mail goes out: from the platform sender (or the club's own mailbox), … |

### members

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/members/` |  |
| POST | `/api/v1/app/members/` |  |
| DELETE | `/api/v1/app/members/<member_id>` |  |
| GET | `/api/v1/app/members/<member_id>` |  |
| PATCH | `/api/v1/app/members/<member_id>` |  |
| POST | `/api/v1/app/members/<member_id>/archive` |  |
| POST | `/api/v1/app/members/<member_id>/disable` |  |
| POST | `/api/v1/app/members/<member_id>/enable` |  |
| POST | `/api/v1/app/members/<member_id>/leave/approve` |  |
| POST | `/api/v1/app/members/<member_id>/leave/decline` |  |
| POST | `/api/v1/app/members/<member_id>/provision` |  |
| DELETE | `/api/v1/app/members/<member_id>/sessions` | Admin endpoint: revoke all sessions for a member (force logout). |
| DELETE | `/api/v1/app/members/<member_id>/soft` | Soft-delete a member (sets deleted_at, preserves data). |
| POST | `/api/v1/app/members/<member_id>/unarchive` |  |
| GET | `/api/v1/app/members/count` |  |
| GET | `/api/v1/app/members/export` |  |
| POST | `/api/v1/app/members/import` | Import members from a CSV file upload. |
| GET | `/api/v1/app/members/invites` | Invites the club sent that nobody accepted yet, newest first. |
| DELETE | `/api/v1/app/members/invites/<invite_id>` | Withdraw an invite; its link stops working. |
| POST | `/api/v1/app/members/invites/<invite_id>/resend` | Send the invite again with a fresh link (the old link stops working). |
| GET | `/api/v1/app/members/leave-requests` |  |
| GET | `/api/v1/app/members/me/directory` | What the member shows other members of this club. |
| PUT | `/api/v1/app/members/me/directory` |  |
| DELETE | `/api/v1/app/members/me/leave` |  |
| GET | `/api/v1/app/members/me/leave` |  |
| POST | `/api/v1/app/members/me/leave` | Leave the club now, or ask to leave when the club wants to approve it. |
| GET | `/api/v1/app/members/me/mail` | Return the authenticated member's mailbox and aliases. |
| GET | `/api/v1/app/members/me/notifications` | Per topic, whether the member gets it in the bell, by browser push, (reminders only) by mail, and through … |
| PUT | `/api/v1/app/members/me/notifications` | Body `{topic: {channel: bool}}`; what is left out keeps its value. |
| GET | `/api/v1/app/members/me/reminders` | Whether the member gets reminder mails before events and polls. |
| PUT | `/api/v1/app/members/me/reminders` |  |
| GET | `/api/v1/app/members/stats` |  |
| GET | `/api/v1/app/members/stats.csv` |  |

### modules

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/modules/` | All modules with their state for the current club. |
| PUT | `/api/v1/app/modules/<code>` |  |
| PUT | `/api/v1/app/modules/<code>/settings` |  |

### notifications

| Method | Path | What it does |
| --- | --- | --- |
| DELETE | `/api/v1/app/notifications/` | Clear the caller's own notifications; `?read=1` keeps unread ones. |
| GET | `/api/v1/app/notifications/` |  |
| POST | `/api/v1/app/notifications/` |  |
| DELETE | `/api/v1/app/notifications/<notification_id>` |  |
| PATCH | `/api/v1/app/notifications/<notification_id>/read` |  |
| POST | `/api/v1/app/notifications/read-all` |  |

### oauth

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/oauth/apps` |  |
| POST | `/api/v1/app/oauth/apps` | A "Sign in with Hubra" app for the club's website or forum: signs in the club's members only, reads nothing. |
| DELETE | `/api/v1/app/oauth/apps/<app_id>` | Deletes the app and every sign-in it holds. |
| PATCH | `/api/v1/app/oauth/apps/<app_id>` |  |
| POST | `/api/v1/app/oauth/apps/<app_id>/secret` |  |

### permissions

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/permissions` | Return a sorted list of all permission-gated endpoints. |

### polls

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/polls/` |  |
| POST | `/api/v1/app/polls/` |  |
| DELETE | `/api/v1/app/polls/<poll_id>` |  |
| GET | `/api/v1/app/polls/<poll_id>` |  |
| PATCH | `/api/v1/app/polls/<poll_id>` |  |
| PATCH | `/api/v1/app/polls/<poll_id>/close` |  |
| DELETE | `/api/v1/app/polls/<poll_id>/proxy` |  |
| GET | `/api/v1/app/polls/<poll_id>/proxy` |  |
| POST | `/api/v1/app/polls/<poll_id>/proxy` |  |
| POST | `/api/v1/app/polls/<poll_id>/remind` |  |
| POST | `/api/v1/app/polls/<poll_id>/vote` |  |

### posts

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/posts/` |  |
| POST | `/api/v1/app/posts/` |  |
| DELETE | `/api/v1/app/posts/<post_id>` |  |
| GET | `/api/v1/app/posts/<post_id>` |  |
| PATCH | `/api/v1/app/posts/<post_id>` |  |
| GET | `/api/v1/app/posts/<post_id>/comments` |  |
| POST | `/api/v1/app/posts/<post_id>/comments` |  |
| DELETE | `/api/v1/app/posts/<post_id>/comments/<comment_id>` |  |
| DELETE | `/api/v1/app/posts/<post_id>/like` |  |
| POST | `/api/v1/app/posts/<post_id>/like` |  |

### roles

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/roles/` |  |
| POST | `/api/v1/app/roles/` |  |
| DELETE | `/api/v1/app/roles/<role_id>` |  |
| PATCH | `/api/v1/app/roles/<role_id>` |  |
| GET | `/api/v1/app/roles/<role_id>/permissions` |  |
| PUT | `/api/v1/app/roles/<role_id>/permissions` |  |
| GET | `/api/v1/app/roles/<role_id>/scopes` |  |
| POST | `/api/v1/app/roles/<role_id>/scopes` |  |
| DELETE | `/api/v1/app/roles/<role_id>/scopes/<scope_id>` |  |

### settings

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/settings/` |  |
| DELETE | `/api/v1/app/settings/<key>` |  |
| PUT | `/api/v1/app/settings/<key>` |  |
| POST | `/api/v1/app/settings/<key>/revert` |  |
| GET | `/api/v1/app/settings/club-profile` | Name, look and announcement banner of the club, for every member. |

### tiers

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/app/tiers/` |  |
| POST | `/api/v1/app/tiers/` |  |
| DELETE | `/api/v1/app/tiers/<tier_id>` |  |
| PATCH | `/api/v1/app/tiers/<tier_id>` |  |
| GET | `/api/v1/app/tiers/<tier_id>/members` |  |
| GET | `/api/v1/app/tiers/<tier_id>/plans` |  |
| POST | `/api/v1/app/tiers/<tier_id>/plans` |  |
| POST | `/api/v1/app/tiers/calculate-cost` |  |
| PUT | `/api/v1/app/tiers/members/<member_id>/plan` |  |
| GET | `/api/v1/app/tiers/my-plan` |  |
| PUT | `/api/v1/app/tiers/my-plan` |  |
| DELETE | `/api/v1/app/tiers/plans/<plan_id>` |  |
| PATCH | `/api/v1/app/tiers/plans/<plan_id>` |  |

## Platform / manage (`/api/v1/platform`)

147 routes.

### addons

| Method | Path | What it does |
| --- | --- | --- |
| PUT | `/api/v1/platform/addons/<code>` |  |

### alerts

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/alerts/api-errors` | Where API errors happen: per route and exact status code, per ten minutes, and what the error-rate alert … |
| GET | `/api/v1/platform/alerts/me` | Which alert mails the signed-in platform admin gets. |
| PUT | `/api/v1/platform/alerts/me` | Body `{"<type>": bool, ...}` for the types in `platform_monitor.ALERT_TYPES`; types left out keep … |
| GET | `/api/v1/platform/alerts/overview` | What is wrong right now, the latest alerts, and 24 h of warnings and errors per area, for manage › Alerts. |
| GET | `/api/v1/platform/alerts/performance` | API timing per route and slow queries, for manage › Alerts › Performance. `hours`: 1 to 24 clock hours, … |
| GET | `/api/v1/platform/alerts/switches` |  |
| PUT | `/api/v1/platform/alerts/switches` | Body `{"enabled": bool, "types": {"<type>": {"mail": bool, "discord": bool}}, "events": {"<category>": … |

### api-tokens

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/api-tokens/` |  |
| DELETE | `/api/v1/platform/api-tokens/<token_id>` |  |
| GET | `/api/v1/platform/api-tokens/mine` |  |
| POST | `/api/v1/platform/api-tokens/mine` |  |
| DELETE | `/api/v1/platform/api-tokens/mine/<token_id>` |  |
| PATCH | `/api/v1/platform/api-tokens/mine/<token_id>` |  |
| POST | `/api/v1/platform/api-tokens/mine/<token_id>/roll` |  |
| GET | `/api/v1/platform/api-tokens/self` |  |

### backups

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/backups/` | Backup records, newest first (`?tenant_id=` for one club's). |
| POST | `/api/v1/platform/backups/` | Start a manual backup via Celery. Returns 202 with the task ID. |
| DELETE | `/api/v1/platform/backups/<record_id>` | Delete a backup (S3 object and record). |
| GET | `/api/v1/platform/backups/<record_id>` |  |
| POST | `/api/v1/platform/backups/<record_id>/restore` | Restore one club from a club backup. Returns 202 (200 when TESTING). |
| POST | `/api/v1/platform/backups/<record_id>/verify` | Start a verification via Celery. Returns 202. |
| GET | `/api/v1/platform/backups/config` | S3 connection and encryption status. |

### clubs

| Method | Path | What it does |
| --- | --- | --- |
| PUT | `/api/v1/platform/clubs/<tenant_id>/backup-key` | Body `{"public_key": "age1..." \| null}`: the club's own backup key. Its next backups are encrypted to … |

### discord

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/v1/platform/discord/check` | Ask Discord again now instead of using the last check. |
| GET | `/api/v1/platform/discord/clubs` | Every club server the bot is on, with what it does there. |
| GET | `/api/v1/platform/discord/clubs/<connection_id>/activity` | One club server's bot log. |
| GET | `/api/v1/platform/discord/servers` | The servers the bot is on, for picking the platform log server. |
| GET | `/api/v1/platform/discord/servers/<guild_id>/channels` | Text channels on one of the bot's servers that the bot can post in. |
| POST | `/api/v1/platform/discord/servers/<guild_id>/channels` | Make a text channel on one of the bot's servers (private by default), for the platform log or audit channel. |
| GET | `/api/v1/platform/discord/status` | The Discord bot: settings, sign-in, platform log, club servers. |
| POST | `/api/v1/platform/discord/test` | Post a test message with the bot to the platform log channel, or with `{"channel": "audit"}` to the … |

### encryption

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/encryption` | The master key, each club's data key and backup key, and how many stored values are not on the current … |
| POST | `/api/v1/platform/encryption/rotate` | Move every stored value onto the current keys (after a master key change). Body `{"new_keys": true, … |

### errors

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/errors` | Grouped API errors. `status`: open (default), resolved or all; `q` searches type, message, route and … |
| GET | `/api/v1/platform/errors/<group_id>` |  |
| POST | `/api/v1/platform/errors/<group_id>/<any(resolve, reopen):action>` | Mark a group resolved (it opens again if it happens again), or open. |

### events

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/events` | The platform event log, newest first. |

### features

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/features` | Early-access flags: stage, how many clubs have each, the group. |
| PUT | `/api/v1/platform/features/<key>` | `{"stage": "off" \| "early" \| "all"}`. |

### health

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/health` | Every service check with latencies, run now, plus the version. |

### jobs

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/jobs` | Background jobs for manage › Diagnostics › Background jobs: queued and running jobs, per-task counts for … |
| DELETE | `/api/v1/platform/jobs/failed/<failure_id>` | Remove a failed job from the list (it is not run again). |
| POST | `/api/v1/platform/jobs/failed/<failure_id>/retry` | Run a failed job again with the same arguments (and club). |

### mail

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/v1/platform/mail/test` | Send a test mail from the system sender through the relay, or with `via: "fallback"` through the … |

### mail-relay

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/mail-relay` | Both relays with their last check, whether mail skips the main relay right now, and the last 24 hours of … |
| POST | `/api/v1/platform/mail-relay/check` | Body `{"which": "relay" \| "fallback"}` (both if left out): log in to the relay now, without sending a mail. |
| POST | `/api/v1/platform/mail-relay/use-main` | Try the main relay again for the next mail, instead of waiting for the 15 minutes after a fallback to run … |

### mail-server

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/mail-server` | Every mailbox and alias on the shared mail server, with its club. |
| DELETE | `/api/v1/platform/mail-server/<entry_type>/<entry_id>` | Delete a mailbox or alias that no club manages. |
| POST | `/api/v1/platform/mail-server/reconcile` | Reconcile every club's addresses with the mail server now. |

### maintenance

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/maintenance` |  |
| PUT | `/api/v1/platform/maintenance` | Body `{"on": bool, "message": str, "minutes": int \| null}`. |
| GET | `/api/v1/platform/maintenance/windows` | Planned, running and the last 20 past windows (newest first). |
| POST | `/api/v1/platform/maintenance/windows` | Body `{"starts_at", "ends_at", "message", "tenant_ids": [..] \| null, "notice_hours"}`; `tenant_ids` … |
| POST | `/api/v1/platform/maintenance/windows/<window_id>/cancel` | Cancel a planned window, or end a running one now. |

### oauth

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/oauth/apps` |  |
| POST | `/api/v1/platform/oauth/apps` |  |
| DELETE | `/api/v1/platform/oauth/apps/<app_id>` | Deletes the app and every sign-in it holds. |
| PATCH | `/api/v1/platform/oauth/apps/<app_id>` |  |
| POST | `/api/v1/platform/oauth/apps/<app_id>/secret` |  |
| POST | `/api/v1/platform/oauth/keys/rotate` | A new ID token signing key; the one before stays published so tokens signed just now still check out. |

### permissions

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/permissions` | Every club API endpoint that a club permission guards, by path and method. |

### plans

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/plans` |  |
| POST | `/api/v1/platform/plans` |  |
| DELETE | `/api/v1/platform/plans/<key>` |  |
| PATCH | `/api/v1/platform/plans/<key>` |  |

### plugins

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/plugins/` | Every plugin: shipped, installed and offered by the repositories. |
| DELETE | `/api/v1/platform/plugins/<plugin_id>` |  |
| PUT | `/api/v1/platform/plugins/<plugin_id>/hold` |  |
| POST | `/api/v1/platform/plugins/<plugin_id>/install` | Install or update *plugin_id*. |
| POST | `/api/v1/platform/plugins/<plugin_id>/rollback` |  |
| GET | `/api/v1/platform/plugins/keys` | Every key this platform trusts, with its purpose: "plugins" (signs plugins), "index" (signs a repository … |
| POST | `/api/v1/platform/plugins/keys` | Trust an author's public key (their plugins then install as community). |
| DELETE | `/api/v1/platform/plugins/keys/<key_pk>` |  |
| GET | `/api/v1/platform/plugins/repositories` |  |
| POST | `/api/v1/platform/plugins/repositories` | Add a repository; `keyId` is the key the manager compared. |
| DELETE | `/api/v1/platform/plugins/repositories/<repo_id>` | Remove a repository. Plugins installed from it stay installed. |
| PUT | `/api/v1/platform/plugins/repositories/<repo_id>` |  |
| POST | `/api/v1/platform/plugins/repositories/preview` | Fetch an index and show its name and key, before trusting it. |
| DELETE | `/api/v1/platform/plugins/stage/<token>` |  |
| POST | `/api/v1/platform/plugins/stage/<token>/confirm` |  |
| GET | `/api/v1/platform/plugins/status` | What this process has loaded, to tell when a reload went through. |
| PUT | `/api/v1/platform/plugins/updates` |  |
| POST | `/api/v1/platform/plugins/updates/check` |  |
| POST | `/api/v1/platform/plugins/upload` | Check an uploaded .zip; answers what would be installed (confirm next). |

### settings

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/settings` | Every platform setting with its value and where it comes from. |
| PATCH | `/api/v1/platform/settings` | Body: `{"<key>": "<value>" \| null, ...}`. `null` resets to the env default. |

### support

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/support/cases` | `?kind=bug\|feature\|question&status=active\|<status>&area=&q=&page=&per_page=`. |
| GET | `/api/v1/platform/support/cases/<case_id>` |  |
| PATCH | `/api/v1/platform/support/cases/<case_id>` | Body: any of `status`, `isPublic`, `roadmapItem` (a ROADMAP.yaml id or null), `title`, … |
| POST | `/api/v1/platform/support/cases/<case_id>/comments` | Body: `{"body": str, "internal"?: bool}`. A visible answer is mailed to the reporter; an internal note … |
| POST | `/api/v1/platform/support/cases/<case_id>/merge` | Body: `{"into": <case id>}`. The case closes and points there; its votes (and its reporter's) move to … |

### system

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/system/audit` | List platform-wide audit entries with pagination and filters. |
| GET | `/api/v1/platform/system/audit/export` | The same search as CSV, at most 10 000 rows. The export itself is written to the platform log. |
| GET | `/api/v1/platform/system/audit/search` | The platform log and every club's audit log in one list, newest first. `q` searches action, people, … |
| GET | `/api/v1/platform/system/data-requests` |  |
| PATCH | `/api/v1/platform/system/data-requests/<request_id>` |  |
| POST | `/api/v1/platform/system/data-requests/<request_id>/<any(done, rejected):status>` |  |
| POST | `/api/v1/platform/system/data-requests/<request_id>/delete-member` | Delete the member's data in the club. The body repeats the club's slug, so it is not done by a stray click. |
| POST | `/api/v1/platform/system/data-requests/<request_id>/export` | The member's data as JSON; the download is noted on the request. |
| GET | `/api/v1/platform/system/global-permissions` | List all available global permissions. |
| GET | `/api/v1/platform/system/global-roles` | List all global roles with their permissions. |
| POST | `/api/v1/platform/system/global-roles` | Create a custom global role. |
| PATCH | `/api/v1/platform/system/global-roles/<role_id>` | Update a global role's permissions. |
| GET | `/api/v1/platform/system/metrics` | Aggregate platform metrics from Redis counters. |
| GET | `/api/v1/platform/system/plans` | The plans a club can be put on (not hidden), for the plan pickers. |
| GET | `/api/v1/platform/system/support-sessions` | Every time platform staff opened a club as one of its members, newest first: who, which club and member, … |
| POST | `/api/v1/platform/system/support-sessions/<session_id>/end` | End someone's running support session now: its tokens are refused from the next request on. |
| GET | `/api/v1/platform/system/tenant-requests` | List all tenant requests (superadmin only). |
| POST | `/api/v1/platform/system/tenant-requests` | Submit a request for a new tenant (any authenticated user). |
| POST | `/api/v1/platform/system/tenant-requests/<req_id>/approve` | Approve a tenant request and provision the tenant (superadmin only). |
| POST | `/api/v1/platform/system/tenant-requests/<req_id>/reject` | Reject a tenant request (superadmin only). |
| GET | `/api/v1/platform/system/tenants` | List all tenants with optional search, filtering, sorting, pagination. |
| POST | `/api/v1/platform/system/tenants` | Provision a new tenant (creates record + schema + seeds). |
| DELETE | `/api/v1/platform/system/tenants/<tenant_id>` | Delete a tenant. Soft-delete by default; force=true for permanent deletion. |
| GET | `/api/v1/platform/system/tenants/<tenant_id>` | Get a single tenant by ID, including usage summary. |
| PATCH | `/api/v1/platform/system/tenants/<tenant_id>` | Update tenant attributes (name, plan, settings). |
| GET | `/api/v1/platform/system/tenants/<tenant_id>/admins` | The club's owners and admins, and what the caller may change. |
| POST | `/api/v1/platform/system/tenants/<tenant_id>/admins` | Make an existing account an admin (or owner) of the club. |
| DELETE | `/api/v1/platform/system/tenants/<tenant_id>/admins/<user_id>` | Take the admin and owner roles away; the person stays a member. |
| POST | `/api/v1/platform/system/tenants/<tenant_id>/archive` | Archive a tenant. |
| GET | `/api/v1/platform/system/tenants/<tenant_id>/billing` | Plan status, price, discount, sponsor and add-ons (stored only). |
| PATCH | `/api/v1/platform/system/tenants/<tenant_id>/billing` | Change some of the club's terms (see services/club_billing.py). |
| POST | `/api/v1/platform/system/tenants/<tenant_id>/data-requests` |  |
| POST | `/api/v1/platform/system/tenants/<tenant_id>/disable` | Suspend a tenant. |
| GET | `/api/v1/platform/system/tenants/<tenant_id>/early-access` | Whether the club is in the early-access group, and each flag for it. |
| PUT | `/api/v1/platform/system/tenants/<tenant_id>/early-access` | `{"early_access": bool, "features": {key: true \| false \| null}}`; both optional (null: back to the … |
| POST | `/api/v1/platform/system/tenants/<tenant_id>/enable` | Reactivate a tenant. |
| POST | `/api/v1/platform/system/tenants/<tenant_id>/impersonate` | Start impersonating a user within a tenant. |
| GET | `/api/v1/platform/system/tenants/<tenant_id>/limits` | Members, mails this month and storage against the club's limits. |
| PUT | `/api/v1/platform/system/tenants/<tenant_id>/limits` | The club's own limits: `{kind: number \| null \| "plan"}` (null: no limit; "plan": back to the plan's). |
| GET | `/api/v1/platform/system/tenants/<tenant_id>/members` | List all members in a tenant schema. |
| POST | `/api/v1/platform/system/tenants/<tenant_id>/members` | Add an existing User to a tenant as a Member. |
| GET | `/api/v1/platform/system/tenants/<tenant_id>/provisioning-status` | Get async provisioning status for a tenant. |
| GET | `/api/v1/platform/system/tenants/<tenant_id>/stats` | Get detailed usage statistics for a tenant. |
| PATCH | `/api/v1/platform/system/tenants/<tenant_id>/status` | Update tenant status (active / suspended / archived). |
| GET | `/api/v1/platform/system/tenants/<tenant_id>/trends` | Logins, active members, members, events, invoices and mails per week or month (`range`: 12w, 26w or 12m). |
| GET | `/api/v1/platform/system/tenants/health` | Every club with its health, for manage › Alle Vereine. |
| GET | `/api/v1/platform/system/users` | List all users with pagination and search. |
| GET | `/api/v1/platform/system/users/<user_id>` | Get a user's details including tenant memberships. |
| GET | `/api/v1/platform/system/users/<user_id>/roles` | List a user's global role assignments, each with the clubs it is limited to. |
| POST | `/api/v1/platform/system/users/<user_id>/roles` | Assign a global role to a user: `{"role_id", "tenant_ids"?}`. |
| DELETE | `/api/v1/platform/system/users/<user_id>/roles/<role_id>` | Remove a global role from a user. |
| GET | `/api/v1/platform/system/users/search` | Search users by email for role assignment. |

### translation-requests

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/v1/platform/translation-requests` | Clubs' suggestions; `?status=pending\|accepted\|rejected` (all if left out). |
| POST | `/api/v1/platform/translation-requests/<request_id>` | Body: `{"accept": bool, "value"?: str, "note"?: str}`. |

## Outside the areas

3 routes.

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/.well-known/oauth-authorization-server` |  |
| GET | `/.well-known/openid-configuration` |  |
| GET | `/health` |  |

