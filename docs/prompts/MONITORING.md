Set up basic uptime/health monitoring and alerting so infrastructure problems (mail stack down, disk full, cert expiring, container crash-looping) are surfaced proactively instead of discovered manually via docker compose logs. Also expose a member/admin-facing status page in the frontend so the Verein can see system health without needing server access.

## Step 1 — Decide on tooling

Recommend ONE of the following, with reasoning, before implementing:
(a) Uptime Kuma — self-hosted, simple web UI, supports HTTP checks + Docker container monitoring + many notification channels including Discord webhooks, AND has a built-in public status page feature that could potentially be embedded or linked rather than building one from scratch.
(b) A lightweight custom cron + curl + webhook script — less overhead, less maintenance burden, but less visibility/history than a proper monitoring UI, and no built-in status page (would need to build one entirely from scratch).

Given the existing stack complexity (12+ containers across mail, app, and infra) AND the new requirement for a frontend-facing status view, lean toward (a) Uptime Kuma — its built-in public status page may satisfy the frontend requirement with minimal extra work, which changes the calculus compared to before. Propose this and confirm before implementing, including whether Uptime Kuma's native status page is sufficient or whether a custom-built page inside the existing app frontend is actually wanted instead (see Step 5).

## Step 2 — What to monitor

1. HTTP check against the minimal public /api/v1/health endpoint (the one without detailed infra info, from the security work) — alert if it returns non-200 for more than N consecutive checks
2. Docker container health — alert on any community-* container that's restarting repeatedly or exited
3. Disk space on the VPS — alert below a threshold (e.g. 15% free)
4. TLS certificate expiry — alert if mail.vollbuild.ch cert is within 14 days of expiry (belt-and-suspenders alongside the existing certbot-renew automation, in case renewal silently starts failing)
5. Mail queue depth — if ZoneMTA's queue grows unusually large (could indicate delivery is stuck), this is a stretch goal — flag if it's not easily exposed via a metric/endpoint and deprioritize if so

## Step 3 — Alerting destination

Wire alerts to a Discord webhook in a dedicated #alerts or #infra channel for Pixel and Pine, given the existing Discord bot work already done for the Verein. Confirm the webhook URL/channel before implementing.

## Step 4 — Implement and verify (backend/monitoring)

1. Add the chosen monitoring service to compose (likely a new service block, isolated to the internal network with only the necessary egress for webhook delivery)
2. Configure all checks from Step 2
3. Deliberately trigger one test alert (e.g. temporarily stop a non-critical container) to confirm the Discord notification actually arrives, then restore it
4. Document the monitoring setup and how to add new checks later

## Step 5 — Frontend status page

Decide and confirm with me which of these two approaches before implementing, since they have very different scope:

**Option A — Use Uptime Kuma's built-in public status page, link to it from the app.**
Lowest effort: Uptime Kuma generates its own hosted status page (e.g. status.vollbuild.ch via a new Traefik route + cert, following the existing certbot/Traefik pattern already established for other subdomains). The main app frontend just needs a nav link or footer link to it. No new frontend code beyond that link. Confirm whether this satisfies "a frontend for this" or whether a more integrated, branded-to-match-the-app status view is actually wanted.

**Option B — Build a status widget/page INSIDE the existing app frontend**, matching the app's own design system rather than Uptime Kuma's default UI. This requires:

1. A backend endpoint that aggregates current status (likely reusing/extending the existing /api/v1/health infrastructure, or querying Uptime Kuma's API if running in parallel) and returns a simplified, public-safe status payload — e.g. `{"overall": "operational" | "degraded" | "down", "components": [{"name": "Mail", "status": "operational"}, {"name": "Website", "status": "operational"}, ...]}`. Component names should be user-friendly (e.g. "Mail", "Member Portal") not raw container names like "community-zonemta" — map internal services to friendly labels.
2. A new frontend page/route (e.g. /status, publicly accessible without login, since the point of a status page is that anyone — including a member trying to figure out "is mail down or is it just me" — can check it without needing to log in first)
3. A simple, clear UI: overall status banner (green/yellow/red), list of components with individual status, and ideally an incident history/timeline if feasible (Uptime Kuma tracks downtime history — surface this if accessible via its API, otherwise skip for v1 and note it as a future enhancement)
4. If the app already has the Swiss German translation work in progress or completed, this new page's strings need to follow the SAME established glossary/style conventions (reference the GLOSSARY.md from that earlier work) rather than introducing English or Hochdeutsch text inconsistent with the rest of the app

Confirm with me which option (A or B) before implementing — Option A is significantly less work and may be entirely sufficient; Option B is a better fit if the goal is a cohesive, branded member-facing page consistent with the rest of the app's design and language. Default recommendation: start with Option A given it's nearly free once Uptime Kuma is running, and only invest in Option B later if Option A genuinely feels insufficient in practice.

## Step 6 — Verify and report

- Confirm monitoring is live and the test alert reached Discord
- Confirm the chosen frontend status approach (A or B) is reachable, accurate, and reflects real component status (test by intentionally stopping a service and confirming the status page reflects it within a reasonable delay)
- Document: the monitoring setup, how to add new checks, and how the frontend status page sources its data
