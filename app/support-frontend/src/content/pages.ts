/**
 * Longer texts of the support site that are not help articles: the
 * developer page and the security page. Same Markdown subset as the help.
 * Keep the developer page in step with docs/api-tokens.md and docs/mcp.md.
 */

export const DEVELOPERS = {
  de: `Hubra hat eine REST-API unter \`https://api.hubra.club/api/v1\`. Alles, was die Vereins-App kann, läuft über sie. Für Skripte, Auswertungen und Integrationen gibt es **API-Tokens**.

## API-Tokens

| Art | Beginnt mit | Wer macht ihn | Darf |
| --- | --- | --- | --- |
| Persönlich | \`hbr_pat_\` | ein Mitglied (Admins immer, andere nur wenn der Verein es erlaubt) | was dieses Mitglied in diesem einen Verein darf |
| Verein | \`hbr_club_\` | ein Vereins-Admin | höchstens, was dieser Admin darf |
| Plattform | \`hbr_plat_\` | ein Plattform-Admin | nur lesen, nur Plattform-Routen |

Jeder Token hat seine eigene Liste von **Rechten** (z. B. \`events.events.read\`). Eine Anfrage geht nur durch, wenn die Person es gerade darf **und** das Recht auf dem Token steht.

\`\`\`
curl -H "Authorization: Bearer hbr_pat_…" \\
  https://api.hubra.club/api/v1/app/events/
\`\`\`

## Regeln, die du kennen solltest

- Einen Token machen braucht **Zwei-Faktor** auf dem Konto und eine frische Passwortbestätigung. Das Geheimnis siehst du **nur einmal**.
- Laufzeit 7, 30, 90 oder 365 Tage. Ein Token, der 60 Tage nicht benutzt wurde, endet von selbst.
- **Nicht im Browser:** Anfragen mit \`Origin\`-Header werden abgelehnt. Tokens gehören in Skripte und Server, nie in eine Webseite.
- Anmeldung, Konto, Backups, Plugins und alles mit Passwortbestätigung geht nie mit einem Token.
- Grenzen: 120 Lese- und 30 Schreibanfragen pro Minute und Token.
- **Rollen** gibt ein neues Geheimnis; das alte gilt auf Wunsch noch bis zu 7 Tage weiter, damit Skripte ohne Unterbruch wechseln.
- Schreibende Anfragen stehen im Protokoll des Vereins als «Name (Token «Tokenname»)».

## Claude-Connector

Der Hubra-MCP-Server unter \`https://mcp.hubra.club/mcp\` lässt Claude in Hubra **lesen**: Mitglieder, Anlässe, Anwesenheit, Rechnungen, Umfragen und mehr, je nach den Rechten des Tokens. Er schreibt nie etwas.

\`\`\`
claude mcp add --transport http hubra https://mcp.hubra.club/mcp \\
  --header "Authorization: Bearer hbr_pat_…"
\`\`\`

> Vereinsdaten erreichen den Connector nur, wenn ein Vereins-Admin **KI-Assistenten** erlaubt hat. Ohne diesen Schalter antwortet Hubra mit \`API_TOKEN_AI_OFF\`.

## Öffentliche Daten

Ohne Anmeldung und von jeder Webseite aus abrufbar:

- \`GET /api/v1/public/pricing\`: die öffentlichen Tarife.
- \`GET /api/v1/public/plugins\`: die angebotenen Plugins.
- \`GET /api/v1/global/roadmap\`: die Roadmap mit Stimmen.
- \`GET /api/v1/global/status\`: der Systemstatus.

## Plugins

Eigene Module baust du als Plugin. Die Anleitung, die Vorlage und der Marktplatz sind auf [plugins.hubra.club](https://plugins.hubra.club). Ein Plugin wird signiert und von der Plattform installiert; Vereine schalten es danach wie jedes Modul ein.

## Fehlercodes

| Code | Bedeutung |
| --- | --- |
| \`API_TOKEN_INVALID\` / \`_EXPIRED\` / \`_REVOKED\` (401) | Token falsch, abgelaufen oder widerrufen |
| \`API_TOKEN_SCOPE\` (403) | das nötige Recht fehlt auf dem Token |
| \`API_TOKEN_NOT_ALLOWED\` (403) | diese Route nimmt keine Tokens |
| \`API_TOKEN_READ_ONLY\` (403) | Plattform-Tokens lesen nur |
| \`API_TOKEN_BROWSER\` (403) | Anfrage aus einem Browser |
| \`API_TOKEN_AI_OFF\` (403) | der Verein hat KI-Assistenten nicht erlaubt |
| \`RATE_LIMITED\` (429) | zu viele Anfragen, kurz warten |

Fragen oder eine Route, die fehlt? [Schreib uns](/kontakt) oder [schlage sie vor](/idee).`,
  en: `Hubra has a REST API at \`https://api.hubra.club/api/v1\`. Everything the club app does goes through it. For scripts, reports and integrations there are **API tokens**.

## API tokens

| Kind | Starts with | Made by | May |
| --- | --- | --- | --- |
| Personal | \`hbr_pat_\` | a member (admins always, others only if the club allows it) | what that member may do in that one club |
| Club | \`hbr_club_\` | a club admin | at most what that admin may do |
| Platform | \`hbr_plat_\` | a platform admin | read only, platform routes only |

Each token has its own list of **permissions** (for example \`events.events.read\`). A request passes only if the person may do it right now **and** the permission is on the token.

\`\`\`
curl -H "Authorization: Bearer hbr_pat_…" \\
  https://api.hubra.club/api/v1/app/events/
\`\`\`

## Rules to know

- Making a token needs **two-factor** on the account and a fresh password confirmation. You see the secret **only once**.
- Lifetime 7, 30, 90 or 365 days. A token unused for 60 days ends by itself.
- **Not in the browser:** requests with an \`Origin\` header are refused. Tokens belong in scripts and servers, never in a web page.
- Sign-in, account, backups, plugins and everything that needs a password confirmation never work with a token.
- Limits: 120 reads and 30 writes per minute per token.
- **Rolling** gives a new secret; the old one can keep working for up to 7 days so scripts switch without downtime.
- Writes show in the club's audit log as "Name (Token "token name")".

## Claude connector

The Hubra MCP server at \`https://mcp.hubra.club/mcp\` lets Claude **read** Hubra: members, events, attendance, invoices, polls and more, depending on the token's permissions. It never writes anything.

\`\`\`
claude mcp add --transport http hubra https://mcp.hubra.club/mcp \\
  --header "Authorization: Bearer hbr_pat_…"
\`\`\`

> Club data reaches the connector only when a club admin has allowed **AI assistants**. Without that switch Hubra answers \`API_TOKEN_AI_OFF\`.

## Public data

Without signing in, from any web page:

- \`GET /api/v1/public/pricing\`: the public plans.
- \`GET /api/v1/public/plugins\`: the plugins on offer.
- \`GET /api/v1/global/roadmap\`: the roadmap with votes.
- \`GET /api/v1/global/status\`: the system status.

## Plugins

Build your own modules as a plugin. The guide, the template and the marketplace are on [plugins.hubra.club](https://plugins.hubra.club). A plugin is signed and installed by the platform; clubs then switch it on like any module.

## Error codes

| Code | Meaning |
| --- | --- |
| \`API_TOKEN_INVALID\` / \`_EXPIRED\` / \`_REVOKED\` (401) | token wrong, expired or revoked |
| \`API_TOKEN_SCOPE\` (403) | the permission is missing on the token |
| \`API_TOKEN_NOT_ALLOWED\` (403) | this route takes no tokens |
| \`API_TOKEN_READ_ONLY\` (403) | platform tokens only read |
| \`API_TOKEN_BROWSER\` (403) | request from a browser |
| \`API_TOKEN_AI_OFF\` (403) | the club has not allowed AI assistants |
| \`RATE_LIMITED\` (429) | too many requests, wait a moment |

Questions, or a route that is missing? [Write to us](/kontakt) or [suggest it](/idee).`,
}

