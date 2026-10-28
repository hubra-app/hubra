# Frontend React Best-Practice Review

Review date: 2026-07-10
Scope: `app/frontend/` (main COS app), `app/admin-frontend/` (admin portal), `app/sso-frontend/` (SSO/identity portal)
Stack: React 19 + TypeScript + Vite + TanStack Query v5 + React Router 7 + Mantine 7 + @mantine/form + zod + i18next (main frontend only)

This review supersedes the previous `app/frontend/FRONTEND-REVIEW.md` (2026-07-09), which covered only the main frontend. Several findings from that review have been fixed and are noted in "What's already good" below.

---

## Critical

### C1. `exhaustive-deps` rule disabled in admin-frontend and sso-frontend
Files: `app/admin-frontend/eslint.config.js:27`, `app/sso-frontend/eslint.config.js:27`

Problem: Both satellite apps explicitly set `'react-hooks/exhaustive-deps': 'off'`. The main frontend correctly uses `reactHooks.configs.flat.recommended` (`app/frontend/eslint.config.js:15`) which enables the rule. With it off, every effect-dependency bug — missing deps, stale closures, request loops — goes completely undetected by lint. This is the single most impactful tooling gap: the rule that mechanically prevents most of the findings in this review is disabled in two of the three apps.

Fix: Replace the manual rule config with the recommended preset, matching the main frontend:
```js
// admin-frontend/eslint.config.js and sso-frontend/eslint.config.js
extends: [
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs.flat.recommended,  // add this
],
rules: {
  'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
  // remove: 'react-hooks/exhaustive-deps': 'off',
},
```

### C2. Context provider values not memoized in admin-frontend and sso-frontend
Files: `app/admin-frontend/src/context/AdminContext.tsx:101-108`, `app/sso-frontend/src/context/SsoContext.tsx:149-156`

Problem: Both providers create a fresh `value` object on every render:
```tsx
// AdminContext.tsx:101
const value: AdminAppState = { authStatus, isSuperadmin, ... }
return <AdminContext.Provider value={value}>{children}</AdminContext.Provider>
```
No `useMemo`. Every state change in the provider (`authStatus`, `permData`) creates a new object reference, re-rendering **all** consumers — even those that only read `notify` or `logout` (both stable via `useCallback`). The main frontend solved this with `useMemo` + split contexts (`AppContext.tsx:492-582`); these apps didn't.

Fix: Wrap the value in `useMemo`:
```tsx
const value = useMemo<AdminAppState>(
  () => ({ authStatus, isSuperadmin, permissions, impersonation, notify, logout }),
  [authStatus, isSuperadmin, permissions, impersonation, notify, logout],
)
```

### C3. Triple-duplicated `apiFetch` / `client.ts` across all three frontends
Files: `app/frontend/src/api/client.ts:55-93`, `app/admin-frontend/src/api/client.ts:45-83`, `app/sso-frontend/src/api/client.ts:49-87`

Problem: The same ~90-line `apiFetch` function, `refreshAccess` singleton, `getCookie`, `hasTokens`, and `setAuthFailureHandler` are copy-pasted across all three apps with only cosmetic differences (semicolons, `clearTokens` no-op present in 2 of 3). The 401→refresh→retry-once logic is the app's most security-critical path, and a bug fix (e.g. to the refresh race or CSRF handling) must be applied manually in 3 places. This is a maintenance hazard that has already drifted: `frontend/src/api/client.ts` has a `clearTokens` export; `admin-frontend` doesn't; `sso-frontend` does.

Fix: Extract a shared package or module:
```
packages/
  api-client/
    client.ts    # apiFetch, refreshAccess, getCookie, hasTokens, setAuthFailureHandler
    index.ts     # public exports
```
Each app imports from `@hubra/api-client`. This is a low-risk refactor since the code is functionally identical — the main work is import path updates.

---

## Important

### I1. `AdminContext` effect fires `getMyPermissions` without AbortController — StrictMode double-fires
File: `app/admin-frontend/src/context/AdminContext.tsx:41-71`

