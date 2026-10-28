Set up a lightweight staging/preview environment so risky changes (the JWT cookie auth migration, password policy changes, the Swiss German translation rollout, future schema migrations) can be tested before hitting the production VPS directly. Currently all work in this project appears to happen directly against the production containers on vps-public-matterhorn — confirm this is accurate before proceeding.

## Step 1 — Confirm current deployment model

Ask/confirm: is there genuinely no staging environment today, and is vps-public-matterhorn the only deployment target? Is there a second VPS or spare capacity (vps-public-eiger was used for external connectivity testing earlier in this work — is that VPS available/appropriate to host staging, or is it used for something else)?

## Step 2 — Propose architecture

Given the existing compose.yml + compose.override.yml pattern (base + environment-specific override), propose a third overlay: compose.staging.yml, following the SAME lean-override philosophy established earlier (only diverge from base where actually needed — different Traefik hostname/router rule, separate database/volume names or a separate host entirely, reduced resource limits if running alongside other things).

Key decisions to confirm before implementing:

- Same VPS with different ports/subdomain (e.g. staging.vollbuild.ch) vs a separate VPS entirely (cleaner isolation, avoids resource contention with production mail stack, but costs more / adds an extra host to maintain)
- Does staging need its own WildDuck/Haraka/ZoneMTA mail stack, or can mail-related testing be skipped/mocked in staging (running a full mail server stack twice is meaningful complexity — propose mocking/stubbing outbound mail in staging, e.g. an MailHog/Mailpit-style catch-all SMTP sink, rather than running real Haraka/ZoneMTA/WildDuck twice, unless mail-stack changes specifically are what's being tested)
- Database: staging should have its own Postgres/Mongo with either synthetic seed data or a sanitized/anonymized copy of production data (NEVER a raw copy of production member PII into a less-protected staging environment — flag this explicitly as a hard requirement if data copying is ever proposed)

## Step 3 — Implement

1. Create compose.staging.yml following the confirmed architecture
2. Set up Traefik routing for a staging subdomain with its own Let's Encrypt cert (reuse the existing certbot pattern)
3. Set up seed data (synthetic, not copied production PII) for testing
4. Document the deploy-to-staging workflow (e.g. docker compose -f compose.yml -f compose.staging.yml up -d) in the repo

## Step 4 — Verify

Deploy current main branch to staging, confirm it's reachable and functional, confirm production is completely unaffected/isolated from staging (separate volumes, separate networks, no shared state).

Report back the final staging URL, deploy process, and any limitations (e.g. "mail sending in staging goes to Mailpit catch-all, not real recipients") so future work knows what staging can and can't verify.
