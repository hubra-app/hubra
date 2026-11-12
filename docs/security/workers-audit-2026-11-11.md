# Security audit: workers (2026-11-11)

## What counts as the workers image

There is no separate workers image. The background processes run from the
backend images (`app/backend/Dockerfile`): `backend` (Compose) and the role
images `app-backend`, `global-backend`, `platform-backend`. Audited:

- `celery-worker` and `celery-beat` (`hubra.core.tasks`, all `hubra/core/tasks/*.py`)
- `discord-gateway` (`flask modules run discord-gateway`, plugin-discord `gateway.py`)
- the task modules of every plugin (board, booking, community, discord,
  documents, finances, forms, imap-inbox, kasse, keys, letters, messengers,
  payments, qualifications, teams) and the outbound code they call
- the Dockerfile, `docker-compose.yml`, `requirements.lock` (pip-audit)

Stripe webhook verification lives in the API, not the workers; the backend
audit covers it.

## Findings

| # | Sev | Where | Finding | Status |
|---|-----|-------|---------|--------|
| W1 | Medium | plugin-messengers `transports.py` `check_url`/`_request` | Signal/Matrix URLs (set by club admins) were checked with one DNS lookup and called with a second one. A name with a short TTL that answers public first and `10.x`/`127.0.0.1` second (DNS rebinding) made the worker POST/PUT into the internal network, and up to 200 chars of the error answer came back to the board. Answers were also read without a size limit. | Fixed: connection checks the address it connects to, no proxy env, 1 MB cap |
| W2 | Medium | plugin-teams `feed.py` `_check_host`/`fetch` | Same DNS-rebinding gap for iCal fixture feeds (GET, every sync). | Fixed: pinned, checked connection incl. redirects |
| W3 | Medium | plugin-imap-inbox `imap.py` `fetch` | The 25 MB message cap trusts the server's `RFC822.SIZE`. A club admin can point a mailbox at their own IMAP server that announces 1 KB and sends gigabytes; imaplib reads the whole literal into the worker's memory (512 MB limit), killing jobs of every club. | Fixed: literals above 26 MB are refused before reading |
| W4 | Low | core `tasks/__init__.py` `_run_in_tenant` | A job queued for a club that was deleted before it ran set `search_path` to the missing schema; Postgres skips a missing schema, so the job ran on `public` with `g.tenant=None`. | Fixed: such jobs are dropped with a warning |
| W5 | Low | core `services/job_monitor.py` `failure_to_json` | Failed jobs hide secret-looking *keyword* args, but positional ones were shown, e.g. the Discord interaction token of `approve_request(req_id, user_id, token)`. | Fixed: positional args are named from the task signature and hidden the same way |
| W6 | Medium (design) | all backend images, `scripts/pg-init/10-app-role.sh` | Every process (API, worker, beat, gateway, plugin code) uses one DB role that owns every club schema. Club isolation in jobs rests on `search_path` only (well done: `_restore_search_path`, `in_club`, `per_tenant_job`), with nothing in the database to stop a bug or a plugin from reading another club. | Open: needs a decision (see below) |
| W7 | Low | `app/backend/Dockerfile` base stage | The runtime image keeps `curl`, `lsb-release` and `gnupg` used only to add the PGDG repo (gnupg is also the gpg backup fallback); `wget` is used by health checks. | Open: shared with the backend audit; removing curl may break exec probes in the cluster repo |
| W8 | Low | `docker-compose.yml` backend services | `no-new-privileges` is set, but no `cap_drop: [ALL]` and no `read_only: true` root filesystem. | Open (backend audit, same services) |
| W9 | Info | Celery over Redis | Anyone who can write to Redis can queue any registered task with any args and `tenant_id` header. JSON-only serializer (no pickle), Redis password and internal network keep that to someone already inside. | By design |
| W10 | Info | plugin-discord `gateway.py` `read_frame` | Frame length from Discord is not capped (TLS to discord.com only). | Accepted |

## Checked and fine

- Serialization: `task_serializer`/`accept_content` JSON only, no pickle anywhere.
- Credentials: IMAP passwords Fernet per plugin with rotation; module settings of type `secret` (Telegram/Matrix/Signal tokens, webhooks) and platform secrets (SMTP, S3, Stripe, Discord) stored encrypted; Discord tasks pass connection ids, never tokens; WildDuck tasks no longer take passwords; backup keys sealed; `PGPASSWORD` via env, not argv. No secret found in log lines.
- Job payloads: tenant comes from the header set at queue time; webhook, outbox and plugin-event tasks re-read rows by id inside the club.
- Parsers: camt refuses any DOCTYPE/entity before parsing, 10 MB cap for bank files; mail HTML through nh3, text capped; no zip handling in workers.
- Outbound: webhooks pin the checked address and follow no redirects; Web Push only to the browsers' push hosts; Nuki, Pingen, Stripe, Discord, Telegram, Google Wallet, Anthropic are fixed hosts; IMAP pinned to a checked public address with TLS verified.
- SMTP: TLS verified; port 25 opportunistic STARTTLS (known, platform relay).
- Limits: soft/hard time limits, `max_tasks_per_child`, `max_memory_per_child`, late ack.
- Image: base pinned by digest, pip `--require-hashes`, runs as `appuser`, no compilers.
- Dependencies: `pip-audit -r requirements.lock`: no known vulnerabilities. Plugins add no packages of their own.

## Open decision

W6: options are (a) keep one role and add a CI test that every raw SQL and
plugin query goes through the tenant session (cheap, no DB guarantee);
(b) Postgres row-level security keyed on a `hubra.tenant_id` setting
(large migration of every club table); (c) one DB role per club schema,
switched with `SET ROLE` per request/job (strong isolation, moderate work,
needs the app role to be a member of every club role). Recommendation: (c).