Problem: The mount effect calls `getMyPermissions()` with no `signal` argument, even though the function accepts one (`api/auth.ts:17-21`). The cleanup sets `cancelled = true` but cannot abort the in-flight fetch. Under React 19 StrictMode (`main.tsx:28`), the effect runs twice on every dev mount, firing two `/account/permissions` requests. These concurrent calls race `apiFetch`'s 401→refresh logic, contributing to the 401-storm pattern.

Fix: Thread `AbortController` through:
```tsx
useEffect(() => {
  if (!hasTokens()) { redirectToSso(); return }
  const ctrl = new AbortController()
  let cancelled = false
  getMyPermissions(ctrl.signal)
    .then((data) => { if (!cancelled) { /* ... */ } })
    .catch(() => { if (!cancelled) { /* ... */ } })
  return () => { cancelled = true; ctrl.abort() }
}, [])
```

### I2. `SsoContext` reads `window.location.search` during render — not reactive
File: `app/sso-frontend/src/context/SsoContext.tsx:60-63`

Problem: `const params = new URLSearchParams(window.location.search)` runs in the component body, not in `useMemo` or an effect. If the URL changes via client-side navigation, `redirectTarget` and `errorParam` won't update — they're frozen at initial mount. This is a render-phase read of a mutable global.

Fix: Wrap in `useMemo` (or `useState` initializer if truly only needed once):
```tsx
const { redirectTarget, errorParam } = useMemo(() => {
  const params = new URLSearchParams(window.location.search)
  return {
    redirectTarget: validateRedirect(params.get('redirect')),
    errorParam: params.get('error'),
  }
}, [])
```

### I3. `RequireAuth` in admin-frontend fires `window.location.assign` during render
File: `app/admin-frontend/src/App.tsx:20-23, 34-39`

Problem: `RequireAuth` calls `window.location.assign(...)` directly in the render body when `authStatus === 'anon'`:
```tsx
function RequireAuth({ children }) {
  const { authStatus, isSuperadmin } = useAdmin()
  if (authStatus === 'anon' || !isSuperadmin) {
    window.location.assign(`${SSO_URL}/login?redirect=...`)  // side-effect in render!
    return <Center h="100vh"><Loader /></Center>
  }
  return <>{children}</>
}
```
React 19 StrictMode renders components twice in dev, so this fires the redirect twice. `SsoLoginRedirect` (line 34) has the same issue. Render-phase side-effects are a React anti-pattern.

Fix: Move the redirect to a `useEffect`:
```tsx
function RequireAuth({ children }) {
  const { authStatus, isSuperadmin } = useAdmin()
  useEffect(() => {
    if (authStatus === 'anon' || !isSuperadmin) {
      window.location.assign(`${SSO_URL}/login?redirect=${encodeURIComponent(window.location.href)}`)
    }
  }, [authStatus, isSuperadmin])
  if (authStatus === 'loading' || authStatus === 'anon' || !isSuperadmin)
    return <Center h="100vh"><Loader /></Center>
  return <>{children}</>
}
```

### I4. No error boundary in admin-frontend or sso-frontend
Files: `app/admin-frontend/src/App.tsx` (no boundary), `app/sso-frontend/src/App.tsx` (no boundary)

Problem: Neither app has `react-error-boundary` in its dependencies (`package.json` confirms — only the main frontend has it). A render error or failed lazy-load in any screen takes down the whole app with no recovery UI. The main frontend correctly wraps lazy routes in `RouteErrorBoundary` with `resetKeys` (`App.tsx:204-223`).

Fix: Add `react-error-boundary` to both apps' `package.json`, and wrap routes:
```tsx
import { ErrorBoundary } from 'react-error-boundary'

<RouteErrorBoundary resetKeys={[location.pathname]} onReset={() => window.location.reload()}>
  <Suspense fallback={<Center h="100vh"><Loader /></Center>}>
    <Routes>...</Routes>
  </Suspense>
</RouteErrorBoundary>
```

