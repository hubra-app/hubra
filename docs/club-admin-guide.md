# Club admin guide

For club owners and admins: setting up a club in Hubra, bringing members in,
and choosing what the club uses. Running the installation itself (backups,
upgrades, the mail relay) is the platform's job; see
[operator-guide.md](operator-guide.md).

Menu names are given in English with the German label in brackets the first
time, because the app shows whichever language you picked.

## Where things are

| Place | Address (default) | What you do there |
| ----- | ----------------- | ----------------- |
| Club app | `app.hubra.club/<club>/app/…` | Everything inside the club: members, finance, events, settings |
| Manager portal | `manage.hubra.club` | My clubs (Meine Vereine): your clubs, and who else is a club admin |
| SSO | `sso.hubra.club` | Your own account: name, e-mail, password, language, sessions |

A Hubra account belongs to its person and can be in several clubs. The club
sees a member's account data (name, e-mail, address, avatar) read-only. Only
the person changes their name, e-mail address or password, on SSO. A club
never creates accounts or sets passwords.

## Getting a club

On the join site (`join.hubra.club/start`, or **Start a club** in manage),
fill in the club's name and address. The platform team approves the request;
you become the club's **owner**. Some installations create clubs directly
instead.

Who runs the club:

- **Owner**: the person who started it. Everything, including naming or
  removing other owners. The last owner can't be removed.
- **Admin**: everything inside the club, and adding or removing admins in
  manage under My clubs › the club › Admins.
- Everyone else gets the rights of their roles; see
  [Roles and permissions](#roles-and-permissions).

## First steps

1. **Settings › Club (Einstellungen › Verein).** Name, description, colours,
   time zone, language and date format.
2. **Settings › Modules & plugins (Module & Plugins).** Switch off what the
   club doesn't use; see [Modules and plugins](#modules-and-plugins).
3. **Members › Tiers (Mitglieder › Stufen).** The membership tiers and what
   they cost, with payment plans if a tier can be paid in parts.
4. **Permissions (Berechtigungen).** Check the roles before you invite
   people.
5. **Invite** the first members.

## Members

### Inviting

Members › All members › **Invite member (Mitglied einladen)**. Enter the
e-mail address; name, tier, groups and roles are optional. The person gets a
personal link, valid for 14 days. They sign in, or sign up with that
address, and accept; then they are a member.

You can't add someone without them accepting, and you can't set their
password. If the e-mail doesn't arrive, check the address and ask the
platform team whether the installation's mail is set up.

### Requests to join

People can find the club on the join site (`join.hubra.club/clubs/<club>`)
and ask to join. Requests show up under Members › Applications (Anträge).
**Approve** makes them a member.

### Leaving

A member leaves under their account settings in the club app. With
Settings › Club › **Leaving needs approval** on, they ask instead, and you
confirm under Members › Applications. With it off, they leave at once.
Leaving keeps their invoices and entries with the club; their account and
other clubs stay.

### Member data

- The member list can be exported as CSV (Members › All members).
- **Archive** a member who is no longer active: they disappear from lists and
  keep their history. Archived members can be shown with the filter.
- Settings › Club › **Member directory visible to all members** decides
  whether ordinary members see the directory.

## Roles and permissions

Permissions (Berechtigungen) lists the club's roles. Each role grants
permissions per area, such as members, finance, events or settings, with
read, create, update and delete. A member can have several roles; they get
everything any of them grants.

- **Owner** and **Admin** are fixed roles with full access.
- A new member gets the role marked as default.
- **Templates** set up a typical role set in one step (standard club, small
  association, makerspace).
- **Functions** (Funktionen), such as president or treasurer, are under
  Members › Functions. They record who holds an office; rights still come
  from roles.

## Modules and plugins

Settings › Modules & plugins lists everything the club can use.

| Module | What it is | On for a new club |
| ------ | ---------- | ----------------- |
| Core, Members, Roles & permissions | Sign-in, dashboard, members, roles | Always |
| Events | Events and workshops with registration | Yes |
| Finance | Transactions, invoices with Swiss QR-bill, reminders | Yes |
| Functions | Club offices and who holds them | Yes |
| Groups | Teams, committees, interest groups | Yes |
| Polls | Member polls and voting | Yes |
| Posts | Announcements and community posts | Yes |
| Codes | Encrypted door codes and passcodes | No |
| Inventory | Tools, machines, materials, checkouts | No |
| Bindings | Sync club data with external services | No |
| Mail | Club mailboxes and addresses | No, and needs the platform's mail server |

- **Switching off** hides the module and its menu entries for everyone. The
  data stays and comes back when you switch it on again.
- **Dependencies:** a module needs the ones it builds on (Mail needs Groups,
  for example). Hubra refuses to switch off a module that another enabled
  module needs.
- **Settings:** some modules have their own settings, shown under the module.
  Secret values (API tokens) are never shown again; leave the field empty to
  keep the stored value.
- **Blocked:** the platform team can block a module for your club. It then
  stays off.
- **Plugins** (for example keys, budgets, bank import, Discord) appear in the
  same list once the platform team has installed them for the installation.
  You switch them on like any other module. Ask the platform team if one you
  need is missing.

## Settings

### Club (Verein)

| Section | What it does |
| ------- | ------------ |
| Club identity | Name and description |
| Branding | Primary, secondary and accent colour |
| Localization | Time zone, the club's default language, date format |
| Privacy | Whether all members see the member directory; whether groups are listed publicly |
| Membership | Leaving needs approval (see [Leaving](#leaving)) |
| Announcement Banner | A line shown at the top of every page, for example for the general meeting |

### Domains

Add a domain the club owns and confirm it with the DNS TXT record shown.
Hubra records the confirmed domain; serving the club app or mail under it is
not built yet.

### Advanced (Erweitert)

The club's raw settings as key and value. Change these only when the
documentation or the platform team tells you to; the other screens set the
same values safely.

### Translations (Übersetzungen)

Every text in the app can be changed for your club, per language. Texts the
app uses but nobody has translated yet are marked, so you can fill them in.

## Records and history

- **Audit log (Protokoll):** who changed what and when in the club. Use it
  before asking "who deleted …".
- **Backups:** the platform makes daily, weekly and monthly backups of every
  club. Clubs have no backup screen. If data was lost, ask the platform team
  to restore your club from a backup from before the mistake; other clubs are
  not affected, but everything in your club since that backup is replaced.
