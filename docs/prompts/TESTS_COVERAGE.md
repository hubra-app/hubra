Audit the entire backend test suite (now reorganized into per-blueprint directories under app/backend/tests/) against the actual codebase to identify coverage gaps, and write additional tests where genuinely needed. This is a coverage AUDIT first, test-writing second — don't write tests just to inflate numbers, write them where real risk exists.

## Step 1 — Establish current coverage baseline

1. Run the suite with coverage reporting (add pytest-cov if not already present):
   docker compose exec -T backend python -m pytest --cov=vollbuild --cov-report=term-missing --cov-report=html -ra

2. Report the overall coverage percentage and, more usefully, a per-module breakdown sorted from lowest to highest coverage:
   docker compose exec -T backend python -m pytest --cov=vollbuild --cov-report=term-missing | grep -E "^vollbuild"

3. Identify modules with notably low or zero coverage. Cross-reference against what we know from this conversation to be high-risk/high-complexity areas that deserve scrutiny regardless of raw percentage:
   - vollbuild/tasks/mail_sync.py (had the "messages" vs "total" field bug — was this bug actually catchable by a unit test with a mocked WildDuck response? If not, that's a coverage gap worth closing specifically)
   - vollbuild/api/mail/services.py and vollbuild/api/members/services.py (the consolidated MailService logic from the refactor)
   - The new RBAC permission-checking decorator/mechanism (if implemented) — this is security-critical and needs strong coverage
   - The new device_sessions / login history logic (if implemented) — also security-critical
   - vollbuild/api/auth/services.py (login, password reset, rate limiting interactions)
   - SRS/email-adjacent logic if any lives in the backend rather than purely in ZoneMTA/Haraka config

## Step 2 — Identify gap categories, not just percentage gaps

Beyond raw line coverage, specifically check for these gap TYPES across the codebase, since percentage alone doesn't catch them:

1. **Error/exception path coverage** — for each service method that catches WildDuckError, ValidationError, or similar, is there a test that actually exercises the failure path (e.g. WildDuck API returning an error, a DB constraint violation), or are only the happy paths tested? Grep for try/except blocks and cross-reference against whether a corresponding test mocks the failure condition:
   grep -rn "except WildDuckError\|except.*Error" app/backend/vollbuild/api/*/services.py app/backend/vollbuild/tasks/*.py

2. **Permission/authorization boundary tests** — for every @require_permission (or the new RBAC decorator) protected endpoint, is there a test confirming a user WITHOUT that permission is correctly denied (403), not just that a user WITH the permission succeeds? This is the single most important gap category given the RBAC work — an endpoint with only a "happy path, user has permission" test provides false confidence; the security-relevant test is the denial case.

3. **Boundary/edge-case tests for the field-name-bug class of issues** — given we found a real production bug (mb.get("messages", 0) when the actual field is "total") that silently returned wrong-but-valid-looking data rather than erroring, check whether tests for WildDuck-integration code mock realistic WildDuck API response shapes (matching the actual documented/observed response format) or use simplified/idealized mock data that wouldn't have caught this kind of field-name mismatch. Recommend that any test mocking an external API response be built from an actual captured real response shape (we have one in this conversation's history for the mailboxes endpoint) rather than a hand-typed approximation, specifically to prevent this bug class recurring.

4. **Concurrency/race-condition coverage** — for things like the device-session revocation, the mail sync upsert logic (which reads-then-writes per folder), are there any tests for concurrent access scenarios (e.g. two requests revoking the same session simultaneously, or the sync task running while a manual sync is also triggered)? This is often genuinely hard to test well — flag as a gap to be aware of rather than necessarily fully solving, and propose what's reasonably testable vs what would require excessive test infrastructure investment.

5. **Migration/data-integrity tests** — for the service-layer refactor and the device_sessions migration, is there a test confirming the migration is idempotent (running it twice doesn't break/duplicate) and confirming old data (if any was migrated/backfilled) maps correctly?

## Step 3 — Cross-reference against recent changes specifically

Since the codebase has had substantial recent work in this conversation's history, check test coverage specifically for:

- The service-layer refactor blueprints (mail, members, and whichever of the other 16 were completed) — confirm tests were updated to test the new Service classes directly (unit-testable without going through the full HTTP route), not just integration tests hitting the route
- The RBAC permission system (if implemented) — confirm the auto-discovery/sync mechanism has a test verifying a route without a corresponding registered permission fails closed as designed, not just that normal permission checks work
- The pytest warnings cleanup pass — confirm no new warnings were silently introduced by any tests written in THIS audit pass (run with -W error or whatever strict mode was settled on earlier)

## Step 4 — Write tests for genuine gaps, with restraint

For each gap identified in Steps 1-3 that represents real risk (not just a coverage percentage number), write a test. Prioritize in this order:

1. Security boundary tests (permission denial, session revocation enforcement) — highest priority
2. Error/exception path tests for external integrations (WildDuck, mail sending)
3. Field-shape/response-mocking fidelity fixes for existing tests that use unrealistic mock data
4. Everything else, only if clearly valuable

Do NOT write tests purely to bump a coverage percentage number for lines that are trivial (e.g. a simple property getter, a **repr** method) — flag these as acceptable to leave uncovered and explain why, rather than padding the suite with low-value tests.

For every new test file, follow the established naming/organization convention from the earlier test reorganization (one directory per blueprint, files named by what they test).

## Step 5 — Verify and report

1. Re-run full coverage report after additions, compare before/after percentage AND before/after gap-category coverage (the qualitative gaps from Step 2, which matter more than the raw number)
2. Run the full suite to confirm everything still passes and no new warnings introduced
3. Report a final summary:
   - Before/after overall coverage %
   - List of specific gap-category findings (permission denial tests missing on X endpoints, error-path tests missing on Y services, unrealistic mock data in Z tests) and which were fixed in this pass vs explicitly deferred with reasoning
   - Any genuinely new bugs discovered while writing these tests (separate from coverage gaps — sometimes writing a proper error-path test reveals the error handling itself is broken; surface these prominently, they're the most valuable finding from this whole exercise)
   - Explicit confirmation: are there now tests that would have caught the "messages" vs "total" field bug had they existed at the time? If not yet, that's the single most important remaining gap to close before considering this audit complete.

Work through Steps 1-3 (investigation/reporting) first and share the categorized findings before writing any new tests, so I can confirm priority/scope before the implementation work begins.
