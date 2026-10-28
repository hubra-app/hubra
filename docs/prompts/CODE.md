Perform a full codebase coherence audit across both backend and frontend, identifying dead code, duplicate models/concepts, conflicting feature implementations, and UI fragmentation — then produce a consolidation plan before touching any code. This is an INVESTIGATION AND REPORT pass first, implementation second.

═══════════════════════════════════════════════════════════════
PART 1 — Backend: Dead and Duplicate Models
═══════════════════════════════════════════════════════════════

## Step 1.1 — Map every model and its actual usage

List every SQLAlchemy model in the codebase:
   find app/backend/vollbuild/models -name "*.py" | xargs grep -l "class.*db.Model\|class.*Base" | grep -v ".pyc"

For each model found, determine:

1. Is it referenced by any active route/service (not just imported by a migration)?
2. Does it have any rows in the production DB right now?
3. Does it overlap conceptually with another model (e.g. the legacy mailboxes table vs the new ManagedMailAddress table)?

Run this to get row counts for every table at once:
   docker compose exec -T postgres psql -U club_user -d club_db -c "
     SELECT
       schemaname,
       tablename,
       n_live_tup as row_count
     FROM pg_stat_user_tables
     ORDER BY n_live_tup DESC, tablename;
   "

Cross-reference against imports in active service/route files:
   for model_file in $(find app/backend/vollbuild/models -name "*.py" | grep -v __init__); do
     model_name=$(grep "^class " $model_file | sed 's/class \([A-Za-z]*\).*/\1/')
     echo "=== $model_name ==="
     grep -rln "$model_name" app/backend/vollbuild/api/ app/backend/vollbuild/tasks/ \
       --include="*.py" 2>/dev/null | grep -v test | grep -v ".pyc"
   done

Report every model that is either:

- Defined but never imported/used in any active route or service
- Has 0 rows AND no active write path
- Conceptually duplicates another model (e.g. two tables tracking the same domain concept)

## Step 1.2 — Specifically audit mail-related models

Given the problem statement explicitly calls out mail fragmentation, audit every mail-adjacent model carefully:
   grep -rln "mail\|mailbox\|alias\|forward\|wildduck" \
     app/backend/vollbuild/models/ --include="*.py"

For each found, answer:

- What does it track?
- Who writes to it (which service/task/route)?
- Who reads from it (which route/service)?
- Does another model track the same or overlapping thing?

Specifically compare:

- Legacy mailboxes table (found earlier with 0 rows, columns: address, quota_used, quota_total, message_count, send_only) — is anything still reading/writing this?
- mailbox_folders table (written by the mail_sync Celery task, per-folder message/unread counts) — is the frontend actually reading this?
- ManagedMailAddress (protected addresses — Vorstand, Kassier, postmaster)
- Any Group-level mail fields (mail_enabled, mail_prefix mentioned in the problem statement) — where do these live and what do they actually do?
- MailLogEntry / MailLogLine — are these written to, read from, displayed anywhere?

## Step 1.3 — Audit Group mail fields specifically

The problem statement says: "Groups define mail enabled and mail prefix. Mail Group Settings enable mail and forwarding (again?) add additional aliases to a Group and link it."

This suggests at least two separate implementations of group-mail concepts that have grown independently. Find them all:
   grep -rn "mail_enabled\|mail_prefix\|mail_group\|group.*mail\|mail.*alias" \
     app/backend/vollbuild/models/ app/backend/vollbuck/api/ --include="*.py" | \
     grep -v test | grep -v ".pyc"

For each field/table found:

- Where is it set (which API endpoint, which UI)?
- Where is it read (which service, which frontend component)?
- How does it relate to ManagedMailAddress (the newer, more deliberate model)?
- Is it actually wired to WildDuck, or is it a DB field with no real mail-system effect?

Report the full picture of Group-mail fields: what exists, what's wired, what's dead, and where the two "enable mail and forwarding" concepts diverge.

