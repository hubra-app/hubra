Agent Configuration for Club Management Suite

General Rules


Never create files outside the project directory
Ask before deleting any file
Explain reasoning before writing code
If unsure, ask. Don't guess.
Always work in an isolated git worktree (see Coding Prerequisites)
Always commit changes after completing a task


Cost Controls

Subagent Spawning

Default to staying in the main agent and working sequentially. Spawn at most
one subagent (there is no true parallelism — see the concurrency cap below),
and only when one of these is true:


Searching more than 20 files
A genuinely independent, self-contained subtask can be delegated wholesale
User explicitly requests a subagent


For normal implementation tasks:


Work sequentially
Stay in the main agent
Avoid exploratory subagents


Maximum concurrent subagents: 1. Never run subagents in parallel. If two
independent tasks exist, do them one after another in the main agent rather
than fanning out.

Efficiency


Prefer working in the main conversation.
Do not create subagents for single-file edits.
Do not create subagents for bug fixes unless explicitly requested.
Use Explore only for large codebase searches.
Keep responses concise.
Read only files relevant to the task.
Summarize findings instead of pasting large code blocks.


Coding Prerequisites

Before every implementation task:

1. Git Worktree Isolation

Always load the using-git-worktrees skill at the start of every task.
Follow its Step-0→Step-1→Step-2→Step-3 workflow to ensure work happens
in an isolated worktree.

1a. Worktree Environment Setup

A new worktree contains only tracked files. Gitignored artifacts
(.env.dev, .venv/, node_modules/) do not carry over and must be
recreated inside each worktree before the pre-commit gate can run.

Immediately after creating the worktree, from the worktree root:

shcd .worktrees/<name>

# 1. Dev env file (gitignored — copy from the main checkout, never commit it)
cp ../../.env.dev .env.dev

# 2. Backend: fresh per-worktree venv + deps (uv)
cd app/backend
uv venv                        # creates .venv from pyproject.toml's Python version
uv sync                        # installs from uv.lock (add --dev for dev deps)
cd ../..

# 3. Frontend: clean, reproducible install from the lockfile
cd app/frontend && npm ci                          # fall back to `npm install` if no lockfile

Notes:


The venv is per-worktree by design — each worktree gets isolated
dependency state so concurrent tasks can't clobber each other.
uv sync installs the locked dependency set from uv.lock. Use
uv sync --dev (or --all-extras) if the pre-commit gate needs dev/test
deps like pytest. Prefer uv run <cmd> over manually activating .venv.
npm ci wipes and rebuilds node_modules from package-lock.json for
reproducibility; use npm install only if a lockfile is absent.
.env.dev (repo root) is gitignored. Copy it in; never stage or commit it.


2. Pre-commit Verification Gate

Before every commit, run (in order):

Frontend (if app/frontend/ was modified):

shcd app/frontend && npm run build && npm run lint

Backend (if app/backend/ was modified):

shcd app/backend && uv run pytest tests/ --ignore=tests/test_s11_backend_gaps.py

If either fails, fix the issue before committing. Do NOT bypass failures.

3. Commit Requirement


Always commit after completing a task.
Write meaningful commit messages (matching repo style).
Keep commits atomic — one logical change per commit.
Use Conventional Commits format:
type(scope): description (e.g. feat:, fix:, chore:, refactor:).
Enforced by conventional-pre-commit in .pre-commit-config.yaml.


4. Push, Merge, and Worktree Cleanup

After committing in the worktree:


Push the branch to origin:


sh   git push -u origin <branch-name>

The pre-push hook runs the full pytest suite, which includes
test_s11_backend_gaps.py. That test hangs if Redis is unreachable, so
bring the stack (or at least Redis) up before pushing:

sh   docker compose up -d redis

Pushing outside Docker without a reachable Redis will hang the pre-push
hook. (Longer term: guard s11 in the hook behind a Redis ping / pytest
marker so an unreachable Redis skips it instead of hanging.)


Create a merge request on GitLab via the gitlab_create_merge_request
tool (project: VollBuild/club-operations-suite). Set squash: true and
remove_source_branch: true for clean history.
Merge the MR via gitlab_merge_merge_request with squash: true and
should_remove_source_branch: true.

This auto-merges your own MR to master with no external review gate.
That's a deliberate solo-repo choice — own it. If you ever want a review
checkpoint, stop after step 2.




Clean up the worktree — remove the worktree directory and delete the
local branch:


sh   git worktree remove .worktrees/<worktree-name> --force
   git branch -D <branch-name>

