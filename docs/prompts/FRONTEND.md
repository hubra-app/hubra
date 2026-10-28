Audit and refactor the frontend so every screen/page is defined in exactly one dedicated file, with no screen-level components duplicated across files, no screen logic embedded in shared components, and no shared component files that are actually rendering full pages.

## Step 1 — Map the current screen structure

1. Find the router configuration to understand what screens currently exist as registered routes:
   find app/frontend/src -name "*.tsx" -o -name "*.ts" | \
     xargs grep -l "createBrowserRouter\|BrowserRouter\|Route\|path=" 2>/dev/null | \
     grep -v node_modules | grep -v test

   Show the full router definition:
   cat $(find app/frontend/src -name "*.tsx" -o -name "*.ts" | \
     xargs grep -l "createBrowserRouter\|RouterProvider" 2>/dev/null | \
     grep -v node_modules | head -1)

2. List the current directory structure of the frontend src:
   find app/frontend/src -type f -name "*.tsx" | \
     sort | sed 's|app/frontend/src/||'

3. For each registered route, identify which file actually renders the top-level screen content — this is the file that should be the "screen file":
   grep -rn "element=\|component=" app/frontend/src/ \
     --include="*.tsx" | grep -v node_modules | grep "Route"

4. Identify files that are currently rendering screen-level content but are NOT registered directly as route elements — i.e. a component that takes up a full page but is embedded inside another component rather than being a route-level screen:

   # Look for files that use the full layout/shell (sidebar, navbar, etc.)

   # but aren't in the router

   grep -rln "Sidebar\|NavBar\|Shell\|Layout\|PageHeader" \
     app/frontend/src/ --include="*.tsx" | grep -v node_modules

5. Identify files that are currently doing double duty — both a reusable component AND rendering screen-level logic:

   # Large files are a signal — screen files are typically larger

   find app/frontend/src -name "*.tsx" | grep -v node_modules | \
     xargs wc -l | sort -rn | head -30

Report the full picture: every route, what file it points to, and any suspected screen-level content embedded in non-screen files.

## Step 2 — Define the desired structure (confirm before implementing)

Propose a screen file convention. Based on common React project conventions and the existing structure found in Step 1, propose one of:

**Option A — screens/ directory at top level:**
app/frontend/src/

screens/

DashboardScreen.tsx

MembersScreen.tsx

MemberDetailScreen.tsx

GroupsScreen.tsx

GroupDetailScreen.tsx

MailScreen.tsx

EventsScreen.tsx

PollsScreen.tsx

FinanceScreen.tsx

InventoryScreen.tsx

SettingsScreen.tsx

AccountScreen.tsx

LoginScreen.tsx

NotFoundScreen.tsx

...

components/           (shared, reusable, non-screen components only)

api/                  (API client, hooks)

hooks/                (shared hooks)

lib/                  (utilities)

**Option B — co-located with feature directories:**
app/frontend/src/

features/

members/

MembersScreen.tsx      (the page/screen)

MemberCard.tsx         (component used on this screen)

MemberForm.tsx         (component used on this screen)

useMember.ts           (hook used on this screen)

groups/

GroupsScreen.tsx

GroupDetail.tsx

...

shared/

components/

hooks/

lib/

