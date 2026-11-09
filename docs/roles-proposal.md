# Proposal: standard club roles and module access

Status: **decisions taken 2026-11-09 (see §6), not built yet.** Asked by Mike on 2026-11-09:

> define role / function standards for a club? members, Board (Aktuar / Archivar,
> Finanzen / Kassier, Präsident / Vizepräsident). Also restrict access to entire
> modules for roles / functions? Hidden by default if no access at all?

Short answer: yes to both. Hubra already has most of the pieces (roles, functions
that grant a role, levels on the roles page, a sidebar that hides entries you may
not open). What is missing is a standard set every club starts with, one switch
per module on a role, and a way for plugins to bring sensible defaults.

## 1. What exists today

| Piece | Where | What it does |
| --- | --- | --- |
| Roles | `core/models/role.py`, seeded in `_seed_tenant` (`core/tenant/service.py`) | Every new club gets 4 system roles: **Owner**, **Admin** (both bypass all checks), **Treasurer**, **Member** (`is_default`, every member has it). Permissions of Treasurer and Member are editable. |
| Permission keys | `@permission_required(resource, action)` → `<module>.<resource>.<action>` | ~200 keys, synced into the catalog by `flask sync-permissions`. Plugins add theirs the same way. |
| Functions (Ämter) | `core/models/function.py` | An office with holders and terms (Kassier, …). `grants_tenant_role_id` gives the holder **one** role while the term runs (derived at check time, `permissions.function_roles`). |
| Group-scoped roles | `member_role_scopes` | A role held for one group only (group leaders). |
| Object-level rules | `permission_required(allow=…)` | Creator of an event, owner of an item, etc. |
| Roles page | `screens/private/system/roles/levels.ts` | Per **resource**: Keine / Ansehen / Bearbeiten / Alles. |
| Sidebar | `components/Shell/nav.tsx` (`buildNav`) | An entry is shown when its module is on **and** the person holds at least one of the entry's `perms`. Entries without `perms` show for everyone. |
| Direct URL | `modules/RequireModule.tsx` | Same rule; shows "Kein Zugriff" otherwise. |
| API gate | `core/modules/gate.py` | Refuses a module's routes when the module is off (`MODULE_DISABLED`) or the member has no licence (`LICENSE_REQUIRED`). No per-role check; each route checks its own key. |

Gaps that matter for this ask:

1. **Functions and roles do not line up.** `flask seed` creates the functions
   Kassier, Präsidium and Aktuar and a "Vorstand" group, but only in the
   legacy/dev schema (`core/seeds.py`). A new club (`_seed_tenant`) gets no
   functions, no Vorstand, and Kassier does not grant Treasurer anywhere.
2. **A function grants only one role.** The Kassier needs board rights *and*
   finance rights; today that means copying the board keys into Treasurer.
3. **Modules without `perms` cannot be hidden per role.** Booking, Community,
   Forms, Kasse (expense claims), Supporters, Teams, Guides (Skills), Events,
   Polls, Posts and Dashboards show for every member as soon as the module is
   on. Some of their routes have no permission check at all, so the API is
   open to every member too.
4. **Plugins grant nothing by default.** After installing a plugin only admins
   can use it until someone ticks keys on each role. Treasurer's defaults still
   only list the core finance keys.
5. **The roles page is per resource, not per module.** Finanzen alone is ~10
   rows; there is no "Finanzen: Keine" in one click.

## 2. Standard roles and functions

Keep the split Hubra already has: a **function** is the office a person holds
(with term and mail alias), a **role** is the bundle of rights. Every new club
gets both, linked.

| Function (Amt) | Mail alias | Grants role(s) | Notes |
| --- | --- | --- | --- |
| — (every member) | — | **Mitglied** (Member) | default role, as today |
| Präsident/in | `praesidium@` | **Vorstand** + **Präsidium** | |
| Vizepräsident/in | `praesidium@` (shared) | **Vorstand** + **Präsidium** | |
| Aktuar/in (Sekretariat, Archiv) | `aktuar@` | **Vorstand** + **Aktuar** | Mike's "Actuar / Archiver"; Archivar can be its own function granting the same role |
| Kassier/in (Finanzen) | `kassier@` | **Vorstand** + **Kassier** (Treasurer) | |
| Beisitzer/in (optional) | — | **Vorstand** | plain board member without an office |

Owner and Admin stay as they are (technical full access, not an office).

### What each role can do by default

Levels as on the roles page: **–** none (module hidden), **A** Ansehen (see and
take part), **B** Bearbeiten (create, change), **✓** Alles (also delete,
export, moderate, give roles).

| Module | Mitglied | Vorstand | Aktuar | Kassier | Präsidium |
| --- | :-: | :-: | :-: | :-: | :-: |
| Dashboard, Benachrichtigungen | A | A | A | A | A |
| Mitglieder (directory) | A | A | ✓ | A | ✓ |
| Anträge (applications), Beitragskategorien | – | A | ✓ | A (+ fee reductions B) | ✓ |
| Gruppen | A | B | B | A | ✓ |
| Funktionen | A | A | B | A | ✓ |
| Rollen | – | A | A | A | ✓ |
| Termine (events) | A + sign up | B | B | A | ✓ |
| Umfragen (polls) | A + vote | B | B | A | ✓ |
| Beiträge (posts) | A + like/comment | B | B | A | ✓ (moderate) |
| Mail (aliases, lists) | – | A | B | A | B |
| Rechnungen (core invoices) | own only | A | A | ✓ | A |
| Finanzen (books, budgets, bank import, payments) | – | A | – | ✓ | A |
| Spesen (Kasse) | own claims | own claims + A | own claims | ✓ (approve, pay) | A (approve) |
| Sponsoren (Supporters) | – | A | B | ✓ | B |
| Dokumente, Briefe, Protokolle | – | A | ✓ | A | B |
| Vorstand-Board (tasks) | – | B | B | B | ✓ |
| Inventar, Schlüssel, Codes | per module (§4) | A | B | A | B |
| Audit-Log | – | – | A | A | A |
| Einstellungen, Module | – | – | – | – | ✓ (Admin) |