If git worktree remove fails with permission errors (file locks from
graphify or antivirus), manually delete the directory then run
git worktree prune followed by git branch -D <branch-name>.


Close the associated work item and/or milestone — after the MR is
merged, close any GitLab work item(s) this task addressed:

Use gitlab_update_work_item with state_event: "close" and add a
status::fixed or status::closed label.
If the work item was the last open item in a milestone, close the
milestone via gitlab_update_milestone with state_event: "close"
(activate the milestones toolset first via gitlab_discover_tools
with category: "milestones" if needed).
Add a note to the work item referencing the merged MR URL.





5. Update Knowledge Graph

After modifying code, run graphify update . to keep the knowledge graph
current (AST-only, no API cost).

6. Use Available MCP Servers and Skills

When working on tasks, leverage configured MCP servers where appropriate:


gitlab — Manage merge requests, issues, branches, pipelines, labels, and project settings; accessible via gitlab_* tools (e.g. gitlab_create_merge_request, gitlab_get_merge_request, gitlab_merge_merge_request, gitlab_get_project, gitlab_list_merge_request_pipelines, gitlab_create_issue, gitlab_list_labels, etc.)
postgres/redis — Query database state, inspect cache, verify migrations
context7/qmd — Fetch library docs, search local knowledge base
mantine — Look up Mantine component props and examples
playwright — Run E2E tests, verify UI behavior
docker — Inspect container logs, restart services


Load relevant .agents/skills/ at task start using the skill tool
(e.g. flask-api-development, docker-expert, playwright-cli).

7. Track Work as GitLab Work Items

Create features, issues, and todos as GitLab work items (not just issues)
so they appear in the project's work item tracker with proper typing:


Use gitlab_create_work_item with type set to:

"issue" — bugs, vulnerabilities, problems to investigate
"task" — concrete actionable work items
"epic" — large features spanning multiple issues
"incident" — production incidents



Always assign labels from the project's label set:

type::* — type::issue, type::feature, type::question
priority::* — priority::critical, priority::high, priority::medium, priority::low
status::* — status::open, status::in progress, status::fixed, status::resolved, status::closed
security — any security-related finding or hardening task



Activate the workitems toolset first via gitlab_discover_tools with
category: "workitems" if the tools are not yet active.
After fixing a work item, update it via gitlab_update_work_item with
state_event: "close" and add a status::fixed label.


8. Changelog and GitLab Releases

After merging a significant change to master:


Update app/backend/CHANGELOG.md — bump the version per the rules in
step 3 below (do not blindly minor-bump) and add an entry under a new
## [X.Y.Z] - YYYY-MM-DD heading. Follow the
Keep a Changelog format with ### Added,
### Changed, ### Fixed, ### Removed subsections. Move the previous
[Unreleased] content under the new version heading.
Create a GitLab release — a release is a distinct object, not a work
item/epic. Tag the release commit first, then create the release from that
tag:


sh   git tag vX.Y.Z && git push origin vX.Y.Z

