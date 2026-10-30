# Frontend

## Stack

- **React 19** with hooks and functional components (StrictMode enabled)
- **TypeScript 6** strict mode
- **Vite 8** for dev server and build
- **Mantine 9** (`@mantine/core`, `@mantine/hooks`, `@mantine/form`,
  `@mantine/notifications`, `@mantine/tiptap`) — component library, theming,
  forms, notifications. PostCSS uses `postcss-preset-mantine`. The light
  variant keeps Mantine 8's see-through tints (`cssVariablesResolver` in
  `@hubra/ui`).
- **Tiptap 3** with `tiptap-markdown` for the post editor (stores Markdown)
- **TanStack Query 5** (`@tanstack/react-query`) — server state, cache,
  dedup, automatic refetch. All server data goes through it (see Data layer).
- **zod** + `mantine-form-zod-resolver` — schema-based form validation
- **React Router 7** for client-side routing
- **Playwright** for E2E tests
- Custom CSS design system (`src/index.css`) — no Tailwind

## Project structure

```
app/frontend/src/
├── api/            # API client modules (one per blueprint)
│   ├── client.ts   # Base fetch wrapper (credentials, CSRF, refresh)
│   ├── members.ts
│   ├── groups.ts
│   ├── finance.ts
│   ├── mail.ts
│   └── ...
├── components/     # Shared UI components (Mantine-based)
│   └── Shell/      # App shell with sidebar, header, content area
├── context/        # AppContext: user, club, modules, club switching
├── data/           # Query keys and data hooks (see Data layer)
├── screens/        # Route-level page components
├── locales/        # i18n (translation loading + useT hook)
├── types/          # TypeScript interfaces matching API responses
├── App.tsx         # Root component + router
└── main.tsx        # Entry point (StrictMode)
```

## API client pattern

All API modules in `src/api/` export typed functions that call backend
endpoints. They use the shared `apiFetch` from `client.ts` which automatically:

1. Sends cookies cross-origin (`credentials: "include"`)
2. Attaches the `X-CSRF-TOKEN` header (read from the `csrf_access_token` cookie)
3. Retries once on 401 by calling `/auth/refresh` (using `csrf_refresh_token`)
4. Calls the auth failure handler if refresh also fails

```typescript
import { apiFetch } from "./client";

export function listMembers(
  params?: MemberQueryParams,
): Promise<PaginatedResponse<Member>> {
  const qs = params ? "?" + new URLSearchParams(params as any).toString() : "";
  return apiFetch(`/members${qs}`);
}
```

`apiFetch` prepends `BASE` (from `VITE_API_BASE` env var + `/v1`), so calls go
to `https://api.hubra.club/api/v1/...` in production or
`http://localhost:5000/api/v1/...` in local dev.

## Data layer

Server data lives in the TanStack Query cache, not in React context.
`AppContext` only holds who is signed in, the club and its modules.

- `src/data/keys.ts` has every query key (`qk`). A key's first entry names the
  list, so invalidating `qk.members.all` refreshes every members query. ESLint
  rejects hand-written `queryKey: ['...']`. Plugins invalidate some keys by
  their strings (such as `['invoices']`), so keep the strings stable.
- `src/data/lists.ts` has the hooks for the lists several screens share
  (`useEvents`, `usePolls`, `usePosts`, `useInvoices`, `useDashboardSummary`,
  `useNavCounts`, ...). Each loads only when its module is on and the user may
  see it, and only on the screens that call it. `useListCache(key)` updates a
  cached list after a mutation.
- `src/data/members.ts` has `useMemberSearch`, which searches on the server.
  Use `components/MemberPicker` for any "pick a member" field instead of
  loading every member into a Select.

## Shared package

`packages/ui` (`@hubra/ui`) is shared by the club app, manage and sign-in: the
Mantine theme and brand colours, `createLang` (the `tr(de, en)` language store
manage and sign-in use), and the page blocks `PageHead`, `StatTile`,
`StatGrid`, `Tabs` and `Pagination` with their styles in `ui.css`. Like
`packages/api-client` it is wired in by path alias (`vite.config.ts`,
`tsconfig.app.json`) and copied in each Dockerfile; it takes React and
Mantine from the app's own `node_modules`.

## Plugin host API

Plugin frontends get React, Mantine and the other shared libraries from the
app at run time (`src/plugins/host.ts`). `HOST_API` there is the version of
that hand-over; a plugin built for another version does not load. Raise it
when a library the host hands over changes in a breaking way (it went to 2
with Mantine 9), then rebuild the plugins (`npm run build:plugin`), bump their
versions and set their `hubra:` range to the Hubra version that has the new
host.

## Development

```bash
cd app/frontend
npm install        # Install dependencies
npm run dev        # Dev server with hot-reload on :5173
npm run build      # tsc + vite build (production)
npm run lint       # ESLint check
```

In local dev, `VITE_API_BASE=http://localhost:5000/api` (in
`app/frontend/.env`) points directly at the Flask backend. In production,
`VITE_API_BASE=https://api.hubra.club/api` is set via
`docker-compose.override.yaml` and Traefik routes `api.hubra.club` directly
to the backend container.

## Tests

Component tests (Vitest and Testing Library) sit next to the code as
`*.test.tsx` and run with `npm test`. Playwright tests live in
`app/frontend/e2e/` and run against a real stack: they sign in on the SSO
portal with the account in `e2e/env.ts` (or the `E2E_*` variables) and use the
API as that user. CI runs both: the component tests in the `frontend-tests` job,
the browser tests in `compose-smoke` (release-checks.yml, see docs/ci.md) against the Compose stack.

```bash
cd app/frontend
npm test                   # Component tests
docker compose up -d       # or the dev servers
E2E_APP_URL=http://localhost:8080 E2E_SSO_URL=http://localhost:8082 \
E2E_MANAGE_URL=http://localhost:8081 E2E_CLUB=<club> E2E_EMAIL=<admin> \
E2E_PASSWORD=<password> npm run test:e2e
```

## Known issues

See [frontend_issues.md](frontend_issues.md) for a snapshot of the React
best-practice review (some items have been addressed since).