### I5. Manual form state in satellite apps — no form library or schema validation
Files: `app/admin-frontend/src/screens/CreateTenantModal.tsx:31-38` (7 useState fields), `app/sso-frontend/src/screens/Login.tsx:28-33` (6 useState fields)

Problem: Both satellite apps manage forms with per-field `useState` and ad-hoc validation (`if (!name || !slug) { setError('...') }`). No schema, no type-safe validation, no dirty/pristine tracking. The main frontend uses `@mantine/form` + `zodResolver` consistently (e.g. `MemberEditModal.tsx:61-76`, `AccountSettingsProfileTab.tsx:30-38`).

Fix: Add `@mantine/form`, `zod`, and `mantine-form-zod-resolver` to both apps. Convert forms:
```tsx
const form = useForm({
  validate: zodResolver(z.object({
    name: z.string().min(1, 'Name is required'),
    slug: z.string().min(3).max(64),
  })),
  initialValues: { name: '', slug: '' },
})
```

### I6. Raw `fetch()` calls bypass `apiFetch` for downloads/exports — no 401 refresh
Files: `app/frontend/src/api/events.ts:206`, `app/frontend/src/api/finance.ts:403`, `app/frontend/src/api/members.ts:321,352`, `app/frontend/src/api/i18n.ts:66,100`

Problem: Six `fetch()` calls bypass the central `apiFetch` wrapper. They manually set `credentials: 'include'` and `X-CSRF-TOKEN` but skip the 401→refresh→retry logic. If the access token expires during a download, the request fails silently instead of refreshing. Example:
```ts
// events.ts:206
const res = await fetch(`${BASE}/events/calendar`, {
  credentials: "include",
  headers: { "X-CSRF-TOKEN": getCookie("csrf_access_token") },
});
if (!res.ok) throw new Error(`Calendar export failed: HTTP ${res.status}`);
```

Fix: Add an `apiFetchBlob()` helper to `client.ts` that uses the same auth/refresh logic but returns `Blob`:
```ts
export async function apiFetchBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  // same makeReq + 401-refresh logic as apiFetch, but:
  // - don't set Content-Type: application/json (let fetch infer for FormData)
  // - return res.blob() instead of res.json()
}
```
Then replace all 6 raw `fetch()` calls with `apiFetchBlob()`.

### I7. `RolesTab.tsx` casts JSX labels to `string` via `as unknown as string`
File: `app/frontend/src/screens/private/system/RolesTab.tsx:907,916`

Problem:
```tsx
{
  value: 'permission',
  label: (<Group gap={4}><IconList size={14} />By permission</Group>) as unknown as string,
},
```
This hides a real type error — Mantine's `SegmentedControl` `data` prop expects `{ value: string; label: string }` but JSX is being passed. The double cast (`as unknown as string`) defeats TypeScript's safety.

Fix: Mantine v7 `SegmentedControl` supports `ReactNode` labels. Check the `SegmentedControlItem` type — if `label` is `ReactNode`, remove the cast. If it's strictly `string`, use the `children`/`label` render prop pattern or move to a different control.

### I8. `formatRelative` is hand-rolled — should use `Intl.RelativeTimeFormat`
File: `app/frontend/src/format.ts:50-63`

Problem: Manual string concatenation for relative times (`"just now"`, `"5 min ago"`, `"3h ago"`, etc.) is locale-unaware and won't translate. The rest of `format.ts` correctly uses `Intl.NumberFormat`/`Intl.DateTimeFormat` with `"de-CH"`.

