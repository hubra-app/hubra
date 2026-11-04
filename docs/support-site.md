# Support site (support.hubra.club)

`app/support-frontend` is the public help and feedback site: help articles,
a set-up checklist for new clubs, the roadmap with voting, what's new, the
system status, problem reports, ideas, a contact form, the person's own
reports, a developer page, a security page and the person's privacy requests.

It used to be spread over SSO (`/roadmap`, `/status`) and the club app. SSO
now forwards `/roadmap` and `/status` to the support site (with their query,
so `/status?club=<slug>` keeps working).

## Why its own image

The support site is its own image (`ghcr.io/hubra-app/hubra/support-frontend`)
and its own Deployment. Upgrading the backend or the other frontends doesn't
restart it, so the status page and the help stay reachable while the rest of
Hubra rolls. On k3s it runs two replicas with `maxUnavailable: 0` and a
PodDisruptionBudget, because it is where people look when something else is
down. When the API itself is down, the status page says so ("the status
cannot be loaded right now"), which is the answer people need.

## Sign-in

There is no sign-in of its own. The SSO cookies are set for the parent
domain (`JWT_COOKIE_DOMAIN=.hubra.club`), so a person signed in anywhere in
Hubra is signed in on the support site too. "Anmelden" goes to
`sso.hubra.club/login?redirect=<support page>`; SSO trusts the support origin
from `VITE_SUPPORT_URL` (`app/sso-frontend/src/redirect.ts`).

Reading needs no account: help, roadmap, what's new, status, developer and
security pages. Voting, reports, ideas, questions, "My reports" and
"My data" need one.

## Pages

| Path | What | API |
| --- | --- | --- |
| `/` | search, tiles, topics, live status pill | `GET /global/status` |
| `/hilfe`, `/hilfe/<slug>` | help articles (`src/content/help.ts`), search | none |
| `/start` | checklist for a new club; ticks kept in the browser only | `GET /global/account/my-tenants` |
| `/roadmap` | the one roadmap; vote when signed in | `GET /global/roadmap`, `/global/support/roadmap`, votes |
| `/neuigkeiten` | release notes | `GET /global/version/changelog` |
| `/status` | system status (`?club=<slug>`) | `GET /global/status` |
| `/melden`, `/idee`, `/kontakt` | problem report, idea, question | `POST /global/support/cases` |
| `/meine`, `/meine/<id>` | own cases with answers, reply | `/global/support/cases…` |
| `/entwickler` | API tokens, Claude connector, public data, plugins | none |
| `/sicherheit` | how to report a vulnerability | none |
| `/datenschutz` | download the account, delete it | `/global/account/export`, `/global/account/deletion` |
| `/.well-known/security.txt` | static file | none |

English paths (`/help`, `/privacy`, …) redirect to the German ones; the
language switch changes the texts, not the paths.

### Help articles

`src/content/help.ts` holds every article in German and English, in the
small Markdown subset of `src/components/Markdown.tsx` (## and ###, lists,
`>` notes, code blocks, tables, `**bold**`, `` `code` `` and links; no HTML).
`tests/content.test.ts` checks that both languages have the same sections
and that every internal link points at a page or article that exists.
`docs/club-admin-guide.md` is the longer version for admins; keep the menu
names in step with the club app.

### Questions

The contact form sends a case of kind `question` (besides `bug` and
`feature`): title, text and optionally the club and area, no steps, device
info or votes. Manage › Reports & ideas has a Questions tab, and answers
mail the person like the other kinds.

### My data

- **Download** (`GET /global/account/export`): one JSON file with the
  profile, the clubs, account sign-ins, known devices, passkeys, linked
  accounts, API tokens, club requests and the person's support cases with
  their answers. Columns with secrets (passwords, hashes, TOTP, recovery
  codes, token secrets, push keys) are never included
  (`hubra/core/services/account_privacy.py`).
- **Delete** (`POST /global/account/deletion` with `currentPassword`): only
  when the account is in no club (`user_tenants` is empty) and has no
  platform role or superadmin flag; `GET /global/account/deletion` lists
  what stands in the way. The `users` row stays, because support cases,
  audit entries and archived member records in clubs point at it, but it is
  anonymised (login `deleted-<id>@deleted.invalid`, no name, address, phone,
  avatar, two-factor), disabled, and every sign-in, device, passkey, push
  subscription, linked account and API token is removed. A confirmation
  goes to the old address (template `account_closed`).

What a club keeps about its members (member record, invoices, attendance)
belongs to the club. The page says so; the person asks the club, and leaves
the club first.

## Setting it up

1. DNS: `support.hubra.club` to the cluster (like the other hosts).
2. `CORS_ORIGINS`: add `https://support.hubra.club` (secret `hubra-env`),
   then restart the backends. Without it the browser blocks every API call
   from the support site.
3. Manage › Reports & ideas › Support site: set the address
   (`support.url`, starts out as `SUPPORT_BASE_URL`). Answers to reports and
   the password-changed mail then link to the support site; empty keeps the
   old links to the club app.
4. Pin the image in the cluster overlay once a release has it
   (`deploy/clusters/contabo/kustomization.yaml`).

The frontends read the address from `VITE_SUPPORT_URL` (ConfigMap
`hubra-frontend`, Compose `SUPPORT_BASE_URL`, default
`https://support.hubra.club`).

Compose publishes it on `127.0.0.1:8083`; with `docker-compose.traefik.yml`
it gets `${HUBRA_SUPPORT_HOST:-support.hubra.club}`.

## Developing

```
cd app/support-frontend
npm ci
npm run dev     # http://localhost:5176, API proxied to :5000
npm test        # content and helper tests (node --test)
```

Sign in on the SSO dev server (`:5175`) first: on localhost the cookies are
shared across ports.