Then create the release via the GitLab Releases API
(POST /projects/:id/releases) or the gitlab_create_release tool if
available, targeting tag vX.Y.Z on master, with the CHANGELOG entry as
the release description. Do not create an epic/work item as a stand-in
for a release.
3. Versioning rules (these govern step 1's bump):


Minor (X.Y+1.0) — new features, security fixes, or other
significant changes.
Patch (X.Y.Z+1) — bug fixes only.


Code Style & Standards

Python (backend)


Follow PEP 8 — enforced by ruff
Use snake_case for variables, functions, file names
Use PascalCase for classes
Type-annotate all function signatures


TypeScript (frontend)


Follow the project's ESLint + Prettier config — enforced by pre-commit
Use camelCase for variables, functions
Use PascalCase for components, types, interfaces
File names: PascalCase for components (MemberCard.tsx), camelCase for utilities (apiClient.ts)
UI is Mantine (migrated off Tailwind/Bulma). Reach for Mantine
components and its theming system, not Tailwind utility classes. Use the
mantine MCP server for props/examples.


Branch Naming

Conventional-commit prefix + slash + kebab-case description. Scope is
optional; include it only when it adds clarity:


Without scope (common): feat/member-export, fix/login-redirect, chore/deps-update
With scope: feat/mail-outbound-retry, fix/auth-token-refresh


Stack


Frontend: React 19 + TypeScript + Vite + Mantine (app/frontend/)
Backend: Flask + Python + PostgreSQL + Redis + MongoDB (app/backend/)
Mail: Inbound via Infomaniak (IMAP/SMTP). Outbound via Celery →
Infomaniak SMTP. (WildDuck / Haraka / ZoneMTA have been removed from the
stack.)
Reverse proxy: Traefik → Caddy → backend (effective one hop for
ProxyFix — set x_for=1 etc. accordingly).
Deployment: Docker Compose (docker-compose.yml)


Development Commands

Start frontend dev server:

shcd app/frontend && npm run dev

Run database migrations (prefix with uv run outside the container, e.g.
uv run flask db upgrade):

shflask db upgrade

Seed the database:

shflask seed

Docker

Start all services:

shdocker compose up -d

Rebuild a specific service after code changes:

shdocker compose up -d --build frontend
docker compose up -d --build backend

View logs:

shdocker compose logs -f backend

Important Rules


Never commit .env, .env.dev, or any file containing secrets
Don't modify docker-compose.yml without discussing first
Database migrations live in app/backend/migrations/ — always generate via flask db migrate, never hand-edit
All backend API routes are documented in app/backend/README.md


Notes


test_s11_backend_gaps.py requires a running Redis instance and will hang if
Redis is unavailable. Run with --ignore=tests/test_s11_backend_gaps.py when
testing without Docker:


sh  uv run pytest --ignore=tests/test_s11_backend_gaps.py


The full suite (excluding test_s11_backend_gaps.py) is expected to pass —
~300+ tests. Don't hardcode the count here; check the actual run.


graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types /graphify, use the installed graphify skill or instructions before doing anything else.

Rules:


For codebase questions, first run graphify query "<question>" when graphify-out/graph.json exists. Use graphify path "<A>" "<B>" for relationships and graphify explain "<concept>" for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.


Migration Note

Never hand-write migrations. Always generate via flask db migrate.
If no working database is available, spin up Docker (docker compose up -d postgres)
or use SQLite temporarily to generate the migration. Hand-written migrations cause
PostgreSQL/SQLite compatibility bugs (boolean defaults, type casts, idempotency)
that only surface in production.

The only exception is if flask db migrate is fundamentally broken and cannot
produce a migration — in that case, ask the user before hand-writing.

Frontend Best Practices

These rules apply to all three frontends: app/frontend/, app/admin-frontend/,
and app/sso-frontend/. They are enforced by review and lint. See
docs/FRONTEND-REVIEW.md for the full audit that produced them.

Data Fetching & Server State

TanStack Query owns server state. Never hand-roll a fetch + useState +
useEffect triad for data that comes from the API. Use useQuery for reads
and useMutation for writes. The query cache handles dedup, retry, cache,
and invalidation — reimplementing those manually is a bug source.

Effects

Always pass AbortSignal to API calls inside effects. Create an
AbortController, pass ctrl.signal to the fetch function, and abort in
the cleanup. This makes effects idempotent under React 18/19 StrictMode
double-invoke (dev mounts components twice and runs each effect twice).
Never disable StrictMode — fix the effect instead.
Never set react-hooks/exhaustive-deps to 'off' in eslint config. It
mechanically prevents stale-closure bugs and request loops. Use
reactHooks.configs.flat.recommended to enable it. Legitimate run-once
effects can use eslint-disable-next-line react-hooks/exhaustive-deps
with a comment explaining why.
Never call setState (including via queueMicrotask) to initialize
derived state from query data — compute during render or use a lazy
useState initializer.

Auth & HTTP

One central apiFetch instance per app with a single 401 -> refresh ->
retry-once path. No scattered 401 handling or redirect logic in
individual components. Use setAuthFailureHandler for the central
redirect.
No raw fetch() in feature/screen code. Use apiFetch for JSON or
apiFetchBlob for downloads/exports. Raw fetch bypasses the 401 refresh
handler and CSRF token injection.
Auth tokens in httpOnly cookies only. Never store auth tokens in
localStorage or sessionStorage (XSS-readable). Only non-sensitive
preferences (e.g. language) may use localStorage.
QueryClient retry must skip 401 and 403 — auth failures are never
blindly retried. (Already configured in all three apps — keep it.)

Context & State

Always useMemo context provider values. A non-memoized value object
creates a new reference every render, re-rendering all consumers
unnecessarily.
Use split contexts (ToastContext, AuthContext, NavContext, DataContext)
with narrow hooks (useAuth, useNav, useData, useToast). Never export a
merged useApp() that collapses them — it defeats the split.
Global state used for what should be local is an anti-pattern. Only
genuinely cross-cutting state belongs in context.

Forms

Use @mantine/form + mantine-form-zod-resolver + zod for all forms. No
manual per-field useState. Validation schemas should be shared with the
backend contract where possible (zod schemas double as runtime
validation and inferred TypeScript types).
Only setValues from query data when the form is not dirty — background
refetch clobbers in-progress edits otherwise.

Routing

Use React Router guards (RequireAuth, RequirePermission, RequireFeature)
for auth/permission/feature gating. Protected queries must be gated
behind enabled: authStatus === 'authed' — never fire a protected
request before auth status is known.
Use lazy() for route-level code splitting. Wrap lazy/Suspense routes
in react-error-boundary with resetKeys={[location.pathname]} so a
failed chunk load can retry without a full reload.
No window.location.assign() or window.location.href in render bodies —
move redirects to useEffect or use React Router's <Navigate>.

Dates, Numbers & i18n

Use Intl.NumberFormat, Intl.DateTimeFormat, and
Intl.RelativeTimeFormat with the "de-CH" locale for Swiss date/number/
currency formatting. Never use toLocaleDateString() without an explicit
locale, and never hand-roll relative time strings. See app/frontend/
src/format.ts for the established pattern.
Use react-i18next + useT() for all user-facing strings. No hardcoded
user-facing strings in component code. i18n interpolation escapeValue
must be true.

TypeScript at the API Boundary

No as any or as unknown as casts to silence type errors. If the type
is wrong, fix the type. No @ts-ignore or @ts-expect-error.
Type all API responses with interfaces. Prefer zod schemas that
double as runtime validation + inferred types (z.infer<typeof schema>).

Rendering & Performance

Memoize props passed to memoized children (useMemo for objects/arrays,
useCallback for functions). Stable keys — never use array index as key
for lists that can reorder. No derived state stored in useState and
synced via effect — compute during render.

Lint & Tooling

eslint-plugin-react-hooks with exhaustive-deps enabled in every
frontend app. Never set it to 'off'. npm run lint must pass before
commit. The repo-root .pre-commit-config.yaml should gate frontend
lint alongside backend style.

Shared Code

Do not duplicate apiFetch/client.ts across apps. Extract shared code
into a package (e.g. packages/api-client/) imported by all three
frontends. Bug fixes to the auth/CSRF path must apply once, not three
times.


Security Best Practices

These rules apply to all frontends and the backend.

Token Storage

Auth tokens in httpOnly cookies only. Never in localStorage or
sessionStorage — those are readable by any JavaScript on the page
(XSS). Only non-sensitive preferences (language, UI state) may use
localStorage.
SESSION_COOKIE_HTTPONLY = True, SESSION_COOKIE_SAMESITE = 'Lax',
SESSION_COOKIE_SECURE = True in production Flask config.

CSRF

X-CSRF-TOKEN header on every POST/PATCH/DELETE request. The frontend
reads the csrf_access_token cookie and sends it as a header (double-
submit cookie pattern). This is already implemented in apiFetch —
keep it consistent. Any raw fetch() call that bypasses apiFetch also
bypasses CSRF (see Frontend Best Practices — no raw fetch).
Backend must validate the CSRF token on every mutating route.

Secrets in the Bundle

Anything under VITE_ is embedded in the client bundle in plaintext.
Only public config belongs there: API base URL, SSO URL, admin portal
URL. Never put API keys, mail-stack credentials, or backend secrets in
a VITE_ variable.
Production source maps must be disabled (vite.config.ts:
sourcemap: false — already set in all three apps, keep it).

Authorization Boundary

Frontend permission checks (RequirePermission, hasPermission) are UX,
not security. Real authorization is enforced server-side (Flask
decorators). Never rely on hiding UI as a security boundary — always
assume the user can call any API endpoint directly.
Backend: use @login_required and @permission_required decorators on
every route. Never trust the frontend to enforce access control.

Redirect Validation

Validate redirect URLs against an allowlist before redirecting. The
SSO frontend's validateRedirect() function (sso-frontend/src/context/
SsoContext.tsx:34-48) is the correct pattern — only allow
*.vollbuild.ch or localhost. Never redirect to an arbitrary user-
supplied URL (open redirect vulnerability).