Präsidium: the open question is whether Präsidium simply grants the **Admin**
role (full access, simplest, matches how small clubs work) or a separate
Präsidium role that is "everything except settings and modules" (decision D1).

## 3. Module access: one switch per module, hidden when "Keine"

**Rule:** a person who has no access to a module does not see it anywhere:
not in the sidebar, not on "Weitere", not as a dashboard widget, not in search,
and its API answers `403 MODULE_ACCESS`. That is the default for every module
a role has not been given.

How it works:

1. **One access key per module.** The registry adds `<code>.module.access`
   for every module that is not `required` (e.g. `inventory.module.access`).
   It is the "Ansehen" floor: holding any other key of the module implies it,
   so existing roles keep working.
2. **API gate.** `module_gate` gets a third check next to "enabled" and
   "licence": the signed-in member must hold the module's access key (admins
   pass, public endpoints and contract calls between modules are not routed
   through the gate and are unaffected). This also closes gap 3 for routes
   that today have no check.
3. **Sidebar.** `navEntries` adds the access key to each entry's `permKeys`,
   so entries that today have no `perms` (Booking, Community, …) hide when the
   role has no access. `RequireModule`, the "Weitere" cards, dashboard widgets
   and search use the same `canUseModule(code)` helper.
4. **Roles page.** The role detail groups areas by **module** with one level
   picker per module (Keine / Ansehen / Bearbeiten / Alles) that sets every
   key of that module. The per-resource rows stay as "Details" for fine
   tuning, like today's "Vergleichen".
5. **Functions as well as roles.** Since functions grant roles, "restrict a
   module for a function" is done on the role the function grants. No
   separate per-function access list (keeps one place to look).

Not hidden: modules a member reaches through their own data (own invoices,
own expense claims, own items) stay reachable from their profile even
without module access; only the module's own pages hide. (decision D4)

## 4. Defaults for plugins

Roles get a stable `key` (`member`, `board`, `secretary`, `treasurer`,
`president`) so a plugin can name them without knowing the club's labels.
A module manifest gets an optional field:

```python
role_defaults={"member": "view", "board": "view", "treasurer": "all"}
```

When a club switches the module on for the **first** time, Hubra applies
these levels to the standard roles that still exist. Later changes by the
club are never overwritten; switching off and on again does not re-apply.
Without `role_defaults` a module gets "–" for everyone but admins (hidden by
default). The template and all plugin repos get a `role_defaults` line.

Suggested defaults: Inventory, Booking, Community, Teams, Forms, Guides:
`member: view`; Keys, Codes: `board: view` (members see their own keys via
the profile); Finances, Payments, Bank import, Budgets: `treasurer: all`,
`board: view`; Kasse: `member: view` (own claims), `treasurer: all`;
Documents, Letters, Board: `board: edit`, `secretary: all`; Discord,
Messengers, Inbox, Assistant: admin only.

## 5. What changes

Backend (hubra):
- Migration: `roles.key` (nullable, unique), table `function_roles`
  (function → several roles; `grants_tenant_role_id` copied over, then dropped
  in a later release), table `module_role_defaults_applied` (club, module) so
  defaults apply once.
- `_seed_tenant`: seed the 5 standard roles with their default keys, the
  functions Präsident/in, Vizepräsident/in, Aktuar/in, Kassier/in linked to
  them, and the Vorstand group (moves out of the legacy `run_seeds`).
- Registry: auto-register `<code>.module.access`; `role_defaults` on `Module`;
  apply on first enable (`core/modules/state.py`).
- Gate: access check in `core/modules/gate.py` (`403 MODULE_ACCESS`).
- `permissions.function_roles` reads `function_roles` instead of the single
  column.
- `flask roles standardise [--tenant]`: for **existing clubs**, add missing
  standard roles/functions (never renames or removes the club's own), and
  give the access key of every module that members can use today to
  **Mitglied**, so nothing disappears on upgrade. Run once per club on deploy.

Frontend:
- `nav.tsx` / `RequireModule` / Weitere / widgets: `canUseModule(code)`.
- Roles page: module-level pickers; role detail shows "Kommt mit Funktion
  Kassier/in".
- Functions page: pick several roles per function.

Plugins: one `role_defaults` line each (19 plugin PRs) plus the template.
Plugins never depend on each other; nothing here changes that.

Rough size: core 1 PR (migration + gate + seed + UI), template 1 PR, plugins
one small PR each.

## 6. Decisions (Mike, 2026-11-09)

- **D1 Präsidium = Admin: yes.** Präsident/in and Vizepräsident/in get the
  Admin role (full access incl. settings) through their functions; there is
  no separate Präsidium role. Read the "Präsidium" column in §2 as Admin.
- **D2 Vorstand as its own role: yes.** Every board function grants Vorstand
  plus its office role, so functions grant several roles (`function_roles`).
- **D3 Existing clubs: yes.** `flask roles standardise` runs on deploy and
  adds the standard set next to what the club already has.
- **D4 Own data without module access: yes.** A member without access to a
  module still sees their own items (invoices, expense claims, items) on
  their profile; only the module's own pages hide.
- **D5 Names: as proposed.** Mitglied, Vorstand, Aktuar/in (covers the
  archive), Kassier/in, Präsident/in, Vizepräsident/in; keys stay English.
