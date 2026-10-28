Replace the current single-column device-tracking on the Member model with a proper login-history/session table supporting multiple concurrent and historical devices per member, new-device notification, and a force-logout-all-sessions capability.

## Step 1 — Investigate current state

1. Find the existing device tracking column(s) on Member and how it's currently written/read:
   grep -rn "last_device\|device\|user_agent\|last_login" app/backend/vollbuild/models/member.py app/backend/vollbuild/api/auth/

2. Confirm how sessions/auth currently work end to end — given the earlier JWT cookie migration (HttpOnly, SameSite=Strict, JWT_COOKIE_CSRF_PROTECT) from the security remediation work, check:
   - Are tokens stateless (no server-side session record at all, just a signed JWT with an expiry), or is there already a server-side session/token table?
   - What's the current access token lifetime and is there a refresh token mechanism? (ACCESS_TOKEN_MINUTES appeared as an env var earlier in this conversation — confirm its current value and whether refresh tokens exist)

   This matters a lot: a pure stateless JWT system CANNOT support "force sign out all sessions" without either (a) maintaining a server-side revocation list/table the auth check consults on every request, or (b) a token versioning scheme on the Member row that invalidates all previously-issued tokens when bumped. Report which (if either) currently exists before proposing the design.

## Step 2 — Design

Propose, and confirm with me before implementing, the following:

### New table: device_sessions (or login_sessions — pick a name and justify)

Columns to support multi-device tracking, history, and revocation:

- id
- member_id (FK)
- session_token_id or jti (JWT ID claim — a unique identifier embedded in each issued token, NOT the token itself, so we never store raw tokens/secrets in the DB)
- device_fingerprint or a simpler combination of (user_agent, ip_address) — discuss tradeoffs: a hashed fingerprint is more precise for "is this actually a new device" detection but adds complexity; raw user_agent + IP is simpler and good enough for notification purposes. Recommend the simpler approach unless there's a clear reason for fingerprinting, and confirm with me.
- ip_address
- user_agent (raw string, parsed into friendly display fields if a user-agent parsing library is added — e.g. "Chrome on Windows", "Safari on iPhone" rather than the raw UA string, much better for the member-facing UI)
- created_at (first seen / login time)
- last_active_at (updated on each authenticated request, or on each token refresh — decide granularity, updating on EVERY request may be excessive DB writes; updating on refresh/periodic intervals is more practical — propose and confirm)
- revoked_at (nullable — null means active session, set means manually or automatically revoked)
- revoked_reason (nullable — e.g. "user_logout", "force_logout_all", "admin_action", "expired")

### Token validation flow change

Since you want force-logout-all-sessions to actually work, the auth check needs a server-side component even with JWT. Propose: embed the device_sessions.id (or jti) as a claim in each issued JWT, and on every authenticated request, check that the corresponding device_sessions row exists and has revoked_at IS NULL — if revoked, reject the request as unauthorized even though the JWT signature itself is still technically valid. This does mean every authenticated request now requires one DB lookup (or a Redis-cached version, given Redis is already in the stack for rate limiting — propose caching the active/revoked status in Redis with a short TTL, invalidated immediately on revocation, to avoid a DB hit on every single request). Confirm this approach and the caching strategy before implementing, since this is the architecturally significant decision in this whole feature, similar in weight to the RBAC permission-resolution caching decision from earlier.

### New-device detection logic

On each successful login, compare the new request's (user_agent, ip_address) or fingerprint against the member's existing device_sessions history:

- If no matching prior session exists for this member at all → this is genuinely a new device, trigger notification
- If the user_agent is similar/identical to a prior session but the IP changed → this is likely just network change (home wifi to mobile data), NOT necessarily a new device — propose NOT notifying on IP-only changes to avoid notification fatigue, only notify when the device/browser signature itself is new
- Decide the matching window: should "new device" detection only consider currently-active (non-revoked, non-expired) sessions, or all-time history (so a device seen 6 months ago and not seen since wouldn't re-trigger a notification today)? Propose all-time history matching as more correct (re-logging in from an old phone shouldn't ping a false "new device" alert), confirm with me.

### Notification mechanism

