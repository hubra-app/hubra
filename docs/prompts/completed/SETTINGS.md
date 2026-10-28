Add club-level configuration (name, banking details, finance contact, yearly expenses) to the application using the EXISTING settings namespace pattern (/api/v1/settings/{namespace}/{key}) rather than introducing a new, separate settings architecture. This is additive to the current settings system, not a replacement.

## Step 1 — Investigate the existing namespace pattern before designing anything

1. Find the current settings route(s) implementing this pattern:
   grep -rn "settings/<.*>/<.*>\|namespace" app/backend/vollbuild/api/settings/routes.py

2. List every namespace currently in use, so new work follows existing conventions rather than inventing new ones:
   docker compose exec -T postgres psql -U club_user -d club_db -c "SELECT DISTINCT namespace FROM settings ORDER BY namespace;" 2>/dev/null || \
   grep -rn "namespace.*=" app/backend/vollbuild/models/settings.py

3. Show me the Settings model's actual schema (columns, types, any existing per-namespace conventions for validation, typing, or access control):
   find app/backend/vollbuild/models -iname "*settings*" -exec cat {} \;

4. Show me the existing service/route logic for settings to confirm: how is a setting's value typed/deserialized today (raw strings everywhere, or some typed mechanism)? Is there already per-key validation, or per-namespace access control (vs one flat permission for all settings)?

5. We know mail.webhook_secret exists as a setting from earlier work — confirm what namespace it currently lives under. This tells us whether existing namespaces are domain-based (e.g. "mail", suggesting we should add a parallel "club" namespace) and whether the key-naming convention within a namespace uses dot-notation, snake_case, or something else — match it exactly for the new keys.

6. Explicitly resolve the secrets boundary question: should infrastructure/secret-bearing config (mail server connection details, API tokens, JWT secrets) ever be exposed via this settings API, even read-only — or should those stay purely in env vars/compose and never appear in the namespace system at all? If mail.webhook_secret already exists in the settings system today, determine and state explicitly whether that's a legitimate app-level/rotatable value (fine to be there) or itself a boundary violation worth flagging separately. This determines whether the new "club" namespace should ever contain anything secret-like (it shouldn't — IBAN and address are not secrets, but flag if anything proposed below risks crossing this line).

Report all of this back before proposing anything further.

## Step 2 — Design proposal (confirm before implementing)

Based on Step 1 findings, propose:

1. **Namespace and keys.** Most likely a new "club" namespace with keys: club/name, club/iban, club/address_street, club/address_house_number, club/address_postal_code, club/address_city, club/address_country, club/finance_email, club/yearly_expenses_chf. Match the exact naming convention (separator style, casing) of existing namespaces from Step 1 rather than this list verbatim if it differs.

