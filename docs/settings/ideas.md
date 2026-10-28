# Bigger settings and feature ideas

Ideas that came out of the settings review (October 2026) and are too big
for an overnight change. Rough size: S = a day, M = a few days, L = a week
or more. Nothing here is decided.

## Make the existing club settings work

| Idea | Size | Notes |
| --- | --- | --- |
| Club colours in the club app | M | Read `primary_color` from `/settings/club-profile` and build the Mantine theme from it. Needs a contrast check, so a pale colour doesn't make buttons unreadable, and a decision on how far a club may override the Hubra violet. |
| Club logo and name in the sidebar | S | The profile endpoint already returns them. Logos are stored as data URLs in `Tenant.settings`, up to 2 MB, which is heavy for every page load; move them to object storage first. |
| Club time zone and date format | M | Use them in the shared date formatting helper and in mails (invoice due dates are ISO today). Touches many screens. |
| Club language as the default for new members and for mails to people without a language | S | `de-CH` is hard-coded in invites and several mails. |
| Member directory visible to all members | M | Today the directory needs `members.members.read`. Needs a members-only directory endpoint that returns only name, photo and the fields a member chose to share. |
| List groups publicly | S | Show groups on the club's join page on SSO. |

## Membership

| Idea | Size | Notes |
| --- | --- | --- |
| Default tier for invites and approved applications | S | Club setting; used when an invite or application names no tier. |
| Auto-approve join requests | S | Club setting, off by default. Pairs with the platform-wide "club request approval mode" that is still open. |
| Application form with custom questions | L | Questions defined per club, answers kept on the application and copied to the member. |
| Member limit and waiting list | M | Close join requests automatically at N members, keep a waiting list. |
| Minimum age, or guardian consent below it | M | Needs a birth date on the account and a consent step on SSO. |
| Membership renewal / end dates per tier | L | Tiers with a fixed term, reminders before the end, automatic leave or renewal invoice. |

## Notifications

| Idea | Size | Notes |
| --- | --- | --- |
| Per-member notification preferences | M | Per kind (posts, events, polls, invoices) and per channel (in-app, email). New table on the user or member; the club settings added now become the club default. |
| Email digest | M | Daily or weekly summary of new posts, events and polls instead of one notification each. Celery job per club. |
| Web push | L | Service worker, VAPID keys as platform settings, subscription table. |
| Event reminders | S | "Remind attendees N hours before" as an events module setting. |

## Finance

| Idea | Size | Notes |
| --- | --- | --- |
| Reminder fees | S | Add a fixed fee to the second reminder (finance setting). |
| Third reminder and "hand over to collections" status | S | Builds on the reminder settings added now. |
| Prefill due dates in the invoice forms | S | Frontend reads the finance config; needs the module config readable by finance users, not only by module admins. |
| Default invoice text and footer | S | Finance setting printed on the QR-bill PDF. |
| Pro-rata fees for members who join mid-period | M | Pricing change in `hubra/core/pricing.py`. |
| Other currencies (EUR) | M | QR-bill supports CHF and EUR; amounts and mails assume CHF today. |

## Platform (Manage)

| Idea | Size | Notes |
| --- | --- | --- |
| Club request approval: review or automatic | S | Platform setting; open since the platform/club split. |
| Modules a new club starts with | S | `Feature.default_enabled` exists; give it a form in Manage. |
| Sign-up on or off | S | For closed installs: only invited people can create an account. |
| Imprint and privacy links | S | Platform settings shown in the SSO footer and in mails. |
| Platform notice | S | A banner on every club for maintenance windows, like the club banner. |
| Instance name and logo | M | For installs that are not hubra.club. |

## Features as plugins

These fit the plugin system better than core, so a club that doesn't need
them never sees them.

| Idea | Size | Notes |
| --- | --- | --- |
| Shift and duty rosters | L | Volunteer shifts for events, sign-up, swap, reminders. |
| Room and equipment booking | M | Builds on inventory; calendar view and conflicts. |
| Member cards with a QR code | M | Wallet pass or PDF; check-in at events. |
| Attendance tracking for trainings | M | Per group, with statistics per member. |
| Newsletter | M | Builds on mail; sends a post to all members or a group by email. |
| Document library | M | Statutes, minutes, forms; per-role access. |
