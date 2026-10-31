# Operator guide

For the people who run a Hubra installation: install it, keep it up to date,
back it up and decide what clubs can use. Club owners and admins have their
own guide, [club-admin-guide.md](club-admin-guide.md).

This page is the overview. The details live in the linked pages.

## The parts

| Host (default)      | What                         | Who uses it                                   |
| ------------------- | ---------------------------- | --------------------------------------------- |
| `sso.hubra.club`    | Sign-in, sign-up, account    | Everyone                                      |
| `join.hubra.club`   | Same app: start or find a club (`/start`, `/clubs`) | People without a club yet |
| `app.hubra.club`    | The club app, `/<club>/app/…` | Members and club admins                      |
| `manage.hubra.club` | Manager portal               | Platform staff, club owners and club admins   |
| `api.hubra.club`    | REST API                     | The three apps                                |

Behind them run the Flask backend, a Celery worker and Celery beat, Postgres
and Redis. Each club has its own Postgres schema (`tenant_<id>`); accounts,
clubs and platform settings are in `public`. The optional self-hosted mail
stack is in [modules/mail/](../modules/mail/README.md).

## Install

Pick one:

- **Docker Compose** on one machine: [run-with-docker.md](run-with-docker.md).
- **Kubernetes (k3s)** with Kustomize, by hand or from a GitOps tool: [k3s.md](k3s.md).

Both use the same images from `ghcr.io/hubra-app/hubra/*` and the same
`.env` (on k3s it becomes the Secret `hubra-env`). Start from
`scripts/init-env.sh`, which fills every secret with a random value.

### Checklist for a new installation

1. **Secrets.** `SECRET_KEY`, `JWT_SECRET_KEY` and `FERNET_KEY` are set,
   and `BACKUP_PUBLIC_KEY` holds the public half of a pair from
   `flask backups keygen`. Put the backup private key and `FERNET_KEY` in a
   password manager now: without them, backups and stored door codes
   cannot be read. The private key does not go on the server.
