# Membership rules: invite-only clubs and invite validity

**Where:** Settings › Verein › Mitgliedschaft (next to "Leaving needs
approval"). Stored in `Tenant.settings["branding"]`, validated by
`ClubSettingsSchema`.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `join_requests_open` | bool | on | Off: people can't ask to join from join.hubra.club; the club adds members by invite only |
| `invite_valid_days` | int, 1 to 60 | 14 | How long a new invite link works |

**Invite-only.** `POST /system/clubs/<slug>/join` answers
`403 JOIN_REQUESTS_CLOSED` when the setting is off. Platform managers, who
join directly, are not affected. `GET /system/clubs` and
`GET /system/clubs/<slug>` return `acceptsRequests`, and the SSO club list
and join page show "Nur auf Einladung" instead of the "Ask to join" button.
Applications that were already filed stay and can still be approved.

**Invite validity** applies to invites sent after the change; existing links
keep their expiry.

**Code.** `hubra/core/tenant/club_settings.py` (`club_setting()`,
`accepts_join_requests()`).

**Not included.** A default tier for invites, auto-approval of join
requests, an application form with custom questions, and a member limit.
See [ideas.md](ideas.md).

**Tests:** `tests/tenant/test_join_club.py`, `tests/members/test_invites.py`,
`tests/test_club_settings_api.py`.
