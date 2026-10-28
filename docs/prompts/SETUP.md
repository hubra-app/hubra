Perform a full review of the application's seeding and initial setup process end-to-end, covering everything that needs to exist in a freshly deployed instance before the app is usable. This is an audit-and-fix pass — identify what's currently seeded, what's missing, what's inconsistent, and what depends on manual steps that should be automated.

## Step 1 — Map the current seed process completely

1. Show the full current flask seed command and everything it calls:
   find app/backend -name "*.py" | xargs grep -l "seed\|cli.command" | grep -v test | grep -v ".pyc"
   cat app/backend/vollbuild/cli.py 2>/dev/null || find app/backend -name "cli.py" -exec cat {} \;

2. Show the flask-init container's exact startup sequence from compose:
   grep -A 10 "flask-init" docker-compose*.yml compose*.yml 2>/dev/null

3. List everything currently in the DB after a fresh seed (check every table):
   docker compose exec -T postgres psql -U club_user -d club_db -c "
     SELECT table_name FROM information_schema.tables
     WHERE table_schema = 'public'
     ORDER BY table_name;
   "

   For each table, check row counts post-seed:
   docker compose exec -T postgres psql -U club_user -d club_db -c "
     SELECT schemaname, tablename, n_live_tup
     FROM pg_stat_user_tables
     ORDER BY n_live_tup DESC;
   "

4. List everything currently seeded in WildDuck (users, addresses, filters, webhooks):
   docker exec community-mailserver sh -c "
     wget -qO- '<http://127.0.0.1:8080/users?limit=25>' \
     --header 'X-Access-Token: change-me-wildduck-token'
   "
   docker exec community-mailserver sh -c "
     wget -qO- '<http://127.0.0.1:8080/addresses?limit=25>' \
     --header 'X-Access-Token: change-me-wildduck-token'
   "

5. Identify everything that currently requires MANUAL steps after a fresh deploy (not automated in seed or compose startup) — things like:
   - The <noreply@vollbuild.ch> WildDuck user (created manually during this conversation)
   - The WildDuck webhook registration (flask register-webhook command run manually)
   - Any Cloudflare DNS records added manually
   - Any Traefik configuration applied manually
   - Any settings keys populated manually (Club.Banking.Iban, Club.Identity.Name, etc.)
   - Any WildDuck domain/emailDomain configuration confirmed manually
   Report each manual step found, what it does, and whether it SHOULD be automated in seed.

Report all findings before proceeding — this gives a complete picture of current state vs desired state.

## Step 2 — Define desired state (confirm before implementing)

Based on Step 1 findings, propose the complete list of what should exist after a successful fresh deploy + seed, grouped by category:

### Postgres (via flask db upgrade + flask seed)

