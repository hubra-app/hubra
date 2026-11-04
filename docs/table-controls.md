# Table controls: search, filter, sort

Lists in the club app and in manage share one toolbar (`FilterBar` in
`packages/ui/src/filters.tsx`). It replaced rows of filter chips, extra
selects and a sort select that sat next to each other on the busier pages.

## The pattern

```
[ 🔍 Search …                    ] [ ⚙ Filter (2) ]          [actions] [▦ ≡]
  Status: Offen ×   Zweck: Mitgliedschaft ×   Zurücksetzen
```

1. **One search field**, always visible, with a clear (×) button.
2. **One "Filter" button.** It opens a panel with every filter of the page
   and, last, the sort order. On wider screens the panel is a popover under
   the button; on phones it is a bottom sheet. The button shows how many
   filters are set.
3. **Active filters as chips** under the toolbar, each with its own ×. A
   filter at its default value shows no chip, so an untouched list has one
   quiet row. "Zurücksetzen" appears when two or more are set.
4. **Sort in the column header** where the list sorts by that column
   (members: name, joined, status; manage clubs: every numeric column). The
   same order is also in the panel, because the card view has no headers.
5. **Cards or list**: pages with a card layout keep the icon switch on the
   right of the toolbar, remembered per page (`viewKey`). Cards are the
   default where a row needs more than four columns to be useful
   (members, codes, inventory).
6. **Paging** sits below the list. The row above the list only appears when
   there is more than one page.
7. A filter group shows its options as buttons up to 8 options, and as a
   searchable select above that (roles, audit actions, clubs, builds).

Filters that already lived in the URL stay there (members `?role=`), and
every filter keeps its old default, so a page shows the same rows as before
until someone opens the panel.

### Exception: a primary status with counts

manage › Diagnose › Fehler keeps *Offen (n) / Behoben (n) / Alle* as a
visible segmented control. It is the page's main triage switch and the counts
are information in their own right. Use this only when the options carry
counts; otherwise the status goes into the panel.

### Plain lists instead of tables

A table only earns its headers when people compare several columns. Short
records (a name and one or two facts) use `SimpleList` from
`components/data.tsx`: one row per record with a title, a subtitle, facts on
the right and the actions at the end. Used for transaction categories,
external parties, custom domains and the recent transactions on the finance
overview. Codes show as cards only (`cardsOnly` on `DataTable`), without the
list switch.

Tables stay where columns are compared: members (list view), invoices,
transactions, events, audit logs, mail addresses, recurring bookings (amounts,
per year, totals), fee basis, notification settings (a matrix of switches)
and the manage tables.

## How to use it

Club app: pass `filterGroups` to `DataTable` (and `sortValue` /
`onSortChange` plus `sort` on columns for header sorting).

```tsx
filterGroups={[
  {
    key: 'status',
    label: t('common.status', 'Status'),
    value: statusFilter,
    defaultValue: 'All',
    options: [
      { value: 'All', label: t('common.all', 'Alle') },
      { value: 'Open', label: t('finance.invoiceFilter.open', 'Offen') },
    ],
    onChange: setStatusFilter,
  },
]}
```

`kind: 'select'` forces a select, `kind: 'date'` a date field, `hidden`
drops a group for now (e.g. tiers while the archive is shown), and `sort:
true` lists it last as the sort order.

manage: use `FilterBar` from `@/components/FilterBar` above the table.

## Inventory (2026-11-04)

The app has no usage analytics, so "how often" is judged from defaults and
what each page is for.

| Page | Before | After |
| --- | --- | --- |
| Club › Mitglieder | search, one chip per tier + Archiviert, role select, sort select, view switch | search, Filter (Anzeigen, Stufe, Rollen, Sortieren), sortable headers, view switch |
| Club › Finanzen › Rechnungen | search, 6 chips (4 status + 2 purpose, mixed in one row) | search, Filter (Status, Zweck) |
| Club › Finanzen › Einnahmen und Ausgaben | search, Alle/Ein/Aus chips, status select | search, Filter (Richtung, Status) |
| Club › Anlässe | search, Zeitraum chips + Typ chips in two labelled slots | search, Filter (Zeitraum, Typ) |
| Club › Inventar | search, category chips, status select, own view switch, a second copy of the toolbar for the card view | one DataTable with cards, search, Filter (Kategorie, Status) |
| Club › Codes | search, 3 status chips, view switch | search, Filter (Status), view switch |
| Club › Audit-Log | search, action select | search, Filter (Aktion) |
| Club › Mail › Adressen | search, type select, state select, 5 sync chips, refresh | search, Filter (Typ, Zustand, Abgleich), refresh |
| Club › Mail › System | search, sync select | search, Filter (Abgleich) |
| manage › Alle Vereine | search, plan select, status select, sortable headers | search, Filter (Plan, Status), sortable headers |
| manage › Audit-Log | search, club select, from/to dates, log segmented, hide sign-ins checkbox, export | search, Filter (Protokoll, Verein, Von, Bis, Anmeldungen), export |
| manage › Diagnose › Fehler | status segmented, search, sort select, build select | status segmented, search, Filter (Version, Sortierung) |

Left alone, and why:

- Tables without filters (fee basis, categories, external parties, recurring,
  domains, invoice lines, member detail, notification settings, permission
  and resource matrices, manage club detail/modules/billing, roles, plans,
  backups, encryption, Discord, jobs, translations, performance, trends,
  maintenance, support sessions, club admins, requests): they have at most one
  control, usually a segmented time range or tab, which is already simple.
- Settings key/value tables (`KVTable`): search only, grouped by section.
- manage › Plugin-Katalog: a card catalogue with its own stats row, not a table.
- manage › Mail-Monitor and Diagnose: one search field each.
- Groups, polls, posts: card lists with one segmented filter.