2. **Permission scoping.** Determine whether namespace-level access control already exists (e.g. a permission scoped to all of club/*using the structured resource.action RBAC convention from earlier work, like settings.club.manage). If it doesn't exist yet for any namespace, propose adding it using the same auto-discovered structured-permission-key pattern as the rest of RBAC — not a one-off special case just for this namespace. Confirm whether read and write should be gated by the same permission or split (e.g. a treasurer/Kassier role might warrant write access to club/* specifically without broader settings access — this argues for namespace-scoped permissions being genuinely useful here, not just a stretch goal).

3. **Validation.** Determine whether per-key value typing/validation already exists. If values are currently all raw strings cast ad-hoc wherever read, propose a lightweight per-key validator/type registry so club/iban gets IBAN format + QR-IBAN range validation (5th-6th digits 30-31, since QRR references require a QR-IBAN specifically, not a regular IBAN) and club/yearly_expenses_chf gets numeric validation — without duplicating this logic at every read site. If a decent pattern already exists, just follow it for consistency rather than building something parallel.

Wait for my confirmation on Step 1 findings and this Step 2 proposal — especially the secrets boundary call and the permission-scoping approach — before writing any implementation code.

## Step 3 — Implementation

1. Add the new "club" namespace keys to the existing Settings table, following its established conventions exactly. Confirm no schema change is needed if the existing structure is already generic enough (namespace/key/value, or similar) — don't add a migration unless genuinely required.

2. Add per-key validation for club/iban and club/yearly_expenses_chf per the Step 2 decision.

3. Wire RBAC permission gating for the new namespace.

4. Add API support: GET /api/v1/settings/club/<key> (and a list-all-under-namespace variant if the existing pattern supports one, e.g. GET /api/v1/settings/club) and PATCH /api/v1/settings/club/<key>, following whatever the existing route signature already looks like rather than inventing a new shape.

## Step 4 — Connect dependent consumers

1. Find where the tier cost calculation currently sources its yearly-expenses figure (it must come from somewhere today, even if ad hoc) and point it at club/yearly_expenses_chf instead:
   grep -rn "yearly_expense\|expense" app/backend/vollbuild/api/tiers/ app/backend/vollbuild/api/finance/
   Confirm the old source is fully removed (not left as an unused duplicate) once the new path is verified working.

2. Grep for hardcoded club name / finance contact email elsewhere in the codebase (email templates, frontend constants) that should now read from club/name and club/finance_email instead:
   grep -rln "VollBuild\|vollbuild\.ch" app/backend/vollbuild/ --include="*.py" | grep -v test

## Step 5 — Frontend

Add a "Club" section/tab to whatever Settings UI already exists, matching its current organization (if the frontend already renders namespaces as tabs/sections, the new "club" namespace should slot in naturally). Build form fields for club name, IBAN (inline format validation feedback as the user types/on blur), structured address, finance email, and yearly expenses (CHF, Swiss thousands-separator format — apostrophe, e.g. 12'000). Gate the entire section behind the RBAC permission from Step 2 — hide it entirely for members without access, per the established proactive-permission-hiding pattern from the earlier RBAC frontend work.

## Step 6 — Verify

1. GET/PATCH against /api/v1/settings/club/<key> works for every new key, including validation correctly rejecting a malformed/non-QR IBAN and a non-numeric yearly_expenses_chf with clear error messages
2. Permission gating correctly blocks read and/or write (per the Step 2 decision) for a member without the relevant permission
3. Tier cost calculation correctly reads the new value end-to-end after the change
4. Full test suite passes; add tests for the new namespace's validation and permission boundaries, following the existing test organization convention (likely app/backend/tests/settings/test_club_namespace.py)

## Step 7 — Report

Confirm: existing namespace conventions found in Step 1, exact key names added, whether new validation infrastructure was built or an existing pattern reused, the permission-scoping decision, and confirmation tier calculation now reads from this single consolidated source.

Addendum — settings key naming convention: use strict dotted notation throughout, formatted as Section.Usage.VariableName (e.g. Club.Banking.Iban, Club.Banking.YearlyExpensesChf, Club.Identity.Name, Club.Contact.FinanceEmail, Mail.Webhook.Secret), rather than the slash-namespace/flat-key or snake_case styles considered earlier. This convention applies to BOTH prompts below — confirm it matches or update the existing settings system's current convention before applying it to new keys.

## Step 0 — Reconcile with existing convention first

Before adding any new keys, check what convention is ALREADY in use for existing settings (we know mail.webhook_secret exists from earlier work — confirm its exact current casing/format):
   docker compose exec -T postgres psql -U club_user -d club_db -c "SELECT namespace, key FROM settings ORDER BY namespace, key;" 2>/dev/null || \
   grep -rn "webhook_secret\|namespace.*key" app/backend/vollbuild/models/settings.py app/backend/vollbuild/api/settings/

Report back exactly what's there today. Then resolve one of two paths:

**Path A — Existing keys already roughly match this dotted convention** (e.g. mail.webhook_secret could become Mail.Webhook.Secret or already follows a similar three-part dotted shape) — in this case, propose a precise casing rule (PascalCase per segment? lowercase? a mix?) and apply it consistently to BOTH new club keys and, if low-risk, rename existing keys to match exactly. Confirm whether renaming existing keys is safe (check if any code reads them by literal string match that would break) before doing so.

**Path B — Existing keys use a meaningfully different convention** (e.g. flat snake_case, or a separate namespace column rather than dots baked into the key itself) — in this case, do NOT silently introduce a second, inconsistent convention alongside the old one. Stop and report the conflict explicitly: should ALL settings be migrated to the new Section.Usage.VariableName format in this pass (bigger, but keeps the system consistent), or should the new dotted format apply ONLY to newly added keys going forward, accepting that the settings table will have two coexisting styles for a while (smaller risk now, but a known inconsistency to clean up later)? Ask me to choose before implementing either new keys or any migration.

## Step 1 — Apply to the Club Settings Namespace prompt

Once Step 0 is resolved, the keys proposed in Prompt 1 (Club Settings Namespace) become:

- Club.Identity.Name
- Club.Banking.Iban
- Club.Address.Street
- Club.Address.HouseNumber
- Club.Address.PostalCode
- Club.Address.City
- Club.Address.Country
- Club.Contact.FinanceEmail
- Club.Banking.YearlyExpensesChf

(Adjust exact section/usage groupings if Step 0's findings suggest a different breakdown fits the existing system's actual granularity better — e.g. if "Banking" and "Address" should be one section vs split, follow whatever logical grouping the existing keys already demonstrate. Report your final proposed key list before implementing.)

Everything else in the original Club Settings Namespace prompt (investigation steps, permission scoping via the structured RBAC pattern, per-key validation for the IBAN and yearly-expenses fields, secrets-boundary confirmation, frontend implementation, verification) stays as previously specified — only the literal key strings change to match this dotted convention.

## Step 2 — Apply to the QR-bill generation prompt

The QR-bill PDF generation step (Step 2 of the second prompt) that reads creditor info should reference the renamed keys: Club.Identity.Name, Club.Banking.Iban, Club.Address.Street, Club.Address.HouseNumber, Club.Address.PostalCode, Club.Address.City, Club.Address.Country, Club.Contact.FinanceEmail. Update the prompt's references accordingly — no other changes to that prompt's scope or steps.

## Step 3 — Verify

1. Confirm the final key list and casing convention adopted matches consistently across every new key added in both prompts — no mixed casing or accidental snake_case creeping back in
2. If Path B's "migrate everything" option was chosen, confirm all existing settings reads/writes throughout the codebase were updated to the new key strings (grep for old literal key references to make sure none were missed):
   grep -rn "webhook_secret\|mail\.webhook" app/backend/vollbuild/ --include="*.py" | grep -v test
3. Confirm settings round-trip correctly (write via PATCH, read back via GET) using the new key format end-to-end

Report back Step 0's findings and your Path A/B resolution before proceeding to implement either of the two main prompts with the new key format.

Extend the existing System SMTP user (the <noreply@vollbuild.ch> account already created and used for transactional email — verification emails, password resets, etc.) so it can ALSO send from the Club.Contact.FinanceEmail address (Prompt 1's settings key) once that setting is configured, and correctly handle add/remove of that send-as capability whenever Club.Contact.FinanceEmail is created, changed, or cleared via the settings system.

## Step 1 — Investigate current state

1. Find how the existing <noreply@vollbuild.ch> WildDuck user was originally created and how its "from" capability currently works — was it given a single fixed address, or does the codebase already use WildDuck's fromWhitelist mechanism (referenced in the WildDuck API docs we pulled earlier: "fromWhitelist — a list of additional email addresses this user can send mail from. Wildcard is allowed")?
   grep -rn "fromWhitelist\|noreply@\|create_user\|SMTP_USER" app/backend/vollbuild/ --include="*.py" | grep -v test

2. Confirm exactly how outbound mail currently picks its From address for different email types (verification, password reset, invoice notifications) — is the From address hardcoded to <noreply@vollbuild.ch> everywhere, or is there already a parameter/config for choosing it per email type?
   grep -rn "sender_email\|MAIL_FROM\|from_address" app/backend/vollbuild/services/email.py app/backend/vollbuild/api/*/routes.py 2>/dev/null

3. Confirm the System SMTP user's WildDuck user_id is stored somewhere retrievable (env var, settings key, hardcoded) so this work can target the right WildDuck account via the API:
   grep -rn "system.*smtp.*user\|smtp_user_id\|noreply.*wildduck" app/backend/vollbuild/

Report findings before proposing the mechanism — specifically confirm whether fromWhitelist is the right WildDuck primitive to use here (it should be, per the API docs, but confirm no other mechanism is already half-built for this).

## Step 2 — Design the trigger mechanism

Propose, and confirm before implementing, how changes to Club.Contact.FinanceEmail should propagate to WildDuck:

1. **Trigger point.** This should fire as part of the PATCH /api/v1/settings/club/<key> (or whatever the final settings route shape from the dotted-key prompt turns out to be) handling specifically for the Club.Contact.FinanceEmail key — not as a generic side effect bolted onto all settings writes. Propose a clean mechanism: e.g. a small registry of "settings keys with side effects" (similar in spirit to the per-key validator registry from the earlier settings prompt) mapping Club.Contact.FinanceEmail to a handler function that syncs WildDuck's fromWhitelist, rather than hardcoding an if key == "Club.Contact.FinanceEmail" check inline in the generic settings update route. This keeps the settings system itself generic while still supporting keys that need real side effects.

2. **Add behavior.** When Club.Contact.FinanceEmail is set to a new value (either first-time set, or changed from a previous value):
   - Add the new email address to the System SMTP user's fromWhitelist via the WildDuck API (PUT /users/{id} with an updated fromWhitelist array — confirm exact request shape against the WildDuck API docs/your existing WildDuckClient wrapper)
   - If the email is being CHANGED (not just newly set), also REMOVE the old value from fromWhitelist so stale entries don't accumulate — this requires fetching the current fromWhitelist first, removing the old finance email if present, adding the new one, then writing back the full updated list (WildDuck's API takes the whole array, not an add/remove delta — confirm this against the actual API behavior before implementing, since getting this wrong could silently wipe out other entries already in fromWhitelist, like <noreply@vollbuild.ch> itself, which must NEVER be removed by this logic).

