# Frontend

## Stack

- **React 19** with hooks and functional components (StrictMode enabled)
- **TypeScript 6** strict mode
- **Vite 8** for dev server and build
- **Mantine 7** (`@mantine/core`, `@mantine/hooks`, `@mantine/form`,
  `@mantine/notifications`, `@mantine/tiptap`) — component library, theming,
  forms, notifications. PostCSS uses `postcss-preset-mantine`.
- **TanStack Query 5** (`@tanstack/react-query`) — server state, cache,
  dedup, automatic refetch. Used in `AppContext` and progressively in screens.
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
├── screens/        # Route-level page components
├── locales/        # i18n (translation loading + useT hook)
├── types/          # TypeScript interfaces matching API responses
├── App.tsx         # Root component + router
├── AppContext.tsx  # Global context (TanStack Query, auth, nav)
├── Shell.tsx       # App shell with sidebar, header, content area
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
to `https://api.vollbuild.ch/api/v1/...` in production or
`http://localhost:5000/api/v1/...` in local dev.

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
`VITE_API_BASE=https://api.vollbuild.ch/api` is set via
`docker-compose.override.yaml` and Traefik routes `api.vollbuild.ch` directly
to the backend container.

## E2E tests

Playwright tests live in `app/frontend/e2e/`. They require a running app
stack:

```bash
docker compose up -d       # Start the app
cd app/frontend
npx playwright test        # Run E2E tests
```

## Known issues

See [frontend_issues.md](frontend_issues.md) for a snapshot of the React
best-practice review (some items have been addressed since).
