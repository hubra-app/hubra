# Disaster Recovery Runbook

## Prerequisites (keep these safe BEFORE disaster strikes)

1. **Backup private key** — the `AGE-SECRET-KEY-1…` line that belongs to
   `BACKUP_PUBLIC_KEY` (made with `flask backups keygen`). It is not on the
   server: keep it in a password manager (1Password, Bitwarden, etc.) and on
   paper. For backups from before `BACKUP_PUBLIC_KEY` (`.dump.gpg` files)
   you need the old passphrase `BACKUP_ENCRYPTION_KEY` instead.
   **If the key is lost, the backups made with it are unrecoverable.**
   A club with its own backup key (`flask backups club-key`) can also open
   its own club backups with its private key.

   **`FERNET_KEY`** too: restored data opens, but the stored secrets in it
   (door codes, mailbox passwords, binding values) only open with the master
   key that locked the club keys in the global backup.

2. **S3 credentials** — Contabo S3 endpoint, bucket name, access key, and secret key.
   These come from `BACKUP_S3_*` in `.env` on the production server, unless a
   superadmin overrode them in manage under Platform › Platform Settings.

3. **`pg_restore`** — PostgreSQL 16+ client tools must be installed on the
   recovery machine. Install with:

   ```sh
   # Debian/Ubuntu
   sh -c 'echo "deb https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
   curl -o /etc/apt/trusted.gpg.d/pgdg.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc
   apt update && apt install -y postgresql-client-16

   # macOS
   brew install libpq && export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
   ```

4. **`age`** — for `.dump.age` backups (`apt install age`, `brew install age`).
   **`gpg`** for older `.dump.gpg` backups (standard on most Linux/macOS systems).

5. **`aws-cli`** or **`s3cmd`** — for downloading from S3. Install with:
   ```sh
   pip install awscli
   # or
   apt install -y s3cmd
   ```

---

## What a backup holds

There is no backup of the whole database. Each backup holds one schema:

- **Global** — the `public` schema: accounts, clubs, domains, platform
  settings, global roles, and the id sequences every club table uses.
  Stored under `backups/global/`.
- **Club** — one club's `tenant_<id>` schema: its members, finances, events
  and settings. Stored under `backups/clubs/<id>-<slug>/`.

Every scheduled run makes one global backup and one per active club.

**Most incidents are one club** (an admin deleted the wrong thing, a bad
import). Restore just that club from manage, see Step 3A. Only when the
whole database is lost do you need Steps 1–3B.

---

## Step 1 — List available backups

Configure AWS CLI with Contabo S3 credentials:

```sh
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_ENDPOINT_URL="https://eu2.contabostorage.com"
export AWS_DEFAULT_REGION="default"
```

List all backups:

```sh
aws s3 ls s3://your-bucket-name/backups/ --endpoint-url="$AWS_ENDPOINT_URL" --recursive
```

Output will look like:

```
2026-10-29 03:00:15   52012  backups/global/2026-10-29_030000_scheduled_daily.dump.gpg
2026-10-29 03:00:16   11921  backups/clubs/1-rowers/2026-10-29_030001_scheduled_daily.dump.gpg
2026-10-29 03:00:17    9840  backups/clubs/2-tennis-zug/2026-10-29_030002_scheduled_daily.dump.gpg
```

Pick the most recent set (or the one from before the incident). Files
directly under `backups/` are whole-database dumps from before per-club
backups; restore those as one database (Step 3B, without the per-club part).

---

## Step 2 — Download and decrypt

```sh
# Download
aws s3 cp s3://your-bucket-name/backups/global/2026-10-31_030000_scheduled_daily.dump.age \
    ./global.dump.age \
    --endpoint-url="$AWS_ENDPOINT_URL"

# Decrypt with the backup private key (a file holding the AGE-SECRET-KEY-1… line)
age --decrypt --identity backup-key.txt --output global.dump global.dump.age
```

Delete `backup-key.txt` when you are done. Older `.dump.gpg` backups use the
passphrase instead (prompts for it):

```sh
gpg --decrypt --output global.dump global.dump.gpg
```

To give the passphrase non-interactively:

```sh
gpg --batch --yes --passphrase "YOUR_BACKUP_ENCRYPTION_KEY" \
    --decrypt --output global.dump global.dump.gpg
```

Do the same for each club you need (`club-<id>.dump`).

---

## Step 3 — Restore

### Option A: One club, from manage (the usual case)

manage › Platform › Backups, filter by the club, pick the backup and click
the restore icon. Type the club's address to confirm.

What happens:

1. The backup is downloaded and decrypted.
2. The club's current schema is renamed to
   `tenant_<id>_before_restore_<timestamp>` (the safety copy).
3. The backup is restored into a fresh `tenant_<id>` in one transaction.
4. The restored schema is migrated to the running code.

If any step fails, the half-restored schema is dropped and the safety copy
gets its name back, so the club is exactly as before; the error shows on the
backup row. Other clubs and the global data are never touched.

The safety copy stays in the database until you drop it. Once the club has
checked its data:

```sh
psql "$DATABASE_URL" -c 'DROP SCHEMA "tenant_1_before_restore_20261029101500123456" CASCADE'
```

A club backup refers to accounts in the global schema (members linked to a
user). If such an account was deleted after the backup was taken, the
restore fails on that link and the club stays as it was; restore the global
backup first (Option B) or recreate the account.

The same thing by API (platform staff):

