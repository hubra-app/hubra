# Standard roles and module access

Every club has the same starting set of roles and board functions, and each
role says per module whether its holders may use it at all. A module a person
may not use is hidden from them. The decisions behind this are in
[roles-proposal.md](roles-proposal.md).

## The standard set

| Role (key) | Shown as | What it may do from the start |
| --- | --- | --- |
| `owner` | Inhaber/in | everything, and gives or takes the Owner role |
| `admin` | Administration | everything except the Owner role |
| `member` | Mitglied | default role: member list, groups, events (sign up), polls (vote), posts (like, comment) |
| `board` | Vorstand | sees members, applications, tiers, functions, finance and mail; creates and changes events, polls, posts and groups |
| `secretary` | Aktuar/in | everything in Mitglieder (register, applications, tiers) except giving roles; functions, mail, events, polls, posts and groups; the audit log |
| `treasurer` | Kassier/in | everything in Finanzen; sees members, tiers and the audit log; sets members' own fees |

Roles are additive: a board member who is also Kassier/in holds Vorstand and
Kassier/in and gets everything either gives.

| Function (key) | Gives the roles |
| --- | --- |
| Präsident/in (`president`) | Admin, Vorstand |
| Vizepräsident/in (`vice_president`) | Admin, Vorstand |
| Aktuar/in (`secretary`) | Vorstand, Aktuar/in |
| Kassier/in (`treasurer`) | Vorstand, Kassier/in |

A function gives its roles while the holder's term runs; when the term ends
or the holder leaves, the roles go with it. A function can give any number of
roles (Mitglieder › Funktionen › Bearbeiten › "Gibt die Rollen"), except
Owner.

The keys stay the same whatever a club renames its roles and functions to;
plugins and upgrades find them by key.

## Module access

Every module with pages of its own that a club can switch off has an access
permission, `module.<code>.access`. On Einstellungen › Rollen each module has
one level for the role:

- **Keine**: the module is hidden for the role's holders: not in the
  sidebar or on Weitere, its pages say "Kein Zugriff", its tabs, dashboard
  widgets and search results don't show, and its API answers
  `403 MODULE_ACCESS`.
- **Ansehen**, **Bearbeiten**, **Alles**: as before, now for the whole
  module in one click. The areas inside a module still have their own
  levels and single permissions (the arrow).

Rules:

- **Any right in a module brings access to it.** Giving a role
  `inventory.items.read` also gives `module.inventory.access`.
- **Admins use every module.**
- **Own data stays.** A member without access still sees their own invoices,
  expense claims, items and other data from the module on their profile and
  dashboard: routes under `/mine` or `/my-…` (or marked with
  `hubra.core.module_access.own_data`) stay open, and plugin slots only need
  the module switched on.
- A person holds a module if any of their roles holds it, including roles
  that come with a function or are held for one group.

## Plugins: `role_defaults`

A module manifest can say which standard roles get it, and at which level,
when a club switches it on for the first time:

```python
module = Module(
    code="inventory",
    ...,
    role_defaults={"member": "view", "board": "view", "secretary": "edit"},
)
```

Roles: `member`, `board`, `secretary`, `treasurer` (admins have everything
anyway). Levels: `view`, `edit`, `all`, as on the roles page. They are given
once per club and only added: what the club changes later stays, also when
the module is switched off and on again. A module without `role_defaults`
is hidden from everyone but admins until the club gives a role access.
`role_defaults` needs a Hubra core with standard roles (0.2.5 or later), so
raise the plugin's `hubra:` minimum with it.

## Upgrading a club

New clubs get all of this when they are made. Existing clubs get it from
`flask roles standardise`, which `flask seed` runs for every club on each
deploy (`--tenant <slug>` for one club). The first run in a club:

1. adds the roles and functions it lacks: an existing role or function with
   the same name (Kassier, Präsidium, Aktuar, …) is adopted and keeps its
   rights; an adopted function gets the standard roles it lacks, except
   Admin (an upgrade never makes anyone an admin; give Präsident/in the Admin
   role on the function if you want that),
2. gives every role access to the modules it could use before: those it
   holds any right in, and those whose sidebar entry everyone saw,
3. switches module access on for the club (setting `roles.module_access`).

Until that has run, nothing is hidden. Later runs only add what is missing
and give the `role_defaults` of modules the club has switched on since.

## Groups

Groups can give roles, hold functions of their own, and fill themselves.

- **A group gives roles** (Gruppe › Bearbeiten › "Gibt die Rollen"):
  everyone in the group holds them for the whole club while they are in it;
  leaving the group takes them away. Owner and admin roles can't be given
  this way (being put in a group never makes anyone an admin), and an open
  group gives no roles, since anyone may join it on their own. Adding someone
  to such a group, or taking them out, needs the right to give or take its
  roles, as for a function (`check_grant`); a group leader without those
  rights can't.
- **Group functions** (Funktionen › Bearbeiten › "Gruppenfunktion"): a
  function such as Trainer/in is filled per group, on the function's page
  (pick the group, then the person) or on the group's Funktionen tab. Its
  roles count in that group only, like a role held for one group
  (`member_role_scopes`), so a group function can't give an admin role.
  `max_holders` counts per group. A function switches between club and group
  function only while nobody holds it.
- **Default groups** ("Neue Mitglieder kommen in diese Gruppe"): every new or
  returning member joins them (invite accepted, application approved, added
  by the platform). Existing members aren't moved.
- **Tier groups** (on the group, "Mitglieder dieser Stufen", or on the tier,
  "Mitglieder kommen in die Gruppen"): the tier's members are in the group.
  Linking a tier adds its current members at once; a member whose tier
  changes leaves the old tier's groups (unless they are default groups or
  groups of the new tier too) and joins the new tier's. Unlinking leaves
  everyone where they are.

Marking a group default or linking a tier to it puts members in it later
without asking anyone, so it needs the right to give the group's roles, as
setting the roles does.

Where a member's roles come from shows in the members list and on the
member's page: "(über Kassier/in)" for a function, "(über Gruppe Jugend)"
for a group, "(nur Jugend)" for a role or group function held for one group.
The role filter and the member counts on the roles page include all of them.
