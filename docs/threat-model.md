# Threat model

What Hubra protects, every way into it, and what stops each way being
misused. The handbook (`core/security.md`) asks for one such page per app.
**Update it in the same pull request that adds a new way in** (an API area,
a token kind, a plugin capability, a webhook, a background process that
talks to the outside).

Rows that still need a decision or a check say TODO.

## What we protect

| Asset | Where it lives | Worst case |
| --- | --- | --- |
| Member data (names, addresses, contact, fees, attendance) | Postgres, one schema per club | One club reads or changes another club's members |
| Accounts and sign-ins | `public` schema, HttpOnly JWT cookies | Someone takes over an account, a club admin or a platform admin |
| Club money (invoices, payments, Stripe, bank imports) | Club schema, Stripe | Payments go to the wrong place, records are changed unnoticed |
| Secrets (door codes, mailbox passwords, relay and storage keys, Discord and Stripe keys) | Encrypted with a per-club or platform data key, locked by `FERNET_KEY` ([operator-guide.md](operator-guide.md#encryption-keys)) | A database dump or backup opens them |
| Backups | Encrypted files in backup storage ([disaster-recovery.md](disaster-recovery.md)) | A copy of a backup reveals every club |
| Plugin trust | Official public keys in `app/backend/hubra/core/plugins/keys/`, trust rules in `core/plugins/trust.py` | Foreign code runs inside the app backend |
| The audit log | `global_audit_logs` and each club's log | Changes can't be traced back to who made them |

## Trust boundaries

1. **Internet → ingress.** TLS ends at Traefik or the Kubernetes ingress;
   CrowdSec sees every request ([architecture.md](architecture.md)).
2. **Frontends → API.** The frontends are static files; every decision is
   made in the backend. Frontend permission checks are UX only.
3. **Club → club.** Each club has its own schema, and inside a club the
   connection switches to that club's own database role
   ([club-db-roles.md](club-db-roles.md)), so a query that escapes the
   search path still can't read another club's tables.
4. **Club → platform.** The club app, the global area (sign-in, account) and
   manage are separate API areas and can run as separate backends
   ([platform-backend.md](platform-backend.md)).
5. **Hubra → plugin code.** Plugin code runs only in the app backend and its
   worker; the global and platform backends read manifests only
   (`MANIFEST_ONLY_ROLES`). What a plugin may do depends on who signed it
   ([plugins.md](plugins.md#trust)).
6. **Hubra → the outside.** Outgoing calls (webhooks, mail, Discord, Stripe,
   S3) go to addresses an admin configured.

## Ways in

| Way in | Who | Checks | Docs |
| --- | --- | --- | --- |
| Browser session | Members, club admins, platform staff | HttpOnly `Secure` `SameSite=Lax` cookies, CSRF double-submit header on every write, CORS allowlist without wildcards, sign-ins with an absolute lifetime, rate-limited auth endpoints | [architecture.md](architecture.md#cross-origin-auth) |
| Two-factor sign-in | Everyone; required for platform staff, optional per club | Passkeys or TOTP (secret encrypted), recovery codes; clubs can require it for admins or all members | [operator-guide.md](operator-guide.md#two-factor-sign-in) |
| API tokens (club, personal, platform) | Scripts, integrations | Made only with two-factor sign-in; scopes are permission keys the maker holds; only an HMAC of the secret is stored; expire, roll and revoke; never reach account or sign-in routes | [api-tokens.md](api-tokens.md) |
| OAuth apps, the Claude connector (MCP) | Apps a person signs in to | Short-lived access tokens, refresh-token reuse ends the sign-in, `read`/`write` scopes, platform sign-ins read-only; the MCP server has no database or credentials of its own | [oauth.md](oauth.md), [mcp.md](mcp.md) |
| Sign in with Hubra (OIDC) | Club websites, forums | Client secret shown once, PKCE for apps without a secret, who may sign in checked on every refresh | [oidc.md](oidc.md) |
| Public API | Anyone | Two read-only endpoints, no cookies | [public-api.md](public-api.md) |
| Plugins | Plugin authors | Signature tiers, admin accepts unsigned plugins explicitly, limits per plugin (`core/plugins/limits.py`), routes only under the club area with `permission_required` | [plugins.md](plugins.md) |
| File uploads | Members, plugins | Size limits per plan and club (`MAX_UPLOAD_MB` at nginx and backend), files encrypted with the club's key | [configuration.md](configuration.md) |
| Inbound webhooks (Stripe) | Stripe | Signature checked (`app/backend/hubra/api/billing/routes.py`) | [billing.md](billing.md) |
| Outgoing webhooks | Clubs choose the address | Signed with a per-webhook secret, https only, private, local and reserved addresses refused on every call | [webhooks.md](webhooks.md) |
| Discord | Club Discord servers | Bot and client secrets stored encrypted; TODO: note where interaction signatures are checked | [discord.md](discord.md) |
| Federation | Associations of clubs | Separate permissions; the association sees counts and function holders' club addresses only | [federation.md](federation.md) |
| Mail stack (opt-in) | Inbound SMTP, IMAP clients | TODO: threats of inbound mail and the IMAP server | [modules/mail/README.md](../modules/mail/README.md) |

## Threats and what stops them

| Threat | What stops it |
| --- | --- |
| A member reaches a page or action without the right | Every backend route has `@login_required` and `@permission_required(...)`; every new endpoint gets an auth-failure test |
| One club reads another club's data | Schema per club plus a database role per club; club values encrypted per club, so a copied value reads as empty |
| Stolen cookie or CSRF | HttpOnly cookies, CSRF header on writes, CSP and security headers set by each frontend image |
| Stolen API token | Scoped, expiring, revocable, stored as HMAC; reuse of a replaced refresh token ends the sign-in |
| Brute force on sign-in | Rate limits on the auth endpoints, CrowdSec at the ingress, two-factor sign-in |
| Open redirect after sign-in | Redirect targets checked against an allowlist (`validateRedirect()` in `app/sso-frontend/src/redirect.ts`) |
| Malicious or broken plugin | Signature tiers, manifest-only loading outside the app backend, plugins never import each other, per-plugin limits |
| Server-side request forgery through webhooks | Private, local and reserved addresses refused on every call |
| Database dump or backup leaks | Secrets encrypted with data keys locked by `FERNET_KEY`, which never goes into the database; backups encrypted |
| Secrets in logs, bundles or source maps | Secrets never logged; only public config under `VITE_`; production source maps off |
| Changes nobody can trace | Audit log per club and platform; API token and OAuth actions are audited like a person's |

## Reviews

Audit reports live in [security/](security/). TODO: link each one here as
it lands.