Input Sanitization

React escapes text by default. No dangerouslySetInnerHTML. If HTML
rendering is unavoidable, sanitize with DOMPurify first.
Backend: validate every request body with a schema (marshmallow or
pydantic). Never trust client input.

Rate Limiting

Protect auth endpoints (login, forgot-password, reset-password) with
rate limits. 401 and 403 must never be retried by the frontend
(already enforced in QueryClient retry config — keep it).


Backend / Flask Best Practices

These rules complement the existing rules in AGENTS.md (migrations,
testing, commit gates).

Auth Decorators

Use @login_required on every non-public route. Use
@permission_required('key') for role-gated routes. Never rely on the
frontend to hide functionality — every API endpoint must enforce its
own access control.

CSRF Validation

Validate X-CSRF-TOKEN header on every POST/PATCH/DELETE. Use Flask's
CSRFProtect or the existing double-submit cookie pattern. Reject
requests missing or mismatching the token with 400.

Session Configuration

SESSION_COOKIE_HTTPONLY = True (prevent JS access)
SESSION_COOKIE_SAMESITE = 'Lax' (prevent CSRF)
SESSION_COOKIE_SECURE = True in production (HTTPS only)
SESSION_COOKIE_DOMAIN set to the correct domain in production.

Input Validation

Validate every request body with marshmallow or pydantic. Never
accept unvalidated JSON. Define schemas once and reuse across routes.
Return 400 with a clear error envelope on validation failure.

