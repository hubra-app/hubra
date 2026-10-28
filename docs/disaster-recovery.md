# Disaster Recovery Runbook

## Prerequisites (keep these safe BEFORE disaster strikes)

1. **Encryption key** — `BACKUP_ENCRYPTION_KEY` from `.env` on the production server.
   Store this in a password manager (1Password, Bitwarden, etc.).
   **If this key is lost, all backups are unrecoverable.**

2. **S3 credentials** — Contabo S3 endpoint, bucket name, access key, and secret key.
   These are stored in the Settings KV store (backup namespace) and can also be
   found in `.env` on the production server.

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

4. **`gpg`** — GnuPG must be installed (standard on most Linux/macOS systems).

5. **`aws-cli`** or **`s3cmd`** — for downloading from S3. Install with:
   ```sh
   pip install awscli
   # or
   apt install -y s3cmd
   ```

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
2026-07-08 03:00:15  1048576  backups/2026-07-08_030000_scheduled_daily.dump.gpg
2026-07-08 03:15:22  1048576  backups/2026-07-08_031500_scheduled_weekly.dump.gpg
```

Pick the most recent backup (or the one from before the incident).

---

## Step 2 — Download and decrypt

```sh
# Download
aws s3 cp s3://your-bucket-name/backups/2026-07-08_030000_scheduled_daily.dump.gpg \
    ./backup.dump.gpg \
    --endpoint-url="$AWS_ENDPOINT_URL"

# Decrypt (will prompt for passphrase, or use --passphrase)
gpg --decrypt --output backup.dump backup.dump.gpg
```

If you want to provide the passphrase non-interactively:

```sh
gpg --batch --yes --passphrase "YOUR_BACKUP_ENCRYPTION_KEY" \
    --decrypt --output backup.dump backup.dump.gpg
```

---

## Step 3 — Restore to a fresh Postgres instance

### Option A: Throwaway Docker container (recommended for testing)

```sh
# Start a temporary Postgres 16 container
docker run -d --name restore-test \
    -e POSTGRES_PASSWORD=temppass \
    -e POSTGRES_DB=club_db \
    -p 5433:5432 \
    postgres:16-alpine

# Wait for it to start
sleep 3

# Restore the backup
pg_restore --host localhost --port 5433 \
    --username postgres --dbname club_db \
    --clean --if-exists --no-owner --no-privileges \
    backup.dump

# Verify
PGPASSWORD=temppass psql -h localhost -p 5433 -U postgres -d club_db -c "
    SELECT count(*) AS member_count FROM members;
    SELECT count(*) AS role_count FROM roles;
    SELECT count(*) AS settings_count FROM setting;
"

# Tear down when done
docker rm -f restore-test
```

### Option B: Restore to production (after data loss)

```sh
# 1. Stop the app stack to prevent writes during restore
docker compose down

# 2. Remove the old volume if it's corrupted
docker volume rm club-management-suite_pg_data

# 3. Start only Postgres
docker compose up -d postgres

# 4. Wait for Postgres to be ready
sleep 5

# 5. Restore the backup
docker compose exec -T postgres pg_restore \
    -U club_user -d club_db \
    --clean --if-exists --no-owner --no-privileges \
    < backup.dump

# 6. Start the full stack
docker compose up -d
```

---

## Step 4 — Verify the restore

Run these queries to confirm data integrity:

```sh
docker compose exec -T postgres psql -U club_user -d club_db -c "
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
# 1. Create a backup via the API (or wait for a scheduled one)
curl -X POST https://api.hubra.club/api/v1/backups/ \
    -H "Cookie: csrf_access_token=..." \
    -H "X-CSRF-TOKEN: ..."

# 2. Wait for it to complete, then download it from S3
aws s3 ls s3://your-bucket-name/backups/ --endpoint-url="$AWS_ENDPOINT_URL" | tail -5
aws s3 cp s3://your-bucket-name/backups/LATEST_FILE.dump.gpg ./test-restore.dump.gpg \
    --endpoint-url="$AWS_ENDPOINT_URL"

# 3. Decrypt
gpg --batch --yes --passphrase "$BACKUP_ENCRYPTION_KEY" \
    --decrypt --output test-restore.dump test-restore.dump.gpg

# 4. Restore to throwaway container (Step 3, Option A)

# 5. Run verification queries (Step 4)

# 6. Clean up
docker rm -f restore-test
rm test-restore.dump.gpg test-restore.dump
```

If all queries return expected results, the backup system is working correctly.

---

## Encryption key recovery

**If `BACKUP_ENCRYPTION_KEY` is lost:**

All encrypted backups are permanently unrecoverable. There is no backdoor,
no key escrow, and no way to decrypt the files without the passphrase.

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

Manual backups are never automatically deleted. Scheduled backups are cleaned
up after each scheduled run according to the retention policy.