2. **Host names.** `FRONTEND_BASE_URL`, `MANAGE_BASE_URL`, `SSO_BASE_URL`,
   `CORS_ORIGINS` (all four app hosts, including the join host),
   `JWT_COOKIE_DOMAIN` and `JWT_COOKIE_SECURE=true`. See
   [configuration.md](configuration.md#cross-origin-auth-variables).
3. **Platform admin.** Put your address in `SUPERADMIN_EMAILS`. Sign up on
   the SSO host with that address; the account becomes superadmin on the
   next start (or right away with `flask ensure-superadmins`). One-off
   alternative: `flask make-admin --email you@example.com`.
4. **Mail relay.** In manage › Platform › Settings, fill in the relay and the
   system sender, then press **Send test**. Until mail works, sign-up
   e-mails, invites and password resets don't arrive, and nobody is asked
   to confirm their address.
5. **Backup storage.** In the same page, fill in the S3 bucket. Then press
   **Create backup now** under Platform › Backups once and check that it
   shows up. See [Backups](#backups-and-restore).
6. **Health.** Platform › Diagnostics shows the backend version, the health
   checks (database, Redis, mail relay, IMAP, and a Celery check that runs
   every 20 seconds) and every API route with the permission it needs.
7. **First club.** Either create it yourself under Platform › All clubs
   (**Create club**, optionally with an admin e-mail and password), or let
   people request one on `join.<domain>/start` and approve it under
   Platform › Club requests. Whoever requested the club becomes its owner.

## Upgrade

Every start runs the same steps (Compose service `flask-init`, on k3s the
`flask-init` initContainer of the backend):

```sh
flask db upgrade        # migrations: public and every club schema
flask sync-permissions  # permission catalog from the routes
flask seed --skip-migrate
flask ensure-superadmins
flask plugins sync      # installed plugins: unpack and migrate
```

So an upgrade is: take a backup, switch to the new images, restart.

1. **Read the release notes** on the GitHub release (and
   `app/backend/CHANGELOG.md`). Look for lines that ask you to change `.env`.
2. **Back up.** Platform › Backups › **Create backup now**, for Global and
   for each club. A migration is not undone by going back to the old images;
   the backup is the way back.
3. **Switch the version.**
   - Compose: set `HUBRA_VERSION` in `.env` to the release (`1.2.3`), then
     `docker compose pull && docker compose up -d`.
   - k3s: set `newTag` in `deploy/app/kustomization.yaml` (or your overlay)
     and push or apply. With `latest`, also run
     `kubectl -n hubra rollout restart deployment`.
4. **Watch the migrations.**
   - Compose: `docker compose logs flask-init` must end with exit code 0
     (`docker compose ps` shows `Exited (0)`).
   - k3s: `kubectl -n hubra logs deploy/backend -c flask-init`.

   If a migration fails, the backend doesn't start and the old pods (k3s)
   keep serving. Fix the cause, or go back to the previous version and
   restore the backup from step 2.
5. **Check.** Platform › Diagnostics shows the new backend version and green
   health checks. `scripts/smoke-test.sh` does the same from the command
   line for Compose.

Pin a version for production. `latest` follows the newest release, and
`sha-<commit>` is one exact build.

## Change the encryption key

`FERNET_KEY` encrypts the secrets Hubra stores: door codes, binding values,
mailbox passwords and the secret platform settings (relay passwords, backup
storage key). Production does not start without it. Installs from before it
was required used a key derived from `SECRET_KEY`; those values stay
readable, so setting a fresh `FERNET_KEY` loses nothing.

To change the key (after a leak, or once a year), without downtime:

1. Generate a new key:
   `python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`.
2. Put the new key in `FERNET_KEY` and the old one in `FERNET_OLD_KEYS`
   (comma-separated if there are several). Restart (on k3s, re-run
   `deploy/create-secrets.sh` or update the SOPS secret, then
   `kubectl -n hubra rollout restart deployment`). Everything stays
   readable; new values use the new key.
3. Re-encrypt what is stored: `flask crypto rotate` (Compose:
   `docker compose exec backend flask crypto rotate`, k3s:
   `kubectl -n hubra exec deploy/backend -- flask crypto rotate`).
4. `flask crypto check` must end with `OK: old keys can be removed.` and
   exit 0. If it lists values that no key opens, a key is missing from
   `FERNET_OLD_KEYS`; nothing was overwritten, so add it back and run
   step 3 again.
5. Remove the old key from `FERNET_OLD_KEYS`, restart, and store the new
   key in your password manager. Keep the old key there too until the
   oldest backup made before the change has expired: restoring such a
   backup brings back values encrypted with it.

The IMAP inbox plugin reads `FERNET_OLD_KEYS` too and re-encrypts each
mailbox password on its next sync.

## Mail look and sender logo

Every mail Hubra sends (invites, password resets, invoices, ...) uses one
layout in the Hubra brand: the club's logo and name on top, a white card with
a violet button, and "Sent with hubra" at the bottom. The logo is the one a
club sets in Settings › Verein (PNG, JPEG, GIF or WebP up to 256 KB; an SVG or
bigger logo shows the Hubra mark instead). It is sent inside the mail, so it
shows without "load images". The texts are the platform's translations
(Manage › Platform settings › Übersetzungen; clubs can suggest changes); the
layout is in `app/backend/hubra/templates/email/`.

The round picture next to the sender in an inbox is not part of the mail. The
mail app takes it from the sending domain's **BIMI** record:

1. The domain of the system sender needs DMARC with `p=quarantine` or
   `p=reject` (`_dmarc.example.org TXT "v=DMARC1; p=quarantine; ..."`).
2. Serve [`brand/hubra-bimi.svg`](../brand/hubra-bimi.svg) over HTTPS, e.g. at
   `https://hubra.club/bimi.svg`.
3. Add `default._bimi.example.org TXT "v=BIMI1; l=https://hubra.club/bimi.svg"`.

Yahoo, AOL, Fastmail and others then show the logo. Gmail and Apple Mail also
want a VMC or CMC certificate in the record's `a=` tag, which needs a
registered trademark (VMC) or a logo in public use for a year (CMC).

## Backups and restore

Backups are a platform task: manage › Platform › Backups, global permission
`backups.manage` (superadmins have it). Clubs have no backup screen.

- Each backup holds one schema: **Global** (`public`: accounts, clubs,
  platform settings) or **one club**. A single club can be restored without
  touching the others.
- Celery beat makes a scheduled set every day, week and month, and keeps
  7 daily, 4 weekly and 6 monthly backups per set. Manual backups are kept
  until you delete them.
- Files are encrypted to `BACKUP_PUBLIC_KEY` ([age](https://age-encryption.org))
  and stored in the S3 bucket from Platform › Settings › Backup storage. The
  server only has the public key, so a break-in on the server cannot read
  the backups. The private key stays in your password manager; restore
  asks for it. Make the pair with `flask backups keygen`.
- A club can get its own key: `flask backups club-key <club> age1…`. Its
  backups are then encrypted to both keys, so the club can open its own
  backups with its private key, and you still can with yours.
- **Verify** without a key checks that the file in storage is complete and
  unchanged (checksum). Paste the private key to also open it and count the
  tables; do that now and then as a test restore.
- `BACKUP_PRIVATE_KEY` in `.env` lets verify and restore run without asking,
  at the price that a break-in on the server then opens the backups too.
- Installs without `BACKUP_PUBLIC_KEY` keep using the `BACKUP_ENCRYPTION_KEY`
  passphrase (GPG). Older `.dump.gpg` backups always open with it, so keep
  it until they have expired.

**Restore one club** (the usual case: someone deleted the wrong thing):
Platform › Backups, filter by the club, pick a backup from before the
mistake, click the restore icon, paste the backup private key and type the club's
address to confirm. The key is used for this restore only and not stored
(on its way to the background worker it is encrypted with `FERNET_KEY` and
expires after an hour). The
current schema is kept as a safety copy (`tenant_<id>_before_restore_…`),
the backup is restored and migrated to the running code, and the rest of the
platform is untouched. If anything fails, the club stays as it was. Drop the
safety copy once the club has checked its data
([disaster-recovery.md](disaster-recovery.md), Step 3 Option A).

**Restore everything** (database lost): download and decrypt the global
backup and every club's, restore global first, then the clubs, then bring
the id sequences up. The commands are in
[disaster-recovery.md](disaster-recovery.md), Step 3 Option B. Practise it on
a throwaway database once a quarter (Step 5 there).

A plain `pg_dump` of the whole database also works as an extra copy, for
example before an upgrade on Compose:
`docker compose exec postgres pg_dump -U hubra -Fc hubra > hubra.dump`.

## Modules

Every section of the club app is a module. Core, Members and Roles are always
on. Events, Finance, Functions, Groups, Polls and Posts are on for a new
club; Bindings, Codes, Inventory and Mail are off.

- **Club admins** switch modules on and off in the club app under
  Settings › Modules & plugins. Switching off hides the module and keeps its
  data.
- **You** can block a module for one club: Platform › All clubs › the club ›
  Modules. A blocked module stays off and the club can't switch it on.
- **Command line**, for scripts:

  ```sh
  flask modules list --tenant <slug>
  flask modules enable <code> --tenant <slug>
  flask modules disable <code> --tenant <slug>
  ```

The **Mail** module needs the self-hosted mail stack
([modules/mail/README.md](../modules/mail/README.md)); don't let clubs switch
it on without it.

How modules are built: [app/backend/hubra/modules/README.md](../app/backend/hubra/modules/README.md).

## Plugins

Plugins add modules that are not part of Hubra (keys, budgets, bank import,
Discord and more). You install a plugin once for the whole platform in manage
› Platform › Plugin catalogue; each club then switches its modules on in
Settings › Modules & plugins like a built-in module.

- Only the global permission `plugins.manage` (superadmins) can install.
- A plugin runs with access to every club's data. Install only official
  plugins, or ones signed with a key you trust. An unsigned plugin needs an
  explicit "I trust this code".
- Installing runs the plugin's migrations in every club. All backend and
  Celery processes load it within about 15 seconds, without a restart.
- Updates: the catalogue checks every six hours and notes new versions in the
  audit log. You can hold a plugin at a version or roll back; rollback does
  not undo migrations.
- Uninstalling keeps the plugin's tables unless you tick "also delete its
  data".

Details, the trust badges and the CLI: [plugins/README.md](../plugins/README.md).

## Settings

There are four levels, each changed in a different place.

| Level | Where | Examples |
| ----- | ----- | -------- |
| Installation | `.env` (k3s: Secret `hubra-env`), restart needed | Secrets, database, Redis, host names, CORS, cookie domain, `SUPERADMIN_EMAILS`, plugin directories |
| Limits | `settings.yaml`, or env with `__` (`LIMITS__MAX_MEMBERS=50`) | Members per club, events per month |
| Platform | manage › Platform › Settings, no restart | Mail relay, system sender, backup storage |
| Club | club app › Settings (club admins) | Name, colours, language, privacy, leaving rules, banner, modules, domains |

A platform setting starts from its env variable. A value saved in manage
wins until you press **Reset to env**. `BACKUP_ENCRYPTION_KEY` is env only.
The full list is in [configuration.md](configuration.md) and `.env.example`.

## People and permissions on the platform

- **Superadmin** (`SUPERADMIN_EMAILS` or `flask make-admin`): everything in
  manage › Platform.
- **Global roles** (manage › Platform › Roles) give staff single platform
  permissions, such as `backups.manage`, `platform.settings`,
  `platform.diagnostics` or `plugins.manage`, without making them
  superadmin.
- **Club owners and admins** see manage too, but only Personal › My clubs
  and the clubs they run. There they choose who else is a club admin
  (My clubs › the club › Admins). Platform staff find the same list, and the
  club's modules, under Platform › All clubs › the club.
- Accounts belong to their people. Clubs never create accounts, set
  passwords or change e-mail addresses; members join through an invite link
  or a request on the join page.

Everything staff do in manage is written to Platform › Audit log.

## Day to day

```sh
# Compose (on k3s: kubectl -n hubra exec deploy/backend -- <command>)
docker compose exec backend flask list-tenants
docker compose exec backend flask modules list --tenant <slug>
docker compose exec backend flask plugins list
docker compose logs -f backend celery-worker celery-beat
```

- **Celery beat** must run exactly once: it starts the scheduled backups,
  invoice generation and reminders, health checks, plugin update checks and
  mail housekeeping.
- **Rate limits** use Redis. Behind a proxy, set `REAL_IP_FROM` (Compose) so
  limits see real client addresses.
- **Logs** are JSON lines on stdout; lines of one API request share a
  `request_id`.
