Replace the current fixed-string permission system (e.g. @require_permission("View finances"), @require_permission("Record transactions")) with a full RBAC (Role-Based Access Control) system where every API endpoint has its own discrete, individually-grantable permission, manageable by admins through the UI rather than hardcoded.

## Step 1 — Investigate current state before changing anything

1. Find every usage of @require_permission across the codebase and extract the full list of currently-used permission strings:
   grep -rn "@require_permission(" app/backend/vollbuild/api/ | sed -E 's/.*require_permission\("([^"]+)"\).*/\1/' | sort -u

2. Look at how require_permission and the underlying permission check are currently implemented:
   cat app/backend/vollbuild/api/permissions.py

3. Find the current Role/Permission database models if they exist:
   grep -rln "class Role\|class Permission" app/backend/vollbuild/models/

4. Report: are permission strings currently free-text matched against something in the DB (loose coupling, easy to typo and silently fail open/closed), or is there already a defined Permission table with a fixed set of rows that route decorators reference? This determines how much of the current system can be reused vs needs replacing.

5. Check how roles are currently assigned to users/members and how the permission check resolves at request time (does it query the DB on every request, is it cached in the JWT claims, etc.):
   grep -n "def require_permission\|def has_permission" app/backend/vollbuild/api/permissions.py

6. Admin Role or Flag to give all permissions to a Role

Report all of this back before proposing the new design — I want to understand exactly what we're replacing/extending versus building from scratch.

## Step 2 — Design proposal (confirm before implementing)

Propose a design covering:

1. **Permission identity**: should permissions be identified by a structured key like `finance.transactions.create` or `finance:transaction_categories:write` (resource + action pattern) rather than free-text human labels like "Record transactions"? A structured key is far more reliable for "one permission per endpoint" since it can be derived predictably from blueprint + resource + HTTP method, reduces typos, and makes auto-discovery (Step 3) possible. Human-readable labels ("Record transactions") become a separate display_name field on the Permission model for the admin UI, decoupled from the actual permission key used in code.

2. **Auto-discovery vs manual registration**: propose whether permissions should be:
   (a) Auto-derived from route registration (e.g. a decorator that, instead of taking a hardcoded string, takes structured metadata like resource="transaction_categories", action="create" and the permission key + a sensible default display name get generated automatically), with a startup/migration step that syncs the DB Permission table against all currently-registered routes (adding new ones, flagging orphaned ones whose route no longer exists), OR
   (b) Manually defined permission keys per route as today, just restructured to be more granular and consistently one-per-endpoint.

   Recommend (a) given the goal is "permission for each API endpoint" — auto-discovery prevents permissions from drifting out of sync with actual routes (a real risk with the current manual string-matching approach, where it's easy to add a new endpoint and forget to gate it, or typo a permission string so it never matches any role). Propose the exact mechanism (e.g. a custom decorator @permission_required(resource, action) that both enforces the check AND registers metadata pytest/Flask can introspect at startup to sync the DB) and confirm with me before implementing, since this is the most architecturally significant decision in this whole change.

3. **Role-Permission-User model shape**: propose the schema (likely already partially exists given roles.py blueprint and roles/permissions tests found in the test suite reorganization). Should be roughly:
   - Permission (id, key, display_name, resource, action, description)
   - Role (id, name, description)
   - RolePermission (join table: role_id, permission_id)
   - Member/User has a role_id (or many-to-many if a member can hold multiple roles — check current model, this affects the design)

   Confirm against what already exists rather than assuming a fresh build — the prior service-layer refactor touched a roles blueprint, and test_m003_s02_roles_perms.py / test_issue022_role_permissions.py suggest some of this already exists in some form.

4. **Performance**: decide whether permission resolution happens via a DB query per request (simplest, but adds latency to every authenticated request) or is cached — e.g. permissions baked into the JWT at login time (fast, but stale until re-login/token refresh if permissions change), or cached in Redis with a short TTL/invalidation on role change (good middle ground given Redis is already in the stack for rate limiting and Celery). Propose one and justify given the existing infrastructure, and confirm before implementing — this is also architecturally significant and harder to change later.

5. **Admin UI for managing roles/permissions**: confirm this is in scope for this pass (granting permission for each endpoint via UI was explicitly requested) — propose a frontend page (likely under Settings or a new Roles & Permissions admin section) where an admin can: view all auto-discovered permissions grouped by resource/blueprint, create/edit roles, and check/uncheck which permissions each role has. This is a meaningful frontend task on top of the backend work — confirm whether to scope it into this same effort or treat it as a clearly-flagged follow-up after the backend RBAC core is solid.

## Step 3 — Implementation plan (only after Step 2 design is confirmed)

1. Build/extend the Permission, Role, RolePermission models per the confirmed schema
2. Build the new permission-checking decorator/mechanism per the confirmed auto-discovery approach
3. Write a migration/sync script that walks all registered Flask routes at startup (or via a CLI command, e.g. `flask sync-permissions`) and ensures the Permission table matches reality — creating missing rows, and reporting (not auto-deleting, for safety) any Permission rows whose corresponding route no longer exists
4. Migrate every existing @require_permission("Some Label") call across ALL blueprints to the new decorator/key scheme — this touches every blueprint, not just finance. Use the inventory from Step 1 as the checklist and confirm 1:1 coverage (every old permission string maps to exactly one new structured permission, nothing lost)
5. Seed/migrate existing roles' permission grants from whatever the old free-text matching implied, so existing role assignments don't silently lose access after the migration — this is critical, flag and confirm the mapping before applying it to production data, since getting this wrong means either members suddenly lose access to things they should have, or worse, gain access to things they shouldn't.
6. If Step 2.5 (admin UI) is in scope, implement the frontend page for managing roles/permissions.

## Step 4 — Verify

1. Run the full test suite — given the test reorganization, the roles/permissions tests should now live in tests/roles/ or tests/auth/, confirm they still pass and extend them to cover: a new endpoint added without explicit permission registration gets auto-discovered (or fails closed/visibly rather than silently being unprotected — decide and confirm which failure mode is correct, fail-closed is almost certainly the right default for a permission system)
2. Manually verify: create a test role with only ONE specific permission granted, log in as a member with that role, confirm they can access exactly that one endpoint and are correctly denied everything else
3. Confirm the migration correctly preserved existing role assignments — spot check a few real roles/members against their pre-migration access level

## Step 5 — Report

Provide: the full old-permission-string → new-structured-key mapping table, confirmation every existing @require_permission call was migrated (grep to confirm zero old-style string-literal permission calls remain), the chosen performance/caching approach and why, and whether the admin UI was included in this pass or deferred.

Wait for my confirmation on the Step 2 design proposal — especially the auto-discovery mechanism and caching approach — before writing any implementation code, since these are the hardest parts to change after the fact once roles/permissions exist in production with real member access depending on them.