- [ ] All Alembic migrations applied
- [ ] Default Roles seeded (matching the RBAC role hierarchy: Präsidium, Kassier, Aktuar, Core, Member, Supporter, Gast — confirm exact list against Statuten/codebase)
- [ ] Default Permissions seeded and synced (auto-discovered from registered routes per the RBAC work)
- [ ] Default Role-Permission assignments seeded (confirm which permissions each default role should have out of the box)
- [ ] Default Groups seeded: Vorstand (protected)
- [ ] Default Functions seeded: Kassier, Präsidium, Aktuar (protected — confirm whether all three or just Kassier for now)
- [ ] ManagedMailAddress rows seeded: <vorstand@vollbuild.ch>, <kassier@vollbuild.ch>, <postmaster@vollbuild.ch> (all protected)
- [ ] Settings keys seeded with sensible defaults (Club.Identity.Name = "VollBuild", Club.Address.Country = "CH", etc. — any key with a known default that doesn't require manual input should be pre-populated; keys requiring real input like Club.Banking.Iban should have a null/empty value but the ROW should exist so the admin UI can show them as "needs configuration")
- [ ] An initial superadmin/Präsidium member (confirm: should seed create a default admin account, or is first-run account creation handled via a bootstrap/onboarding flow? The test_s12_bootstrap_disable.py file suggests a bootstrap mechanism exists — investigate this)

### WildDuck (via seed command calling WildDuckClient)

- [ ] <noreply@vollbuild.ch> user created (the System SMTP user)
- [ ] <vorstand@vollbuild.ch> user created with keepInInbox filter
- [ ] <kassier@vollbuild.ch> user created with keepInInbox filter
- [ ] <postmaster@vollbuild.ch> user created with keepInInbox filter/catch-all
- [ ] WildDuck webhook registered (currently done via flask register-webhook — confirm this should be folded into seed)
- [ ] Domain configuration confirmed (vollbuild.ch as the email domain — check if this needs API-level setup or is purely config-driven via APPCONF_emailDomain)

### Everything that should NOT be in seed (requires real human input, should be clearly documented)

- Club.Banking.Iban (requires real QR-IBAN from the bank — cannot be seeded)
- Cloudflare DNS records (infrastructure, not app-level)
- Traefik external config
- Real member accounts (these are created by members applying/being invited, not seeded)
- TLS certificates (handled by certbot-init or Traefik, not seed)

Confirm the complete desired-state list with me before implementing.

## Step 3 — Investigate the bootstrap mechanism

1. Check test_s12_bootstrap_disable.py and related bootstrap logic to understand the current first-run flow:
   cat app/backend/tests/test_s12_bootstrap_disable.py
   grep -rn "bootstrap" app/backend/vollbuild/ --include="*.py" | grep -v test | grep -v ".pyc"

2. Determine: is there already a mechanism for creating the first admin account on a fresh instance (a one-time bootstrap endpoint, a seed-created default admin, or purely manual)? If a bootstrap endpoint exists, confirm it's correctly disabled after first use (per the test file name suggesting this behavior is tested).

3. Confirm whether the bootstrap flow and the seed flow are cleanly separated (bootstrap = one-time first-admin creation, seed = repeatable default data) or conflated — they should be distinct to allow seed to be idempotent (runnable multiple times without creating duplicate data) while bootstrap is a one-time operation.

## Step 4 — Implement missing seed steps

For each gap identified in Steps 1-2, implement the missing seed step. Apply these principles throughout:

### Idempotency (most important)

Every seed step must be safe to run multiple times. The flask-init container runs on every `docker compose up` — if seed is not fully idempotent, repeated deploys cause errors or duplicate data. Pattern for each seedable entity:

```python
existing = Model.query.filter_by(key_field=value).first()
if existing:
    continue  # already seeded, skip without error or update
# create new row
```

For updates vs creates: seed should ONLY create rows that don't exist — it should NOT update existing rows on re-run, since an admin may have intentionally changed a seeded default (e.g. changed a role's permissions) and seed re-running should not overwrite those changes.

### WildDuck provisioning resilience

Any WildDuck API call in seed must handle WildDuck being temporarily unavailable (e.g. WildDuck container still starting up when flask-init runs). Follow the established pattern: catch the exception, set provisioning_status="sync_failed" on the local row, log a warning, continue to the next item — do NOT raise and abort the whole seed. The Celery retry task handles reprovisioning sync_failed rows.

Add an explicit depends_on for the mailserver service to flask-init in compose if not already present (to reduce the likelihood of WildDuck being unavailable when seed runs, though a race condition is always possible and the sync_failed path must still be robust):
   grep -A 10 "flask-init" docker-compose*.yml 2>/dev/null | grep "depends_on\|mailserver"

### Order of operations within seed

Some seed steps depend on others — enforce correct ordering:

1. Roles (no dependencies)
2. Permissions sync (depends on routes being registered — confirm this runs correctly within Flask app context during seed)
3. Role-Permission assignments (depends on roles and permissions existing)
4. Groups and Functions (depends on roles existing for any role-linkage)
5. ManagedMailAddress rows (depends on groups/functions existing for linked_group_id / linked_function_id)
6. WildDuck provisioning (depends on ManagedMailAddress rows existing, and WildDuck being reachable)
7. Settings defaults (no dependencies)
8. WildDuck webhook registration (depends on WildDuck being reachable)

### Error reporting