Fix: Replace with `Intl.RelativeTimeFormat`:
```ts
const rtf = new Intl.RelativeTimeFormat("de-CH", { style: "short" });
export function formatRelative(iso: string | Date): string {
  const diff = new Date(iso).getTime() - Date.now();
  const sec = Math.round(diff / 1000);
  const min = Math.round(sec / 60);
  const hr = Math.round(min / 60);
  const day = Math.round(hr / 24);
  if (Math.abs(sec) < 60) return rtf.format(Math.round(sec), "second");
  if (Math.abs(min) < 60) return rtf.format(min, "minute");
  if (Math.abs(hr) < 24) return rtf.format(hr, "hour");
  if (Math.abs(day) < 30) return rtf.format(day, "day");
  const mo = Math.round(day / 30);
  if (Math.abs(mo) < 12) return rtf.format(mo, "month");
  return rtf.format(Math.round(mo / 12), "year");
}
```

---

## Minor

### M1. No i18n in admin-frontend and sso-frontend — all strings hardcoded English
Files: All screens in `app/admin-frontend/src/screens/` and `app/sso-frontend/src/screens/`

Problem: The main frontend has full `react-i18next` setup (`src/locales/i18n.ts`) with `de-CH`/`en-GB` translations. The two satellite apps have no i18n dependency and all user-facing strings are hardcoded English (e.g. `"Welcome back"`, `"Create Tenant"`, `"Loading tenants..."`). If a second language or string consistency will ever matter, these need i18n too.

Fix: Add `i18next` + `react-i18next` to both apps, or accept that these are admin-only tools that stay English-only and document that decision.

### M2. Dates in admin-frontend use `toLocaleDateString()` without explicit locale
Files: `app/admin-frontend/src/screens/TenantsTab.tsx:161`, `app/admin-frontend/src/screens/TenantDetail.tsx:170,174,180`, `app/admin-frontend/src/screens/GlobalAuditTab.tsx:69`

Problem: `new Date(t.created_at).toLocaleDateString()` uses the browser's default locale, which varies by user settings. The main frontend uses `Intl.DateTimeFormat("de-CH", {...})` consistently (`format.ts:11-28`). This is inconsistent and can produce confusing date formats for Swiss users.

Fix: Add a `format.ts` to admin-frontend (or import from shared) and use explicit `de-CH` formatting.

### M3. `sso-frontend` `VerifyEmail` has no AbortController — StrictMode double-fires single-use token
File: `app/sso-frontend/src/screens/VerifyEmail.tsx:21-37`

Problem: The `cancelled` flag suppresses `setState` but doesn't abort the fetch. Under StrictMode, `verifyEmail(token)` fires twice — the second call hits an already-consumed token and can flash an error state.

Fix: Add `AbortController` or convert to `useQuery({ enabled: !!token })`.

### M4. `stopImpersonation` duplicates redirect code in `.then()` and `.catch()`
File: `app/frontend/src/context/AppContext.tsx:478-488`

Problem: Both branches do the exact same `window.location.href` assignment:
```tsx
apiFetch('/system/impersonation/stop', { method: 'POST' })
  .then(() => { window.location.href = `${adminUrl}/tenants` })
  .catch(() => { window.location.href = `${adminUrl}/tenants` })
```

Fix: Use `.finally()`:
```tsx
apiFetch('/system/impersonation/stop', { method: 'POST' })
  .finally(() => { window.location.href = `${adminUrl}/tenants` })
```

### M5. `admin-frontend` uses raw `<button>` for filter chips instead of Mantine components
File: `app/admin-frontend/src/screens/TenantsTab.tsx:71-81, 84-95`

Problem: `<button className="chip">` is a hand-styled element, inconsistent with the Mantine design system used everywhere else. Missing keyboard/focus handling that Mantine `Button`/`UnstyledButton`/`Chip` provide.

Fix: Use Mantine `Chip` or `UnstyledButton` with Mantine styling.

### M6. `SsoContext` `setAuthFailureHandler` effect has no dependency on `navigate`
File: `app/sso-frontend/src/context/SsoContext.tsx:130-136`

Problem: The effect doesn't call `navigate` (it just resets state), but the eslint-disable is on the session-check effect (`:127`), not this one. This effect is actually fine — but the session check effect at `:77-128` suppresses `exhaustive-deps` for `navigate` and `redirectTarget`, which could mask future bugs if those values become non-stable.