Reuse the existing notification system already in the app (create_notification was referenced in the earlier mail webhook work) for in-app notification, AND send an email via the existing mail-sending path (SMTP through ZoneMTA, same as the verification/password-reset emails) for new-device login, since a security-relevant notification arriving only in-app (where the attacker, if it really is unauthorized access, might also see it) is less useful than an email sent to the verified address. Email content should include: approximate time, device/browser description, IP address (and optionally rough geolocation if a GeoIP lookup is feasible/already available — flag this as optional/stretch, don't add a new external dependency for it without confirming first), and a direct link to the new "active sessions" management page (see Step 2 frontend section) where they can review and revoke if it wasn't them.

## Step 3 — Backend implementation

1. Create the device_sessions model and migration
2. Modify the login flow (auth/services.py or wherever login logic now lives post-refactor) to: create a new device_sessions row on each successful login, run the new-device detection logic, trigger notification if new
3. Modify the JWT issuance to embed the session row's identifier as a claim
4. Modify the auth-checking middleware/decorator to validate the session is still active (not revoked) per the Step 2 caching design
5. Add endpoints:
   - GET /api/v1/account/sessions — list the current member's own sessions (active and recent history), for the "active sessions" UI
   - DELETE /api/v1/account/sessions/<session_id> — revoke one specific session (e.g. "log out that old laptop")
   - POST /api/v1/account/sessions/revoke-all — force logout of ALL sessions for the current member, including (decide and confirm) whether this also revokes the CURRENT session the request is being made from, or only all OTHER sessions, keeping the current one alive. Propose "revoke all others, keep current" as the default/primary action (matches how most apps like Google/GitHub do it — "log out everywhere else"), with a clearly separate, more deliberate action for "log out absolutely everywhere including this device" if needed.
   - For admins: an equivalent admin-initiated force-logout for a given member (e.g. if an account is suspected compromised or a member needs immediate access revocation) — gate this behind the new RBAC permission system from the earlier work (e.g. a permission like `members.sessions.revoke`)
6. Add a periodic Celery task to clean up old revoked/expired session rows past some retention window (e.g. 90 days) so the table doesn't grow unbounded — follow the same Celery beat pattern already established for mail sync.

## Step 4 — Frontend implementation

1. Add an "Active Sessions" / "Devices" section, likely under the Account tab from the earlier dashboard/account merge work, listing:
   - Each active session with friendly device description, location/IP, last active time, and a "Log out" button per session
   - The current session clearly marked as "This device" and not individually revokable from this list (or revokable but with a clear warning, since revoking your own current session logs you out immediately)
   - A prominent "Log out of all other devices" button
2. Handle the new-device notification surfacing in-app too (not just email) — likely via the existing notifications system/bell icon already in the app.
3. If following the Swiss German translation glossary from earlier work, ensure all new strings here follow the established conventions and get added to the glossary.

## Step 5 — Verify

1. Test multi-device login: log in from two different browsers/devices as the same test member, confirm both appear in the sessions list correctly with distinguishable device descriptions
2. Test new-device notification: log in from a genuinely new browser/UA combination, confirm both the in-app and email notification fire correctly; log in again from the SAME device shortly after, confirm no duplicate notification fires
3. Test revoke-one-session: revoke a non-current session, confirm that device's next authenticated request is correctly rejected (not just that the DB row shows revoked, but that the actual auth check enforces it)
4. Test revoke-all-others: confirm all other sessions are correctly invalidated while the session making the request remains valid
5. Test the Redis caching layer (if implemented) for correctness under revocation — specifically confirm there's no meaningful delay window where a revoked session could still succeed requests due to stale cache, and if there is some delay, report exactly how long and confirm it's acceptable (should be seconds, not minutes)
6. Confirm migration of any existing single-column device tracking data on Member — decide whether to backfill a device_sessions row from the existing column's data, or simply leave the old column's historical data as-is and start fresh with the new table going forward. Propose starting fresh (the old single-column data is likely low-fidelity and not worth migrating) and confirm with me, then remove the old column from Member once confirmed safe to drop.

## Step 6 — Report

Confirm: the chosen revocation-checking architecture (DB-per-request vs Redis-cached) and measured/estimated added latency per authenticated request, the new-device detection logic and notification channels, full endpoint list added, and confirmation the old single-column tracking was either migrated or deliberately discarded with my sign-off.

Wait for my confirmation on Step 2's architectural decisions (server-side revocation mechanism + caching strategy, new-device matching window, revoke-all semantics) before implementing, since these determine both the security properties and performance characteristics of every authenticated request going forward.