Seed should produce clear, structured output summarizing what was created vs already existed vs failed:
[SEED] Roles: 7 created, 0 skipped

[SEED] Permissions: 142 synced

[SEED] Groups: 1 created (Vorstand), 0 skipped

[SEED] Functions: 1 created (Kassier), 0 skipped

[SEED] ManagedMailAddress: 3 created, 0 skipped

[SEED] WildDuck: <vorstand@vollbuild.ch> provisioned, <kassier@vollbuild.ch> provisioned, <postmaster@vollbuild.ch> sync_failed (retry queued)

[SEED] Settings: 8 defaults applied

[SEED] Webhook: registered

[SEED] Done. Review sync_failed items in admin UI.

## Step 5 — Post-deploy checklist document

Create app/docs/DEPLOY.md (or update it if it already exists) documenting:

1. **Automated on every deploy** (handled by docker compose up + flask-init): list every seed step confirmed in Steps 2-4
2. **One-time manual steps on first deploy only**: DNS records, external Traefik config, bootstrap first-admin creation
3. **Manual configuration required before full functionality**: Club settings that cannot be seeded (IBAN, etc.), with a link to the Club Settings UI and explanation of what's needed
4. **How to verify seed ran correctly**: the specific SQL queries and WildDuck API queries from Step 1 that can be run to confirm expected state
5. **How to re-run seed manually if needed**: docker compose exec backend flask seed
6. **How to reset to a clean state** (for testing/staging): the exact commands to drop and recreate the DB and WildDuck data, with a prominent warning never to run this on production

## Step 6 — Verify

1. Completely clean deploy test (drop all volumes, re-run compose up):
   docker compose down -v
   docker compose up -d

   # Wait for flask-init to complete

   docker compose logs flask-init