```sh
curl -X POST https://api.hubra.club/api/v1/manager/platform/backups/<id>/restore \
    -H "Content-Type: application/json" -d '{"confirm": "rowers"}' ...
```

### Option B: The whole database (after losing it)

Restore the global backup first, then every club, then bring the id
sequences up to the highest id in use (the global backup may be older than
some club backups, and club tables take their ids from sequences in public).

```sh
# Throwaway container for a test, or the production Postgres after
# `docker compose down && docker compose up -d postgres`
docker run -d --name restore-test \
    -e POSTGRES_PASSWORD=temppass -e POSTGRES_DB=club_db \
    -p 5433:5432 postgres:16-alpine
sleep 3
export PGHOST=localhost PGPORT=5433 PGUSER=postgres PGPASSWORD=temppass PGDATABASE=club_db

# 1. Global first: accounts, clubs, sequences
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$PGDATABASE" global.dump

# 2. Every club (one file per club, any order)
for f in club-*.dump; do
    pg_restore --no-owner --no-privileges --exit-on-error --single-transaction \
        --dbname "$PGDATABASE" "$f"
done

# 3. Sequences up to the highest id in public and every club
psql <<'SQL'
DO $$
DECLARE s record; t record; mx bigint; cur bigint;
BEGIN
  FOR s IN
    SELECT seq.relname AS seq, tbl.relname AS tbl, att.attname AS col
    FROM pg_class seq
    JOIN pg_namespace n ON n.oid = seq.relnamespace AND n.nspname = 'public'
    JOIN pg_depend d ON d.objid = seq.oid AND d.deptype IN ('a', 'i')
    JOIN pg_class tbl ON tbl.oid = d.refobjid
    JOIN pg_attribute att ON att.attrelid = tbl.oid AND att.attnum = d.refobjsubid
    WHERE seq.relkind = 'S'
  LOOP
    mx := 0;
    FOR t IN
      SELECT table_schema FROM information_schema.columns
      WHERE table_name = s.tbl AND column_name = s.col
        AND (table_schema = 'public' OR table_schema ~ '^tenant_[0-9]+$')
    LOOP
      EXECUTE format('SELECT coalesce(max(%I), 0) FROM %I.%I', s.col, t.table_schema, s.tbl) INTO cur;
      mx := greatest(mx, cur);
    END LOOP;
    IF mx > 0 THEN
      PERFORM setval(format('public.%I', s.seq), mx);
    END IF;
  END LOOP;
END $$;
SQL

# 4. Bring everything to the running code
flask db upgrade && flask apply-tenant-migrations
```

---

## Step 4 — Verify the restore

Run these queries to confirm data integrity (for a club, set its schema
first, e.g. `SET search_path TO tenant_1, public;`):

```sh
docker compose exec -T postgres psql -U club_user -d club_db -c "
    SET search_path TO tenant_1, public;
    -- Check table counts
    SELECT 'members' AS table_name, count(*) FROM members
    UNION ALL SELECT 'roles', count(*) FROM roles
    UNION ALL SELECT 'groups', count(*) FROM groups
    UNION ALL SELECT 'settings', count(*) FROM setting
    UNION ALL SELECT 'invoices', count(*) FROM invoices
    UNION ALL SELECT 'transactions', count(*) FROM transactions
    ORDER BY table_name;

    -- Check that the admin role exists
    SELECT name, is_admin FROM roles WHERE is_admin = true;

    -- Check that settings are populated
    SELECT key, value FROM setting WHERE key IN ('club.name', 'mail.domain');
"
```

Expected: non-zero counts for all tables, at least one admin role, and populated
settings values.

---

## Step 5 — Full restore test (do this quarterly)

This procedure tests the entire backup→restore pipeline without touching
production:

```sh
# 1. Take the latest scheduled set, or make one: manage › Platform › Backups,
#    "Create backup now" once for Global and once per club to test

# 2. Download and decrypt the global backup and a club's (Steps 1–2)

# 3. Restore them into a throwaway container (Step 3, Option B)

# 4. Run verification queries (Step 4)

# 5. Clean up
docker rm -f restore-test
rm -f *.dump *.dump.gpg
```

If all queries return expected results, the backup system is working correctly.

---

## Encryption key recovery

**If the backup private key (or, for `.dump.gpg` files, `BACKUP_ENCRYPTION_KEY`) is lost:**

The backups made with it are permanently unrecoverable. There is no backdoor,
no key escrow, and no way to decrypt the files without the key. Make a new
pair with `flask backups keygen`, put the public key in `BACKUP_PUBLIC_KEY`,
restart, and take a fresh backup right away.

**Changing the backup key pair:** new backups use the new public key at
once. Keep the old private key until the last backup made with it has
expired (6 months with the default retention).

**Prevention:**

- Store the key in at least two locations (password manager + physical printout)
- Include it in your organization's key-sharing protocol
- Document who has access to it

---

## Backup schedule reference

| Schedule | Frequency              | Retention |
| -------- | ---------------------- | --------- |
| Daily    | Every day at 03:00 UTC | 7 days    |
| Weekly   | Sunday at 03:15 UTC    | 4 weeks   |
| Monthly  | 1st of month at 03:30  | 6 months  |
| Manual   | On demand              | Unlimited |

Each scheduled run backs up the global schema and every active club.
Retention counts per set: the global backups and each club's backups are
kept separately (7 daily for the global data, 7 daily for each club, and so
on). Manual backups are never automatically deleted. Scheduled backups are
cleaned up after each scheduled run according to the retention policy.