Check what the existing project structure already leans toward (Step 1's directory listing) and recommend matching it rather than forcing a full reorganization on top of the screen-extraction work. Propose the option that requires fewer file moves while still enforcing the "one screen per file" rule. Confirm with me before proceeding.

## Step 3 — Identify every violation of "one screen per file"

For each of the following violation types, find every instance:

### Violation 1: Multiple screens in one file

A single .tsx file that renders different "pages" based on a prop or route param in a way that should be two separate screen files:

# Files with multiple large export functions/components

   grep -rn "^export default\|^export const.*=.*(" \
     app/frontend/src/ --include="*.tsx" | \
     grep -v node_modules | \
     awk -F: '{print $1}' | sort | uniq -c | sort -rn | head -20

# Files with multiple route-level sections

   grep -rln "tab.*==\|activeTab\|currentTab\|selectedTab" \
     app/frontend/src/ --include="*.tsx" | grep -v node_modules

### Violation 2: Screen logic embedded in shared components

A component in components/ that is actually rendering a full page, not a reusable widget:

# Components that use the full layout wrapper

   grep -rln "Layout\|Shell\|PageWrapper\|MainContent" \
     app/frontend/src/components/ --include="*.tsx" 2>/dev/null

### Violation 3: Screen imported and re-rendered inside another screen

A screen component imported into another screen and rendered as a child (rather than being navigated to via the router):
   for screen_file in $(find app/frontend/src -name "*Screen*" -o -name "*Page*" 2>/dev/null | grep -v node_modules); do
     screen_name=$(basename $screen_file .tsx)
     matches=$(grep -rln "import.*$screen_name\|<$screen_name" \
       app/frontend/src/ --include="*.tsx" | grep -v node_modules | \
       grep -v "$screen_file")
     [ -n "$matches" ] && echo "EMBEDDED: $screen_name imported in: $matches"
   done

### Violation 4: Mail fragmentation (specifically called out in the problem statement)

Find every file that renders mail-related UI and map which "screen" it currently lives on:
   grep -rln "mail\|mailbox\|forward\|alias\|smtp\|imap" \
     app/frontend/src/ --include="*.tsx" | grep -v node_modules | \
     grep -v "\.test\."

For each match, report: what mail concept does it show, and which route/screen is it currently embedded in?

Report the full violation list before proceeding to Step 4.

## Step 4 — Consolidation plan (confirm before implementing)

Based on Steps 1-3, produce a mapping of EVERY screen that should exist and which file it belongs in:

### The canonical screen list (adjust based on Step 1 findings)

Each of these should map to exactly ONE file:
LoginScreen          — /login

DashboardScreen      — /dashboard (the merged dashboard/account from earlier work)

AccountScreen        — /dashboard?tab=account (or /account redirecting here)

MembersScreen        — /members

MemberDetailScreen   — /members/:id

GroupsScreen         — /groups

GroupDetailScreen    — /groups/:id

EventsScreen         — /events

EventDetailScreen    — /events/:id (if exists)

PollsScreen          — /polls

FinanceScreen        — /finance

InventoryScreen      — /inventory

MailScreen           — /admin/mail (the consolidated admin mail overview from earlier)

SettingsScreen       — /settings (tabbed: System, Club)

NotFoundScreen       — /* (catch-all 404)

StatusScreen         — /status (public health status page from monitoring prompt)

Confirm this list (add/remove based on actual routes found in Step 1) and confirm the file naming convention (Screen suffix, Page suffix, or none) before Step 5.

For the mail fragmentation specifically — propose where each currently-fragmented mail concept lives in the consolidated structure:

- Member mailbox counts → stays on MemberDetailScreen (one section, not its own screen)
- Group mail address / forwarding → stays on GroupDetailScreen (one section)
- System mail overview (all ManagedMailAddress rows, provisioning status, mail log) → MailScreen (/admin/mail), one dedicated screen
- Club mail settings (Club.Contact.FinanceEmail, SMTP config display) → SettingsScreen Club tab, not a separate screen

## Step 5 — Implementation

Work through screens one at a time. For each screen:

1. Create the dedicated screen file in the confirmed location/naming convention
2. Move screen-level logic (data fetching hooks, page-level state, layout) INTO the screen file
3. Extract any genuinely reusable sub-components INTO dedicated component files (not embedded in the screen file — a screen file should primarily be composition of smaller components, not a monolith)
4. Update the router to point to the new screen file
5. Delete the old file if its content was fully moved (do not leave empty shell files)
6. Confirm no other file imports the old file name

Do NOT move sub-components that are genuinely local to one screen into a shared components/ directory — local components can stay co-located with their screen file, or in a screen-specific subdirectory. Only components used by 2+ screens belong in shared components/.

### Special handling for the mail fragmentation

The mail UI currently spread across multiple screens needs deliberate consolidation per the plan in Step 4 — for each mail concept currently in the wrong place:

1. Remove it from where it currently lives (e.g. remove the forwarding settings from wherever they currently appear outside the group detail screen)
2. Add it to its single confirmed home
3. Update the relevant API calls if the screen change means a different endpoint needs to be called (e.g. if forwarding settings were being loaded on a page that fetched the wrong data shape)

### Preserve all existing functionality

This is a structural refactor only — no feature changes. Every screen should render exactly the same content after the move as before, just sourced from one file instead of multiple.

## Step 6 — Verify

1. After each screen is moved, confirm the route still renders correctly in the browser (or via component test if tests exist for that screen)

2. After all screens are moved, confirm NO .tsx file in the src directory other than the dedicated screen files renders a full-page layout:
   grep -rln "Layout\|Shell\|MainContent\|PageWrapper" \
     app/frontend/src/ --include="*.tsx" | grep -v node_modules | \
     grep -v "screens/\|pages/"

3. Confirm the router still has exactly one element per route (no routes pointing at wrapper components that then render a screen internally):
   grep -A 2 "<Route" $(find app/frontend/src -name "*.tsx" | \
     xargs grep -l "Route" | grep -v node_modules | head -1)

4. Confirm no dead imports remain (files that import a screen component that no longer exists at that path):
   docker compose exec -T frontend sh -c "npm run build 2>&1 | grep -i 'error\|cannot find\|not found'" 2>/dev/null || \
   cd app/frontend && npm run build 2>&1 | grep -i "error\|cannot find"

5. Run the frontend test suite if it exists:
   docker compose exec -T frontend sh -c "npm test -- --watchAll=false" 2>/dev/null

6. Confirm mail UI is now consolidated — search for mail-related renders and confirm each concept appears exactly once:
   grep -rn "mailbox\|forwarding\|mail_address\|ManagedMail" \
     app/frontend/src/ --include="*.tsx" | grep -v node_modules | \
     grep -v "\.test\." | grep -v "import "

## Step 7 — Report

Provide:

1. Complete before/after mapping: every route and what file it pointed to before vs after
2. Every file deleted (with the reason it was removed)
3. Every new file created
4. The mail fragmentation resolution: where each mail concept now lives and confirmation it appears in exactly one place
5. Any violations found but NOT fixed in this pass (with reasoning — e.g. a component that's technically dual-purpose but fixing it is out of scope for a pure structural refactor)

Wait for Step 1 investigation findings, Step 2 structure confirmation, and Step 3 violation list before implementing Step 5. The investigation and plan must be complete and confirmed before any files are moved or deleted.
