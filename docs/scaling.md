# Running more than one replica

Hubra runs as three processes from the backend image: the API (gunicorn),
the Celery worker and Celery beat. One of each is the default in
`docker-compose.yml`, and that is enough for most installs.
This page says which of them you can run more than once, and what keeps the
work from happening twice.

## Short version

| Process        | More than one? | Notes |
| -------------- | -------------- | ----- |
| API (`backend`, `global-backend`, `platform-backend`) | Yes | Stateless. The init step (migrations, seeds, plugin sync) runs under a Postgres advisory lock, so pods starting together take turns. On Kubernetes, run it in `platform-backend` only ([platform-backend.md](platform-backend.md)). |
| Celery worker (`celery-worker`, `platform-worker`) | Yes | Each task message goes to one worker. A scheduled job never runs twice at the same time (see below). |
| Celery beat    | Safe, not needed | Two beats send each scheduled run once. Run one; a second is only a hot standby. |
| Postgres       | One primary | Replicas or CloudNativePG are fine for failover; the app talks to the primary. |
| Redis          | One | Broker, result backend, rate limits, caches and the beat slot claims share it. |

## What keeps scheduled jobs single

Every periodic job is an entry in Celery beat's schedule
(`app/backend/hubra/core/tasks/__init__.py`, plus `schedule=` in module and
plugin manifests). Nothing else in Hubra runs on a timer, so beat is the only
place a job could be started twice. Two guards in
`app/backend/hubra/core/tasks/scheduling.py` handle that:

1. **One send per slot.** Before beat sends a due job, it claims
   `hubra:beat:<entry>:<slot>` in Redis (`SET NX` with an expiry). The slot
   is the time the run was due: the last cron time for crontab entries, or
   the current interval for "every N seconds". A second beat, or a beat that
   restarted with an old schedule file and wants to catch up on a run that
   already happened, finds the slot taken and skips it.
2. **One run at a time.** Jobs sent by beat carry the entry name in a
   `hubra_schedule` header. The worker holds a Postgres advisory lock
   (`pg_try_advisory_lock`) named after the entry while the job runs. If the
   previous run is still going on another worker, or in another process of
   the same worker, the new run is skipped and logged instead of overlapping.

Both fail open. Without Redis there is no slot claim, so one beat behaves
exactly as before; without Postgres (SQLite in development) jobs run without
the lock. Tasks started by hand, such as "Back up now" in the manager portal
or `.delay()` from a request, carry no header and are never skipped.

## Every background job

All of these are beat entries, so both guards apply to each. "Twice would"
says what a second run used to cause; it doesn't happen any more.

| Job (beat entry) | Every | Twice would |
| ---------------- | ----- | ----------- |
| `generate-invoices-daily` | 08:00 | Race between two runs (each skips members already billed, but only once the other has committed) |
| `book-recurring-transactions-daily` | 06:00 | Race; could book the same recurring transaction twice |
| `send-account-statements-monthly` | 1st, 07:00 | Mail the statement twice |
| `send-overdue-reminders-daily` | 09:00 | Race; reminders tracked per invoice |
| `event-reminders`, `poll-reminders` (modules) | 15 min | Race on `reminder_sent_at`; mail and bell twice |
| `trial-signups-purge` (events module) | 24 h | Harmless, deletes are idempotent |
| `backup-daily`, `-weekly`, `-monthly` | 03:00 / Sun 03:15 / 1st 03:30 | Two backup sets, and retention counting them |
| `retention-cleanup-daily` | 02:00 | Harmless, deletes are idempotent |
| `cleanup-token-blocklist-daily` | 03:00 | Harmless |
| `cleanup-revoked-sessions-weekly` | Sun 03:00 | Harmless |
| `verify-protected-mail-daily` | 04:00 | Duplicate WildDuck calls |
| `sync-wildduck-message-counts` | 60 s | Duplicate WildDuck calls |
| `sync-wildduck-quota-5min` | 5 min | Duplicate WildDuck calls |
| `mail-reconcile-v2-15min` | 15 min | Two reconciles creating the same mailbox or alias |
| `check-mailbox-quota-hourly` | :05 | Duplicate quota warnings |
| `health-check-20s` | 20 s | Duplicate "service down/up" alerts |
| `infra-checks-hourly` | :00 | Duplicate alerts |
| `api-error-rate-10min` | every 10 min | Duplicate alerts |
| `check-domains-every-minute` | 60 s | Duplicate DNS lookups and domain status mails |
| `check-mail-relays-5min` | 5 min | Duplicate relay alerts (cooldown races) |
| `prune-platform-events-daily` | 02:30 | Harmless |
| `plugin-updates` | every 6 h, :40 | Duplicate "update available" notices |
| `discord-role-sync` (Discord plugin) | 24 h | Duplicate Discord API calls, rate limits |
| `inbox-sync-5min` (IMAP inbox plugin) | 5 min | Two fetches importing the same mail |