SQL Injection

Use SQLAlchemy ORM or parameterized queries. Never f-string or
string-concatenate SQL. Use db.session.execute(text(query),
params) with bound parameters, not text(f"...{var}...").

Secrets

Load all secrets from environment variables (os.environ). Never
hardcode. Never log secrets. Use .env.dev for local development
(gitignored — never commit it). Use docker secrets or env vars in
production.

Error Handling

Catch exceptions at route boundaries and return JSON error envelopes
({ "error": "...", "message": "..." }). Never leak stack traces or
internal error details in production. Log the full error server-side.

Testing

uv run pytest --ignore=tests/test_s11_backend_gaps.py for local
runs (Redis dependency). Aim for high coverage on auth + RBAC paths.
Every new endpoint should have at least one happy-path and one
auth-failure test.


Debugging Context


These are investigation notes, not durable config. Consider relocating to
docs/DEBUGGING.md to keep this file lean.



Seed bug: translations not persisting to database

The flask seed --skip-migrate command outputs "Seeded N translations for locale 'X'" and
"Seed data inserted.", but the translation table remains empty (0 rows) from any other
connection. Even a simple ORM insert‑and‑commit

pythont = Translation(locale='en-GB', ...)
db.session.add(t)
db.session.commit()
count = db.session.query(Translation).count()  # returns 1

reports success (count=1) inside the same app.app_context() block, but the row is not
visible from any subsequent connection (including a raw SQL engine connection via
from sqlalchemy import create_engine; engine.connect()), which sees 0 rows in
translation. A raw SQL INSERT + conn.commit() does persist and is visible
everywhere.

Most likely root cause — check this FIRST: the ORM engine and the raw/psql
connection are pointing at different databases (or the same database but a different
schema via search_path). The symptom set — psql/raw SQL persist and are visible,
ORM commit() reports count=1 only within its own session, and nothing is ever visible
elsewhere — is the textbook signature of a connection-target mismatch, not a commit
that never fires. Verify identity before chasing SQLAlchemy internals:


Log str(db.engine.url) and compare exactly to os.environ['DATABASE_URL'] and
to the DSN psql/raw create_engine() uses (host, port, dbname, and any
?options=-csearch_path=...).
Run SHOW search_path; on the ORM connection vs. the raw connection.
Confirm app.config['SQLALCHEMY_DATABASE_URI'] is identical to DATABASE_URL.


If any of those differ, that's the bug — the checklist below is a red herring.

Secondary checklist (only if URI + search_path are provably identical):


Is app.config['SQLALCHEMY_ENGINE_OPTIONS'] (or SQLALCHEMY_ECHO) overriding
connection behaviour?
Is db.session.commit() actually emitting a COMMIT to PostgreSQL? (Enable
SQLALCHEMY_ECHO to verify the wire traffic.)
Could db.session be bound to a different sessionmaker / engine than the one that
owns the translation table?
Are there Flask‑SQLAlchemy event hooks (before_commit, after_commit) registered
that could interfere?
Could the vollbuild/extensions.py db object be initialised with engine options
that route commit through a different connection than raw create_engine()?


Temporary workaround: Use raw SQL (engine.execute(...)) or direct psql for seed
inserts instead of ORM db.session.add() + commit().
