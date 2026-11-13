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
- **Kubernetes**, with manifests kept in the cluster's own repository (see [Kubernetes](#kubernetes) below).

Both use the same images from `ghcr.io/hubra-app/hubra/*` and the same
`.env` (on Kubernetes it becomes a Secret). Start from
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
4. **Mail relay.** In manage › Mail › Relay and › System sender, fill in the relay and the
   system sender, then press **Send test**. Until mail works, sign-up
   e-mails, invites and password resets don't arrive, and nobody is asked
   to confirm their address.
5. **Backup storage.** In the same page, fill in the S3 bucket. Then press
   **Create backup now** under Backups once and check that it
   shows up. See [Backups](#backups-and-restore).
6. **Health.** Diagnostics shows the backend version, the health
   checks (database, Redis, mail relay, IMAP, and a Celery check that runs
   every 20 seconds) and every API route with the permission it needs.
7. **First club.** Either create it yourself under All clubs
   (**Create club**, optionally with an admin e-mail and password), or let
   people request one on `join.<domain>/start` and approve it under
   All clubs › Requests. Whoever requested the club becomes its owner.

### Kubernetes

This repository builds the images and runs them with Docker Compose; it
holds no Kubernetes manifests. A cluster keeps its own in its GitOps
repository. What those manifests need from Hubra:

- The same images (`ghcr.io/hubra-app/hubra/<name>`) and the same
  environment as `.env`, from a Secret. The roles, which image runs which
  process and the init step are in [platform-backend.md](platform-backend.md).
- One Celery beat (`Recreate`, its own volume for the schedule file) and
  any number of API and worker replicas ([scaling.md](scaling.md)).
- Club domains (optional): the platform worker creates a cert-manager
  `Certificate` and an `Ingress` per verified club domain
  (`hubra.core.services.domain_serving`). Its service account needs a Role
  that may get, list, create, patch and delete `ingresses`
  (`networking.k8s.io`) and `certificates` (`cert-manager.io`) in Hubra's
  namespace. Outside a cluster this does nothing.

## Upgrade

Every start runs the same steps (Compose service `flask-init`, on Kubernetes
an init container of the platform backend):

```sh
flask db upgrade        # migrations: public and every club schema
flask sync-tenant-schemas  # club schemas get any table/column public has and they lack
flask sync-permissions  # permission catalog from the routes
flask seed --skip-migrate
flask ensure-superadmins
flask plugins sync      # installed plugins: unpack and migrate
```

So an upgrade is: take a backup, switch to the new images, restart.

If the backend starts without that init step (for example a cluster that runs
the image's plain `gunicorn` command), the worker runs the steps itself: once
every backend process reports the new build, a club worker takes the init
lock and runs `flask db upgrade`, `sync-tenant-schemas`, `sync-permissions`,
`seed --skip-migrate` and `plugins sync`, once per build
(`hubra.core.services.post_deploy`). The result, with the output of a step
that failed, is on manage › Diagnostics › System health › Builds, where
**Run now** starts them again; a failure also sends an `upgrades` alert.
Where an init step already holds the lock, the worker leaves it to it. The
platform setting **Run the post-deploy steps** (Diagnostics › Settings)
turns the automatic run off.

For a release with longer migrations, put the platform in maintenance
first (`flask maintenance on --minutes 15`, or the card on manage ›
Alerts): members see a maintenance page instead of errors and no alerts
go out. `flask maintenance off` afterwards; it also ends on its own.

1. **Read the release notes** on the GitHub release (and
   `app/backend/CHANGELOG.md`). Look for lines that ask you to change `.env`.
2. **Back up.** Backups › **Create backup now**, for Global and
   for each club. A migration is not undone by going back to the old images;
   the backup is the way back.
3. **Switch the version.**
   - Compose: set `HUBRA_VERSION` in `.env` to the release (`1.2.3`), then
     `docker compose pull && docker compose up -d`.
   - Kubernetes: pin the new tags or the digest block from the Images run
     summary in the cluster's repository.
4. **Watch the migrations.**
   - Compose: `docker compose logs flask-init` must end with exit code 0
     (`docker compose ps` shows `Exited (0)`).
   - Kubernetes: the logs of the init container.

   If a migration fails, the backend doesn't start and the old pods (Kubernetes)
   keep serving. Fix the cause, or go back to the previous version and
   restore the backup from step 2.
5. **Check.** Diagnostics shows the new backend version and green
   health checks. `scripts/smoke-test.sh` does the same from the command
   line for Compose.

Pin a version for production. `latest` follows the newest release, and
`sha-<commit>` is one exact build.

### PostgreSQL 18 (Compose)

The Compose stack runs PostgreSQL 18, in the volume `pg18_data`. Stacks from
before kept PostgreSQL 16 in `pg_data`. A major version can't read the
other's files, so the data is moved once, with a dump and restore. Until
then the `postgres` service doesn't start: `docker compose logs postgres`
says so, instead of Hubra coming up as an empty new install.

1. Back up (step 2 above).
2. Switch the version as usual (`HUBRA_VERSION`, new `docker-compose.yml`).
3. From the directory with `docker-compose.yml` and `.env`:

   ```sh
   scripts/pg-upgrade-18.sh
   ```

   It stops the stack, starts PostgreSQL 16 on `pg_data` (Compose profile
   `pg-upgrade`) and an empty PostgreSQL 18, copies everything with
   `pg_dumpall` (roles and their passwords, so `.env` stays as it is, the
   database and every club schema), checks that both have the same roles,
   tables and row counts, and starts the stack. It needs about as long as a
   backup of the whole database, and stops with nothing changed if the
   check fails.
4. Check the stack (step 5 above). Then delete the dump the script left in
   the directory (`pg16-dumpall-<date>.sql`, every club's data).

`pg_data` stays as it was. Going back is the previous `docker-compose.yml`
and Hubra version. Once you don't need that any more, empty it with
`docker volume rm <project>_pg_data` (`docker volume ls` shows the name).
Kubernetes and managed databases run their own PostgreSQL. Their upgrade
is the provider's (`pg_upgrade`, or a dump and restore like the script).

### The app's database role

New stacks connect to Postgres as `POSTGRES_APP_USER` (default `hubra_app`),
an unprivileged role that owns only Hubra's data — a compromised backend or
plugin then cannot reach beyond it. A fresh data volume creates the role by
itself (`scripts/pg-init`). A stack from before this role exists keeps
running as the superuser until you run the one-time upgrade:

```sh
docker compose cp scripts/pg-app-role-upgrade.sh postgres:/tmp/
docker compose exec \
  -e POSTGRES_APP_USER=hubra_app \
  -e POSTGRES_APP_PASSWORD=<new strong password> \
  postgres sh /tmp/pg-app-role-upgrade.sh
```

Then put the same `POSTGRES_APP_USER` and `POSTGRES_APP_PASSWORD` in `.env`
and `docker compose up -d` (on Kubernetes, update the Secret and restart). The script also hands the role ownership of the existing schemas
and tables, which later migrations need.

The app role also needs `CREATEROLE`, so that every club gets its own
database role ([club-db-roles.md](club-db-roles.md)). New volumes get it;
on an existing stack run the upgrade script again, or as the superuser:

```sql
ALTER ROLE hubra_app CREATEROLE;
```

Without it Hubra works as before and the init step says
"Club database roles: off".

## Encryption keys

Hubra stores a few secrets encrypted: door codes, binding values, mailbox
passwords and the secret platform settings (relay passwords, backup storage
key). Every club has its **own data key** for its secrets, and the platform
has one; a value carries its club and column, so it never opens in another
club (a value copied across clubs reads as empty). The data keys live in the
`data_keys` table, locked by the **master key** `FERNET_KEY` from env.

The master key stays out of the database on purpose: anyone with a database
dump or backup could otherwise open everything. Production does not start
without it. Installs from before it was required used a key derived from
`SECRET_KEY`; those values stay readable, so setting a fresh `FERNET_KEY`
loses nothing.

Manage › Access & security › **Encryption** shows the state (master key set,
old keys, values not on the current keys), and has the buttons for the
steps below. The same works on the command line with `flask crypto check`
and `flask crypto rotate`.

**After upgrading to per-club keys**, press **Re-encrypt** once (or run
`flask crypto rotate`): values stored before move onto their club's key.
Until then they stay readable with the master key.

**New key for a club** (someone who knew the codes left, or once a year):
**New key** next to the club, or `flask crypto rotate --new-keys --club
<slug>`. No restart, no env change. The club's values are re-encrypted; the
older key version stays, so older backups still open. **New keys for every
club** does it for all.

**Change the master key** (after a leak of `.env` or the SOPS secret):

1. Generate a new key:
   `python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`.
2. Put the new key in `FERNET_KEY` and the old one in `FERNET_OLD_KEYS`
   (comma-separated if there are several), then restart the backends and
   workers. Everything stays readable.
3. Press **Re-encrypt** (or `flask crypto rotate`). It rewraps the club keys
   with the new master key, one row per club, so it takes seconds.
4. The Encryption tab (or `flask crypto check`, exit 0) must show nothing on
   an old key. If values no key opens are listed, a key is missing from
   `FERNET_OLD_KEYS`; nothing was overwritten, so add it back and repeat 3.
5. Remove the old key from `FERNET_OLD_KEYS`, commit, restart. Store the new
   key in your password manager; keep the old one there until the oldest
   backup from before the change has expired, because restoring such a
   backup brings back club keys locked with it (run step 3 after such a
   restore).

**Deleting a club for good** also deletes its data keys, so its secrets are
unreadable everywhere afterwards, in old backups too.

The IMAP inbox plugin has its own key derived from `FERNET_KEY`, reads
`FERNET_OLD_KEYS` too, and re-encrypts each mailbox password on its next
sync.

## Mail look and sender logo

Every mail Hubra sends (invites, password resets, invoices, ...) uses one
layout in the Hubra brand: the club's logo and name on top, a white card with
a violet button, and "Sent with hubra" at the bottom. The logo is the one a
club sets in Settings › Verein (PNG, JPEG, GIF or WebP up to 256 KB; an SVG or
bigger logo shows the Hubra mark instead). It is sent inside the mail, so it
shows without "load images". The texts are the platform's translations
(Manage › Services › Translations; clubs can suggest changes); the
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

Backups are a platform task: manage › Backups, global permission
`backups.manage` (superadmins have it). Clubs have no backup screen.

- Each backup holds one schema: **Global** (`public`: accounts, clubs,
  platform settings) or **one club**. A single club can be restored without
  touching the others.
- Celery beat makes a scheduled set every day, week and month. Retention is
  set in manage › Backups › Einstellungen (`backup.keep_*`): by default each
  set keeps its newest 7 daily, 4 weekly and 12 monthly backups; manual
  backups are deleted after 90 days (`backup.keep_manual_days`; 0 keeps
  them); each backup of a club deleted for good is deleted 30 days after it
  was made (`backup.keep_deleted_club_days`; 0 lets them follow the counts
  like any club's). Only completed
  backups count; pruning runs after each scheduled run.
- Files are encrypted to `BACKUP_PUBLIC_KEY` ([age](https://age-encryption.org))
  (platform setting, default from env) and stored in the S3 bucket from
  Backups › Storage. The
  server only has the public key, so a break-in on the server cannot read
  the backups. The private key stays in your password manager; restore
  asks for it. Make the pair with `flask backups keygen`.
- A club can get its own key. Club admins set it up themselves in the club
  app under Settings › Encryption: a guide explains the key, makes the pair
  in the browser (the private key is never sent), has them store it and
  proves they did before the public key is saved. You can also set it in
  Access & security › Encryption, or with
  `flask backups club-key <club> age1…`. Its
  backups are then encrypted to both keys, so the club can open its own
  backups with its private key, and you still can with yours.
- A club admin can also turn on **Only our key** there (they type the
  club's short name to confirm). New backups of that club are then
  encrypted to the club key alone: you can no longer verify-open or
  restore them unless the club gives you its private key. Manage ›
  Encryption marks such clubs "Club key only". It only works with age
  backups and a club key; removing the club key turns it off.
- **Verify** without a key checks that the file in storage is complete and
  unchanged (checksum). Paste the private key to also open it and count the
  tables; do that now and then as a test restore.
- `BACKUP_PRIVATE_KEY` in `.env` lets verify and restore run without asking,
  at the price that a break-in on the server then opens the backups too.
- Installs without `BACKUP_PUBLIC_KEY` keep using the `BACKUP_ENCRYPTION_KEY`
  passphrase (GPG). Older `.dump.gpg` backups always open with it, so keep
  it until they have expired.

**Restore one club** (the usual case: someone deleted the wrong thing):
Backups, filter by the club, pick a backup from before the
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

**PostgreSQL version.** `pg_dump` refuses a server with a newer major
version than its own. The backend image has the PostgreSQL 16, 17 and 18
clients and backups use the one matching the server, so a Compose or Kubernetes
install can run its own (or a managed) PostgreSQL up to 18. The Backups page
shows an error, and `flask backups check-client` exits non-zero, when the
server is newer than every client in the image.

A plain `pg_dump` of the whole database also works as an extra copy, for
example before an upgrade on Compose:
`docker compose exec postgres pg_dump -U hubra -Fc hubra > hubra.dump`.

## Club files

Clubs' files, for example those of the document library, go to Hubra's file
store (`hubra.core.files`). Set it in manage › Backups › Storage under
**File storage** (`files.*`, or `FILES_S3_*` in the environment):

- **With an S3 bucket** (`files.s3.bucket`) files go there. Use a bucket of
  its own, not the backup bucket. Several backend replicas need this.
- **Without a bucket** files stay in `FILES_DIR` (default
  `/var/lib/hubra/files`) on the server. Mount a volume there; this only
  suits a single server.
- Every file is encrypted with its club's data key before it is stored, so
  the bucket only ever holds ciphertext, and a file opens only in its own
  club. A club's files count towards its storage, and deleting a club for
  good deletes its files.
- The largest file a club can upload is set per plan (All clubs › Tarife &
  Preise, "Grösste Datei") and, for one club, on its page (Limits ›
  Anpassen). A plan without its own value uses `files.max_mb` (default 25).
  Nothing goes above `MAX_UPLOAD_MB` (env, default 100), the largest upload
  the backend and the frontends' nginx take; on k3s the Ingress in front
  needs a body size at least that large too.
- The database backups don't contain the files. Keep the bucket versioned or
  copy it elsewhere; without the database (the club's data keys) a copy of
  the bucket can't be opened.

## Modules

Every section of the club app is a module. Core, Members and Roles are always
on. Events, Finance, Functions, Groups, Polls and Posts are on for a new
club; Bindings and Mail are off. Everything else (the books, inventory,
codes, keys, Discord, …) comes from a plugin, see below.

- **Club admins** switch modules on and off in the club app under
  Settings › Modules. Switching off hides the module and keeps its
  data.
- **You** can block a module for one club: All clubs › the club ›
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

Plugins add modules that are not part of Hubra (the books, inventory, codes,
keys, budgets, bank import, Discord and more). You install a plugin once for the whole platform in manage
› Plugin catalogue; each club then switches its modules on in
Settings › Modules like a built-in module.

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
- Usage: manage › Plugin catalogue › **Nutzung** shows, per module and
  plugin, in how many active clubs it is on, in how many something was
  written to its tables in the last 30 days, and where it is on but unused,
  plus installed plugins no club has on. It is counted every night at 04:40
  (`usage-snapshot-nightly`, `services/module_usage.py`, kept in Redis);
  **Jetzt zählen** counts at once. Modules without timestamped tables of
  their own show "nicht messbar".

Details, the trust badges and the CLI: [plugins/README.md](../plugins/README.md).

## Settings

There are four levels, each changed in a different place.

| Level | Where | Examples |
| ----- | ----- | -------- |
| Installation | `.env` (Kubernetes: a Secret), restart needed | Secrets, database, Redis, host names, CORS, cookie domain, `SUPERADMIN_EMAILS`, plugin directories |
| Limits | `settings.yaml`, or env with `__` (`LIMITS__MAX_MEMBERS=50`) | Members per club, events per month |
| Platform | manage (Mail, Backups › Storage, Discord, …), no restart | Mail relay, system sender, backup storage |
| Club | club app › Settings (club admins) | Name, colours, language, privacy, leaving rules, banner, modules, domains |

A platform setting starts from its env variable. A value saved in manage
wins until you press **Reset to env**. `BACKUP_ENCRYPTION_KEY` is env only.
The full list is in [configuration.md](configuration.md) and `.env.example`.

## People and permissions on the platform

- **Superadmin** (`SUPERADMIN_EMAILS` or `flask make-admin`): everything in
  manage › Platform.
- **Global roles** (manage › Roles) give staff single platform
  permissions, such as `backups.manage`, `platform.settings`,
  `platform.diagnostics` or `plugins.manage`, without making them
  superadmin.
- **A role for some clubs only**: when you assign a role, pick clubs under
  **Only for these clubs**. The person then sees only those clubs in All
  clubs and may open them as a member (read-only unless they ask for
  changes, every session logged under Audit log › Support access), and
  nothing else: of the role's rights only `tenants.read`,
  `tenants.members.read` and `impersonate` count there. Use it for a
  helper who looks after a few clubs. Leave the field empty for the whole
  platform.
- **Club owners and admins** see manage too, but only Personal › My clubs
  and the clubs they run. There they choose who else is a club admin
  (My clubs › the club › Admins). Platform staff find the same list, and the
  club's modules, under All clubs › the club.
- Accounts belong to their people. Clubs never create accounts, set
  passwords or change e-mail addresses; members join through an invite link
  or a request on the join page.

Everything staff do in manage is written to Audit log.

### Sign-in alerts

When an account signs in from a browser it has not used before, its
(confirmed) address gets a mail with the time, IP address and browser, and
a button to its sessions on the SSO portal. Each browser keeps a random
token in the `hubra_device` cookie (HttpOnly, 400 days, survives sign-out);
the database keeps only its hash, in `known_devices`. The first browser an
account is seen with, including every account's first sign-in after the
upgrade, is learnt without a mail. Cleared cookies or a private window
count as a new device. Times in the mail use `MAIL_TIMEZONE`
(default `Europe/Zurich`).

### Two-factor sign-in

Everyone can turn on a second step at sign-in in SSO › Konto › Zwei-Faktor:
a passkey (Face ID, fingerprint, device PIN or a security key) or a 6-digit
code from an authenticator app (TOTP), plus ten one-time recovery codes for
when the device is gone. The TOTP secret is stored encrypted with
`FERNET_KEY`.

A passkey also signs in on its own ("Mit Passkey anmelden"), without the
password; it always asks for the device's fingerprint, face or PIN.
Passkeys belong to the SSO host: the relying party is the host of
`SSO_BASE_URL` (override with `WEBAUTHN_RP_ID`, and list extra origins in
`WEBAUTHN_ORIGINS`). Changing the SSO host later makes existing passkeys
stop working, so pick it before people add them. Without `SSO_BASE_URL`
passkeys are off.

Platform staff (superadmins and holders of a global role) must turn it on
(a passkey or the app):
until they do, manage › Platform answers `MFA_SETUP_REQUIRED` and manage
sends them to the setup page. `MFA_REQUIRED_FOR_STAFF=false` switches the
rule off, for example while the relay or SSO is being set up.

Someone who lost both the app and the recovery codes: check that it really
is them, then run `flask reset-mfa --email them@example.org`. They sign in
with the password alone and set it up again.

Clubs can require it too: Settings › Mitgliedschaft › Zwei-Faktor-Anmeldung
is *Freiwillig* (default), *Für Admins* (owners and admins, also through a
function) or *Für alle Mitglieder*. Whoever it applies to and has neither a
passkey nor the app can't open the club (`403 MFA_REQUIRED_BY_CLUB` on
`/auth/switch-tenant` and on a club sign-in). A club session from before the
rule gets the same answer on its next request and is turned back into a
plain account session, so the club app sends the person to SSO › Konto ›
Zwei-Faktor and back into the club afterwards. Only someone who has
two-factor themselves can turn the rule on (`MFA_SETUP_FIRST`). The rule is
stored as `mfa_required` in the club's settings.

The platform API itself runs only on an *account* sign-in: a club session's
token is refused there (`ACCOUNT_TOKEN_REQUIRED`), so a script in the club
app can never drive manage with a staff member's session. Sign-ins from
before this rule lack the account cookie; signing in again fixes a manage
that suddenly asks for it. The destructive actions — installing or removing
plugins, restoring or deleting backups, rotating encryption keys, opening a
club as a member — additionally ask for the password (and the code, with
two-factor on) again and hold that for ten minutes (`STEP_UP_REQUIRED`;
`STEP_UP_ENFORCED=false` switches the rule off). Accounts with a passkey can
confirm with it instead: passkeys belong to the SSO address, so manage opens
SSO `/confirm` in a small window and carries on once that sign-in is
confirmed. Allow pop-ups for the manage address; the password stays as the
fallback.

## Day to day

```sh
# Compose (on Kubernetes: kubectl exec into a backend pod)
docker compose exec backend flask list-tenants
docker compose exec backend flask modules list --tenant <slug>
docker compose exec backend flask plugins list
docker compose logs -f backend celery-worker celery-beat
```

- **Celery beat** starts the scheduled backups, invoice generation and
  reminders, health checks, plugin update checks and mail housekeeping. Run
  one. A second beat no longer sends jobs twice, and API and worker replicas
  are safe too: see [Running more than one replica](scaling.md).
- **Rate limits** use Redis. Behind a proxy, set `REAL_IP_FROM` (Compose) so
  limits see real client addresses.
- **Logs** are JSON lines on stdout; lines of one API request share a
  `request_id`.
