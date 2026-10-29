# Club and platform settings

What a club admin and a platform manager can set today, what was missing,
and what was added in October 2026. One short spec per new setting sits next
to this file; bigger ideas are in [ideas.md](ideas.md).

## Where settings live

| Where in the UI | Stored in | Read with | Who |
| --- | --- | --- | --- |
| Club app › Settings › Verein | `Tenant.settings["branding"]` (public schema) | `hubra.core.tenant.club_settings.club_setting()` | club admins |
| Club app › Settings › Module & Plugins › *module* › Einstellungen | `TenantFeature.config` | `hubra.core.modules.get_config("<code>")` | club admins (`modules.modules.write`) |
| Club app › Settings › Erweitert | `setting` table in the club schema (key/value) | `SettingService.get()` | per namespace permission |
| Manage › Platform Settings | `platform_settings` table | `hubra.core.services.platform_settings` | superadmins |

Rule of thumb for new settings: a setting that belongs to one module goes in
that module's manifest (`settings=`), so it disappears with the module and
gets a form for free. A setting about the club as a whole goes in
Settings › Verein. Required modules (core, members, roles) have no settings
form, which is why the membership rules below live under Verein.

## Review (main at 2ada90a)

Most of Settings › Verein was saved and then never read:

| Setting | Before | Now |
| --- | --- | --- |
| Club name, description, logo | saved only | readable by members ([club-profile.md](club-profile.md)); not yet shown |
| Primary / secondary / accent colour | saved only | readable by members; not yet applied to the theme (see ideas) |
| Time zone, language, date format | saved only | readable by members; not yet used for dates or mails (see ideas) |
| Member directory visible to all | saved only | unchanged; needs a members-only directory endpoint (see ideas) |
| List groups publicly | saved only | unchanged (see ideas) |
| Leaving needs approval | used | unchanged |
| Announcement banner | saved only | **shown** at the top of the club app ([club-profile.md](club-profile.md)) |
| Accept requests to join | missing | **new** ([membership-rules.md](membership-rules.md)) |
| Invites valid for (days) | fixed 14 | **new** ([membership-rules.md](membership-rules.md)) |

Values that were fixed in the code and are now module settings:

| Module | Setting | Spec |
| --- | --- | --- |
| Finance | payment term, invoice emails, reminders and their days | [finance-billing.md](finance-billing.md) |
| Posts, Events, Polls | notify members on publish | [publish-notifications.md](publish-notifications.md) |

Platform settings (Manage) cover the mail relay, the system sender and the
backup bucket. Missing there: how club requests are approved, which modules
a new club starts with, sign-up on/off, and legal links. These are in
[ideas.md](ideas.md).

## API changes in this round

All additive; existing clients keep working.

- `GET /api/v1/settings/club-profile` (new, any member of the club).
- `GET /api/v1/system/clubs` and `GET /api/v1/system/clubs/<slug>`: new
  field `acceptsRequests` (bool).
- `POST /api/v1/system/clubs/<slug>/join`: new error
  `403 JOIN_REQUESTS_CLOSED`.
- `PATCH /api/v1/admin/club-settings`: new fields `join_requests_open`
  (bool) and `invite_valid_days` (1 to 60).
- `POST /api/v1/finance/invoices/bulk`: `due` is now optional.
- `GET /api/v1/modules`: finance, posts, events and polls now list settings.
