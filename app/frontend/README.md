# Hubra — Frontend

React SPA for club management (members, finance, events, polls, mail, and more).

## Stack

- **React 19** + **TypeScript 6** + **Vite 8**
- **Mantine 9** — UI components, forms, notifications
- **TanStack Query 5** — server state, cache, automatic refetch
- **zod** + `mantine-form-zod-resolver` — form validation
- **React Router 7** — client-side routing
- **Playwright** — E2E tests
- The shared theme and components from `@hubra/ui` (`packages/ui`), plus `src/index.css`

## Development

```bash
npm install        # Install dependencies
npm run dev        # Dev server with HMR on :5173
npm run build      # tsc + vite build (type-check + production bundle)
npm run lint       # ESLint
```

## Environment

| Variable         | Dev                          | Production                       |
| ---------------- | ---------------------------- | -------------------------------- |
| `VITE_API_BASE`  | `http://localhost:5000/api`  | `/api`, or `https://api.hubra.club/api` behind Traefik |

In dev, `app/frontend/.env` sets `VITE_API_BASE` to point at the Flask backend
directly. The image gets its `VITE_*` values when the container starts
(`app/deploy/nginx/40-hubra-runtime.sh`); see
[docs/frontend.md](../../docs/frontend.md#development).

## API client

All API calls go through `apiFetch()` from `@hubra/api-client`
(`packages/api-client/src/client.ts`):

- Sends cookies cross-origin (`credentials: "include"`)
- Attaches `X-CSRF-TOKEN` header (from `csrf_access_token` cookie)
- Auto-retries on 401 via `/global/auth/refresh`
- Base URL from `VITE_API_BASE` + `/v1`

See [docs/frontend.md](../../docs/frontend.md) for full architecture details.

## Tests

```bash
npm test                   # Component tests (Vitest, src/**/*.test.tsx)
npm run test:e2e           # Browser tests (Playwright, e2e/) against a running stack
```

The browser tests sign in on the SSO portal and run against the dev servers
by default; `E2E_APP_URL`, `E2E_SSO_URL`, `E2E_MANAGE_URL`, `E2E_CLUB`,
`E2E_EMAIL` and `E2E_PASSWORD` point them elsewhere (see `e2e/env.ts`). CI runs
them against the Compose stack in three parallel workers (`E2E_WORKERS=3`),
each with its own club and account from `scripts/e2e-accounts.sh`.
