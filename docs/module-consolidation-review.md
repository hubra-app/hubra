# Module consolidation review (2026-11-09)

Which Hubra modules and plugins work on the same things, and which of them
should be merged into one module or become an add-on of another. This is a
review only: nothing here is built yet.

Read from `main` of hubra and of every `hubra-plugin-*` repository on
2026-11-09. Open PRs that change the picture are named where they matter
(keys#14 / inventory#10 "keys are an inventory type", hubra#266 "member
badge"). It builds on the plugin overlap check of 2026-11-06 (Forms vs Polls,
Skills vs Teams) and does not repeat its verdicts.

## The three proposals to do first

1. **Merge Codes into Keys and rename it "Access" (Zutritt).** Two plugins
   keep secrets that open doors; Keys already pushes keypad codes to Nuki
   locks. Already being built in keys#14 + codes#6 through a contract
   takeover. See [A1](#a1-codes-into-keys-access).
2. **Merge Budgets into Finances, and make Bank import an add-on of
   Finances.** Both only make sense next to the books, both are already tabs
   under Finanzen, and today neither is linked to the Finances plugin at all.
   See [B1](#b1-budgets-into-finances) and [B2](#b2-bank-import-as-add-on-of-finances).
3. **One place for "who may use this machine".** Inventory inductions
   (`item_instructions`) and Guides qualifications (`member_qualifications`)
   record the same fact twice. Merge Guides into Inventory, with inductions
   that can expire. See [A2](#a2-guides-into-inventory).

Each is low to medium risk, removes one plugin a club admin has to
understand, and does not touch core tables.

## How merging and add-ons work today

- **Add-on**: a plugin whose first `depends:` entry (or the plugin that
  provides its first `requires:` module) is another plugin. The catalogue
  shows it inside the parent's card, and installs/updates check the parent's
  version ([plugins.md, Add-ons](plugins.md#add-ons)). A Hubra (core) module
  is never a parent, so a plugin that only needs core `finance` stands alone.
- **No plugin imports another plugin** (standing rule since 2026-11-05).
  An add-on talks to its parent only through contracts
  ([contracts.md](contracts.md)), so "add-on" changes packaging and the
  catalogue, not the coupling rules.
- **Merging two plugins** means the surviving plugin's migration chain takes
  over the other plugin's tables. Each plugin has its own Alembic version
  table in the club schema, so this works without core changes, **but** core
  has no way to say "this plugin replaces that one" yet. Every merge below
  needs a small core step first, called **M0** in this document:
  - a manifest field `replaces: [codes]`;
  - installing or updating the surviving plugin then marks the old plugin as
    replaced: its row in `installed_plugins` goes, its module switch is
    carried over to the new module code, its permission keys are renamed
    (or granted again under the new keys to the same roles), and its tables
    are **never dropped**;
  - the surviving plugin's first migration adopts the old tables
    (`CREATE TABLE IF NOT EXISTS`, then only `ALTER`), so a club that never
    had the old plugin also works;
  - the index marks the old plugin as replaced, so the catalogue offers the
    new one instead.
  Without M0 a merge means "uninstall, install, hope the tables survive",
  which is exactly the kind of step that lost Guides for a day on 2026-11-05.

## What exists today

### Core modules (hubra)

| Module | What it does | Data it owns |
|---|---|---|
| core | Sign-in, accounts, settings, dashboard, audit log, notifications | users, settings, audit, notifications |
| members | Directory, profiles, applications, membership tiers | members, tiers, applications |
| groups | Teams, committees, interest groups, self-join | groups, memberships |
| functions | Club offices and who holds them | functions, holders |
| roles | Roles and permissions | roles, permissions |
| events | Events, registration, reminders, attendance | club_events, event_registrations, event_attendance |
| polls | Formal votes with proxies, eligibility, auto-close | polls, poll_options, poll_votes, poll_proxies |
| posts | Announcements, likes, comments | posts, post_likes, post_comments |
| finance | Invoices with QR-bill, reminders, billing periods, fee runs | invoices, external parties, billing settings |
| dashboards | Members' own widget dashboards | dashboards, widgets |
| mail | Club mailboxes and aliases (self-hosted mail stack) | mailboxes, aliases |
| federation | Member clubs of an association, shared events | federation links |
| webhooks | Signed calls to the club's own tools | webhook endpoints, deliveries |
| bindings | Sync club data with external APIs | bindings |

### Plugins (hubra-plugin-*)

| Plugin (module) | What it does | Tables | Needs | Parent today |
|---|---|---|---|---|
| finances (`finance.books`) | Books: transactions, categories, recurring bookings, monthly statement, annual accounts | (uses core finance tables) | finance | none |
| budgets (`finance.budgets`) | Yearly budget per category vs booked | budgets, budget_lines | finance | none |
| bank-import (`finance.bank`) | camt/MT940/CSV import, match payments to invoices, book the rest by rules | bank_csv_profiles, bank_payments, bank_rules | finance | none |
| payments (`payments`) | Stripe Connect: members pay invoices by card/TWINT | payments_account, payments_checkouts | members, finance | none |
| kasse (`kasse`) | Expense claims, drinks tab (Strichliste), collective orders; totals on the invoice | kasse_claims, kasse_products, kasse_ticks, kasse_orders, kasse_order_items, kasse_order_lines | members, finance | none |
| supporters (`supporters`) | Sponsor packages and invoices, fundraising goals and donations | supporters_packages, supporters_sponsors, supporters_goals, supporters_donations | members, finance | none |
| inventory (`inventory`) | Items, owners, checkouts, inductions | inventory_items, inventory_checkouts, item_instructions (+ history in inventory#10) | members | none |
| keys (`inventory.keys`) | Physical keys and handovers, member QR cards and check-in, Nuki smart locks | keys, key_handovers, member_cards, checkins, smart_locks, lock_access | inventory | **inventory** |
| guides (`inventory.guides`) | Usage guide per item; qualifications with expiry and reminders | item_guides, qualification_kinds, member_qualifications | inventory | **inventory** |
| codes (`codes`) | Door codes and passcodes, encrypted | codes | members | none |
| booking (`booking`) | Rooms and equipment on a calendar, approval, fee on the invoice | booking_resources, booking_bookings | members, finance | none |
| board (`board`) | Tasks per function, year planner, contracts and insurances, general meeting | board_tasks, board_duties, board_contracts, board_meetings, board_agenda_items, board_attendance | members, functions | none |
| documents (`documents`) | Folders, uploads, access per role/group | documents_folders, documents_files | members | none |
| forms (`forms`) | Questionnaires and surveys with CSV | forms_forms, forms_fields, forms_responses | members | none |
| community (`community`) | Photo albums, skills and lending directory, idea box, welcome checklist, jubilees, honorary tier | community_* (11 tables) | members | none |
| teams (`teams`) | Fixtures from league feed, availability, line-up, carpooling | teams_* (6 tables) | members, groups | none |
| discord (`discord`) | Discord bot: announcements, roles, channels, poll buttons, DMs, changelogs | (settings only) | members | none |
| messengers (`messengers`) | Announcements to Telegram, Signal, Matrix | messengers_log | members | none |
| letters (`letters`) | Serial letters as PDF or by post (Pingen) | letters_letters, letters_items | members | none |
| imap-inbox (`inbox`) | Read external club mailboxes inside Hubra | inbox_mailboxes, inbox_messages | members | none |
| assistant (`assistant`) | Claude drafts posts, invitations, minutes summaries | assistant_drafts | members | none |

Only two of 21 plugins are add-ons today (Keys, Guides). Four plugins are
named `finance.*` but none of them is linked to the Finances plugin, because
they all point at the core `finance` module.

## Groups and proposals

Each proposal says: **what** (merge / add-on / keep), **why**, **what
changes for club admins**, **migration risk**, and **when** (its place in
the order at the end).

### A. Things and access: Inventory, Keys, Guides, Codes, Booking, Community lending

Inventory is the natural base. Keys is already becoming an inventory type
(inventory#10 + keys#14, in review).

#### A1. Codes into Keys ("Access")

> **Update 2026-11-09:** this is already being built in keys#14 +
> codes#6. There a code is a key of kind "code" (encrypted, reveal audited),
> and Codes 2.1.0 exports its rows through a query contract that Keys takes
> over once. After that, Codes can be uninstalled. This path needs no M0. What
> is left from A1 is the rename to "Access" and removing Codes from the index
> once clubs have moved over.

- **What:** merge Codes into Keys; rename Keys to **Access / Zutritt**:
  keys, cards, door codes and smart locks in one place.
- **Why:** both answer "how does someone get in". Keys already manages
  keypad codes on Nuki locks (`lock_access`), so a club with a Nuki lock and
  a padlock combination today keeps one code in Keys and the other in Codes.
  Codes is one table and has no contracts.
- **Admins:** one "Access" page with tabs Keys, Codes, Locks. Codes keep
  their encryption (club key) and who may read them. The Codes plugin
  disappears from the catalogue.
- **Risk:** low. One table (`codes`) adopted by Keys' migrations, needs M0.
  The encrypted values move as they are (same club key). Permission keys
  `codes.*` map to `keys.codes.*`.
- **Note:** Codes needs only `members`; after the merge it needs Inventory
  too (Keys is an add-on of Inventory). A club with door codes but no
  inventory would have to switch Inventory on. If that matters, merge the
  other way: Access as its own plugin with Keys as an inventory type inside
  it, but that undoes keys#14, so I recommend accepting the dependency.

#### A2. Guides into Inventory

- **What:** merge Guides into Inventory. Item guides become a section of the
  item page; qualifications become **inductions that can expire**, replacing
  Inventory's own `item_instructions`.
- **Why:** "who may use this machine" lives twice: Inventory's
  `item_instructions` (member × item, no expiry, checked on checkout) and
  Guides' `item_guides.qualification_kind` + `member_qualifications`
  (with expiry and reminders). A club using both inducts a member twice and
  only one of the two is checked at checkout. Guides is already an add-on
  with `inventory.guides` as module, and was the plugin that broke the
  no-cross-plugin rule on 2026-11-05.
- **Admins:** the guide and the induction rules sit on the item; one
  "Inductions" list with expiry dates and reminders. The Guides plugin
  disappears.
- **Risk:** medium. Three tables adopted, and existing `item_instructions`
  rows become qualifications without expiry (no data lost). Needs M0.
- **Open question for Mike:** qualifications that are not about an item
  (trainer licence, J+S, first aid) would then live in Inventory, which a
  sports club without inventory doesn't install. Two options:
  (a) keep them in Inventory and accept that; (b) move item-free
  qualifications to Community next to skills (board-checked skills with an
  expiry). I lean to (b) once A2 is done, as its own step.

#### A3. Member cards and check-in out of Keys

- **What:** move member QR cards and check-in (`member_cards`, `checkins`)
  out of Keys into core, next to the member badge (hubra#266, in review)
  and event attendance.
- **Why:** with keys#14 Keys becomes "an inventory type", but check-in marks
  attendance on core events and has nothing to do with inventory. hubra#266
  adds a per-person badge code in core, so a member would have two QR codes.
  Today a club must install Inventory to get check-in at trainings.
- **Admins:** check-in at trainings works without Inventory/Keys; one QR
  code per member.
- **Risk:** medium. Moving plugin tables into core is the "table adoption"
  step from the core-to-plugins review in reverse; old card tokens must keep
  working or be renewed on purpose (printed cards). Do after hubra#266.

#### A4. Booking stays on its own

- **What:** keep. Booking already links to an inventory item by id when
  Inventory is there (`booking_resources.inventory_item_id`, via contracts)
  and books rooms without it.
- **Why not an add-on:** making it an add-on would force every club that
  only books a room to run Inventory.

#### A5. Community lending into Inventory personal items

- **What:** the "lend" entries of the Community skills directory become
  Inventory items with visibility private (a member's own item, which
  Inventory already lends with checkouts).
- **Why:** two lending lists; Inventory's has due dates and a history,
  Community's is a text card.
- **Admins:** "I can lend my drill" moves from Community to Inventory › Mine
  when Inventory is on; Community keeps skills only. If Inventory is off,
  Community keeps showing lend entries as today.
- **Risk:** low-medium; copy rows via the `inventory.items.save` contract
  (no import), keep the Community rows until confirmed. Lowest priority of A.

### B. Money: Finances, Budgets, Bank import, Payments, Kasse, Supporters

Core `finance` keeps invoices (decided in the finance split). The books are
the Finances plugin. Everything else is a satellite.

#### B1. Budgets into Finances

- **What:** merge Budgets into Finances.
- **Why:** a budget is compared with booked transactions. The transaction
  table is still core, but booking them (the books UI, recurring bookings,
  categories page) is the Finances plugin (`finance.books`). Budgets is two
  tables, already a tab under Finanzen, and offers the fee basis next to
  Finances' own fee-basis queries. Installed without Finances it compares
  the budget with bookings nobody can make.
- **Admins:** Budget becomes a tab that Finances always has (switchable as
  a sub-module `finance.budgets`, so a club that doesn't plan can hide it).
  One plugin less to update.
- **Risk:** low. Two tables adopted, permission keys stay (`budgets.*` can
  stay as they are, module code `finance.budgets` unchanged). Needs M0.

#### B2. Bank import as add-on of Finances

- **What:** keep the plugin, add `depends: {finances: ">=1.0,<2"}` and
  `requires: [finance.books]`.
- **Why:** its rules book non-invoice payments into the books, which needs
  Finances. Today it says it needs only core `finance`, so the catalogue
  shows it as standalone and lets it install where its rules can't book.
  Keep it separate: file formats are Swiss/bank specific and many clubs
  never import files.
- **Admins:** shown inside the Finances card; can't be installed without it.
- **Risk:** very low. Manifest change and a release; no data moves.
  Check first that bank-import has no installs without Finances.

#### B3. Payments, Kasse, Supporters stay on their own

- **Payments:** works on invoices, which are core. Many clubs want online
  payment without bookkeeping. Keep standalone.
- **Kasse** and **Supporters:** their money parts already show as Finanzen
  tabs (expenses, sponsors since supporters#6 / kasse#6) and they invoice
  through core contracts. Their other parts (drinks tab, orders, fundraising
  goals, public sponsor logos) are member-facing and unrelated to the books.
  Keep both; no merge. Optional later: if expense claims should be booked
  automatically, make that a contract event (`kasse.claim.paid`) that
  Finances books, not a merge.

### C. Communication: Posts, Mail, Discord, Messengers, Letters, Inbox, Assistant

These are channels, not overlapping data. Discord and Messengers both
announce events, posts and polls, but Discord is a two-way bot with its own
gateway process and ten times the code; Messengers is one log table.

- **Keep all as plugins.** A merge buys little and Discord's release cadence
  (2.8.0) would drag Messengers along.
- **Do instead (core, small):** one settings page "Where announcements go"
  listing mail, Discord, Telegram/Signal/Matrix and letters with the same
  switches per kind (event, post, poll, reminder). Today each plugin has its
  own copy of these switches.
- **Inbox (IMAP) vs Mail (core):** both are "club mailboxes". Keep the code
  apart (Mail needs the self-hosted stack, Inbox reads any provider), but
  show both under one Mail area in the nav.
- **Assistant:** keep; it drafts for posts, events and minutes across
  modules, so no single parent fits.

### D. Board and governance: Board, Functions, Polls, Documents, Forms

- **Board:** keep. It links functions, polls (agenda items) and members; no
  other plugin has its data.
- **Board contracts vs Documents:** the contract register stores contract
  data and reminders, Documents stores files. Keep both; later let a contract
  link a document through a contract query, no merge.
- **Forms vs Polls:** keep both (2026-11-06 verdict).

### E. Club life: Events, Teams, Community

- **Teams:** keep as its own plugin. The one overlap is availability:
  `teams_answers` duplicates core `event_registrations` for matches that are
  already mirrored as events. Follow-up (from 2026-11-06): write availability
  to event registrations and match presence to attendance through the
  events contracts. Not a merge.
- **Community:** a bundle of six small features. Keep it as one plugin;
  splitting it into six would make the catalogue worse, not better. It gives
  up lending in A5 and may gain item-free qualifications in A2 (b).

## Order

| # | Step | Depends on | Risk | Size |
|---|---|---|---|---|
| 1 | B2 Bank import as add-on of Finances | – | very low | manifest + release |
| 2 | M0 `replaces:` in core (adopt tables, carry module switch and permissions) | – | medium (core) | 1–2 days with tests |
| 3 | A1 Codes into Keys / Access (in progress: keys#14, codes#6, no M0 needed) | keys#14 merged | low | rename only |
| 4 | B1 Budgets into Finances | M0 | low | 1 day |
| 5 | A2 Guides into Inventory | M0, inventory#10 merged | medium | 2 days |
| 6 | A3 Member cards and check-in into core | hubra#266 merged | medium | 2 days |
| 7 | C "Where announcements go" page | – | low | 1–2 days |
| 8 | A5 Community lending into Inventory | A2 | low-medium | 1 day |
| 9 | A2 (b) item-free qualifications to Community | A2, Mike's pick | medium | 1–2 days |

After 1–5 the catalogue goes from 21 plugins to 18, and the Finances and
Inventory cards carry their add-ons. Releases of each changed plugin stay
Mike's step.

## Not proposed, and why

- **Payments into Finances:** invoices are core, payment without books is
  common.
- **Booking as add-on of Inventory:** forces Inventory on clubs that only
  book rooms.
- **Messengers into Discord:** different runtime (bot gateway), different
  release pace, no shared data.
- **Forms into Polls or the other way:** see the 2026-11-06 review; Board
  and Discord depend on polls as they are.
- **Splitting Community:** six features in one plugin is fine for admins;
  the parts are small and switched together.