Other background work is per process and meant to be:

- **Plugin reload watcher** (`hubra/core/plugins/reload.py`): a thread in
  every gunicorn arbiter, worker and beat that restarts that process after a
  plugin change. Each replica must run its own.
- **Discord bot**: commands and buttons come in as HTTP requests to
  `/api/v1/discord/interactions`, not a gateway connection, so any API
  replica can answer. Announcements go out from event hooks, once per event.
- **Web Push, mails, WildDuck provisioning, last-seen updates**: queued
  tasks, each delivered to one worker.

## Things to know before scaling out

- **Beat schedule file.** Beat keeps its schedule in
  `/celerybeat/celerybeat-schedule` on a `ReadWriteOnce` volume, and the
  Deployment uses `Recreate` so two beats never share it. If you want a
  second beat as a standby, give it its own volume (a StatefulSet with a
  volume claim template, or a separate Deployment), never the same file.
- **Redis is required with several replicas.** Rate limits fall back to
  per-process memory when Redis is unreachable, and the beat slot claim is
  skipped. With one of everything that is fine; with two API pods it halves
  the effective rate limit, and with two beats it brings double sends back.
- **Migrations during a rolling update.** The first new pod migrates while
  old pods still serve. That was already true with one replica; keep
  migrations backwards compatible for one release, as the existing ones are.
- **Mail stack.** WildDuck, Haraka and ZoneMTA in `modules/mail` are
  separate services with their own scaling rules; nothing here changes them.

## Processes per worker

A Celery worker runs its tasks in prefork child processes. Celery's own
default is one per CPU **of the machine**, which in a container is the
node's CPU count, not the pod's limit. A worker with `limits: cpu: "1",
memory: 512Mi` on a 6-CPU node would start six children: each holds a copy
of the app (about 60-70 MB of its own on top of the parent's ~150 MB), so
together they do not fit in 512 MiB, and they take turns on one CPU. Every
statement a task runs then includes the time the process waited for the
CPU, which shows up as trivial queries (`SELECT 1`, `SET search_path`,
`pg_advisory_unlock`) taking hundreds of milliseconds.

So Hubra sets the worker's concurrency itself
(`app/backend/hubra/core/cgroup.py`):

- `CELERY_WORKER_CONCURRENCY`, when set, is the number of children.
- Otherwise, under a CPU limit, two per CPU of the limit, at least two and
  never more than the machine's CPUs (a 1-CPU worker runs two).
- Without a CPU limit (Compose by default), Celery's default.
- `--concurrency` on the command line still wins over all of these.

Measured on a 4-CPU machine with the worker in a 1 CPU / 512 MiB cgroup: the
parent and four idle children used 381 MiB, five used 458 MiB, and with six
the cgroup hit its limit at start-up and the kernel killed the worker. Most
of Hubra's jobs wait on the network (mail relays, WildDuck, Discord), so two
children per CPU keep the CPU busy without making them queue for it. Give the
worker more CPU (and about 80 MiB per extra child) before raising the number.

manage › Diagnostics › Performance marks slow queries and requests that ran
while their pod was CPU-throttled or at its memory limit, read from the
pod's cgroup counters (`cpu.stat`, `memory.events`).

## What the database needs

- PostgreSQL with session-level advisory locks (any supported version;
  Hubra is tested on 16 and runs on 18). These are used for `flask db
  upgrade`, the init step, plugin migrations, scheduled jobs and creating
  the Web Push keys.
- **No transaction-mode pooler** (PgBouncer `pool_mode=transaction`) in
  front of the backend: session-level advisory locks and `search_path` per
  club need a real session. Session mode, or connecting directly, is fine.
- Connections: each scheduled job holds one extra connection while it runs
  (for its lock). Size `max_connections` for roughly
  `(gunicorn workers × API pods + worker concurrency × worker pods) × pool size`
  plus a few for beat, the init step and backups, and check it against
  Postgres' `max_connections` (100 by default).
