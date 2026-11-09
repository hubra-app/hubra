# Ideas and roadmap (November 2026)

85 new ideas for Hubra, and a roadmap for building them. Nothing here is
decided. Written on 2026-11-09 after reading the backlog, `docs/settings/ideas.md`,
`app/backend/ROADMAP.yaml` and what the club app, SSO, Manage, the support
site and the 21 plugins do today.

What this list is **not**: it does not repeat ideas that are already written
down. The backlog's open items (contact book, paid event sign-up, support by
mail, social sign-in, posts as a plugin, custom domains) and its "Ideas (not
planned)" 36 to 55 (family accounts, group chat, newsletter, automations,
report builder, account merge, onboarding funnel, club notes, admin
broadcast, per-club restore, in-app help, status subscriptions, starter
dashboards, "what's new since your last visit") stay where they are. Where an
idea here builds on one of them, it says so as **B#n** (backlog idea n) or
**B-front n** (backlog front item n). Ideas Mike dropped (ClubDesk/Excel
import, helper shifts, J+S NDS export) are left out.

Effort: **S** about a day, **M** a few days, **L** a week or more.
Area: **App** (club app), **SSO** (sign-in and account), **Manage**
(platform admin), **Support** (support site and cases), **Platform**
(developers, plugins, operations).

Every idea respects the plugin rule: plugins never import or call each
other. Where two plugins meet, core offers a contract (event, action, query,
widget, see [contracts.md](contracts.md)) and each plugin talks only to core.

## Contents

