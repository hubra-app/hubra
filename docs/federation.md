# Federation view (associations and member clubs)

For umbrella associations (Verbände) whose member clubs use Hubra too.

## For the association

1. Turn on the module **Federation** (Einstellungen › Module). The sidebar gets **Verband**.
2. Under **Verband › Verein einladen**, enter the club's address in Hubra (`rc-uri` from `hubra.club/rc-uri`).
3. When the club accepts, the page shows its number of active members. If the club also shares contacts, it shows who holds its functions (Präsidium, Kassier, …).
4. Tick **Mit Mitgliedvereinen teilen** on an event and every member club sees it under Anlässe › Vom Verband.

Permissions: `federation.federation.read` (see the page) and `federation.federation.manage` (invite and remove clubs). Admin roles have both.

## For the member club

Einstellungen › Verein › **Verbände** shows invitations and memberships. Only the club's admins can answer them.

- **Beitreten** accepts. **Kontakte unserer Ämter teilen** is off unless the club ticks it.
- The association sees the number of active members and, when shared, the function holders' names. It gets the function's own mail address or the holder's club address (`public_email`), never a private sign-in address. It sees no other member data.
- **Austreten** ends the link at any time. Sharing stops at once.

## How it works

- `federation_links` (public schema) holds association, club, status (`invited` or `active`) and `share_contacts`.
- `club_events.federation_shared` marks an association's event.
- Reads across clubs run in the other club's schema (`in_club`) and select plain columns only.
- Shared events show only while the association has the Federation and Events modules on.

API:

| Who | Request |
| --- | --- |
| Association | `GET/POST /api/v1/app/federation/clubs`, `DELETE /api/v1/app/federation/clubs/<id>` |
| Member club (admins) | `GET /api/v1/app/settings/associations`, `POST …/<id>/accept`, `PATCH …/<id>`, `DELETE …/<id>` |
| Member club (members) | `GET /api/v1/app/events/from-associations` |
