# Frontend React Best-Practice Review — Pass 2

> **Snapshot** — this is a point-in-time review. Several items have been
> addressed since it was written (C3 StrictMode is now enabled, I2 empty
> `src/hooks/` is deleted, M5 `sourcemap: false` is explicit). Verify against
> source before acting on any item below.

## Critical

### C1. 20+ screens still use manual `useEffect` + `useState` + `fetch` — no React Query at screen level
**Files:** `Members.tsx:70-81,131-142`, `Invoices.tsx:52-60`, `Groups.tsx:56-61,384-393`, `Codes.tsx:33-38`, `Tiers.tsx:46-51`, `Functions.tsx:60-63`, `Applications.tsx:26-36`, `AccountSettings.tsx:79-120`, `Account.tsx:31-37`, `DashboardGlobalTab.tsx:24-28`, `Finances.tsx:19-26`, `Transactions.tsx:51-60`, `TransactionCategories.tsx:28-33`, `InvoiceDetail.tsx:23-29`, `MemberDetail.tsx:56-63`, `Inventory.tsx:135-147`, `AuditLog.tsx:22`, `System.tsx:54`, `HealthTab.tsx:37`, `RolesTab.tsx:95`, `KVSettingsTab.tsx:59`, `MailSettingsTab.tsx:15`, `Bindings.tsx:128`, `Translations.tsx:118-156`

**Problem:** Only `AppContext` was migrated to TanStack Query. Every screen still fetches via `useEffect(() => { api().then(setState).catch(console.warn) }, [])`. No dedup, no cache, no retry, no automatic refetch, no abort on unmount. Under React 19 StrictMode double-invoke (which is NOT enabled — see C3), every fetch fires twice in dev.

**Fix:** Convert each screen to `useQuery`. Example for `Codes.tsx`:
```tsx
const { data: codes = [], isLoading } = useQuery({
  queryKey: ['codes'],
  queryFn: listCodes,
})
```
This is incremental — each screen is a separate PR. Mutations should use `useMutation` with `queryClient.invalidateQueries`.

---

### C2. Zero `AbortController` — every fetch can `setState` after unmount
**Files:** All 20+ screen files listed in C1, plus `Shell.tsx:1078-1217` (search)

**Problem:** No file in `src/` uses `AbortController` or passes `signal` to `fetch`. When a user navigates away mid-fetch (e.g., Members list loading, user clicks Groups), the pending promise resolves and calls `setMembers` on an unmounted component. This can silently overwrite fresh state if the user navigates back and a newer fetch is in-flight.

**Fix:** TanStack Query auto-cancels on unmount (if queryFn respects `signal`). For remaining manual fetches, pass `AbortController.signal`:
```tsx
useEffect(() => {
  const ac = new AbortController()
  apiCall({ signal: ac.signal }).then(setState)
  return () => ac.abort()
}, [deps])
```
Best fix: adopt React Query per C1.

---

### C3. No `StrictMode` — hides double-mount bugs in development
**File:** `main.tsx:22-27`

**Problem:** The app is NOT wrapped in `<StrictMode>`. React 19 StrictMode double-mounts components in dev to surface effect cleanup bugs. The manual `useEffect` fetch patterns in C1 appear to work fine but will double-fire all API requests when StrictMode is enabled. This was likely a contributor to the 401-storm issue during development.

**Fix:** Wrap app in `<StrictMode>` AND fix the fetch patterns (C1+C2) so they're idempotent:
```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
```
Do NOT add StrictMode without fixing C1/C2 — that would double every request in dev.

---

### C4. Shell search fires 5 full-list API calls per debounced keystroke
**File:** `Shell.tsx:1078-1217`

**Problem:** `runSearch` calls `Promise.all([listMembers({pageSize:200}), listGroups(), listTransactions(), listInventory(), listAuditLog({pageSize:200})])` on every 200ms-debounced search query. These are full list fetches — filtering is done client-side after the fetch. `events`, `polls`, and `invoices` are filtered from AppContext cache (good), but the other 5 endpoints are raw fetches that re-download the entire dataset on every keystroke.

**Fix:** Cache these 5 lists in React Query (or read from the same cache AppContext populates). Then `runSearch` only filters from cached data — no refetch on keystroke:
```tsx
const { data: allMembers } = useQuery({ queryKey: ['members-search'], queryFn: () => listMembers({pageSize: 200}), enabled: queryEnabled })
const { data: allGroups } = useQuery({ queryKey: ['groups'], queryFn: listGroups, enabled: queryEnabled })
// ... etc, then filter from cached data in runSearch
```

---

### C5. `setPendingApplicationCount` and `setGroupCount` corrupt cache data
**File:** `AppContext.tsx:314-340`

