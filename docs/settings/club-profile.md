# Club profile for members, and the announcement banner

**Problem.** The club's name, logo, colours, regional settings and
announcement banner could be saved under Settings › Verein, but only admins
could read them back (`GET /admin/club-settings`), so nothing used them.

**API.** `GET /api/v1/settings/club-profile`, any signed-in member of the
club:

```json
{
  "club_name": "Rowing Zug",          // falls back to the club's name
  "club_description": null,
  "logo": null,
  "primary_color": "#7441e0",
  "secondary_color": null,
  "accent_color": null,
  "timezone": "Europe/Zurich",
  "locale": "de-CH",
  "date_format": "DD.MM.YYYY",
  "banner": "GV am Freitag!"          // null unless the banner is on
}
```

Membership rules and privacy switches are not in it; they stay admin-only.

**Frontend.** `components/Shell/ClubBanner.tsx` shows the banner at the top
of every page in the club app. A member can close it; it stays hidden for
the browser session until the text changes. Saving Settings › Verein
refreshes it.

**Not included.** Using the colours, logo, time zone and date format; see
[ideas.md](ideas.md). The endpoint is there so those can follow without
another API change.

**Tests:** `tests/test_club_settings_api.py`.
