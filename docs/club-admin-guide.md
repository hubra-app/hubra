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
2. **Settings › Modules (Module).** Switch off what the
   club doesn't use; see [Modules](#modules).
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

**Posters.** Under Members › Applications, **Plakat erstellen** makes a
printable A4 poster or A6 flyer with a QR code, either for asking to join or for
booking a trial. Give each poster a tag, for example `bahnhof` or
`turnhalle`: the QR code carries it, and each request and trial booking
remembers where the person came from. The table above the button counts
requests and trials per tag over the last year, so you can see which poster
works. The poster carries the club's logo and colours from Settings › Verein ›
Erscheinungsbild (Hubra violet and gold while the club has none); the QR code
stays black on white so it scans. Print straight from the dialog; only the
poster is printed.

### Leaving

A member leaves under their account settings in the club app. With
Settings › Club › **Leaving needs approval** on, they ask instead, and you
confirm under Members › Applications. With it off, they leave at once.
Leaving keeps their invoices and entries with the club; their account and
other clubs stay.

**Notice period.** Settings › Mitgliedschaft › **Kündigungsfrist (Monate)**
and **Austritt auf** hold the rule from your statutes, for example three
months' notice to the end of the year. A member who wants to leave then
sees the earliest exit date and their invoices still open (these remain
due), and you see both on the request under Members › Applications. Asked
on 10 November with three months to the end of the year, the earliest exit
is 31 December of the next year. Hubra shows the date; approving the request
still ends the membership on the day you approve it.

### Member data

- The member list can be exported as CSV (Members › All members).
- **Archive** a member who is no longer active: they disappear from lists and
  keep their history. Archived members can be shown with the filter.
- Settings › Club › **Member directory visible to all members** decides
  whether ordinary members see the directory.

### Own fees: exemptions and reductions

Some members pay less than their tier, or nothing: a student, someone out of
work, a family member. On the member's page, the **Mitgliederbeitrag** card
shows the standard fee; **Anpassen** sets the member's own fee:

- **Befreit**: no membership fee; the invoice run skips them.
- **Eigener Betrag**: their own yearly fee, split into their billing periods.
- **Ermässigung**: the standard fee less a percentage (rounded to 5 Rappen).

A **reason** is required; the member sees it under Konto › Mitgliedschaft.
It stays out of the audit log, which only records what kind of fee was set.
An **end date** is optional. A set number of days before it (30 by default,
0 for none) the member gets a notification and a mail asking them to confirm
that the reason still applies; their answer appears on the member page and
everyone who may set own fees is notified. To keep the fee, set a new end
date (that asks again before it). After the end date the member pays the
standard fee from the first billing period that starts after it, and both
the member and the board are told. Members › Tiers lists every own fee,
ending soonest first.

Rights: `tiers.fee_adjustments.read` and `tiers.fee_adjustments.update`
(new clubs give both to the Treasurer role; admins always have them).

### Fee run preview

Every day the invoice run bills each member whose billing period has started
and who has no membership invoice for it yet. Finanzen › Rechnungen ›
**Vorschau Beitragslauf** shows what that run would issue on a day you pick,
before it does: how many invoices, the total and the due date, a total per
tier, every member with their period and amount (pro rata for a first fee,
on a payment plan, without an email address), and why members were left out
(not joined yet, invoice already issued, fee 0). The last twelve months of
membership invoices are shown for comparison. The preview creates and sends
nothing, and uses the same planning as the run itself.

Right: `finance.invoices.bulk_create`.

## Events

### Calling an event off

When an event can't take place (rain, the pitch is closed, too few sign-ups),
**Absagen** in its row (the calendar with a cross) calls it off. Pick one of
the common reasons or write your own; a reason is required. The event stays
in the calendar, struck through and marked **Abgesagt**, with the reason,
and nobody can sign up any more.

Everyone signed up or on the waitlist, and the members of the event's group,
are told with the reason in the bell, by push and in the messengers they
turned on; those signed up also get a mail. Plugins that listen to
`event.changed` (Discord, messengers) get `cancelled` and the reason too. No
reminder goes out for a cancelled event.

**Doch durchführen** (the calendar with a tick) undoes it: sign-ups are kept
and those signed up hear that it takes place after all.

Right: `events.events.update`, or the person who put the event up, or a role
held for the event's group.

### One calendar for all clubs

Members who are in several clubs find **Kalender aller Vereine** in their
account (sign-in › My account › Profile). It is one link for Google, Apple
or Outlook calendars with the events of every club they are an active
member of, each named with its club, from 90 days back on. **Nur meine
Anmeldungen** gives a second link with only the events they signed up for
(or wait for). A cancelled event stays in the calendar, marked cancelled.
Anyone with the link sees the events, so **Neuen Link erstellen** makes new
links and stops the old ones. A club with events switched off, or one the
person left or is blocked in, drops out of the calendar.

### Event templates