═══════════════════════════════════════════════════════════════
PART 2 — Frontend: Fragmentation Map
═══════════════════════════════════════════════════════════════

## Step 2.1 — Find every place mail is rendered

   grep -rln "mail\|mailbox\|imap\|smtp\|forward\|alias" \
     app/frontend/src/ --include="*.tsx" --include="*.ts" | \
     grep -v node_modules | grep -v ".test."

For each file found, identify:

- What mail concept does it render/manage (mailbox counts, forwarding settings, aliases, mail health, mail log)?
- Which route/page is it on (/dashboard, /members, /groups, /settings, /mail, or somewhere else)?
- Which backend endpoint does it call?

Produce a table like:

| File | Page/Route | Concept | Backend endpoint |
| --- | --- | --- | --- |
| MemberMailSection.tsx | /members/:id | IMAP mailbox counts | GET /api/v1/members/:id |
| GroupMailSettings.tsx | /groups/:id | mail_enabled + forwarding | GET /api/v1/groups/:id/mail |
| ... | ... | ... | ... |

## Step 2.2 — Find duplicate/conflicting mail UI

Cross-reference the table from Step 2.1 to find:

- The same concept rendered in more than one place (e.g. forwarding settings on both a Group page and a dedicated Mail Settings page)
- Settings that exist in the UI but have no backend effect (calls an endpoint that doesn't actually write to WildDuck)
- Settings that exist in the backend but have no UI (only set via API directly, never surfaced to the admin)

## Step 2.3 — Find dead frontend code

# Components imported nowhere

   for f in $(find app/frontend/src -name "*.tsx" | grep -v node_modules); do
     component=$(basename $f .tsx)
     if ! grep -rqn "import.*$component\|from.*$(dirname $f | sed 's|app/frontend/src/||')" \
       app/frontend/src/ --include="*.tsx" --include="*.ts" 2>/dev/null; then
       echo "POSSIBLY DEAD: $f"
     fi
   done

Review each flagged file manually — some may be page-level components registered in the router rather than imported directly. Filter false positives by cross-referencing against the router config:
   find app/frontend/src -name "*.tsx" | xargs grep -l "Route\|router\|createBrowserRouter" 2>/dev/null

═══════════════════════════════════════════════════════════════
PART 3 — Backend: Route and Service Audit
═══════════════════════════════════════════════════════════════

## Step 3.1 — Find routes with no corresponding frontend caller

List all registered API routes:
   docker compose exec -T backend python -c "
     from vollbuild import create_app
     app = create_app()
     for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
       print(f'{list(rule.methods - {\"HEAD\", \"OPTIONS\"})} {rule.rule}')
   " 2>/dev/null | grep -v "static"

For each route, check whether the frontend ever calls it:
   while IFS= read -r route; do
     path=$(echo "$route" | grep -oP '/api/v1/[^\s]+')
     [ -z "$path" ] && continue
     # strip path params for matching
     pattern=$(echo "$path" | sed 's|/<[^>]*>||g' | sed 's|/$||')
     count=$(grep -rln "$pattern" app/frontend/src/ \
       --include="*.ts" --include="*.tsx" 2>/dev/null | wc -l)
     [ "$count" -eq 0 ] && echo "UNCALLED: $path"
   done < <(docker compose exec -T backend python -c "..." 2>/dev/null)

Report routes that are defined but never called from the frontend — these may be legitimately internal (called by other services, Discord bot, Celery tasks) or may be genuinely dead.

## Step 3.2 — Find services with no route callers

   for service_file in $(find app/backend/vollbuild/api -name "services.py"); do
     blueprint=$(dirname $service_file | xargs basename)
     echo "=== $blueprint/services.py ==="
     grep "def " $service_file | grep -v "^#" | sed 's/    def \([a-z_]*\).*/\1/'
   done

Cross-reference each service method against the blueprint's routes.py to confirm it's actually called from a route (or a Celery task) vs defined but unused.

═══════════════════════════════════════════════════════════════
PART 4 — Consolidation Plan (confirm before touching code)
═══════════════════════════════════════════════════════════════

Based on Parts 1-3 findings, produce a consolidation plan covering:

### 4.1 Models to deprecate/drop

For each dead or duplicate model identified, propose:

- Drop entirely (with migration to remove the table) — for models with 0 rows and no active write path
- Merge into another model — for conceptually overlapping models where one should be the canonical representation
- Keep but mark as legacy — if it has data that needs migrating before dropping

Specifically propose resolution for:

- The legacy mailboxes table vs ManagedMailAddress vs mailbox_folders — which is canonical for which concept, what happens to each?
- The Group mail_enabled/mail_prefix fields vs ManagedMailAddress — which is the right place to define "this group has a mail address"?

### 4.2 Group mail: one model, one concept

The split between "Group has mail_enabled/mail_prefix" and "ManagedMailAddress links to a Group" needs to collapse into ONE authoritative concept. Propose which wins:

Option A: ManagedMailAddress IS the source of truth. A group "has mail" if and only if a ManagedMailAddress row with linked_group_id pointing to it exists. The mail_enabled and mail_prefix fields on Group are removed. The address on ManagedMailAddress IS the canonical address (group prefix + club domain computed at creation time, stored as the actual address string). Recommend this — it's the newer, more deliberate model and it's already wired to WildDuck correctly.

Option B: Group mail fields stay, ManagedMailAddress is just the tracking layer. Not recommended — this is the current fragmented state and it doesn't resolve the duplication.

Confirm Option A or propose an alternative before any code changes.

### 4.3 Frontend mail consolidation

Propose a single coherent information architecture for mail across the frontend — one place for each concept, no duplication:

Proposed layout (adjust based on Step 2 findings):

- **Member detail page** — shows that member's own mailbox summary (INBOX count, unread count, storage used) sourced from mailbox_folders. Nothing else mail-related.
- **Group detail page** — shows the group's ManagedMailAddress (if one exists): the address, provisioning status, current forward targets derived from group membership. No separate "Mail Group Settings" page — it's all inline on the group page.
- **Settings → Club** — Club.Banking.Iban, Club.Contact.FinanceEmail, etc. (already planned in the settings prompts). No mail configuration duplicated here.
- **Settings → System** — System SMTP user status (<noreply@vollbuild.ch>). Not editable via UI — display-only.
- **Admin → Mail** — a single admin mail overview: all ManagedMailAddress rows with their provisioning status, the verify task's last-run results, the mail log (MailLogEntry). This is the one place an admin goes to understand "what's happening with mail system-wide."
- **No mail config on the Member detail page** — a member's IMAP/forwarding settings (if they have a personal vollbuild.ch mailbox, per the device-session/account work) belong under their own Account settings, not the admin member-management view.

### 4.4 Dead code removal list

List every file/component/model/route to be removed, with a one-line reason for each, as the output of this audit.

═══════════════════════════════════════════════════════════════
DELIVERABLE
═══════════════════════════════════════════════════════════════

Produce a structured report covering:

1. **Dead models** — table name, row count, last write path, proposed action (drop/merge/migrate)
2. **Duplicate concepts** — what duplicates what, which is canonical, what gets removed
3. **Fragmented frontend** — full table from Step 2.1, duplicated concepts identified, proposed single home for each
4. **Dead routes** — list of API endpoints with no frontend caller and no internal caller
5. **Dead frontend components** — list of components imported/rendered nowhere
6. **Group mail resolution** — confirm Option A or alternative
7. **Consolidation implementation order** — what to fix first (DB migrations removing dead tables are lowest risk; removing live UI duplication requires care around active users)

Do NOT implement any changes in this pass — report only. The consolidation implementation should be a separate, deliberately-scoped set of prompts based on this report's findings, since some removals are risky (dropping a table with data, removing a UI component a user might be actively using) and need my explicit sign-off per item.

Wait for this full report before any code changes.