2. After startup, verify EVERY item from the desired-state list in Step 2 exists:
   docker compose exec -T postgres psql -U club_user -d club_db -c "
     SELECT 'roles' as table_name, count(*) FROM roles
     UNION ALL SELECT 'permissions', count(*) FROM permissions
     UNION ALL SELECT 'groups', count(*) FROM groups
     UNION ALL SELECT 'managed_mail_addresses', count(*) FROM managed_mail_addresses
     UNION ALL SELECT 'settings', count(*) FROM settings;
   "

   docker exec community-mailserver sh -c "
     wget -qO- '<http://127.0.0.1:8080/users?limit=25>' \
     --header 'X-Access-Token: change-me-wildduck-token'
   " | grep -o '"address":"[^"]*"'

3. Re-run docker compose up -d (simulate a redeploy without volume wipe), confirm flask-init runs seed again without errors or duplicate data.

4. Confirm sync_failed items (if any, due to timing) are eventually resolved by the Celery retry task within a reasonable window (check celery-worker logs):
   docker compose logs celery-worker | grep -i "sync\|provision\|wildduck"

5. Full test suite passes, with specific attention to: test_s12_bootstrap_disable.py (confirm bootstrap is correctly one-time), and any new seed-idempotency tests added in this pass.

## Step 7 — Report

Provide a complete summary:

- Full list of what was seeded vs what requires manual input (the authoritative version of the DEPLOY.md checklist)
- Every seed step added in this pass that didn't exist before
- Confirmation seed is fully idempotent (tested in Step 6 point 3)
- Any bootstrap mechanism findings (Step 3) and whether it's correctly separated from seed
- Link to the created/updated DEPLOY.md

Wait for Step 1 investigation findings and Step 2 desired-state confirmation before implementing anything in Step 4.

Add a periodic Celery task that verifies all protected ManagedMailAddress rows actually exist and are correctly configured in WildDuck, detecting and repairing drift between the local DB state and WildDuck reality — since WildDuck could have a user manually deleted, a filter removed, or a forward target become stale without the app knowing.

## Step 1 — Investigate current state

1. Confirm the ManagedMailAddress model and provisioning infrastructure exist and are working:
   docker compose exec -T postgres psql -U club_user -d club_db -c "
     SELECT id, address, address_type, is_protected,
            wildduck_user_id, provisioning_status,
            linked_group_id, linked_function_id
     FROM managed_mail_addresses
     ORDER BY is_protected DESC, address;
   "

2. Confirm the existing Celery beat schedule and the retry task infrastructure
   already built for WildDuck sync (vollbuild/tasks/wildduck_sync.py):
   cat app/backend/vollbuild/tasks/wildduck_sync.py 2>/dev/null || \
   find app/backend/vollbuild/tasks -name "*.py" | xargs grep -l "wildduck\|provision" 2>/dev/null

3. Confirm the existing beat schedule to understand how to add the new task
   alongside the mail_sync task already running:
   grep -rn "beat_schedule\|CELERYBEAT\|sync-wildduck" \
     app/backend/vollbuild/tasks/ --include="*.py"

Report findings before proceeding.

## Step 2 — Design

### What to verify per protected address

For each ManagedMailAddress row where is_protected=true, the task should verify:

1. **WildDuck user exists** — the wildduck_user_id stored locally actually resolves
   to a real WildDuck user (GET /users/{id} returns 200, not 404). If missing,
   the user was deleted outside the app and needs reprovisioning.

2. **Forward targets are correct** — the WildDuck user's active filter forward
   targets match the currently expected targets (derived from linked_group_id's
   current membership, linked_function_id's current holder, or the fixed
   destination for unlinked addresses like postmaster). If stale (e.g. a Vorstand
   member was added/removed and the sync task failed silently), repair by
   rewriting the forward targets.

3. **keepInInbox filter exists** — for mailbox-type addresses, confirm the
   keepInInbox filter is still configured (it could have been manually deleted in
   WildDuck). If missing, recreate it.

4. **provisioning_status is consistent** — if WildDuck checks pass, ensure the
   local row shows "provisioned" not "sync_failed" or "pending". If checks fail,
   update to "sync_failed" so the admin UI surfaces the issue.

### Repair vs alert

Propose two-tier response to detected drift:

- **Auto-repair** (safe, no confirmation needed): recreate a missing WildDuck
  user, rewrite stale forward targets, recreate a missing keepInInbox filter.
  These are deterministic, reversible operations with known correct state — the
  local DB is authoritative, WildDuck should match it.

- **Alert only, no auto-repair** (requires human judgment): if the wildduck_user_id
  stored locally doesn't match any WildDuck user AND no user with the same address
  exists in WildDuck either — this is a more serious state that could indicate
  data corruption. Log at ERROR level, update provisioning_status="sync_failed",
  surface in admin health dashboard. Do not silently reprovision without the admin
  being aware, since reprovisioning creates a new WildDuck user with a new ID and
  any existing mail in the old mailbox would be gone.

Confirm this two-tier approach with me before implementing.

### Schedule

Run every 5 minutes — frequent enough to catch drift quickly (e.g. if someone
manually deletes a WildDuck user, forward targets are restored within 5 minutes)
without being so frequent it hammers the WildDuck API unnecessarily. Given N
protected addresses (currently 3: vorstand, kassier, postmaster) this is trivially
fast (3 WildDuck API calls per run). Confirm the 5-minute interval is acceptable
or adjust.

## Step 3 — Implementation

```python
# vollbuild/tasks/wildduck_sync.py (add alongside existing tasks)

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="vollbuild.tasks.wildduck_sync.verify_protected_mail_addresses",
)
def verify_protected_mail_addresses(self) -> dict:
    """
    Periodic integrity check: verify all is_protected ManagedMailAddress
    rows exist and are correctly configured in WildDuck. Auto-repairs
    stale/missing forward targets and filters. Alerts on user-missing
    states that require human review.
    """
    from sqlalchemy import select
    from vollbuild.extensions import db
    from vollbuild.models.mail import ManagedMailAddress
    from vollbuild.services.managed_mail import (
        check_wildduck_user_exists,
        get_current_forward_targets,
        resolve_expected_forward_targets,
        reprovision_managed_mail_address,
        repair_forward_targets,
        repair_keepinbox_filter,
    )
    from vollbuild.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        logger.warning(
            "verify_protected_mail_addresses: WildDuck not configured, skipping"
        )
        return {"ok": False, "reason": "WildDuck not configured"}

    protected = db.session.scalars(
        select(ManagedMailAddress).where(
            ManagedMailAddress.is_protected == True
        )
    ).all()

    results = {
        "checked": 0,
        "ok": 0,
        "repaired": 0,
        "alert": 0,
        "errors": [],
    }

    for row in protected:
        results["checked"] += 1
        try:
            # 1. Check WildDuck user exists
            if not row.wildduck_user_id:
                # Never provisioned — try now
                logger.warning(
                    "verify: %s has no wildduck_user_id, reprovisioning",
                    row.address
                )
                reprovision_managed_mail_address(row)
                results["repaired"] += 1
                continue

            user_data = check_wildduck_user_exists(row.wildduck_user_id)

            if user_data is None:
                # User ID known but WildDuck user gone — check by address
                user_by_address = wd.find_user_by_address(row.address)
                if user_by_address:
                    # Exists but under a different ID — update our record
                    row.wildduck_user_id = user_by_address["id"]
                    db.session.add(row)
                    logger.warning(
                        "verify: %s found by address but ID mismatch — updated",
                        row.address
                    )
                    results["repaired"] += 1
                else:
                    # Genuinely gone — alert, do not auto-reprovision
                    logger.error(
                        "verify: ALERT — %s (wildduck_id=%s) not found in "
                        "WildDuck by ID or address. Manual review required. "
                        "Existing mail may be lost.",
                        row.address, row.wildduck_user_id
                    )
                    row.provisioning_status = "sync_failed"
                    db.session.add(row)
                    results["alert"] += 1
                    results["errors"].append({
                        "address": row.address,
                        "issue": "wildduck_user_missing",
                        "action": "alert_only",
                    })
                    continue

            # 2. Check forward targets are correct
            expected = resolve_expected_forward_targets(row)
            actual = get_current_forward_targets(row.wildduck_user_id)

            if set(expected) != set(actual):
                logger.warning(
                    "verify: %s forward targets stale — expected %s, got %s. "
                    "Repairing.",
                    row.address, expected, actual
                )
                repair_forward_targets(row.wildduck_user_id, expected)
                results["repaired"] += 1
                continue

            # 3. Check keepInInbox filter exists (mailbox-type only)
            if row.address_type == "mailbox":
                filter_ok = repair_keepinbox_filter(
                    row.wildduck_user_id,
                    check_only=True
                )
                if not filter_ok:
                    logger.warning(
                        "verify: %s keepInInbox filter missing — recreating",
                        row.address
                    )
                    repair_keepinbox_filter(
                        row.wildduck_user_id,
                        check_only=False
                    )
                    results["repaired"] += 1
                    continue

            # All checks passed
            if row.provisioning_status != "provisioned":
                row.provisioning_status = "provisioned"
                db.session.add(row)
            results["ok"] += 1

        except WildDuckError as exc:
            logger.error(
                "verify: WildDuck error checking %s: %s",
                row.address, exc
            )
            results["errors"].append({
                "address": row.address,
                "issue": str(exc),
                "action": "skipped",
            })

    db.session.commit()

    logger.info(
        "verify_protected_mail_addresses: checked=%d ok=%d repaired=%d "
        "alerts=%d errors=%d",
        results["checked"],
        results["ok"],
        results["repaired"],
        results["alert"],
        len(results["errors"]),
    )

    return {"ok": True, **results}
```

Register in the Celery beat schedule alongside the existing mail sync task:

```python
celery_app.conf.beat_schedule = {
    # existing tasks...
    "sync-wildduck-message-counts": {
        "task": "vollbuild.tasks.mail_sync.sync_wildduck_message_counts",
        "schedule": 60.0,
    },
    # new task:
    "verify-protected-mail-addresses": {
        "task": "vollbuild.tasks.wildduck_sync.verify_protected_mail_addresses",
        "schedule": 300.0,  # every 5 minutes
    },
}
```

## Step 4 — Surface alerts in admin UI

1. The verify task updates provisioning_status on rows it finds problematic.
   Surface this in the existing ManagedMailAddress admin UI (already planned
   in earlier prompts to show provisioning_status per row):
   - provisioned + green indicator: all checks passed last run
   - sync_failed + amber indicator: auto-repairable issue was found and repaired
     on last run, or repair is pending
   - sync_failed + RED indicator + "Manual review required" label: the
     wildduck_user_missing alert case — an admin must investigate before the
     app attempts to reprovision, since existing mail could be at risk

2. Add the protected address health to the existing /api/v1/health/detailed
   endpoint (from the earlier security remediation work that split health into
   public minimal + admin detailed):

```python
def _check_protected_mail_addresses() -> dict:
    """Check all protected mail addresses are provisioned."""
    from vollbuild.models.mail import ManagedMailAddress
    rows = ManagedMailAddress.query.filter_by(is_protected=True).all()
    failed = [
        r.address for r in rows
        if r.provisioning_status != "provisioned"
    ]
    return {
        "ok": len(failed) == 0,
        "total": len(rows),
        "failed": failed,
    }
```

   Add to the detailed health check response under services.protected_mail.

1. Wire an alert to the Discord #alerts channel (via the existing monitoring
   setup from the Uptime Kuma/monitoring prompt) if the verify task finds
   a wildduck_user_missing case — this is serious enough to warrant an
   immediate human notification, not just a UI indicator:

```python
# In the verify task, after detecting wildduck_user_missing:
if results["alert"] > 0:
    notify_discord_alert(
        level="error",
        title="Protected mail address missing from WildDuck",
        body=f"{results['alert']} protected address(es) not found in WildDuck "
             f"and require manual review: "
             f"{[e['address'] for e in results['errors'] if e['action'] == 'alert_only']}"
    )
```

   Use whatever Discord webhook notification helper already exists in the
   codebase (check if the monitoring work introduced a shared notify_discord_alert
   utility, or implement a minimal one reusing the webhook URL from settings):
   grep -rn "discord.*webhook\|notify.*discord" app/backend/vollbuild/ \
     --include="*.py" | grep -v test

## Step 5 — Verify

1. Confirm the task is registered and running:
   docker compose logs celery-beat | grep "verify-protected"

2. Confirm a clean run with all addresses healthy:
   docker compose exec -T backend python -c "
     from vollbuild.tasks.wildduck_sync import verify_protected_mail_addresses
     result = verify_protected_mail_addresses()
     print(result)
   "
   Expected: checked=3, ok=3, repaired=0, alert=0

3. Simulate drift — manually delete a WildDuck filter for postmaster:

   # Get postmaster's wildduck_user_id from DB

   # Call WildDuck API to delete its filter

   # Wait for or manually trigger verify task

   # Confirm it detects the missing filter and recreates it

   # Confirm provisioning_status returns to "provisioned"

4. Simulate the serious case — manually delete the WildDuck user for
   one of the protected addresses entirely (use a test/staging environment,
   NOT production):

   # Confirm verify task logs ERROR, sets sync_failed, does NOT reprovision

   # Confirm Discord alert fires

   # Confirm admin UI shows red "Manual review required" indicator

5. Confirm the task is non-destructive when WildDuck is temporarily
   unavailable — stop mailserver container, wait for a verify run,
   confirm it logs a warning and returns gracefully without crashing
   or corrupting any DB state.

6. Full test suite passes; add tests for:
   - All three check scenarios: ok, needs-repair (auto-fixed), alert-only
   - The resolve_expected_forward_targets logic (this is where bugs
     most likely creep in — ensure Vorstand membership changes and
     Kassier holder changes both produce correct expected target lists)
   - Discord alert fires exactly once per verify run with alert items,
     not once per affected address (avoid alert spam)

## Step 6 — Report

Confirm: task registered and confirmed running in Celery beat, all three
verify scenarios tested (ok, auto-repair, alert-only), Discord alert confirmed
working for the serious case, and health/detailed endpoint updated to surface
protected mail address status.