- [Five threads that tie the ideas together](#five-threads-that-tie-the-ideas-together)
- [Ideas](#ideas)
  - [App: members and membership](#app-members-and-membership) (1 to 8)
  - [App: events, trainings and attendance](#app-events-trainings-and-attendance) (9 to 20)
  - [App: communication](#app-communication) (21 to 27)
  - [App: money](#app-money) (28 to 34)
  - [App: board and club admin](#app-board-and-club-admin) (35 to 45)
  - [SSO](#sso) (46 to 55)
  - [Manage](#manage) (56 to 69)
  - [Support](#support) (70 to 78)
  - [Platform and developers](#platform-and-developers) (79 to 85)
- [Roadmap](#roadmap)
  - [Phase 1: quick wins](#phase-1-quick-wins)
  - [Phase 2: foundations](#phase-2-foundations)
  - [Phase 3: next](#phase-3-next)
  - [Phase 4: later](#phase-4-later)
  - [Where to start](#where-to-start)

## Five threads that tie the ideas together

Many ideas are small on their own but share one missing piece. Building the
piece once in core makes the rest cheap, and stops each plugin from
inventing its own version.

| Thread | The missing piece | Ideas it unlocks |
| --- | --- | --- |
| **One letterhead** | A core PDF layout service (`pdf.render` action): logo, address, colours, footer, optional QR-bill. Today invoices, letters, GV minutes and receipts each lay out their own PDF. | 7, 32, 35, 40, 66 |
| **One composer, one router** | Channels as a contract (`notify.channel`): mail, push, Discord, Telegram/Signal/Matrix and SMS register as channels, and a post or notice is sent through the channels the author and each member chose. Today each plugin listens to `post.published` on its own and the author can't see where a post will go. | 12, 21, 23, 24, 25 |
| **One calendar** | A `calendar.items` query contract: events (core), bookings (Booking), fixtures (Teams), year-planner duties (Board), contract deadlines (Board) all appear in one calendar view and one personal feed. | 19, 20, 47 |
| **One statement** | An `invoice.line.add` action contract: plugins hand over open items (drinks tab, bookings, shop orders, event fees) and core bills them on one invoice per cycle instead of many small ones. | 29, 30, 31 |
| **One search, one privacy story** | `search` and `privacy.export` / `privacy.erase` query contracts every module offers, so global search, the revDSG export and deletion, and club backups cover plugin data too. | 39, 60, 83, 84 |

## Ideas

### App: members and membership

| # | Idea | What it does | Builds on | Effort |
| --- | --- | --- | --- | --- |
| 1 | Yearly data check | Before the fee run, each member gets "Is this still right?" (address, phone, emergency contact) in the app and the digest. The board sees who hasn't confirmed and who has no postal address. | Member profile, weekly digest, fee run | S |
| 2 | Pause a membership | A member or the board pauses from/to (injury, semester abroad). Fees stop or drop to a "paused" price on the tier, group mails pause, and it resumes by itself with a note a week before. | Tiers, payment plans, `core/pricing.py`, leave requests | M |
| 3 | Tier change requests | A member asks to switch tier (student to adult, active to passive), with an optional proof file. The board approves; the next invoice is adjusted pro rata. | Leave request flow, core file store, pro-rata pricing | M |
| 4 | Notice periods from the statutes | Club setting such as "leave at the end of the year, 3 months' notice". A leave request shows the earliest exit date and which invoice is still due. | Leave requests, finance settings | S |
| 5 | Member timeline | On the member page: joined, tier changes, groups, functions, invoices, payments, attendance, from the audit log plus plugin queries. A first, member-only step towards the contact book (B-front 7). | Audit log, MemberDetail, contracts | M |
| 6 | Emergency contacts and care notes | For youth sections and camps: emergency contact and care notes (allergies, medication), encrypted with the club key, visible only to the trainers of that member's groups and only on the attendance screen. | Club key encryption (as in Codes), group-scoped roles, attendance | M |
| 7 | Membership confirmation PDF | "Mitgliederbestätigung" a member downloads themselves (for student discounts, insurers, employers), with the club letterhead. | Account › Membership, one letterhead (40) | S |
| 8 | Group space | One page per group for its members: next events, posts, polls, files and who's in it. Members stop jumping between tabs. Files come through a `documents.files.list` query with a group filter. | GroupDetail, `group_id` on events/posts/polls, Documents plugin via contract | M |

### App: events, trainings and attendance

| # | Idea | What it does | Builds on | Effort |
| --- | --- | --- | --- | --- |
| 9 | Self check-in by event QR | The trainer shows a QR that changes every 30 seconds; members scan it with the app to mark themselves present, only within the event's time window. The opposite direction of the Keys plugin, where the trainer scans the member card. | Attendance, PWA | S |
| 10 | Offline attendance | Take attendance in a gym or field with no signal; the PWA keeps the marks and sends them when back online, with a "3 not sent yet" badge. | AttendanceScreen, service worker | M |
| 11 | Trainer substitute request | A lead marks "I can't come". Others who hold the trainer function for that group get "I'll take it" with one tap; if nobody does by N hours before, the group is told (or the training is cancelled). | Functions, events, notifications | M |
| 12 | One-tap cancel with reason | "Cancel today's training: pitch closed" from the event, sent to everyone signed up and the group through every channel they use (push, mail, Discord, messengers). | `event.changed`, push, one router (24) | S |
| 13 | Session notes on series dates | What was trained, private trainer notes, a link to a guide page. Shown on the next date of the series so the next trainer knows. | Event series, attendance | S |
| 14 | Attendance alerts | "Missed 4 trainings in a row" or "below 50% this season": a note to the trainer, optionally a friendly mail to the member. A first fixed rule before general automations (B#39). | Attendance overview, notifications | S |
| 15 | Event templates | Save an event (place, times, capacity, deadlines, description, cover) as a template; "New from template" in the events list. | Events | S |
| 16 | Date-finding poll | A poll with date options; closing it turns the winner into an event and signs up everyone who said yes. | Polls, events, `poll.closed` | M |
| 17 | Events in several languages | Finish B#27 for events: title and description in DE/FR/IT/EN, members see their own language, optional DeepL prefill. | PostLanguagesField, `translate.deepl_key` | M |
| 18 | Public sign-up for any public event | Not only trials: a visitor signs up to a public event (open day, concert, tournament) with name and mail, confirms by link and lands on the guest list. Pairs with paid sign-up (B-front 9). | Trial sign-ups, public club page | M |
| 19 | Book the room with the event | When creating an event, pick a room or item; core asks the Booking plugin through a `booking.slot.request` action and shows "booked" or the conflict. | Events, Booking via contract | M |
| 20 | Club calendar | Month and week view in the club app with events, bookings, fixtures and board duties, each plugin offering its items through `calendar.items`. Filters by group and kind. | Events, Booking, Teams, Board via contract | M |

### App: communication

| # | Idea | What it does | Builds on | Effort |
| --- | --- | --- | --- | --- |
| 21 | Must-read posts | Mark a post "please confirm". Members tap "read"; the board sees who hasn't, and a reminder goes out after N days. For safety rules, rule changes, GV papers. | Posts, digest, reminder tasks | S |
| 22 | Scheduled and expiring posts | "Publish at" and "unpin / hide after" on posts. | Posts, Celery beat | S |
| 23 | One composer, all channels | The post and event forms show which channels will carry it (app, mail, push, Discord, Telegram, Signal, Matrix, SMS), with a toggle and a preview each. Plugins register as channels instead of each listening to `post.published` blindly. | Posts, Discord, Messengers, one router (24) | M |
| 24 | Notification router per member | One matrix per member, kind × channel, including Discord DM and messenger DMs, plus quiet hours. Channels come from a `notify.channel` contract. | `core/notifications/prefs.py`, Discord DMs | M |
| 25 | SMS for urgent notices | SMS through a Swiss gateway as a channel in the Messengers plugin, only for kinds the club allows (cancellations), with a monthly budget cap. | Messengers plugin, one router (24) | S |
| 26 | Comment moderation | Report a comment, hide it, mute someone in comments for N days; a club setting for who moderates. | Post comments, roles | S |
| 27 | Two-way group mail | Replies to a mail sent to a group go to the group's function address and are archived on the group page, using the club's own mail stack. | Mailing lists, function addresses, WildDuck | L |

### App: money

| # | Idea | What it does | Builds on | Effort |
| --- | --- | --- | --- | --- |
| 28 | Fee run preview | Before the yearly invoices go out: totals per tier, changes against last year, members without mail (hand to Letters), members on payment plans, and a sample PDF. | Invoice generation (`finance_tasks`), fee basis | S |
| 29 | One statement per member | Drinks tab, booking fees, shop orders and event fees become open items through `invoice.line.add`; core bills them on one invoice per month or quarter, with a minimum amount. | Invoices, Kasse, Booking via contract | L |
| 30 | Credit notes and refunds | A credit note against an invoice; for card and TWINT payments a refund through a `payments.refund` action; booked in Finances through its contract. | Invoices, Payments, Finances via contract | M |
| 31 | Partial payments | An invoice shows what was paid and what is open, with a QR-bill for the rest; bank import and Stripe both record partial amounts. | QR-bill, bank import, Payments | M |
| 32 | Donation receipts per year | In January, one tax receipt PDF per donor for all donations of the past year, mailed or sent by Letters. | Supporters, one letterhead (40) | S |
| 33 | Treasurer cockpit | A ready-made "Kasse" dashboard: cash today, invoice ageing, expected income this month, budget use, open expense claims; widgets from Finances, Budgets and Kasse. | Own dashboards, widget contract, B#53/54 | S |
| 34 | Auditor access | A time-boxed, read-only role for the auditors (Revisoren): books, invoices and documents, invited by mail, ends after the GV, every view in the audit log. | Roles, invites, audit log | S |

### App: board and club admin

| # | Idea | What it does | Builds on | Effort |
| --- | --- | --- | --- | --- |
| 35 | Function handover pack | When a function changes hands, one page lists what to pass on: keys held (Keys query), codes they can see, open board tasks, documents they own, function mail addresses, and a handover PDF both sign. | Functions, Board, Keys, Codes, Documents via contracts | M |
| 36 | Year-end wizard | One guided list: close the books, budget for next year, fee run, GV invitation, insurance renewals, archive minutes. Core and plugins add steps through a `yearend.steps` query; progress is shared by the board. | Finances, Budgets, Board, Documents via contract | M |
| 37 | Club setup by type | At "Start a club", pick sports club, makerspace, choir, association: preset modules, suggested plugins, tiers, roles, groups and starter dashboards. Changes nothing later. | StartClub, `Feature.default_enabled`, B#54 | M |
| 38 | Templates from the association | A Verband publishes a template (tiers, roles, groups, standard documents) that its member clubs apply with one click. | Federation view, idea 37 | M |
| 39 | Global search | Ctrl+K in the club app: members, events, posts, invoices, groups, plus plugin hits (items, documents, bookings) through a `search` query each module offers, filtered by the viewer's rights. | Table search, contracts | M |
| 40 | One letterhead for every PDF | A core PDF layout service used by invoices, letters, GV minutes, receipts and confirmations through a `pdf.render` action, so a logo change shows everywhere. | Branding, invoice PDF, Letters, Board | M |
| 41 | Statutes assistant | Upload the statutes; the Assistant plugin suggests settings (notice period, quorum, GV invitation deadline, fees) and the board accepts them one by one. Opt-in like the rest of Assistant. | Assistant, Documents, club settings | M |
| 42 | Simpler roles page | Role templates (Trainer, Kassier, Aktuar, Gruppenleiter) and a "what can this person do?" view per member, in plain words instead of permission keys. | Roles and permissions | M |
| 43 | Kiosk mode | A clubhouse tablet paired by QR, locked to a few screens: check-in (Keys), drinks tab (Kasse), today's bookings. Members identify by member card or PIN. Plugins register kiosk screens through a slot. | Keys member card, Kasse, Booking, device sessions | M |
| 44 | Sample data switch | A new club fills itself with demo members, events and invoices to try things out, then removes them with one click. | Sandbox clubs, seeds | M |
| 45 | Wallet pass for the member card | Apple and Google Wallet passes for the Keys member card, updated when the membership ends. | Keys member card | M |

### SSO

| # | Idea | What it does | Builds on | Effort |
| --- | --- | --- | --- | --- |
| 46 | My clubs at a glance | `/clubs` shows per club: next event, open invoices, unread posts, open polls, so someone in three clubs sees everything in one place. | Clubs screen, per-club summary endpoint | M |
| 47 | One calendar feed for all clubs | A personal ICS link with the events of every club the person is in (their groups, or only what they signed up for). | Per-club ICS, one calendar (20) | S |
| 48 | Profile once, shared by choice | Change address or phone in SSO and tick which clubs get it; the club sees "updated by the member". | User and member fields | M |
| 49 | Consent centre | All consents (photos, directory, newsletter, AI drafts) across clubs on one SSO tab, with history and one-click withdrawal. | Consent log (revDSG) | S |
| 50 | Export all my data | One download with the account data plus each club's revDSG export. | revDSG self-service | S |
| 51 | Display preferences once | Font size, high contrast, reduced motion, 24h clock, set once in SSO and applied in all frontends and mails. | SSO settings, Mantine theme | S |
| 52 | Join and trial posters | A printable A4/A6 poster with a QR to the join or trial page, with a source tag so the club sees which poster brought people. | Join page, trial page, public club page | S |
| 53 | Step-up for risky club actions | Re-confirm with passkey or TOTP before bulk deletes, payout or bank changes, and giving admin roles, as Manage already does. | StepUpDialog in Manage, passkeys | S |
| 54 | Recovery through the club | When someone loses every second factor, two admins of their club confirm who it is; reset after a 24 h delay, with a mail to the account. | 2FA, recovery codes | M |
| 55 | Sign in on a shared PC by phone | The login page shows a QR; the person approves on their phone where they're signed in (passkey cross-device), no password typed on the clubhouse PC. | Passkeys, sessions | M |

### Manage

| # | Idea | What it does | Builds on | Effort |
| --- | --- | --- | --- | --- |
| 56 | Club health score | One score per club with reasons (logins, active members, invoices sent, errors, open cases, billing state), sortable, combining B#45, B#46 and B#49. | Tenant trends, billing, alerts | M |
| 57 | Module and plugin usage map | Which clubs use which modules and plugins, which are installed but unused, on which versions. Feeds the roadmap. | Modules, plugin installs | S |
| 58 | Upgrade impact check | Before a core release, list clubs whose plugin versions need a higher `hubra:` minimum or use removed APIs; warn in Releases and in the release check. | Plugin loader, index, release check | S |
| 59 | Post-deploy steps run themselves | After a deploy, one job runs pending migrations, seed and `sync-permissions` for every schema and reports in Manage, so "Mike: flask db upgrade" disappears from PRs. | `upgrade_tasks`, startup lock, Jobs page | M |
| 60 | Platform search | One box for clubs, people, cases, error groups, invoices and request ids. | `search_users`, `search_audit`, contracts (39) | S |
| 61 | Cost per club | Storage, mail volume, job time and API calls per club against plan revenue, giving a margin per plan. | Quota tasks, billing overview | M |
| 62 | Soft limits with an upgrade prompt | Near a plan limit the club admin sees which plan fits and upgrades in one click; at the limit, a grace period instead of a hard stop. | Plan limits, Stripe self-service | S |
| 63 | Association billing | A Verband pays for its member clubs on one invoice, with a seat per club. | Federation, Stripe Billing, plan tiers | L |
| 64 | Referral discount | A club invites another club; both get a coupon once the new club pays its first invoice. | Stripe coupons, billing | S |
| 65 | Release rings | Early-access clubs get a feature flag first, then it widens on a schedule; a "roll back" button turns it off everywhere. | Early access, feature flags | M |
| 66 | DPA self-service | The club admin accepts the data processing agreement (AVV) in the app; a PDF with version and date, and a list in Manage. | Legal URLs, one letterhead (40) | S |
| 67 | Synthetic checks | Every 5 minutes a test club signs in, loads the dashboard and sends a test mail; results feed the status page and alerts. | Health tasks, status page, alerts | M |
| 68 | Marketplace reviews | Club admins rate installed plugins and leave a line; install counts and ratings show in the Marketplace and on plugins.hubra.club. | Marketplace tab, plugin index | M |
| 69 | Translation coverage | Missing strings per language and per plugin, with a link to suggest them. | Translations, translation suggestions | S |

### Support

| # | Idea | What it does | Builds on | Effort |
| --- | --- | --- | --- | --- |
| 70 | Reports carry the request id | "Problem melden" attaches the last request ids and API errors of the session, so staff jump from a case straight to the error group. | Request id, API error details, report store | S |
| 71 | Known issue matching | A new case or error that matches an open error group or incident tells the reporter "we know, we're on it", and mails them when it's fixed. | Error groups, support cases, maintenance | M |
| 72 | "Shipped" mails | When a roadmap item or a linked idea ships, everyone who voted or reported it gets a short mail and a note in What's new. | Roadmap votes, `hubra.released` | S |
| 73 | Case to help article | One click turns a good answer on a closed case into a draft help article on support.hubra.club. | Support cases, help content | S |
| 74 | Response targets by plan | Targets per plan, "waiting on us since", and an alert in the platform Discord when one is missed. | B-front 10, plans, platform bot | M |
| 75 | Support access in the club's log | The club sees in its audit log when Hubra staff opened a support session, why and for how long; a club setting can require approval first. | Support sessions, audit log | S |
| 76 | First week for new club admins | A checklist in the club app (invite the board, set tiers, first event, connect bank or Stripe) whose progress shows in Manage next to the onboarding funnel. | B#45, dashboards | S |
| 77 | What's new for my club | What's new shows only changes to modules and plugins the club has, for the reader's role. | What's new, changelogs | S |
| 78 | Status history and maintenance feed | Uptime per component for 90 days and an ICS/RSS feed of planned maintenance. | Status page, maintenance windows | S |

### Platform and developers

| # | Idea | What it does | Builds on | Effort |
| --- | --- | --- | --- | --- |
| 79 | Claude connector can draft | Write tools in the MCP server that create a post, event or invoice as a draft for a person to publish, under a separate token scope. | `app/mcp`, API token scopes | M |
| 80 | No-code integrations | An n8n / Make app on top of webhooks and tokens, with ready recipes (new member to a sheet, paid invoice to accounting). | Webhooks, API tokens | M |
| 81 | Plugin playground | `bnb` / `hubra` CLI boots core plus one plugin with sample data and contract mocks, and runs a contract compatibility test. | Plugin template, hubra-cli, contracts | M |
| 82 | Contract catalogue | Generated pages listing every event, action, query and widget with its schema, and which plugins offer or use it, on plugins.hubra.club. | Contract registry, plugin index | S |
| 83 | Plugin data in privacy export and deletion | Plugins declare personal data through `privacy.export` and `privacy.erase` queries, so the revDSG export and member deletion cover them. | revDSG, contracts | M |
| 84 | Plugin data in club backups and moves | Plugins declare their tables for the per-club backup, restore and move (B#48). | Backups, B#48 | M |
| 85 | Accessibility in CI | An axe check on the main club app flows in the Playwright suite, plus a high-contrast theme. | `docs/accessibility.md`, browser tests | M |

## Roadmap

Four phases. Within a phase the order is the order to build in. Each row
says what it needs first and how it would be built. "Migration" means a new
table or column (and the usual `flask db upgrade` until idea 59 lands).

### Phase 1: quick wins

Small, mostly self-contained, no new contracts. Good for one overnight run,
one PR each. About 3 to 4 weeks of work in total.

| Order | # | Idea | Needs | How |
| --- | --- | --- | --- | --- |
| 1 | 59 | Post-deploy steps run themselves | none | Extend `core/tasks/upgrade_tasks.py`: after a new build id, take the startup lock, run Alembic per schema, `seed` and `sync-permissions`, write a report row; show it on Manage › Jobs. Platform setting to switch it off. Do it first: it removes a manual step from every later PR. |
| 2 | 58 | Upgrade impact check | none | Release check reads installed plugin versions per club and their `hubra:` range from the index; lists clubs at risk on Manage › Releases and fails the dry run if a bundled plugin is out of range. |
| 3 | 70 | Reports carry the request id | none | `reportStore.ts` keeps the last 10 request ids from response headers; the report sends them; the case page links to `ApiErrors` filtered by id. No migration (stored in `details`). |
| 4 | 28 | Fee run preview | none | Dry-run mode of `_generate_invoices` returning lines without writing; a preview modal in Finanzen › Rechnungen. |
| 5 | 12 | One-tap cancel with reason | none | Event action "Cancel" with a reason field; sets status, fires `event.changed` with `cancelled=true`; mail + push templates. Plugins already listening (Discord, Messengers) pick it up. |
| 6 | 15 | Event templates | migration | Table `event_templates` (JSON of event fields); "Save as template" and "New from template" in EventsTab. |
| 7 | 22 | Scheduled and expiring posts | migration | `posts.publish_at`, `posts.hide_at`; beat task publishes and fires `post.published` at that time. |
| 8 | 21 | Must-read posts | migration | `posts.requires_ack`, table `post_reads`; reminder through `reminder_tasks`; "not confirmed" list on PostDetail. |
| 9 | 4 | Notice periods from the statutes | settings | Membership settings `leave.notice_months`, `leave.at` (year end, quarter end); LeaveRequests computes the exit date. |
| 10 | 47 | One calendar feed for all clubs | none | SSO endpoint signs a per-user ICS token and merges each club's events the user may see. Later takes `calendar.items` (20). |
| 11 | 52 | Join and trial posters | none | Club app Settings › Public page: a PDF poster with QR (`?src=poster-n`); join and trial store `src`. |
| 12 | 72 | "Shipped" mails | none | On `hubra.released`, find ROADMAP.yaml items whose `version` matches and mail voters and linked case reporters once. |
| 13 | 73 | Case to help article | none | Manage support case action writes a draft into the help content source (PR to `support-frontend/src/content` via hubra-cli, or a `help_articles` table if help moves to the DB). |
| 14 | 75 | Support access in the club's log | setting | Write a club audit entry when a support session starts and ends; club setting `support.require_approval`. |
| 15 | 77 | What's new for my club | none | Tag changelog entries with module codes (CHANGELOG front matter); filter by the club's modules and the reader's role. |
| 16 | 57 | Module and plugin usage map | none | Manage page from existing installs plus last-use timestamps (count of rows touched in 30 days per module). |
| 17 | 62 | Soft limits with an upgrade prompt | none | Limit checks return `LIMIT_NEAR` with the suggested plan; club app banner; grace period as a platform setting. |
| 18 | 26 | Comment moderation | migration | `post_comments.hidden_at`, `comment_reports`; permission `posts.comments.moderate`. |
| 19 | 13 | Session notes on series dates | migration | `club_events.trainer_notes` (private) and `session_notes` (shown to the group). |
| 20 | 33 | Treasurer cockpit | none | A starter dashboard definition using existing finance widgets; add missing widgets in Finances, Budgets, Kasse (each plugin, no cross-imports). |
| 21 | 69 | Translation coverage | none | Manage › Translations: per-language and per-plugin missing keys from the locale files and plugin bundles. |
| 22 | 50 | Export all my data | none | SSO job builds a zip from the account data and each club's revDSG export endpoint. |
| 23 | 53 | Step-up for risky club actions | none | Reuse the Manage step-up check (`stepUp`) on chosen club routes; a decorator `@requires_step_up`. |
| 24 | 64 | Referral discount | settings | Referral code per club; Stripe coupon applied on both sides after the first paid invoice (billing webhook). |

### Phase 2: foundations

The five threads from the top of this document. Each is a core contract
with the first one or two users, so later ideas become small. Build these
before phase 3. About 4 to 5 weeks.

| Order | # | Idea | Needs | How |
| --- | --- | --- | --- | --- |
| 1 | 83 | Plugin data in privacy export and deletion | none | Core query contracts `privacy.export` (returns JSON per member) and action `privacy.erase`; revDSG export and member deletion call every module that offers them. Template: a CI check that a plugin with personal data offers both. Do first: it closes a gap in a legal promise. |
| 2 | 40 | One letterhead for every PDF | none | `core/services/pdf.py` (layout, branding from club profile, QR-bill block) behind a `pdf.render` action; move invoice PDF onto it; Letters and Board switch in their next release. |
| 3 | 24 | Notification router per member | none | `notify.channel` contract (`send(member, kind, message)`); core mail and push register as channels; Discord and Messengers register theirs. Prefs table gets channel × kind and quiet hours; the router picks channels per member. |
| 4 | 23 | One composer, all channels | 24 | Post and event forms ask core for available channels; a per-post `channels` field; plugins read it from the event payload instead of always posting. |
| 5 | 20 | Club calendar | none | `calendar.items` query (range, viewer) offered by events in core and by Booking, Teams and Board; a calendar screen in the club app. |
| 6 | 39 | Global search | none | `search` query (text, viewer) with a small result model; core offers members, events, posts, invoices, groups; plugins add theirs. Ctrl+K dialog in the club app. |
| 7 | 29 | One statement per member | 40 | `invoice.line.add` action (member, amount, text, source ref) storing open items; a billing cycle setting; the invoice task bundles open items. Kasse and Booking move from their own invoices to lines in their next release. |

### Phase 3: next

Bigger features that use the foundations. One PR per idea, roughly in this
order. About 8 to 10 weeks.

| Order | # | Idea | Needs | How |
| --- | --- | --- | --- | --- |
| 1 | 9 | Self check-in by event QR | none | Signed, time-limited token per event (HMAC with a 30 s step); `/events/<id>/check-in` marks attendance for the signed-in member. |
| 2 | 1 | Yearly data check | none | Table `profile_confirmations`; a digest section and app banner from a date before the fee run; list on Members. |
| 3 | 2 | Pause a membership | migration | `member_pauses` (from, to, reason); pricing reads pauses; tier gets an optional pause price; groups skip paused members in mails; beat resumes. |
| 4 | 3 | Tier change requests | 2 helpful | Table `tier_change_requests` with optional file (core file store); approval in Members › Requests next to leave requests; pro-rata through `pricing.py`. |
| 5 | 16 | Date-finding poll | none | Poll type `dates`; on `poll.closed` create the event and sign up the yes voters. |
| 6 | 11 | Trainer substitute request | none | `event_cover_requests`; offered to holders of the group's trainer function; a beat task escalates N hours before. |
| 7 | 14 | Attendance alerts | none | Group setting with thresholds; a nightly task on attendance stats; note to trainers through the router (24). |
| 8 | 21+12 follow-up | Cancellation through the router | 24 | Move cancel and must-read reminders onto the router so members get them on their chosen channel. |
| 9 | 8 | Group space | 20, 39 | Group page for members using events, posts, polls and `documents.files.list` (new query in Documents). |
| 10 | 5 | Member timeline | 83 | Read audit log plus a `member.timeline` query plugins can offer; show on MemberDetail. Shares the model the contact book (B-front 7) needs. |
| 11 | 18 | Public sign-up for any public event | none | Generalise `trial_signups` into `event_guest_signups` (or add a `kind`); confirm link; guest list on the event. Then B-front 9 adds a price. |
| 12 | 17 | Events in several languages | none | Same pattern as posts (`event_translations`). |
| 13 | 30 | Credit notes and refunds | 29, 40 | Credit note as a negative invoice linked to the original; `payments.refund` action in Payments; Finances books it through its contract. |
| 14 | 34 | Auditor access | none | Role template "Revisor" with read scopes and `expires_at` on the role assignment; invite by mail without full membership. |
| 15 | 42 | Simpler roles page | none | Role templates from seed data; "what can they do" built from permission labels grouped by page. |
| 16 | 35 | Function handover pack | 40 | `function.handover` query each module can offer (Keys: keys held, Board: open tasks, Documents: owned files); core page and PDF. |
| 17 | 36 | Year-end wizard | none | `yearend.steps` query (title, done, link); core screen with shared progress per year. |
| 18 | 37 | Club setup by type | none | Presets in seed data (modules, tiers, roles, groups, dashboards); StartClub shows the choice; plugins suggested, not installed silently. |
| 19 | 32 | Donation receipts per year | 40 | In Supporters: a January task building one receipt per donor through `pdf.render`. |
| 20 | 7 | Membership confirmation PDF | 40 | Account › Membership button; `pdf.render` with a fixed template. |
| 21 | 66 | DPA self-service | 40 | Platform setting with the AVV version and text; club admin accepts; PDF; list in Manage. |
| 22 | 46 | My clubs at a glance | none | `/global/me/summary` fans out to each club's summary (next event, open invoices, unread, polls); cached per user. |
| 23 | 49 | Consent centre | none | SSO tab reading the consent log of each club. |
| 24 | 51 | Display preferences once | none | User preferences in SSO; theme provider in `@hubra/ui` reads them; mail templates honour the font size. |
| 25 | 48 | Profile once, shared by choice | none | `user_profile_shares` (user, club, fields); a change updates the member rows of chosen clubs and logs it. |
| 26 | 56 | Club health score | 57 | A nightly score from tenant trends, billing state, errors and cases; Manage list and club detail panel. |
| 27 | 60 | Platform search | 39 | Manage search across tenants, users, cases, error groups, request ids. |
| 28 | 71 | Known issue matching | 70 | Link cases to error groups by request id and fingerprint; banner for the reporter; mail on resolve. |
| 29 | 74 | Response targets by plan | B-front 10 | Plan field `support_target_hours`; beat task alerts the platform Discord. |
| 30 | 76 | First week for new club admins | none | Checklist from club state (counts), a dashboard card, and the step reached in Manage's funnel. |
| 31 | 19 | Book the room with the event | 20 | `booking.slot.request` action in Booking; events form asks if Booking is on for the club. |
| 32 | 82 | Contract catalogue | none | Build step in hubra-plugins reads each plugin's `provides` / `uses` and core's registry; static pages. |

### Phase 4: later

Large, or waits for something outside the code (a provider, a decision, the
foundations being in use for a while).

| Order | # | Idea | Needs | How |
| --- | --- | --- | --- | --- |
| 1 | 10 | Offline attendance | 9 | IndexedDB queue in the PWA, background sync, conflict rule "last mark wins". |
| 2 | 6 | Emergency contacts and care notes | 42 | Encrypted columns with the club key; read permission bound to the group's trainer role; access logged. Needs a privacy review first. |
| 3 | 43 | Kiosk mode | 53 | Device pairing (`kiosk_devices`), a kiosk token with a narrow scope, a kiosk shell; Keys, Kasse and Booking register screens through a frontend slot. |
| 4 | 45 | Wallet pass | none | In Keys: Apple PassKit signing and Google Wallet API; pass update on `member.left`. Needs developer accounts. |
| 5 | 25 | SMS for urgent notices | 24 | Messengers registers an SMS channel; Swiss gateway; budget per club. |
| 6 | 31 | Partial payments | 29 | Payments table per invoice; QR-bill for the open rest; bank import and Stripe write partial amounts. |
| 7 | 27 | Two-way group mail | 24 | Reply-To on group mails to the function address; WildDuck mailbox per group; archive on the group page. |
| 8 | 38 | Templates from the association | 37 | Export of a club's setup as a template; federation shares it; apply step on the member club. |
| 9 | 41 | Statutes assistant | 40 | In Assistant: read a Documents file through a query, suggest settings as a list the board accepts. |
| 10 | 44 | Sample data switch | 37 | Seed set per club type marked `demo=true`; one action removes everything marked. |
| 11 | 54 | Recovery through the club | none | Recovery request, two admin confirmations, 24 h delay, mail to the account. Needs a security review. |
| 12 | 55 | Sign in on a shared PC by phone | none | QR sign-in session approved from a signed-in device (WebAuthn hybrid or own approval flow). |
| 13 | 61 | Cost per club | 57 | Metering from quota tasks, file store and mail logs; margin per plan in Billing overview. |
| 14 | 63 | Association billing | 56 | Parent Stripe customer for the Verband, seats per member club, plan rules. |
| 15 | 65 | Release rings | none | Ring field on tenants; flags with a ring and a widening schedule; roll-back action. |
| 16 | 67 | Synthetic checks | none | A probe job with a test club and test mailbox; results into health and status. |
| 17 | 68 | Marketplace reviews | none | Ratings table in core, exported to the plugin index at build time. |
| 18 | 78 | Status history and maintenance feed | 67 | Store probe results per day; ICS/RSS from maintenance windows. |
| 19 | 79 | Claude connector can draft | none | New scope `drafts.write`; tools create drafts only; publishing stays a human click. |
| 20 | 80 | No-code integrations | none | n8n community node and Make app over the public API and webhooks. |
| 21 | 81 | Plugin playground | 82 | `hubra plugin dev` in hubra-cli: compose file with core, Postgres and the plugin mounted; contract mocks from the catalogue. |
| 22 | 84 | Plugin data in backups and moves | 83, B#48 | Plugins declare tables in `plugin.yaml`; the per-club backup and restore include them. |
| 23 | 85 | Accessibility in CI | none | `@axe-core/playwright` on the main flows; fail on serious issues; high-contrast theme tokens. |

### Where to start

If only ten get built, these give the most for clubs and for running
Hubra, in this order:

1. **59** post-deploy steps run themselves (every later change gets cheaper to ship)
2. **83** plugin data in the privacy export and deletion (a legal gap today)
3. **70** reports carry the request id, then **71** known issue matching
4. **40** one letterhead (unlocks 7, 32, 35, 66)
5. **24** + **23** one router and one composer
6. **12** one-tap cancel and **21** must-read posts
7. **20** club calendar
8. **2** pause a membership and **4** notice periods
9. **29** one statement per member
10. **56** club health score