3. **Remove behavior.** If Club.Contact.FinanceEmail is cleared/unset entirely, remove that address from fromWhitelist (same care as above — fetch current list, remove only the specific finance email entry, preserve everything else, write back).

4. **Validation before triggering the WildDuck sync.** The new finance email value should pass basic email format validation (and ideally confirm it's actually within the vollbuild.ch domain, since fromWhitelist on this SMTP user should plausibly only ever contain addresses on the Verein's own domain — flag if there's a reason to allow an external domain here, otherwise treat a non-vollbuild.ch address as invalid input and reject the settings update before it ever reaches the WildDuck sync step).

5. **Failure handling.** If the WildDuck API call fails (network issue, WildDuck temporarily down — we've seen this happen in this conversation's history), decide and confirm: should the settings value itself still be saved in the DB even if the WildDuck sync fails (with the sync retried later, e.g. via a Celery task with retry/backoff, following the existing Celery patterns already established for mail_sync), or should the whole settings PATCH fail atomically if the WildDuck sync fails (safer in terms of never having the DB and WildDuck out of sync, but means a transient WildDuck outage blocks an otherwise-unrelated settings change)? Recommend: save the settings value immediately (don't block an admin from saving), but treat the WildDuck sync as a best-effort follow-up step with retry-on-failure and a clear visible warning in the API response / admin UI if the sync didn't succeed yet (e.g. "Setting saved, but mail server sync is pending — will retry automatically"), rather than failing the whole operation. Confirm this approach before implementing.

## Step 3 — Implementation

1. Add a get_user_from_whitelist(user_id) / update_user_from_whitelist(user_id, addresses: list[str]) method (or similar) to the existing WildDuckClient wrapper, following its established patterns (the same client used for list_mailboxes, create_webhook, etc. from earlier work).

2. Implement the settings-side-effect handler for Club.Contact.FinanceEmail per the Step 2 design: fetch current fromWhitelist, compute the diff (remove old finance email if changing, add new one, never touch <noreply@vollbuild.ch> or anything else already present), write back.

3. Wire this into the settings update flow per the registry mechanism from Step 2.1.

4. If retry-on-failure is the chosen approach (Step 2.5), implement it as a Celery task (e.g. vollbuild/tasks/wildduck_sync.py, sync_smtp_user_from_whitelist) with the same retry/backoff pattern already established for webhook posting / mail sync in earlier work, triggered immediately on settings save and retried if it fails.

5. Update the email-sending logic (Step 1.2 findings) so that invoice-related emails (e.g. the QR-bill delivery emails from the earlier QR-bill prompt) can actually USE the finance email as their From address when appropriate, rather than this fromWhitelist sync existing but nothing in the app ever actually sends FROM that address. Confirm which email types should send from Club.Contact.FinanceEmail (likely: QR-bill/invoice notifications, payment reminders) versus which stay on <noreply@vollbuild.ch> (likely: account verification, password reset, system notifications) — propose this mapping and confirm with me.

## Step 4 — Verify

1. Set Club.Contact.FinanceEmail for the first time via the settings API, confirm via direct WildDuck API query that the System SMTP user's fromWhitelist now includes it AND still includes <noreply@vollbuild.ch> (nothing was wiped):
   docker exec community-mailserver sh -c "wget -qO- '<http://127.0.0.1:8080/users/><system_smtp_user_id>' --header 'X-Access-Token: ...'" | grep -A5 fromWhitelist

2. Change Club.Contact.FinanceEmail to a different address, confirm the OLD address is removed from fromWhitelist and the new one is present, <noreply@vollbuild.ch> still untouched.

3. Clear Club.Contact.FinanceEmail entirely, confirm it's removed from fromWhitelist, <noreply@vollbuild.ch> still present.

4. Send a real test email using the finance email as From (via whichever email type was mapped to it in Step 3.5) and confirm it sends successfully — this validates the whole chain end to end, not just that the WildDuck user object looks correct.

5. Test the failure-handling path: simulate a WildDuck API failure during the sync (e.g. temporarily stop the mailserver container) while saving a new Club.Contact.FinanceEmail value, confirm the settings value still saves, confirm the retry mechanism eventually succeeds once WildDuck is back up, confirm the admin UI/API response correctly reflects the pending-sync state in the meantime.

6. Add tests covering: the add/remove/change scenarios for fromWhitelist sync logic specifically (mocking the WildDuck client, following the same mocking-fidelity guidance from the earlier test-coverage audit prompt — build the mock response shape from a REAL captured WildDuck user object, not a hand-typed approximation, given that's exactly the bug class we found and fixed earlier with the messages/total field issue), domain validation rejecting a non-vollbuild.ch finance email, and the retry-on-failure path.

## Step 5 — Report

Confirm: the side-effect-registry mechanism chosen for settings-key-triggers-action, the fromWhitelist sync logic and how it guarantees <noreply@vollbuild.ch> is never accidentally removed, the failure-handling approach implemented, and the final From-address mapping (which email types use noreply@ vs Club.Contact.FinanceEmail).

Wait for my confirmation on: the side-effect trigger mechanism (Step 2.1), the save-immediately-vs-fail-atomically decision for WildDuck sync failures (Step 2.5), and the From-address-per-email-type mapping (Step 3.5) — before implementing.