---

## What's already good (keep)

**Main frontend (`app/frontend/`):**
- **TanStack Query** owns server state everywhere; no broad hand-rolled `fetch + useState + useEffect` triads (the previous `PostDetailScreen.tsx` triad has been fixed — now uses `useQuery`).
- **Central `apiFetch`** with a single 401→refresh→retry-once path and one `setAuthFailureHandler` interceptor (`client.ts:30-32,72-79`) — no scattered 401 handling.
- **QueryClient retry skips 401/403** (`main.tsx:18-22`) — auth failures are never blindly retried.
- **Protected queries are gated**: `RequireAuth` blocks rendering until `authStatus !== 'loading'` (`App.tsx:132-141`); root queries use `enabled: queryEnabled` (`AppContext.tsx:210,218,223,…`).
- **StrictMode is on** (`main.tsx:30`) — correct; fixes add cleanup/abort rather than disabling it.
- **Auth tokens in httpOnly cookies**; only the language preference is in `localStorage` (`i18n.ts:21,104`). No secrets in the bundle.
- **No `dangerouslySetInnerHTML`, no `any`, no `@ts-ignore`/`@ts-expect-error`** across `src/` (only 2 `as unknown as` casts in `RolesTab.tsx` — see I7).
- **Forms use `@mantine/form` + `zodResolver`** consistently.
- **Feature-based folder structure** under `screens/private/{members,finances,operations,system,settings,mail,account,dashboard}`.
- **Split contexts** (`ToastContext`/`AuthContext`/`NavContext`/`DataContext`) with narrow hooks (`useAuth`, `useNav`, etc.) — the `useApp()` collapse issue from the previous review has been largely addressed (only 4 remaining call sites in `App.tsx` for guard components).
- **`RouteErrorBoundary`** wraps lazy/Suspense routes with `resetKeys` (`App.tsx:204-223`).
- **`AbortController`** used for the bootstrap/session chain (`AppContext.tsx:138-191`) and the health poll (`AppContext.tsx:356-378`) — the previous review's C2 finding has been fixed.
- **`i18n` `escapeValue: true`** (`i18n.ts:27`) — the previous review's M4 finding has been fixed.
- **`format.ts`** uses `Intl.NumberFormat`/`Intl.DateTimeFormat` with `"de-CH"` for CHF and dates.
- **Source maps disabled** in production (`vite.config.ts:25` — `sourcemap: false`).
- **`@` path alias** configured in both `vite.config.ts` and `tsconfig.app.json`.

**All three apps:**
- StrictMode enabled.
- QueryClient retry skips 401/403.
- No `dangerouslySetInnerHTML`.
- No secrets in bundle (only `VITE_API_BASE`, `VITE_SSO_URL`, `VITE_ADMIN_PORTAL_URL` — all public URLs).
- `credentials: 'include'` on all requests.
- CSRF token header on all mutating requests.

---

## Top 5 to fix first (ordered by impact-to-effort)

1. **C1 — Re-enable `exhaustive-deps` in admin-frontend and sso-frontend.** One-line change per app, highest mechanical prevention value. Without it, every other effect fix can regress silently.

2. **C2 — Memoize context values in `AdminContext` and `SsoContext`.** Wrap the value object in `useMemo`. Low effort, immediately stops unnecessary re-renders of all consumers.

3. **I1 — Add `AbortController` to `AdminContext` mount effect.** Thread `signal` into `getMyPermissions()`. Prevents StrictMode double-fire of `/account/permissions` and reduces 401-storm risk.

4. **I3 — Move `window.location.assign` out of render in admin-frontend `RequireAuth`.** Move to `useEffect`. Fixes StrictMode double-redirect and the render-phase side-effect anti-pattern.

5. **C3 — Extract shared `api-client` package.** Eliminate the triple-duplicated `client.ts`. Higher effort but pays off on every future auth/CSRF bug fix — apply once, not three times.
