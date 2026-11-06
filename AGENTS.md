# Agent configuration for Hubra

## General rules

- Never create files outside the project directory.
- Ask before deleting any file.
- Explain your reasoning before writing code.
- If unsure, ask. Don't guess.
- Work in an isolated git worktree or branch, never on `main`.
- Commit your changes when a task is done.

## Cost controls

Stay in the main agent and work sequentially by default. Spawn at most one
subagent, and only when:

- the search spans more than 20 files,
- a self-contained subtask can be handed over whole, or
- the user asks for one.

Never run subagents in parallel. Don't spawn one for a single-file edit or a
bug fix unless asked. Read only the files the task needs, and summarise
findings instead of pasting large code blocks.

## Where things are

The code lives on GitHub in `hubra-app/hubra`. Plugins live in their own
repositories (`hubra-app/hubra-plugin-<id>`), the Marketplace in
`hubra-app/hubra-plugins`, the website in `hubra-app/hubra.club`. GitLab is
only a mirror that runs the checks again and creates GitLab Releases
([docs/gitlab.md](docs/gitlab.md)).

| Part | Where |
| --- | --- |
| Backend (Flask, Celery) | `app/backend/` |
| Club app, manage, sign-in, support | `app/frontend/`, `app/admin-frontend/`, `app/sso-frontend/`, `app/support-frontend/` |
| Shared frontend code | `packages/ui` (`@hubra/ui`), `packages/api-client` (`@hubra/api-client`) |
| Claude connector | `app/mcp/` |
| Mail stack (WildDuck, Haraka, ZoneMTA, opt-in) | `modules/mail/` |
| Docs | `docs/`, plus the [README](README.md) table |

Architecture: [docs/architecture.md](docs/architecture.md). API:
[docs/api-overview.md](docs/api-overview.md) and
[app/backend/API.md](app/backend/API.md).

## Before every commit

Run what your change touches:

```sh
# Backend (app/backend/)
cd app/backend
python -m pytest -n auto
ruff check . && ruff format --check .

# A frontend (app/frontend, app/admin-frontend, app/sso-frontend, app/support-frontend)
npm run lint && npm run build && npm test
```

Changes the browser sees also need the browser tests (`npx playwright test`
in `app/frontend`, against a running stack; see [docs/ci.md](docs/ci.md)).
If something fails, fix it. Never bypass a failing check.

For a fresh checkout or worktree: copy `.env` (or run `scripts/init-env.sh`),
install the backend with `pip install -r app/backend/requirements-dev.txt`
(or `uv sync` in `app/backend`), and run `npm ci` in each frontend you work on.

## Commits and pull requests

- Branch from `main`. `main` is protected; every change goes through a pull
  request on GitHub. Open it as a draft; CI starts when it is marked ready
  for review. The required checks are `lint` and `tests`.