export const SECURITY = {
  de: `Wir nehmen die Sicherheit der Vereinsdaten ernst. Hast du eine Schwachstelle gefunden, freuen wir uns über eine Meldung.

## Eine Schwachstelle melden

Schreib an **hi@hubra.club**. Hilfreich sind:

- welche Seite oder Route betroffen ist,
- die Schritte, um es nachzustellen,
- was jemand damit tun könnte.

Wir bestätigen den Eingang innert **3 Arbeitstagen** und halten dich auf dem Laufenden, bis es behoben ist. Auf Wunsch nennen wir dich danach in den Neuigkeiten.

## Bitte beachte

- Teste nur mit deinem eigenen Konto und deinem eigenen Verein. Greif nie auf Daten anderer zu und ändere oder lösche nichts, was nicht dir gehört.
- Keine Last- oder Denial-of-Service-Tests, kein Spam, kein Social Engineering gegen Vereine oder das Hubra-Team.
- Gib uns Zeit zum Beheben, bevor du etwas veröffentlichst (in der Regel 90 Tage).

Wer sich daran hält, muss von uns nichts befürchten.

## Was Hubra schützt

- Konten mit Passwort (Argon2), Zwei-Faktor per App oder Passkey, Mail bei neuen Geräten.
- Jeder Verein in seinem eigenen Datenbankschema, Codes und Geheimnisse mit eigenem Schlüssel pro Verein verschlüsselt.
- Verschlüsselte Backups, auf Wunsch zusätzlich mit dem eigenen Schlüssel des Vereins.
- Server in Europa, keine Werbe- oder Tracking-Dienste.

Den maschinenlesbaren Kontakt findest du unter [security.txt](https://support.hubra.club/.well-known/security.txt).`,
  en: `We take the security of club data seriously. If you found a vulnerability, we are glad to hear about it.

## Report a vulnerability

Write to **hi@hubra.club**. It helps to include:

- which page or route is affected,
- the steps to reproduce it,
- what someone could do with it.

We confirm receipt within **3 working days** and keep you posted until it is fixed. If you like, we credit you in the release notes afterwards.

## Please

- Only test with your own account and your own club. Never access other people's data, and don't change or delete anything that isn't yours.
- No load or denial-of-service tests, no spam, no social engineering against clubs or the Hubra team.
- Give us time to fix it before you publish anything (usually 90 days).

If you stick to this, you have nothing to fear from us.

## What protects Hubra

- Accounts with passwords (Argon2), two-factor by app or passkey, a mail on new devices.
- Every club in its own database schema; codes and secrets encrypted with a key per club.
- Encrypted backups, optionally also to the club's own key.
- Servers in Europe, no advertising or tracking services.

The machine-readable contact is at [security.txt](https://support.hubra.club/.well-known/security.txt).`,
}
