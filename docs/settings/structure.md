# Where settings live (audit and structure, November 2026)

Mike, 2026-11-09: "Settings seem to be all over the place, some modules have
their own settings pages or even settings in subviews. Others have settings in
general settings. Same for manager."

This page lists every place a club admin or a platform operator changes a
setting today, then the one structure both apps follow from now on, and what
is still left to move.

## The structure

**One rule for both apps: a setting lives on the page it configures, in that
page's last tab, called "Einstellungen".** The central page only holds what
belongs to no single page, and lists the rest.

- **Club app**
  - *Einstellungen* (sidebar) holds what is about the whole club: Verein,
    Mitgliedschaft, Module (switch on/off), Verbundene Apps, API, Domains,
    Verschlüsselung, Hubra-Abo, Rollen, Protokoll, Erweitert.
  - A module's own settings are edited in one place only. When the module has
    a settings page of its own (Finanzen › Einstellungen), that is the place,
    and Einstellungen › Module links there. Otherwise it is the module's form
    under Einstellungen › Module, which any page can open directly with
    `/app/settings/modules?module=<code>`.
  - Settings of one thing (one mail address, one team, one mailbox, one
    resource) stay with that thing, in its edit dialog. They are data, not
    settings pages.
  - Personal settings stay under *Mein Konto*.
- **Manage**
  - Every page that has platform settings ends with an *Einstellungen* tab at
    `…/settings`, visible with `platform.settings`. Status and lists come
    first, settings last. There is no catch-all settings page (removed in
    hubra#153, which stays the rule).

## Audit: club app (core)

| Where | What it controls | Stored in | Notes |
| --- | --- | --- | --- |
| Einstellungen › Verein | name, description, logo, colours, region and language, banner, privacy, 2FA | `Tenant.settings["branding"]` | |
| Einstellungen › Mitgliedschaft | leaving needs approval, join requests, invite validity | `Tenant.settings` | |
| Einstellungen › Bank & QR-Rechnung | IBAN, creditor for QR bills | club `setting` table | moves to Finanzen › Bank & QR when Finance is on (redirect) |
| Einstellungen › Module | switch modules on/off; per-module form in a dialog | `TenantFeature.config` | finance, events, posts, polls and plugin fields |
| Einstellungen › Verbundene Apps | Discord and other connections; plugin slot `apps.connection` | plugin tables | |
| Einstellungen › API & Apps | API access switches, sign-in apps, webhooks | core tables | name is close to "Verbundene Apps" (see questions) |
| Einstellungen › Verschlüsselung | club backup key | | |
| Einstellungen › Domains | own domains | | |
| Einstellungen › Hubra-Abo | plan, add-ons, licences | | |
| Einstellungen › Rollen / Protokoll | roles; audit log | | own URLs (/app/system, /app/audit-log) shown as tabs |
| Einstellungen › Erweitert | raw key/value store | club `setting` table | |
| Finanzen › Einstellungen | fee schedule, invoices and reminders, plugin cards (`finance.settings`, e.g. monthly statement), external parties, Bank & QR | `TenantFeature.config["finance"]` | **was also editable in the Module dialog** (fixed, below) |
| Finanzen › Budget & Beiträge › Beitragsgrundlage | fee basis source, extra, manual value | `TenantFeature.config["finance"]` | finance setting on a planning tab |
| Events, Posts, Polls | notify members, reminder hours, event types | `TenantFeature.config` | only in the Module dialog; the pages have no link |
| Mail › Adressen › dialog | one address: forwarding, aliases, prefix | mail tables | per thing, stays |
| Mein Konto › Einstellungen | personal: profile in the club, membership, notifications | user tables | personal, stays |

## Audit: plugins

| Plugin | Where | What | Notes |
| --- | --- | --- | --- |
| assistant | Module dialog | consent, API key | page links to `/app/settings/modules` (not to its own form) |
| messengers | Module dialog | Telegram/Signal/…, what to announce | page has an "Einstellungen" button to `/app/settings/modules` |
| inventory | Module dialog | longest checkout | |
| keys | Module dialog | Nuki token | |
| letters | Module dialog | address window side, … | |
| finances | Finanzen › Einstellungen (slot `finance.settings`) | monthly statement | already on the page it configures |
| discord | Einstellungen › Verbundene Apps (slot `apps.connection`) | server, channels, roles | |
| payments | its own page `/app/payments` | club's Stripe account, fee pass-on | the whole page is settings |
| imap-inbox | Posteingang › dialog "Postfächer" | IMAP mailboxes | settings in a dialog on the page |
| teams, booking, kasse, documents, … | edit dialogs | one team / resource / product | per thing, stays |
| bank-import, budgets, board, codes, community, forms, guides, supporters | none | | no club settings |

## Audit: Manage

| Page | Before | Now |
| --- | --- | --- |
| Alle Vereine | limit warning under Tarife & Preise | Alle Vereine › Einstellungen |
| Warnungen | cooldown, retention, link below the rules | Warnungen › Einstellungen |
| Diagnose | slow request/query, auto-resolve below Leistung | Diagnose › Einstellungen |
| Backups | tab "Speicher" | same content, tab "Einstellungen" (`/settings`) |
| Mail | two tabs, Relay and Systemabsender, in the middle | one Mail › Einstellungen tab, last |
| Discord | two tabs, Einrichtung and Kanäle | one Discord › Einstellungen tab |
| Übersetzungen | DeepL key had **no field anywhere** | Übersetzungen › Einstellungen |
| API-Tokens | connector address under Meine Tokens, self-registration under Apps | API-Tokens › Einstellungen |
| Vereinsdomains, Zahlungen | page is only settings | unchanged |
| Meldungen & Ideen | support site address below the list | unchanged (page draws its own heading; see questions) |
| Wartung | maintenance mode | unchanged (an action, not a setting) |

Old URLs redirect (`LEGACY_REDIRECTS` in `app/admin-frontend/src/nav.tsx`),
so links in old Discord messages and mails keep working.

## Done in this round

- Manage: one Einstellungen tab per page as above; DeepL key and address
  get a form.
- Club app: Einstellungen › Module › Finanzen › "Einstellungen" opens
  Finanzen › Einstellungen instead of a second form for the same values.
- Club app: `/app/settings/modules?module=<code>` opens a module's settings,
  so pages can link to their own settings.

## Questions (not done: they change behaviour or need plugin releases)

1. **Messengers and Assistant** link to `/app/settings/modules`. Point them at
   `?module=messengers` / `?module=assistant` (plugin release each).
2. **Events, Posts, Polls**: add an Einstellungen link or tab on their pages
   that opens their module settings.
3. **Posteingang (imap-inbox)**: move the mailbox dialog into a Posteingang ›
   Einstellungen tab (plugin release).
4. **Payments**: split `/app/payments` into the payment list and a Zahlungen ›
   Einstellungen tab for the Stripe account and fees (plugin release).
5. **Fee basis** sits under Finanzen › Budget & Beiträge › Beitragsgrundlage; move it to
   Finanzen › Einstellungen?
6. **Naming**: "API & Apps" next to "Verbundene Apps" is confusing; rename to
   "API & Webhooks"?
7. **Legal links** (privacy, terms, imprint) sit on Manage › Zahlungen, but
   are used by sign-up and every footer. A small Manage page "Plattform"
   (legal links, support site address) would fit better.
8. **Plugin manifest**: let a plugin declare its own settings page
   (`settings_page=`), so Einstellungen › Module links there the way it does
   for Finance, without a list in core.
