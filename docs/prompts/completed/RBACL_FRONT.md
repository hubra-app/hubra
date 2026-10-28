Addition to the RBAC implementation plan: define and implement a consistent, structured "permission denied" response for every protected endpoint, and handle it uniformly in the frontend.

## Backend — consistent denial response

1. When a request reaches an endpoint but the authenticated user's role(s) don't include the required permission, return HTTP 403 (not 401 — 401 means "not authenticated at all", 403 means "authenticated, but not allowed to do this") with a consistent JSON error shape across the ENTIRE API, not ad-hoc per blueprint:

```json
{
  "error": "permission_denied",
  "message": "You don't have permission to perform this action.",
  "required_permission": "finance.transaction_categories.create"
}
```

1. This should be enforced centrally — in the same permission-checking decorator/mechanism from the RBAC design, not duplicated per route. Confirm there's a single choke point (the new @permission_required decorator) that all 18 blueprints route through, so this response format is automatically consistent everywhere rather than something each blueprint author has to remember to implement correctly.

2. Decide and confirm: should `required_permission` be included in the response at all? Pro: helps frontend/debugging show specifically what's missing. Con: minor information disclosure — an unauthenticated-feeling user now knows the exact internal permission key gating a feature, which is low-risk information but worth a conscious decision rather than an accident. Default recommendation: include it, since these are authenticated users (not anonymous attackers) being denied access to one specific endpoint they can already see exists in the UI — the permission key itself isn't sensitive. Confirm this is acceptable.

3. Also handle the "fail-closed" case from the earlier design: if an endpoint is hit that the permission-sync system doesn't recognize at all (a route exists but somehow has no registered Permission row — shouldn't happen if Step 3 sync runs correctly, but defend against it), return the SAME 403 permission_denied shape rather than a 500 error or silently allowing access. Log this case at WARNING level server-side since it indicates a sync/registration bug worth investigating, but the user-facing response stays a clean 403.

4. Apply this consistently to JWT/auth failures too for comparison — confirm 401 (not authenticated / invalid or expired token) uses a similarly structured, distinguishable response shape:

```json
{
  "error": "unauthorized",
  "message": "Please log in to continue."
}
```

so the frontend can reliably distinguish "you're not logged in" (401, should redirect to login) from "you're logged in but can't do this" (403, should show an in-place message, not redirect to login) — these need different frontend handling and must be distinguishable by status code + error field, not by parsing message text.

## Frontend — centralized handling

1. Find the existing API client/fetch wrapper (likely a single shared module given the codebase's mature structure):
   grep -rln "fetch(\|axios" app/frontend/src/api/ 2>/dev/null | head -5

2. Add centralized response interceptor/handling for both 401 and 403 in this ONE shared location, not per-component:
   - **401 unauthorized** → clear any local auth state, redirect to /login (preserving the originally-attempted URL as a redirect-back target after successful login, if that pattern already exists in the app)
   - **403 permission_denied** → do NOT redirect. Instead, surface an inline, non-disruptive message at the point of the denied action (e.g. a toast/snackbar saying the message field from the response, or disable/hide the triggering UI element going forward) and the calling component should be able to catch this distinctly from other errors (e.g. a typed error class like `PermissionDeniedError` that components can check for, separate from generic network/server errors)

3. Proactive UI hiding vs reactive denial handling — discuss with me which approach to take, since they're complementary but distinct:
   (a) **Reactive only**: UI shows all actions/buttons regardless of permission, and only on actually attempting the action does a 403 come back and get handled per above. Simpler to build, but bad UX (showing a "Delete" button a user will just get denied on click).
   (b) **Proactive**: frontend has access to the current user's resolved permission set (e.g. returned at login or via a /me endpoint) and conditionally renders/disables UI elements (hide the "Delete" button entirely if the user lacks that permission) BEFORE any request is attempted, with the 403 handling from above as a defensive fallback in case of stale client-side permission data (e.g. an admin revokes a permission mid-session) rather than the primary mechanism.

   Recommend (b) as the real UX goal, with (a)'s centralized 403 handling kept as the safety net for the race-condition case. This requires the login/session response (or a dedicated /api/v1/me endpoint) to include the current user's resolved flat list of granted permission keys, which the frontend stores in its auth/session state and checks against before rendering gated UI. Confirm whether this endpoint/data already exists or needs to be added as part of this work.

4. Build a small reusable frontend helper/hook (e.g. `usePermission("finance.transaction_categories.create")` returning a boolean) that components use to conditionally render gated buttons/sections, backed by the permission list from Step 3, so this pattern is consistent and reusable across all pages rather than each page independently checking some ad-hoc condition.

## Verify

1. Test the full flow: a member without a given permission should never even SEE the gated button/action (proactive hiding), and as a defensive check, manually crafting a request to that endpoint anyway (e.g. via browser devtools or curl) should still correctly return 403 permission_denied server-side rather than succeeding — confirm the backend never trusts the frontend's hiding as the actual security boundary, since UI hiding is a UX nicety, not a security control.
2. Test the 401 case separately: an expired/invalid token should redirect to login, not show a permission-denied message.
3. Test the stale-permission race case if feasible: revoke a permission from a role while a member with that role has an active session, confirm their next attempt at the now-revoked action gets the reactive 403 handling correctly even though the proactive UI hadn't yet refreshed to hide it.

Confirm the proactive-vs-reactive approach (recommendation: both, proactive primary + reactive safety net) and whether a /me-style endpoint returning resolved permissions already exists, before implementing.
