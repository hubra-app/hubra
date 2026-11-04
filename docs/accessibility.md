# Accessibility statement

Hubra is used by clubs whose members are of every age and ability. Everyone
should be able to read the news, sign up for an event, vote in a poll or pay
an invoice, whatever device or assistive technology they use.

This statement covers the Hubra apps: the club app (`app.hubra.club`), sign-in
and account (`sso.hubra.club`), manage (`manage.hubra.club`) and the support
site (`support.hubra.club`). The same code runs on self-hosted installs.

_Last reviewed: **not yet audited** (statement written 2026-11-04)._

## Our target

We aim to meet the
[Web Content Accessibility Guidelines (WCAG) 2.1, level AA](https://www.w3.org/TR/WCAG21/).
This is also the level required of public bodies in Switzerland (eCH-0059)
and the EU (EN 301 549).

**Status: partly conformant.** Large parts of Hubra follow the guidelines,
but the apps have not had a full audit, and some parts are known not to
meet them yet (listed below).

## What we do

- **Contrast.** Every text and background pair is meant to reach WCAG AA
  (4.5 : 1 for text, 3 : 1 for large text and controls), in light and dark
  mode. Text on a club's own colours (buttons, links, banner, avatars) is
  picked automatically so it stays readable whatever colours the club sets
  (`packages/ui/src/contrast.ts`).
- **Dark mode** and the system setting for it, per person.
- **Reduced motion.** With "reduce motion" switched on in the operating
  system, animations and transitions are turned off.
- **Language.** The page language (`lang`) follows the language the person
  chose, German or English, so screen readers pronounce it correctly.
- **Text size and phones.** Body text is 16 px, and every page has a phone
  layout, which also takes over when the browser is zoomed in.
- **Keyboard.** The apps are built on Mantine components, which can be
  reached and used with the keyboard and show a visible focus ring. Dialogs
  keep the focus inside and return it when they close. `Ctrl+K` / `Cmd+K`
  jumps to the search in the club app.
- **Labels.** Icon-only buttons carry an `aria-label` and a tooltip (a rule
  in [docs/design-spec.md](design-spec.md)), and form fields have visible
  labels.
- **Status is not only colour.** Status badges and alerts have a text, not
  only a colour.

## Known problems

- There is **no "skip to content" link** yet, so keyboard and screen-reader
  users pass the whole navigation on every page.
- **PDF invoices (QR-bill) and statements** are generated without tags, so
  screen readers read them poorly. The amounts and the reference are also
  shown in the app.
- **Plugins** are built by their own authors and may not follow these
  rules.
- **Accessibility is not tested automatically.** The browser tests do not
  run an accessibility checker such as axe, so regressions can slip in.

We fix these as part of the normal work and track them as issues with the
`accessibility` label.

## Report a barrier

If something in Hubra is hard or impossible for you to use, please tell us.
It is a bug, and we treat it as one.

- Open an [accessibility issue](https://github.com/hubra-app/hubra/issues/new?template=accessibility.yml), or
- write to **[hi@hubra.club](mailto:hi@hubra.club)** with "Accessibility" in the subject.

Tell us which page, what you tried to do, and which browser and assistive
technology you use. We answer within **10 working days**.

If you need content from Hubra in another format (for example an invoice as
plain text), ask your club or write to us, and we will help.

## For contributors

UI changes should keep to this statement: use the components and tokens in
`packages/ui`, give every control a label, check the contrast in both
themes, and try the change with the keyboard alone. See
[CONTRIBUTING.md](../CONTRIBUTING.md) and
[docs/design-spec.md](design-spec.md).
