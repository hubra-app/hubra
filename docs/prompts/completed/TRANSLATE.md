Translate the entire frontend UI to Swiss German (Schweizerdeutsch), using <https://vollbuild.die-ganz-witzige.ch/> as the authoritative style and spelling reference — this is the club's own public-facing website and establishes the exact register, vocabulary, and orthography to match throughout the management app, so the member-facing tool feels consistent with the public site's voice.

## Style reference — confirmed conventions from vollbuild.die-ganz-witzige.ch

Use this site's actual word choices and spelling as the canonical standard. Examples observed directly on the site to follow consistently:

- "wärde" (not "werde"/"werden") — e.g. "Mitglied wärde", "Offe für nüüi Mitglieder"
- "gmeinsam" (not "gemeinsam") — e.g. "Gmeinsam bastle, wärche und chille"
- "Ruum" (not "Raum") — e.g. "Ruum ahluege", "Dä Ruum"
- Double vowels for long sounds: "Wärchzüüg", "Züüg", "Näihe", "üüs", "Bibedibabedi"
- "isch" (not "ist") — "VollBuild isch de Makerspace..."
- "bisch" (not "bist") — "wenn interessiert bisch"
- "send" (not "sind") — "Mir sind es Grüppli" (note: site uses both "sind" and would more dialectally be "send" — verify per-context, but lean toward the site's own actual usage where it appears)
- "gärn" (not "gerne") — "wo gärn bastlet"
- "dezwüsche" (not "dazwischen")
- "Schniid dich los" (imperative dialect form)
- "Üses Verein", "Üüs" for "uns"/"unser"
- "Geräte" stays close to standard spelling — not everything is maximally dialectal; the site mixes near-standard German nouns (Geräte, Maschine, Events, Kontakt, Material, Status) with strongly dialectal verbs/connectors — follow this same balance, don't over-dialect-ify nouns that the site itself keeps closer to standard
- **"Login" stays English** — confirmed directly: "Mitglieder-Login" is used as-is, validating the English-loanword convention from the original prompt
- **Informal address confirmed** — "wenn interessiert bisch", "Schriib üüs" — second-person informal throughout, consistent with the "Du" assumption

Where the site doesn't cover a specific word/concept needed in the management app (e.g. form-specific terms like "Pflichtfeld", "Passwort vergässe", error states, table headers, pagination), extrapolate using the SAME spelling conventions and register demonstrated above, rather than defaulting to Hochdeutsch or inventing a different dialect style. When in doubt about how the site would phrase something, lean toward the more standard-leaning treatment the site gives nouns/technical terms (as seen with "Geräte", "Material", "Events", "Status", "Kontakt") while keeping verbs, pronouns, and connecting words dialectal (gmeinsam, wärde, gärn, üüs, dezwüsche, bisch, isch).

## Everything else from the original task spec applies unchanged

1. **Keep common English tech/UI terms as-is** where natural (Login — now directly confirmed by the reference site — Account, Dashboard, Tab(s), Update/Upload/Download, Email, Link, App, Browser). Translate Password → "Passwort". Use judgment per string, leaning English for tech-native terms a Swiss user would say in English day-to-day.

2. **Informal "Du" form throughout** — confirmed correct via the reference site's own usage.

3. **i18n framework setup** — first check whether one already exists:
   grep -rln "useTranslation\|i18next\|react-intl\|FormattedMessage" app/frontend/src/

   If none exists, flag this and recommend react-i18next as a prerequisite before hardcoding any translated strings — do not hardcode Swiss German directly into JSX components. Confirm with me before taking on the i18n setup work itself, since it's a separate architectural task from translation.

   Configure the i18n setup so that any missing Swiss German translation key falls back to the existing English/German locale rather than displaying the raw key string or breaking the page. Confirm this fallback behavior works correctly by testing with a deliberately incomplete locale file before full rollout.

4. **Section-by-section rollout** with check-ins — translate one blueprint/page area at a time (dashboard/account, members, groups, mail, events, polls, settings, etc.), show me 5-10 sample translated strings in context after each section before continuing, so we can catch tone/register drift early against the reference site's voice.

5. **Critical clarity exceptions** — form validation and error messages must stay unambiguous even in dialect; don't sacrifice clarity for dialect authenticity on messages like "Password too short" or "This field is required." Use the more standard-leaning treatment here if a fully dialectal phrasing would reduce clarity, consistent with how the reference site keeps technical/precise terms closer to standard spelling.

6. **Swiss formatting conventions**: DD.MM.YYYY dates, 24-hour time, CHF currency with apostrophe thousands separator (1'000) wherever currency/numbers appear (finance blueprint, tier pricing).

7. **Backend email/notification templates are OUT OF SCOPE** for this pass unless explicitly confirmed — ask me explicitly whether verification emails, password reset emails, and other backend-generated notification text should also be translated, since these are separate files from frontend UI strings and may currently be in a different language register entirely.

8. **Do not translate**: code comments, variable/function names, log messages, anything not user-facing.

## Before starting

Report back:

- Whether an i18n framework already exists (which one, current locale structure) — or confirm the recommendation to set up react-i18next first
- Confirm you've internalized the reference site's specific spelling conventions listed above (double vowels for long sounds, wärde/isch/bisch/gärn/gmeinsam/üüs, English Login, near-standard treatment of technical nouns) and will apply them consistently
- Confirm whether backend email/notification templates are in scope

Then proceed section by section with check-ins, matching the voice of <https://vollbuild.die-ganz-witzige.ch/> throughout.

Before starting the Swiss German translation work, build a terminology glossary as a standalone reference file (e.g. app/frontend/src/locales/gsw/GLOSSARY.md) covering every domain-specific noun/concept that will recur across the app: Member, Group, Event, Poll, Invoice/Tier, Mailbox, Role, Permission, Notification, Application (membership application), Inventory, Category, Audit Log, Settings, Account, Dashboard. For each term, decide ONE Swiss German (or kept-English) rendering and commit to it before any page is translated. Cross-reference each against how vollbuild.die-ganz-witzige.ch phrases anything overlapping (e.g. it already establishes "Mitglied" for member, "Verein" for the association, "Geräte" for equipment/inventory). Show me this glossary for approval before translating a single page — changing a core term after 5 sections are done means re-touching all 5.

## After

After all sections are translated, run a consistency audit: extract every translated string and grep for variant spellings of the same dialectal pattern (e.g. confirm "wärde" is never accidentally "werde" anywhere, "isch" never "ist", "gmeinsam" never "gemeinsam", "üüs"/"üsi" used consistently for us/our). Also check that the SAME UI concept (e.g. "Save", "Cancel", "Delete", "Required field", "Loading…") uses identical phrasing everywhere it appears rather than being independently translated differently in different components. Report any inconsistencies found before considering the task complete.
