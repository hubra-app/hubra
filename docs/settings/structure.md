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
    Mitgliedschaft, Module (switch on/off), Verbundene Apps, API & Webhooks, Domains,
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
| Einstellungen › API & Webhooks | API access switches, sign-in apps, webhooks | core tables | was "API & Apps" |
| Einstellungen › Verschlüsselung | club backup key | | |
| Einstellungen › Domains | own domains | | |
| Einstellungen › Hubra-Abo | plan, add-ons, licences | | |
| Einstellungen › Rollen / Protokoll | roles; audit log | | own URLs (/app/system, /app/audit-log) shown as tabs |
| Einstellungen › Erweitert | raw key/value store | club `setting` table | |
| Finanzen › Einstellungen | fee schedule, invoices and reminders, plugin cards (`finance.settings`, e.g. monthly statement), external parties, Bank & QR | `TenantFeature.config["finance"]` | **was also editable in the Module dialog** (fixed, below) |
| Finanzen › Einstellungen › Beitragsgrundlage | fee basis source, extra, manual value | `TenantFeature.config["finance"]` | was under Budget & Beiträge |
| Events, Posts, Polls | notify members, reminder hours, event types | `TenantFeature.config` | Module dialog, opened by the page's Einstellungen button |
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

Old URLs redirect (`LEGACY_REDIRECTS` in `app/admin-frontend/src/nav/index.tsx`),
so links in old Discord messages and mails keep working.

## Done in this round

- Manage: one Einstellungen tab per page as above; DeepL key and address
  get a form.
- Club app: Einstellungen › Module › Finanzen › "Einstellungen" opens
  Finanzen › Einstellungen instead of a second form for the same values.
- Club app: `/app/settings/modules?module=<code>` opens a module's settings,
  so pages can link to their own settings.

## Second round (Mike, 2026-11-09: "Sounds good")

All eight questions were answered yes:

1. Messengers and Assistant link to `?module=messengers` / `?module=assistant`
   (plugin PRs, release each).
2. Events, Posts, Polls: an "Einstellungen" button in the page head opens
   their module settings (admins with `modules.modules.write`).
3. Posteingang: the mailbox dialog becomes a Posteingang › Einstellungen tab
   (plugin PR).
4. Payments: `/app/payments` splits into the payment list and a Zahlungen ›
   Einstellungen tab (plugin PR).
5. Beitragsgrundlage moved to Finanzen › Einstellungen (after Abrechnung).
   `/app/finance/fee-basis` still opens it.
6. "API & Apps" is now "API & Webhooks".
7. Manage › Plattform (`/app/platform/general`) holds the legal links and the
   support site address. Zahlungen and Meldungen & Ideen no longer show them.
8. A module manifest may name `settings_page="/app/…"`. Einstellungen › Module
   then opens that page (button and `?module=<code>`) instead of the form.
   Finance uses it; plugins can too.

## Where the code lives

- Each manage page is its own file, `app/admin-frontend/src/nav/pages/<page>.tsx`
  (`definePage(section, position, () => page)`); the sections and their order are in
  `nav/registry.tsx`. A new page is a new file; nothing else changes.
- A settings group that is only fields (title, description, fields, reset) is its own file,
  `app/admin-frontend/src/screens/platform/settings/<group>.ts` (`defineSettings`), with the
  German labels of its keys. Show it with `<SettingsSection section="<group>" />` in the page's
  settings tab. Groups with buttons of their own (mail relay test, Discord channels) stay in
  `SettingsSection.tsx`.