**Problem:** These setters manipulate the React Query cache in a way that destroys data integrity. `setPendingApplicationCount((prev) => prev - 1)` calls `queryClient.setQueryData(['applications'], (prev) => prev.slice(0, newCount))` — it **truncates the applications array** to the new count, silently deleting real application objects. Similarly, `setGroupCount` truncates the groups array. When `Applications.tsx:53` calls `setPendingApplicationCount((prev) => prev - 1)` after approving an application, the `['applications']` cache loses its last N items — not necessarily the approved one. Then `pendingApplicationCount` is derived as `applicationsData?.length ?? 0` (line 246), which now reads the truncated array. The sidebar count updates correctly but the cached data is garbage.

**Fix:** These count setters should not manipulate the data arrays at all. Either:
1. Use `queryClient.invalidateQueries(['applications'])` to refetch from server after approve/decline/create
2. Or properly remove the specific item from the array (the caller already does `setApps(prev => prev.filter(...))` locally — that state should be the query cache, not separate `useState`)
```tsx
const setPendingApplicationCount = useCallback(
  (updater: number | ((prev: number) => number)) => {
    // No-op: count is derived from applicationsData.length.
    // Callers should invalidateQueries or setQueryData to remove the specific item.
  },
  [queryClient],
)
```
Better: remove `setPendingApplicationCount` and `setGroupCount` entirely. Callers should `queryClient.invalidateQueries(['applications'])` after mutations.

---

## Important

### I1. AppContext is a 60-field god context — every consumer re-renders on any change
**File:** `AppContext.tsx:42-102` (interface), `689-774` (value useMemo)

**Problem:** The context value has 60+ fields. The `useMemo` deps array (lines 747-773) includes all data fields. When `notifications` changes (every 30s via refetchInterval), every component that calls `useApp()` re-renders — including `Sidebar` (which only needs `memberCount`, `groupCount`, `polls`, `openInvoiceCount`) and `Topbar` (which needs `events`, `polls`, `invoices`).

**Fix:** Split into multiple contexts: `AuthContext` (currentUser, authStatus, permissions, hasPermission), `NavContext` (sidebar, mobile drawer, counts), `DataContext` (events, polls, invoices, notifications), `ToastContext` (toasts, notify). Or adopt `use-context-selector`. Medium-effort refactor.

---

### I2. Empty `src/hooks/` directory is orphaned structure
**File:** `src/hooks/` (empty directory)

**Problem:** `useApi.ts` was deleted in the previous review pass. The `hooks/` directory is now empty.

**Fix:** Delete `src/hooks/`. Low-risk.

---

### I3. No path aliases — deep relative imports throughout
**Files:** Every screen file uses `../../../components/ui`, `../../../locales/i18n`, etc.

**Problem:** `tsconfig.app.json` has no `paths` config, and `vite.config.ts` has no `resolve.alias`. Every import uses 3-4 level relative paths.

**Fix:** Add path alias to `tsconfig.app.json` and `vite.config.ts`:
```jsonc
// tsconfig.app.json
"paths": { "@/*": ["./src/*"] }
```
```ts
// vite.config.ts
import { resolve } from 'path'
resolve: { alias: { '@': resolve(__dirname, 'src') } }
```
Low-risk, mechanical rename.

---

### I4. No `react-hook-form` / `zod` — all forms are manual `useState` per field
**Files:** `AccountSettings.tsx` (20+ useState, lines 40-76), `Members.tsx:45-68`, `Invoices.tsx:31-48`, `Events.tsx:34-39`, `Codes.tsx:24-27`, `Groups.tsx:370-382`, `Tiers.tsx:25-26`, etc.

**Problem:** Every form field is a separate `useState`. Validation is ad-hoc (e.g., `if (!newMemberId || !newAmount || !newDue) return` at `Invoices.tsx:118`). No schema validation, no shared contract with backend.

**Fix:** Adopt `react-hook-form` + `zod`. Start with `AccountSettings` (most complex form, 20+ fields). This is a larger refactor.

---

### I5. 28 `console.warn` in catch blocks — errors silently swallowed
**Files:** 28 instances across 18 screen files

**Problem:** Pattern `.catch((err) => console.warn(err))` appears 28 times. In production, these errors are invisible to the user. No error UI shown.

**Fix:** Replace with user-visible error state or `notify('error', ...)`. If using React Query (C1), `error` from `useQuery` can be rendered with `ErrorBanner`.

---

### I6. No `Intl.DateTimeFormat` / `Intl.NumberFormat` for Swiss locale
**Files:** `AppContext.tsx:605-618` (`toLocaleString('en', ...)`), `DashboardGlobalTab.tsx:11-16` (manual `CHF` formatting), `Finances.tsx` (CHF amounts), `Invoices.tsx:255` (`inv.amount.toFixed(2)`), `DashboardGlobalTab.tsx:31-36` (`toLocaleDateString('en', ...)`)

**Problem:** Dates and currency use `'en'` locale instead of `'de-CH'`. The app serves Swiss users with CHF currency. Manual string formatting for currency (`fmtNet` function, `toFixed(2)`).

**Fix:** Use `Intl.NumberFormat('de-CH', { style: 'currency', currency: 'CHF' })` and `Intl.DateTimeFormat('de-CH', ...)`.

---

### I7. `Transactions.tsx` has both a `loadTransactions` function and a duplicate `useEffect` fetch
**File:** `Transactions.tsx:38-60`