- One logical change per commit, in
  [Conventional Commits](https://www.conventionalcommits.org/) form with the
  area as scope (`fix(manage): ...`, `feat(club-app): ...`). The
  `conventional-pre-commit` hook checks this.
- Branch names: prefix + kebab-case, for example `feat/member-export` or
  `fix/auth-token-refresh`.
- Fill in the [pull request template](.github/pull_request_template.md). For
  a change you can see, commit screenshots under `docs/screenshots/<topic>/`
  and embed them in the pull request.
- Anything a user or operator would notice gets an entry under
  `## [Unreleased]` in `app/backend/CHANGELOG.md` **and** the same entry in
  German in `app/backend/CHANGELOG.de.md`.
- Update the page in `docs/` that describes what you changed.

Releases start with a `v*` tag push; see [docs/releases.md](docs/releases.md)
and [docs/release-guidelines.md](docs/release-guidelines.md). After a plugin
release, or when a plugin is added, follow
[docs/plugin-releases.md](docs/plugin-releases.md) so the plugin lists stay
current.

## Rules

- Never commit `.env` or any file with secrets.
- Ask before changing `docker-compose*.yml`.
- **Migrations** live in `app/backend/migrations/`. Generate them with
  `flask db migrate`, never by hand: hand-written migrations cause
  PostgreSQL/SQLite differences (boolean defaults, casts, idempotency) that
  only show up in production. If `flask db migrate` cannot produce one, ask
  before writing it by hand. Check that there is one head after merging
  `main`.
- **Plugins never depend on other plugins.** Shared data goes through the
  core API or hooks and events. A plugin may extend a core module, and an
  add-on names its parent with `requires:`/`depends:` (see
  [docs/plugins.md](docs/plugins.md)), but never imports another plugin's
  code.
- Configuration and credentials belong in platform settings (manage) rather
  than new environment variables, unless the value is needed before the
  database is reachable.
- Clubs never create or change accounts; members join by invite link.
- Translations are managed on the platform; clubs can only suggest changes.

## Code style

**Python:** PEP 8 via `ruff`; `snake_case` for functions, variables and
files, `PascalCase` for classes; type-annotate function signatures.

**TypeScript:** ESLint and Prettier as configured; `camelCase` for variables
and functions, `PascalCase` for components and types. Component files are
`PascalCase.tsx`, utilities `camelCase.ts`. The UI is Mantine: use Mantine
components and the shared `@hubra/ui` components and colour tokens, and
follow [docs/design-spec.md](docs/design-spec.md).

## Frontend practices

These apply to every frontend.

**Server state.** TanStack Query owns it. Use `useQuery` for reads and
`useMutation` for writes; don't hand-roll `fetch` + `useState` + `useEffect`.

**Effects.** Pass an `AbortSignal` to API calls in effects and abort in the
cleanup. Never disable StrictMode or `react-hooks/exhaustive-deps`; a
legitimate run-once effect gets an `eslint-disable-next-line` with a reason.
Don't call `setState` to derive state from query data; compute it during
render.

**Auth and HTTP.** Use `apiFetch` (or `apiFetchRaw` for downloads) from `@hubra/api-client`,
never raw `fetch()` in screens: it handles the single 401 → refresh → retry
path and the CSRF header. Auth tokens stay in HttpOnly cookies; only
non-sensitive preferences go in `localStorage`. Query retries skip 401 and
403.

**Context.** Memoise provider values. Keep the split contexts and their
narrow hooks; only cross-cutting state belongs in context.

**Forms.** `@mantine/form` with `mantine-form-zod-resolver` and `zod`. Only
`setValues` from query data while the form is not dirty.

**Routing.** Gate with the route guards (`RequireAuth`, `RequirePermission`,
`RequireModule`), and gate protected queries on the auth status. Split
routes with `lazy()` inside an error boundary keyed on the path. No
`window.location` changes during render.

**Dates, numbers, text.** Use `Intl` with the `de-CH` locale through the
helpers in `app/frontend/src/format.ts`; never `toLocaleDateString()` without
a locale. Every user-facing string goes through i18n (`useT()`), in German
and English.

**Types.** No `as any`, `as unknown as`, `@ts-ignore` or
`@ts-expect-error`; fix the type. Type every API response.

**Rendering.** Memoise objects and callbacks passed to memoised children,
use stable keys (never the array index for lists that can reorder), and
don't sync derived state through an effect.

## Security practices

- Frontend permission checks are UX only. Every backend route enforces its
  own access with `@login_required` and `@permission_required(...)`.
- Every POST, PUT, PATCH and DELETE carries `X-CSRF-TOKEN`
  (double-submit cookie), and the backend checks it.
- Anything under `VITE_` ends up in the bundle: only public config (URLs).
  Production source maps stay off.
- Validate redirect targets against an allowlist, as `validateRedirect()` in
  `app/sso-frontend/src/redirect.ts` does. Never redirect to an arbitrary URL.
- No `dangerouslySetInnerHTML`; if HTML is unavoidable, sanitise it with
  DOMPurify.
- Validate every request body with a schema (Marshmallow). Use the ORM or
  bound parameters, never string-built SQL.
- Secrets come from the environment or encrypted platform settings, never
  from code, and are never logged.
- Return JSON error envelopes; never leak stack traces. Rate-limit the auth
  endpoints.
- Every new endpoint gets at least a happy-path test and an auth-failure
  test.
