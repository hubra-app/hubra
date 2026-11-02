# Hubra design spec

The rules every Hubra frontend follows: the club app (`app/frontend`), manage
(`app/admin-frontend`), the sign-in portal (`app/sso-frontend`, also served as
join.hubra.club) and the website (hubra-app/hubra.club). Plugins that ship UI
follow it too.

Read this before you build a screen. When the code and this page disagree,
the page wins for new code; the [open differences](#open-differences) list
says what still has to be brought in line.

Where things live:

| What | Where |
| --- | --- |
| Mantine theme (colours, type, radius, shadows, component defaults) | `packages/ui/src/theme.ts`, `colors.ts` |
| CSS tokens (`--hb-*`), page base, brand marks, chips, tabs | `packages/ui/src/ui.css` |
| Shared page blocks: `PageHead`, `StatTile`, `StatGrid`, `Tabs`, `Pagination` | `packages/ui/src/layout.tsx` |
| Dialogs, side panels, cards, empty / error / loading states | `packages/ui/src/feedback.tsx` (each app wraps them with its texts) |
| Fonts (self-hosted woff2, SIL OFL) | `packages/ui/fonts/` |
| Text colour on any fill (WCAG) | `packages/ui/src/contrast.ts` (`textOn`, `readableOn`) |
| Light / dark / auto | `packages/ui/src/colorScheme.ts`, `ThemeSwitch.tsx`, `theme.js` |
| Logo files and brand rules | `brand/README.md` |

If a value is in the theme or in a token, use it. Don't write a hex value,
a pixel radius or a shadow into a screen.

---

## 1. Brand

### Name

- The product is **Hubra**. In running text: "Hubra", never "HUBRA" or
  "hubra" (the lowercase form is only the drawn wordmark).
- Clubs are "Verein" / "club". The person using the app is a member
  ("Mitglied"), even when they are an admin.
- Hosts are named by what they do: the club app, manage, sign-in (SSO),
  join, the website.

### Logo

The "Clubhouse" mark: a lowercase h drawn as a doorway on a violet tile, with
a gold dot inside. Files and sizes are in `brand/README.md`.

- In the apps the mark is the `.logo-mark` class (28 px, or 36 px on the
  sign-in card). The wordmark next to it is the `.wordmark` class.
- In a club's app the club's own logo (`.club-logo`, `ClubMark`) replaces
  the Hubra mark in the top bar and the phone menu. Hubra's mark stays on
  sign-in, manage and the website.
- Don't recolour, rotate, stretch or add effects. Don't capitalise the
  wordmark. No Swiss cross (Wappenschutzgesetz), nothing that looks like
  crypto (hubra.app is a DeFi product).

### Colour

**Primary – Hubra Violet** (Mantine `acc`). Shade 6 is the primary in light
mode, shade 4 in dark mode.

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `#f5f1ff` | `#ebe3ff` | `#d6c7ff` | `#bba3fd` | `#9f7cf8` | `#8758f0` | `#7441e0` | `#6131c4` | `#4d27a0` | `#3a1e78` |

`acc` is the **club colour**: a club can set its own (club branding), and
the whole `acc` scale then follows it. So:

- Use `acc` (or `var(--mantine-color-acc-*)`) for anything that should take
  the club's colour: primary buttons, links, the active page, focus rings.
- Never write `violet`, `indigo` or a violet hex in the club app. They stay
  violet when the club is green.
- Manage, sign-in and the website are Hubra's own and always violet, but
  they still use `acc` so the code is the same everywhere.

**Accent – Signal Gold** (Mantine `gold`, `#fece2b`): the logo dot and small
markers for "new", "due" and "highlighted". Always dark ink text on it.
Never a large area, never a button fill.

**Neutrals** (Mantine `gray`, violet-tinted in light mode). Use the tokens,
which switch with the colour scheme:

| Token | Use | Light | Dark |
| --- | --- | --- | --- |
| `--hb-page` | Page background | `#f7f6fb` | `#111113` |
| `--hb-surface` | Cards, dialogs, top bar | `#ffffff` | `#19191c` |
| `--hb-surface-2` | Hover fills, inset areas | `#f4f2f9` | `#222226` |
| `--hb-border` | Lines and card borders | `#e6e3ef` | `#2f2f34` |
| `--hb-text` | Body text, headings | `#1a1625` | `#ededef` |
| `--hb-text-2` | Secondary text | `#5e5873` | `#a8a8b0` |
| `--hb-text-3` | Hints, placeholders, meta | `#8c86a0` | `#7c7c85` |
| `--hb-sidebar` | Sidebar | tint of `acc-0` | `#151517` |
| `--hb-notice-bg` / `--hb-notice-border` | Announcement banner | gold 0 / 3 | gold mixed into surface |

Dark mode is neutral grey on purpose (Mike, 2026-10-30): the club colour is
the only colour on the page, and only on accents.

**Status colours.** One Mantine colour per meaning, used through
`color=` on `Badge`, `Alert`, `ThemeIcon`, `Button`:

| Meaning | Mantine colour | Examples |
| --- | --- | --- |
| Success, paid, active | `green` | Paid invoice, active member, check passed |
| Warning, due, needs a look | `orange` | Unpaid, trial ends, quota near |
| Danger, error, delete | `red` | Overdue, failed, delete buttons |
| Information, neutral notice | `acc` | Hints, "how this works" boxes |
| Off, archived, unknown | `gray` | Inactive, archived, draft |

`yellow` is not a status colour (yellow text fails contrast on white). `gold`
is only for the small "new/due" marker. `blue`, `cyan`, `indigo`, `violet`
are not used for status.

The theme's `green`, `orange` and `red` scales are built from the brand
values (shade 6 = `#18794e`, `#e8a317`, `#c73550`), and text in them uses
`--mantine-color-<name>-text`, which is darkened where needed to pass AA.
In inline styles use `var(--mantine-color-<name>-text)` for text and
`var(--mantine-color-<name>-6)` for dots and bars.

**Category colours** (tags, tiers, event and inventory types, search result
types, finance categories) come from `categoryColors` in `@hubra/ui` (the
avatar palette of `hubra/core/avatar.py`), or from the club's own setting.
Text in them goes through `colorText()`, fills and borders through
`tagStyle()` (or `color-mix()`); filled backgrounds take `textOn()` text.
Don't keep a local map of hex values.

**Contrast.** Every text/background pair meets WCAG AA (4.5 : 1, 3 : 1 for
large text and icons). The theme does this for filled buttons and badges
(`autoContrast`, `--mantine-color-*-contrast`) and for `acc` text
(`--mantine-color-acc-text`). For your own fills, use `textOn(bg)`.

### Type

| Face | Use | Weights |
| --- | --- | --- |
| **Bricolage Grotesque** | Headings, dialog titles, wordmark, big figures (`.stat-value`) | 600, 700, 800 |
| **Hanken Grotesk** | Everything else | 400, 500, 600, 700 |
| **JetBrains Mono** | Numbers you compare or copy: amounts in tables, IBANs, codes, ids, logs (`.num`) | 400, 500, 600 |

Scale (theme `fontSizes` and `headings`):

| Token | Size | Use |
| --- | --- | --- |
| `xs` | 12 px | Table headers (uppercase, +0.04em), meta lines, badges |
| `sm` | 14 px | Default for tables, form labels, buttons, secondary text |
| `md` | 15 px | Body text |
| `lg` | 17 px | Lead paragraphs |
| `xl` | 20 px | Small headings inside content |
| `h1` | 30 px / 1.15 | Page title (one per page, from `PageHead`) |
| `h2` | 22 px / 1.25 | Section title |
| `h3` | 18 px / 1.3 | Card title in a large card |
| `h4` | 16 px / 1.35 | Card header (`Card.Header`) |
| dialog title | 19 px | `Modal` / `Drawer` title (theme) |

- Sentence case everywhere: titles, buttons, tabs, menu items.
- Weights: 400 body, 500 nav rows and switch labels, 600 labels, buttons,
  tabs and table headers, 700 headings.
- Eyebrows (the small line above a page title) are `.eyebrow`: 12 px, 700,
  uppercase, +0.08em, `acc-7`.

### Voice

- German (de-CH) first, English second. Both strings are written together:
  `tr(de, en)` in manage and sign-in, i18next keys with German defaults in
  the club app.
- Informal **du**. Swiss spelling: "ss", never "ß".
- Short, plain sentences. Say what happens: "Rechnung senden", not "OK".
  Errors say what went wrong and what to do next.

---

## 2. Look and feel

### Spacing

Mantine's scale: `xs` 10, `sm` 12, `md` 16, `lg` 20, `xl` 32 px. Prefer the
names; when a number is needed, use a multiple of 4.

| Where | Value |
| --- | --- |
| Page padding (`.page-container`) | 32 px, 20 / 16 px on phones |
| Below `PageHead`, between page sections | 24 px |
| Between cards in a grid | `md` (16 px) |
| Inside a card | `lg` (20 px); `md` for dense list cards |
| Card header | `px="lg" py="md"` with a bottom border |
| Form fields in a dialog | `Stack gap="sm"` |
| Buttons in a row | `Group gap="xs"` |

### Radius

| Token | px | Use |
| --- | --- | --- |
| `xs` | 6 | Code chips, build badge |
| `sm` | 8 | Badges, tooltips, chips |
| `md` | 10 | **Default**: buttons, inputs, menus, popovers, alerts, nav rows |
| `lg` | 16 | Cards, `Paper`, dialogs (theme default: don't set `radius` on a `Paper`) |
| `xl` | 20 / pill | Avatars (`xl` = round), status pills, phone tab pills (999px) |

### Elevation

| Level | Use |
| --- | --- |
| Border, `shadow="xs"` | Cards and `Paper` (theme default). Flat UI is the norm. |
| `shadow="md"` | Menus, popovers, the notification panel |
| `shadow="lg"` | Dialogs and drawers |

Cards always have a border (`withBorder`). Don't stack shadows, don't add
`shadow="sm"` on top of the default. In dark mode borders do the work;
shadows are barely visible there and that is fine.

### Density

- Default control size `sm` (36 px tall). `xs` only inside tables and card
  headers. `md`/`lg` only on sign-in and the website.
- Tables: `verticalSpacing="sm"`, `fontSize="sm"`, hover highlight (theme).
- Touch targets on phones are at least 36 px; tab pills and phone nav rows
  are 36–44 px.

### Icons

- One set: **Tabler** (`@tabler/icons-react`), default stroke.
- Sizes: **16** in buttons, inputs, badges, table rows and menus; **18** in
  alerts and nav rows; **20** for close buttons and top bar actions; **24**
  for empty states and section icons. Don't use 12/14 except inside badges.
- Icon-only buttons are `ActionIcon` (theme: `gray`, `subtle`) with an
  `aria-label` and a `Tooltip`.

### Motion

- 120–150 ms ease for hover and colour changes. Nothing bounces.
- Honour `prefers-reduced-motion` (all motion off). This must hold in every
  app, not only the club app.

### Dark mode

- Every screen works in light and dark. Users pick light / dark / auto
  (`users.theme`, cookie `hubra_theme`); `packages/ui/theme.js` sets it
  before the first paint on every portal.
- Use tokens and Mantine colour names only. A hex value in a screen is a
  dark-mode bug waiting to happen.
- Don't override `--mantine-color-gray-N`: it breaks Mantine's dark subtle
  variants. Change tokens in `ui.css` instead.
- Test every new screen in both schemes before the PR (screenshots in the
  PR, see `docs/screenshots/`).

### Breakpoints

| Name | Width | What changes |
| --- | --- | --- |
| `xs` | 576 px | Stat tiles go to 2 columns |
| `sm` | 768 px | **Phone / desktop switch**: sidebar → phone menu, tabs → pills, small tables → cards, page padding 16 px, build badge hidden |
| `tab` | 870 px | Wide tables become cards; permission matrix tables tighten |
| `md` | 992 px | Detail pages go to two columns; sign-in shows the brand panel |
| `nav` | 1100 px | Extra-wide tables (`xwide`) become cards |
| `lg` / `xl` | 1200 / 1440 px | Wider grids; content stops at 1440 px |

Use Mantine props (`hiddenFrom="sm"`, `cols={{ base, sm, md }}`) or the
`em` values above in CSS. Don't invent new breakpoints.

---

## 3. Layout patterns

### App shell (club app and manage)

| Part | Spec |
| --- | --- |
| Top bar | 64 px, `--hb-surface`, bottom border. Left: logo (club logo in the club app), breadcrumb. Right: search (Ctrl+K), notifications, account menu. |
| Sidebar | 244 px, collapses to 64 px (icons only). Background `--hb-sidebar`. Rows: 18 px icon, 14 px label at 500, `md` radius; the active row is `acc` light. Grouped by task, with a small uppercase group label. |
| Content | `.page-container`: max 1440 px, centred, 32 px padding (16 px on phones). |
| Phone (< 768 px) | Sidebar is replaced by a **full-width** menu drawer from the left, with the account card pinned at the foot. |
| Banners | Support / impersonation / maintenance banners sit above the top bar and push it down (`--hb-header-h`). |
| Build badge | `BuildBadge`, bottom right, hidden on phones and in print. |

### Signed-out pages (sign-in, reset, invite, apply)

`AuthFrame`: two columns from 992 px. Left: the form card, max 400 px (480
wide), mark + wordmark on top. Right: the brand panel, a violet gradient
`acc-6 → acc-7 → acc-9` with the white mark, very large and faint. Phones get
only the form.

### Signed-in SSO pages (account, clubs, roadmap)

`SignedInFrame`: a 60 px top bar and one centred column (560 px by
default). From tablet width the account sections sit in a side list
(`.sso-side-tabs`) instead of tabs.

### Page

Every page starts with `PageHead`: optional back link, optional eyebrow, the
`h1` title, an optional one-line description (dimmed, max 720 px) and the
page actions on the right. Then, in this order, as needed: stat tiles
(`StatGrid` + `StatTile`), tabs (`Tabs`), filters (chips or a `Select` row),
the content.

- One primary (filled) button per page, in `PageHead` actions. Others are
  `default` or `light`.
- On phones page actions share the row (`.page-actions`).

### Card

- `Card` from `@hubra/ui` (a bordered `Paper`, radius `lg`,
  `overflow: hidden`) with `Card.Header` for a titled card.
- Card grids: `CardGrid` (1 / 2 / 3 columns), `CardItem` for clickable
  cards.
- Lists that can be a table or cards use `DataTable` with `renderCard` and
  a cards/list toggle.

### Tabs

- Page tabs are `Tabs` from `@hubra/ui` (the `.hubra-tabs` style): an
  underlined row on desktop, wrapping pills on phones. Tabs change the URL.
- Settings-like pages with many sections (SSO account) may use the side
  list from tablet width.
- `SegmentedControl` is for switching a view of the same data (month /
  year, cards / list), not for navigation.

### Dialog

- `Modal` (radius `lg`, centred, blurred overlay, 19 px title) for a short
  task: create, edit, confirm. Body is a `Stack gap="sm"`; the footer is a
  right-aligned `Group gap="xs"` under a divider: **Cancel** (`default`)
  then the action (filled, or `red` for deleting).
- Size `md` (440 px) for up to ~4 fields, `lg` (620 px) for forms with
  paired fields that stack on phones.
- A dialog is a form: Enter submits.
- Destructive actions confirm with `ConfirmModal` that names the thing
  ("«Name» löschen?") and says if it can be undone. Never `window.confirm`.
- `SlideOver` (drawer from the right, 420 px, full width on phones) for
  viewing or editing a record next to the list.

### Feedback

| Need | Use |
| --- | --- |
| Result of an action | Toast: `notify(kind, title, detail?)` (`@mantine/notifications`, bottom right) |
| Something on the page needs attention | `Alert` (variant `light`) in the status colour |
| Load failed | `ErrorBanner` with a retry button |
| Nothing here yet | `EmptyState`: 24 px icon, title, one line, optional action |
| Loading | `LoadingSpinner` / `Loader` for the area; skeletons for lists that load often |

### Mobile navigation

- Below 768 px: top bar with menu button, logo and account; the menu is a
  full-width drawer; tabs become pills; tables become cards; dialogs and
  slide-overs are full width.
- Nothing scrolls sideways except a wide table inside `.table-matrix-wrap`.

---

## 4. Components

Use the approved component; build a new one only when none fits, and put it
in `packages/ui` when a second app needs it.

| Need | Approved | Variant / notes |
| --- | --- | --- |
| Primary action | `Button` | `filled`, `acc`. One per view. |
| Secondary action | `Button` | `default` (outlined neutral) |
| Low-key / toolbar action | `Button` | `subtle` or `light` |
| Destructive action | `Button` | `color="red"`, `light` in a list, `filled` in the confirm dialog |
| Icon-only action | `ActionIcon` | theme default (`gray`, `subtle`), `aria-label` + `Tooltip` |
| Text field | `TextInput`, `Textarea`, `NumberInput`, `PasswordInput` | size `sm`, label above, description under the label |
| Choice | `Select` (one), `MultiSelect`, `Checkbox`, `Switch` (on/off settings), `SegmentedControl` (2–4 views) | `Select` check on the right |
| Form wrapper | `Field`, `Toggle`, `Seg` (club app `components/form.tsx`) | zod validation, German messages |
| Status | `Badge` | `light`, radius `sm`, status colours from §1 |
| Invoice / payment state | `InvoicePill` | `green` / `orange` / `red` |
| Member status | `StatusBadge` | dot + text in the status colour |
| Filter | `.chip` | `.on` when active |
| Avatar | `Avatar` (club app `display.tsx`) | round; colour from the account; initials with `textOn()` |
| Figures | `StatTile` in `StatGrid` | `.stat-value` 28 px |
| Table | `DataTable` (club app) | sorting, paging, card view on phones; plain `Table` only for small fixed tables |
| Key/value list | `KVTable` | |
| Paging | `Pagination` from `@hubra/ui` | |
| Page head | `PageHead` | |
| Tabs | `Tabs` from `@hubra/ui` | |
| Card | `Card`, `Card.Header`, `CardGrid` (`@hubra/ui`), `CardItem` (club app) | |
| Dialog | `Modal`, `ConfirmModal` (`@hubra/ui`); manage: `useConfirm()` | see §3 |
| Side panel | `SlideOver`, `PanelSection`, `PanelField` (`@hubra/ui`) | |
| Toast | `notify()` | `success` / `error` / `info` |
| Notice | `Alert` | `light`, icon 18 px |
| Empty | `EmptyState` (`@hubra/ui`) | |
| Load error | `ErrorBanner` (`@hubra/ui`) | with retry |
| Theme switch | `ThemeSwitch` / `ThemeToggle` | |
| Rich text | `RichTextEditor` (Tiptap, stores Markdown), `MarkdownRenderer` | |
| Logs, terminal output | `.terminal-block` | mono, dark in both schemes |

---

## 5. Website (hubra.club)

The website is plain static HTML/CSS and can't use the Mantine theme, so it
copies the values into `public/assets/site.css`. It must stay in step with
this page:

- Same violet scale, gold, neutrals, status colours and type as above.
- Body 17 px / 1.6 (marketing size), headings Bricolage 800 with tight
  tracking; buttons radius 10 px, cards 16 px.
- Fonts are self-hosted (no Google request), like the apps
  (`packages/ui/fonts`).

---

## 6. Checklist for a new screen

1. Starts with `PageHead`; one filled button.
2. No hex, rgba, pixel radius or shadow in the screen; tokens and Mantine
   names only.
3. `acc` for brand colour, status colours from §1.
4. Shared components from §4.
5. Works at 375 px wide and in dark mode; screenshots of both in the PR.
6. German and English text, du, Swiss spelling.
7. Keyboard: every action reachable, icon buttons labelled, dialogs submit
   on Enter.

---

## Open differences

What the apps did differently when this page was written (2026-11-02), and
how each was settled. Keep this list: a new difference goes in as a new row
with its fix.

| # | Where | Difference | Fix | Status |
| --- | --- | --- | --- | --- |
| 1 | `brand/README.md`, hubra.club `site.css` | Dark neutrals are violet-tinted (`#14111c` page, `#1e1a2a` surface, `#2e2840` line, `#a39db8` text) while the apps use neutral grey (`#111113`, `#19191c`, `#2f2f34`, `#a8a8b0`) since 2026-10-30. | Update the brand README's dark table to the app values; switch the website's dark tokens to them. | Done (README; website in hubra.club) |
| 2 | Status colours | The README says success `#18794e` / warning `#e8a317` / danger `#c73550`; the apps use Mantine `green`/`orange`/`red`; `StatusBadge` uses its own `#1f9d57`/`#c2870f`/`#ff4d3d`; last-seen uses Tailwind `#22c55e`/`#f59e0b`/`#ef4444`; the website `#1f9d57`. Warnings are `orange` in 25 places and `yellow` in 12. | Add `success`/`warning`/`danger` scales to the theme built from the brand values; point `green`/`orange`/`red` usage and `StatusBadge`/`LastSeenBadge` at them; replace `yellow` alerts with `orange` (warning). | Done |
| 3 | Info alerts | Information boxes use `blue` (5), `cyan`, `indigo`, `violet` (2) or `acc`. `violet` ignores the club colour. | All information alerts `acc`; replace `violet`/`indigo`/`blue`/`cyan`. | Done |
| 4 | Hard-coded hex in screens | 210 hex literals in club app `.tsx` (tier colours, search result types, inventory types, finance), 27 in manage, 5 in sign-in. `.verify-banner` and `.terminal-block` in club app CSS too. | Category colours from the shared avatar palette + `textOn()`; banners from `--hb-notice-*`; move `.terminal-block` to `ui.css`. Tackle per screen when touched, plus a lint warning for new hex literals in `.tsx`. | Done; left are stored-data defaults (avatar, tier, group colours) and the white behind the 2FA QR code. No lint rule yet |
| 5 | Eyebrow | Sign-in overrides `.eyebrow` with JetBrains Mono, wider tracking and a `// ` prefix; club app, manage and website use the shared Hanken 700 style. The `//` looks like code. | Delete the override in `sso-frontend/src/index.css`. | Done |
| 6 | Sign-in brand panel | `.auth-layout`/`.auth-brand` CSS is copied in the club app and sign-in; sign-in hard-codes the gradient hex, the club app uses `acc` variables. | Move the auth layout CSS into `ui.css` using `acc` variables; delete both copies. | Done |
| 7 | Page width | Club app `.page-container` max 1440 px; manage 1240 px. | One `.page-container` in `ui.css` at 1440 px. | Done |
| 8 | Sidebar background | Club app sidebar is `--hb-sidebar` (club-colour tint); manage sidebar is `--hb-surface` (white). | Manage uses `--hb-sidebar` too (it is violet there anyway). | Done |
| 9 | Phone menu | Club app phone menu is full width; manage's is `min(300px, 85vw)`. | Full width in manage (being done in the manage navigation thread). | Done in #153 |
| 10 | Top bar height | 64 px in club app and manage, 60 px on signed-in SSO pages. | 64 px everywhere. | Done |
| 11 | Dialogs | Club app `Modal` wrapper forces a 15 px title, `md` padding and a divider footer. Manage uses Mantine `Modal` directly (theme 19 px title, `lg` padding, `Stack gap={16}`, no divider). Manage has no `ConfirmModal`; deletes use a hand-built dialog. | Move `Modal`, `ConfirmModal`, `SlideOver` to `packages/ui`; title follows the theme (19 px); manage and sign-in use them. | Done |
| 12 | Cards | Sign-in cards use radius `md` (10 px); the apps use `lg` (16 px). Manage often adds `shadow="sm"` and `radius="lg"` by hand (30×); club app mixes `shadow="sm"` and the theme default `xs`. | Plain `<Paper withBorder>` / `Card` with theme defaults everywhere; drop the per-use `radius`/`shadow`. | Done |
| 13 | Shared components only in the club app | `DataTable`, `EmptyState`, `ErrorBanner`, `Avatar`, `Card`, `Field` exist only in the club app. Manage builds tables with raw `Table` (23 files) and has no empty state. | Move them into `packages/ui` and use them in manage. Biggest item; do it screen by screen. | Done for EmptyState, ErrorBanner, Card, dialogs; manage tables still use `Table` (DataTable needs the club app's i18n and paging hooks first) |
| 14 | Toasts | Club app, manage and most of sign-in use `notify()`; sign-in also calls `notifications.show` directly (3 places). | Use `notify()`; put one `notify` in `packages/ui`. | Done |
| 15 | Reduced motion | Only the club app turns motion off for `prefers-reduced-motion`. | Move the rule into `ui.css`. | Done |
| 16 | Fonts | The apps load Bricolage, Hanken and JetBrains Mono from Google Fonts; the website self-hosts Bricolage and Hanken (no JetBrains Mono file, so code falls back). Loading from Google sends visitors' IPs to Google, which is a privacy issue under GDPR / Swiss FADP. | Self-host the three fonts in `packages/ui` (same woff2 files as the website) and add JetBrains Mono to the website. | Done |
| 17 | Icon sizes | 12, 14, 16, 18, 20, 24, 26, 28 are all in use; a few icons set `stroke` 1.5 / 1.6 / 1.75. | Sizes from §2 (16/18/20/24), default stroke. | Done |
| 18 | Website tokens | Website line colour is `#ebe8f2` (apps `#e6e3ef`). | Use `#e6e3ef`. | Done in hubra.club |
| 19 | Spelling | Two "ß" in manage `CreateTenantModal.tsx` and sign-in `StartClub.tsx`. | Replace with "ss". | Not a bug: both are the slug transliteration (`.replace(/ß/g, 'ss')`), not UI text |
| 20 | Table breakpoints | Responsive tables switch to cards at 600 px (`37.5em`) and 900 px (`56.25em`), which are not theme breakpoints. | Switch at `sm` (768 px) and `tab` (870 px). | Done |