**Problem:** `loadTransactions` (lines 38-49) is defined as a standalone function, then a `useEffect` (lines 51-60) duplicates the same fetch logic instead of calling `loadTransactions`. The effect is the initial load; `loadTransactions` is used for manual retry. But they're duplicated code.

**Fix:** Call `loadTransactions` inside the effect:
```tsx
useEffect(() => {
  loadTransactions()
}, [])
```

---

### I8. `eslint-disable` suppressing `exhaustive-deps` on the main `useMemo`
**File:** `AppContext.tsx:746`

**Problem:** `// eslint-disable-next-line react-hooks/exhaustive-deps` hides that the deps array is incomplete — the `useMemo` value object includes many stable callbacks (setters, `go`, `goInvoice`, etc.) that aren't in the deps array. This works because those callbacks are stable (`useCallback` with stable deps), but the suppression masks any future regressions if a callback becomes unstable.

**Fix:** This is acceptable as-is since all excluded values are stable `useCallback` results. But document why with a comment instead of a blind disable:
```tsx
// Stable callbacks (useCallback) intentionally excluded from deps
```

---

## Minor

### M1. `Table` component uses index as key
**File:** `ui.tsx:979-981`

**Problem:** `data.map((item, i) => <tr key={i}>)` — if data reorders or items insert/delete, React reuses wrong DOM nodes.

**Fix:** Accept a `getRowKey?: (item: T) => string` prop, fall back to index.

---

### M2. 8 instances of `key={i}` (index as key) outside Table
**Files:** `Shell.tsx:1305`, `InvoiceDetail.tsx:193`, `HealthTab.tsx:342`, `System.tsx:268`, `MailSettingsModal.tsx:467`, `Inventory.tsx:485,726`

**Fix:** Use stable keys derived from item content (`item.id`, `item.name`, etc.).

---

### M3. `ConfirmModal` has hardcoded English strings
**File:** `ui.tsx:485,495`

**Problem:** "Cancel" and "Delete" are hardcoded English, not using `useT()`.

**Fix:** Import `useT` and use `t('common.cancel')` / `t('common.delete')`.

---

### M4. `div` with `onClick` for interactive elements — no keyboard/ARIA
**File:** `Shell.tsx:378,391,430`, `ui.tsx:200,1156`

**Problem:** Nav items and collapsible headers are `<div onClick={...}>` without `role`, `tabIndex`, or `onKeyDown`.

**Fix:** Use `<button>` or add `role="button" tabIndex={0} onKeyDown={...}`.

---

### M5. Production source maps not explicitly disabled
**File:** `vite.config.ts:18-20`

**Problem:** `build` config has no explicit `sourcemap: false`. Vite defaults to `false`, but being explicit prevents accidental exposure.

**Fix:** Add `sourcemap: false` to the build config.

---

### M6. `ErrorBoundary` fallback uses Tailwind classes inconsistent with design system
**File:** `ErrorBoundary.tsx:33-53`

**Problem:** The top-level ErrorBoundary fallback uses Tailwind utility classes (`bg-gray-50`, `text-red-700`, `rounded-lg`) while the rest of the app uses the custom CSS design system (`.card`, `.btn`, `.modal-overlay`). The per-route `RouteError` in `App.tsx:193-209` correctly uses the design system classes. Inconsistent.

**Fix:** Replace Tailwind classes with design system classes in the ErrorBoundary fallback.

---

### M7. `i18n.ts` fires `loadAllTranslationsFromApi()` at module import time
**File:** `i18n.ts:74-86`

**Problem:** `loadAllTranslationsFromApi()` is called at the bottom of the module, which runs during `import './locales/i18n'` in `main.tsx`. This fires API requests (`fetchLanguages`, `fetchTranslations`) before auth status is resolved. If the backend returns 401 for these endpoints, it contributes to the 401 storm on page load. The request may be safe if translations are public, but it fires unconditionally regardless of auth state.

**Fix:** Defer `loadAllTranslationsFromApi()` until after auth status is known, or confirm these endpoints are public (no auth required).

---

## Top 5 to Fix First (by impact-to-effort)

Fix all others

1. **C5: Fix `setPendingApplicationCount`/`setGroupCount` cache corruption** — These silently destroy cached data. Either make them no-ops (count is derived from array length) or have callers invalidate queries instead. Effort: 30 min.

2. **I2: Delete empty `src/hooks/` directory** — Dead structure. Effort: 1 min.

3. **M5: Add `sourcemap: false` to vite config** — Explicit security hardening. Effort: 1 min.

4. **C4: Cache Shell search lists in React Query** — Eliminates 5 full-list API calls per keystroke. Effort: 1-2h.

5. **C1+C2+C3: Convert screens to React Query + enable StrictMode** — The largest remaining item. Fixes abort-on-unmount, request dedup, StrictMode readiness, and error handling in one sweep. Start with highest-traffic screens (Members, Invoices, Dashboard). Each screen is a separate PR. Effort: ~1-2h per screen, incremental.

Fix all others
