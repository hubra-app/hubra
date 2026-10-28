# Single-club install

Hubra can run one club on its own, without the manager portal
(`manage.`) and the SSO portal (`sso.`). You need the backend (with its
Celery worker and beat), Postgres, Redis and the club frontend. The admin
and SSO frontends are not needed.

## How it works

Set `SINGLE_CLUB` to the club's slug on the backend, worker and beat.

- Every request runs in that club. The frontend sends no club header and
  the club is not part of any URL: its pages live at `/app/…`.
- The club frontend asks `GET /api/v1/instance` at start. When the answer
  says `"mode": "single"`, it uses its own pages for sign-in
  (`/login`), password reset (`/forgot-password`, `/reset-password`) and
  email verification (`/verify-email`). The same frontend image works for
  both setups.
- Mails for password reset and email verification link to
  `FRONTEND_BASE_URL`. `SSO_BASE_URL` is ignored.
- The manager API answers 404: club provisioning, club requests, support
  access (impersonation), the module catalog and everything under
  `/api/v2/manager/`. Club admins still switch modules on and off in
  **Settings › Modules**.
- There is no open sign-up. New people use **Apply for membership**
  (`/apply`), and an admin approves them. Accounts that are not a member
  of the club cannot sign in.

The club is an ordinary club schema (`tenant_<id>`), the same as on a
multi-club install. Moving to the multi-club setup later means removing
`SINGLE_CLUB` and adding the manager and SSO frontends.

## One host

Serve the frontend and the API from the same host, with `/api` going to
the backend. Then the session cookies need no domain and the browser
sends no cross-origin requests:

```
FRONTEND_BASE_URL=https://club.example.org
CORS_ORIGINS=https://club.example.org
# JWT_COOKIE_DOMAIN not set
# VITE_API_BASE not set: the frontend calls /api on its own host
```

## First start

The init job runs, in this order:

```
flask db upgrade
flask sync-permissions
flask seed --skip-migrate
flask setup-club
```

`flask setup-club` reads `SINGLE_CLUB`, `CLUB_NAME`, `ADMIN_EMAIL` and
`ADMIN_PASSWORD` (or the options `--slug`, `--name`, `--admin-email`,
`--admin-password`). It creates the club with its roles, the default
membership tier and its modules, and the first admin as the club's
Owner. Once the club exists it does nothing, so it is safe on every start.

Without `ADMIN_PASSWORD` it prints a one-time password in the job's log:

```
Club 'FC Beispiel' set up (slug=fcb, id=1).
  Owner: praesident@fcb.ch, one-time password: JF9NK9yEfT_opNVF
  The password must be changed at the first sign-in.
```

If `ADMIN_EMAIL` already has an account (for example a superadmin), that
account becomes the Owner and keeps its password.

## Checking it

```
curl https://club.example.org/api/v1/instance
{"club":{"name":"FC Beispiel","slug":"fcb"},"mode":"single","signup":false,"ssoUrl":null}
```

`"club": null` means `flask setup-club` has not run yet. The frontend
then says the club is not set up.