An event you hold again and again (the weekly training, the club evening)
can be kept as a template: the **template** icon in its row saves its place,
time, places, settings (approval, public, trial places, group) and
description under a name, without the date. **Aus Vorlage** next to
**Anlass hinzufügen** lists the templates; picking one opens the new-event
form filled in, and you only choose the date. A multi-day event keeps its
length. The bin next to a template in that list deletes it.

Templates belong to the club. Saving, listing and deleting them takes the
club-wide right `events.events.create`.

### Session notes

The attendance dialog of an event (**Anwesenheit**) has room for notes on
that date: **Was trainiert wurde** (what was trained), a **note for the
next trainer**, and a **link to a guide** (an `https://` link or a page in
the app such as a Guides page). On the next date of the same series the
dialog shows the last notes before it under **Letztes Mal**, so whoever
trains next knows where the group is.

Writing notes takes the right to take attendance (`events.events.add_attendee`,
club-wide or for the event's group). Only those see the trainer note; the
API also gives the event's members what was trained and the guide link.
Clearing all three fields removes the notes.

## Posts

### Scheduled and expiring posts

**Veröffentlichen am** in the post form holds a post back until a time of
your choice (at most a year ahead); the button then reads **Planen**. Until
then only the author and whoever may edit the post see it, marked **Geplant
für …**; within five minutes of that time it goes out at the top of the list
and members are notified as for any new post (bell, push, messengers,
`post.published`). To send a scheduled post at once, clear the date and save.
Once a post is out it cannot be scheduled again.

**Ausblenden nach** hides a post from members after a time, for a notice
that goes stale (the pitch is closed this weekend). The author and whoever
may edit it still see it, marked **Ausgeblendet**, and can give it a later
date or clear the field to show it again. The dashboard and the weekly
digest only show posts members can see.

### Must-read posts

For safety rules, rule changes or the papers for the general meeting, tick
**Lesebestätigung verlangen** in the post form. Members then see
**Gelesen, bestätigen** under the post and confirm with one tap. Whoever may
edit the post sees **n bestätigt**; it opens the list of who confirmed (and
when) and which active members have not yet.

Those still missing get one reminder in the bell (and by push and in the
messengers they turned on) a number of days after the post went out:
Beiträge › Einstellungen › **Erinnerung bei Lesebestätigung (Tage)**,
7 by default, 0 for no reminder.

### Comment moderation

Who moderates is a right on the roles page: **Moderate posts and comments**
(`posts.posts.moderate`). Give it to a role club-wide, or to a role for a
group so it moderates that group's posts only. Admins always moderate.

Any member can **Melden** (report) someone else's comment from its menu,
with an optional reason. The first report of a comment tells the moderators
in the bell. Reporters stay anonymous to everyone but the moderators.

Moderators see how often each comment was reported. From the comment's menu
they **Ausblenden** (hide) it, so members only see *Von der Moderation
ausgeblendet* in its place, **Einblenden** (show) it again, or **Behalten**
(keep) it, which closes its reports. Club-wide moderators also find a
**Moderation** box above the posts, with the reported comments that are
still visible and the members who are muted.

**Beim Kommentieren stummschalten** (mute in comments) stops a member from
commenting for 1 to 30 days, with an optional reason. They can still read
posts. **Aufheben** (lift) in the Moderation box ends the mute early. Every
hide, show, keep, mute and lift is in the audit log.

## Roles and permissions

Permissions (Berechtigungen) lists the club's roles. Each role grants
permissions per area, such as members, finance, events or settings, with
read, create, update and delete. A member can have several roles; they get
everything any of them grants.

- **Owner** and **Admin** are fixed roles with full access.
- **Standard roles.** Every club has Mitglied (the default role), Vorstand,
  Aktuar/in and Kassier/in, and the functions Präsident/in and
  Vizepräsident/in (Admin and Vorstand), Aktuar/in and Kassier/in (Vorstand
  plus their own role). See [roles.md](roles.md).
- **One level per module.** Each module has Keine, Ansehen, Bearbeiten or
  Alles for the role. "Keine" hides the module from the role's holders
  everywhere; their own data from it (invoices, claims, items) stays on
  their profile.
- A new member gets the role marked as default.
- **Templates** set up a typical role set in one step (standard club, small
  association, makerspace).
- **Functions** (Funktionen), such as president or treasurer, are under
  Members › Functions. They record who holds an office, and give their
  holders the roles you pick for them ("Gibt die Rollen") while their term
  runs.
- **A role for one group.** A role can be given to a member for one group
  only (on the role's Members tab). It then counts for that group's things:
  the group itself, and the events, posts and polls that belong to the group.
  An "Event lead" role given for the youth team lets its holder create the
  youth team's events, edit and delete them, handle their sign-ups and take
  attendance, and nothing outside the group. The same goes for posts (the
  holder edits and removes the group's posts like a moderator) and polls.
  Events, posts and polls get their group in their form ("Gruppe"); a member
  who manages only some groups can choose only those and can't move an item
  out of them. Everything stays visible to the whole club, as before.

## Modules

Settings › Modules lists everything the club can use. Missing one? "Suggest a module" at the end of the list sends the idea to the Hubra team (area "Module"); once it is on the roadmap, every club can vote for it.

| Module | What it is | On for a new club |
| ------ | ---------- | ----------------- |
| Core, Members, Roles & permissions | Sign-in, dashboard, members, roles | Always |
| Events | Events and workshops with registration | Yes |
| Finance | Invoices with Swiss QR-bill, reminders, fees | Yes |
| Functions | Club offices and who holds them | Yes |
| Groups | Teams, committees, interest groups | Yes |
| Polls | Member polls and voting | Yes |
| Posts | Announcements and community posts | Yes |
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
- **More modules** (for example the books, inventory, codes, keys, budgets,
  bank import, Discord) appear in
  the same list once the platform offers them. You switch them on like any
  other module. Clubs don't install anything: behind the scenes some modules
  are plugins, which let the platform ship and update a module without a
  release of the whole app. Ask the platform team if one you need is missing.

## Annual accounts

Finance › Annual accounts (Jahresrechnung) turns the year's bookings into a
balance sheet and income statement for the general meeting. You need
`finance.accounts.read` to see it, `finance.accounts.update` to change the
chart of accounts and opening balances, and `finance.accounts.close` to close
a year.

- **Chart of accounts:** each club starts with the standard Swiss club chart
  (1000 Kasse, 1020 Bank, 3000 Mitgliederbeiträge, 6000 Raumaufwand …). New
  categories get an account from their name; check the mapping under "Chart of
  accounts" and add accounts of your own there. Unmapped income and expenses
  land in 3800 / 6900 and are flagged.
- **Cash basis:** the income statement counts completed payments in the year.
  Cash payments go to 1000 Kasse, everything else to 1020 Bank. Open invoices
  are listed in the notes, not booked.
- **Opening balances:** taken from the closed previous year. For the first
  year in Hubra, enter them once ("Opening balances").
- **Fiscal year:** starts in the month set under Finance › Settings (January by
  default).
- **Closing:** once the year is over and the previous one is closed (or has no
  bookings), "Close year" fixes the figures and locks the year's bookings.
  "Reopen" undoes it; both are in the audit log.
- **PDF:** the PDF button gives the accounts with the previous year beside them,
  ready to print for the general meeting.

## Settings

### Club (Verein)

| Section | What it does |
| ------- | ------------ |
| Club identity | Name and description |
| Branding | Primary, secondary and accent colour |
| Localization | Time zone, the club's default language, date format |
| Privacy | Whether all members see the member directory; whether groups are listed publicly |
| Membership | Leaving needs approval, notice period (see [Leaving](#leaving)) |
| Announcement Banner | A line shown at the top of every page, for example for the general meeting |
| Hubra support | Whether Hubra support must ask before opening the club, and their requests (see below) |

**Hubra support in your club.** When Hubra support opens your club to help
(as one of your members, for at most two hours, with a banner the whole
time), the audit log shows it: "Support-Zugriff (ansehen)" or "(mit
Änderungen)" with the member, the length and the reason, and "Support-Zugriff
beendet" at the end. With **Support-Zugriff nur mit Freigabe** on, support
asks first: your admins get a notification, and the request shows under
Settings › Club › Hubra-Support with **Freigeben** and **Ablehnen**. An
approval opens one session, as asked (length, look or change), within 24
hours. Support can't approve its own request or turn the rule off while
inside your club.

### Domains

Add a domain the club owns, then publish the TXT record shown, for example:

| Type | Name | Value |
| ---- | ---- | ----- |
| TXT | `_hubra-verify.fcx.ch` | `hubra-verify=3f9c…` |

The record has its own name, so it also works for a host such as
`members.fcx.ch` that points somewhere with a CNAME. A record on the domain
itself (`fcx.ch`) from before still counts.

- Hubra looks for the record every minute for the first 10 minutes, then
  every hour for 72 hours. **Verify** checks right away. After 72 hours only
  **Verify** checks; a domain that is not verified within 7 days is removed.
- A domain nobody verified does nothing: it can't be the primary domain or
  the club's mail domain, and after 72 hours another club may claim it.
- A verified domain is checked again every week. Leave the record in place:
  if it is gone for 14 days, the domain is no longer verified until you
  verify it again.
- The club's mail domain (**Advanced**, `mail.domain`) must be one of the
  club's verified domains, or the platform's own mail domain.

Serving the club app under a custom domain is not built yet.

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
- **Your own backup key (Settings › Verschlüsselung):** a guide makes a key
  pair in your browser, has you store the private key (password manager,
  second copy with another board member) and checks that you did. Every new
  backup is then also encrypted to your key, so you can open your backups
  yourself with the free tool [age](https://age-encryption.org). The platform
  can still restore them. Losing the key costs you that access, not data.
- **Only our key:** optional, on the same page. New backups are then
  encrypted to your key alone, so nobody else can open them, the platform
  team included. The platform can then no longer restore your club unless
  you hand over the private key, and if you lose it those backups are gone.
  Turn it on only if the key is stored safely in at least two places.
