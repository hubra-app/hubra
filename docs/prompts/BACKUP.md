Set up automated, verified backups for both Postgres (club_db) and MongoDB (wildduck), since these contain irreplaceable member/financial records and all stored member email respectively. Currently there is no known backup mechanism — confirm this is actually true before building anything.

## Step 1 — Confirm current state

1. Check for any existing backup mechanism (cron jobs on the host, backup containers, volume snapshot scripts):
   crontab -l
   docker compose config | grep -i backup
   ls -la /opt/docker/prod/apps/club-operations-suite/ | grep -i backup
2. Check current volume sizes to understand backup scope/storage needs:
   docker system df -v
3. Report findings — confirm there is genuinely no backup today, or document what partial mechanism exists, before proceeding.

## Step 2 — Design

Propose (and confirm with me before implementing) a backup architecture:

- A dedicated backup service in compose running on a schedule (cron-in-container, e.g. via a small Alpine + cron image, or a tool like `offen/docker-volume-backup`)
- pg_dump for Postgres (club_db), mongodump for MongoDB (wildduck)
- Backups must be encrypted and stored OFF the host VPS — not just another Docker volume on vps-public-matterhorn, since that doesn't protect against host failure, disk corruption, or accidental `docker compose down -v`. Propose a destination: options include rsync to a second VPS, an S3-compatible bucket (Backblaze B2, Hetzner Storage Box, etc.), or another mechanism — ask which is available/preferred given existing infrastructure (Hetzner is referenced by hostname "vps-public-matterhorn" — check if a Hetzner Storage Box or second VPS already exists for this purpose)
- Retention policy: propose daily backups retained 7 days, weekly retained 4 weeks, monthly retained 6 months (adjust based on storage cost/availability) — confirm with me before implementing

## Step 3 — Implement

1. Add the backup service to compose.yml (base) with credentials/destination configured via .env, following the existing project convention of env_file + environment vars
2. Implement pg_dump and mongodump commands with proper authentication using existing POSTGRES_* and MongoDB connection details already in the stack
3. Ensure backup files are encrypted at rest (e.g. gpg-encrypt before upload, or rely on the destination's server-side encryption if using S3-compatible storage with a private bucket)
4. Add logging so successful/failed backup runs are visible in `docker compose logs`

## Step 4 — Verify restore actually works (critical — do not skip)

1. Spin up a throwaway Postgres container, restore a recent backup into it, and run a basic query (e.g. count members, check a known record) to confirm data integrity
2. Spin up a throwaway MongoDB container, restore a recent backup, and confirm a known WildDuck user/mailbox exists
3. Document this restore procedure as a runbook (markdown file in the repo, e.g. docs/disaster-recovery.md) with exact commands, since this needs to be followable under stress months from now, possibly by someone other than you

## Step 5 — Report

Confirm: backup schedule running, first successful backup completed, full restore test passed for both databases, runbook documented and committed to the repo.
