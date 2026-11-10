# German glossary (de-CH)

Hubra's German is Standard German with Swiss spelling. It is not Swiss
German dialect. This applies to the club app, Manage, SSO/join, support,
plugins and mails. The old dialect texts are retired: don't bring back
"isch", "Rächnige", "Iistellige" and the like.

## Conventions

- **Spelling:** Swiss, so always `ss`, never `ß` (`Grösse`, `schliessen`).
  The i18n test fails on `ß`.
- **Address:** informal "du", lower case. Never "Sie".
- **Quotes:** Swiss guillemets «…» (inner ‹…›). Not „…“ or "…".
- **Paths in the UI:** `Einstellungen › Module › Briefe`, with `›` and
  spaces. Not `→` or `>`. Name the menu entries exactly as they are
  labelled in the app.
- **Gender forms:** slash form `Inhaber/in`, `Kassier/in`, plural
  `Spieler/innen`. No colon or star forms (`Inhaber:in`, `Spieler*innen`).
  Where a neutral word fits (`Leitung`, `Mitglied`, `Person`), use that.
- **Abbreviations:** `z. B.`, `d. h.`, `inkl.` with spaces between the
  parts.
- **Ellipsis:** `…` after a space in placeholders: `Suchen …`.
- **English words** stay where they are the common term: Login, Dashboard,
  Widget, Webhook, Passkey, Check-in, Discord, Plugin. Write `E-Mail`
  (but `Mail` in compounds such as `Mailprogramm`, `Vereinsmails`) and
  `Website`, never `Webseite`.
- **Placeholders** (`{{name}}`, `{n}`) are kept as they are in English.

## Key terms

| English                  | German                      | Notes                                         |
| ------------------------ | --------------------------- | --------------------------------------------- |
| Event                    | Anlass, Anlässe             | not Veranstaltung or Event                    |
| Training                 | Training                    |                                               |
| Trial training           | Schnuppertraining           | not Probetraining                             |
| Member                   | Mitglied                    |                                               |
| Board                    | Vorstand                    |                                               |
| Tier (membership)        | Stufe                       | Mitgliedschaftsstufe where it needs context   |
| Function                 | Funktion                    | a role held in the club, e.g. Kassier/in      |
| Group                    | Gruppe                      |                                               |
| Post                     | Beitrag                     |                                               |
| Poll                     | Umfrage                     |                                               |
| Transaction / booking    | Buchung                     | verb: buchen                                  |
| Invoice                  | Rechnung                    |                                               |
| Invoice reminder         | Zahlungserinnerung          | not Mahnung                                   |
| Expense claim            | Spesen                      |                                               |
| Induction / instruction  | Einweisung, eingewiesen     | not Einführung                                |
| Check out (an item)      | ausleihen                   |                                               |
| Suspended (member)       | Gesperrt                    | not pausiert                                  |
| Archived                 | Archiviert                  |                                               |
| Owner                    | Inhaber/in                  |                                               |
| Holder (of a key)        | Inhaber/in                  |                                               |
| Mobile (phone)           | Mobil                       |                                               |
| Email address            | E-Mail-Adresse              |                                               |
| Website                  | Website                     |                                               |
| Settings                 | Einstellungen               | last tab of a page that has settings          |
| Modules                  | Module                      | Einstellungen › Module                        |
| Account (club app)       | Konto                       | tabs: Im Verein, Mitgliedschaft               |
| My account (SSO)         | Mein Konto                  |                                               |
| Two-factor sign-in       | Zwei-Faktor-Anmeldung       |                                               |
| Sign in / sign out       | anmelden / abmelden         |                                               |
| Notifications            | Benachrichtigungen          |                                               |
| Shared inbox             | Gemeinsames Postfach        |                                               |
| Platform admin           | Plattform-Admin             | Manage is the platform's admin site           |
| Alerts (Manage)          | Warnungen                   |                                               |

## Where texts live

- Club app: `app/frontend/src/locales/{de-CH,en}/translation.json` and the
  seed files `app/backend/hubra/core/seed_data/translations/{de-CH,en-GB}.json`
  (same keys and values; `tests/i18n` checks them). When you change a
  shipped value, add the old one to `superseded.json`.
- Manage, SSO and support: `tr('Deutsch', 'English')` in the code.
- API errors: `packages/api-client/src/errors.ts` (German by message, pattern
  or code).
- Plugins: each plugin's `frontend/src/translations.json`.
