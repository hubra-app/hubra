# Discord

Hubra has one Discord bot for every club on the platform. A club adds it to
its own Discord server under **Einstellungen › Verbundene Apps** (the
`discord` plugin must be installed and switched on). Members link their own
Discord account on the SSO account page (**Mein Konto › Verknüpfungen**), so
the bot can recognise them.

The credentials are platform settings (manage › Platform settings ›
Discord), stored encrypted with the platform's data key. Clubs never see or
paste a token; what Hubra stores per club is only the link (Discord server id,
channel, role mapping).

## Set up the Discord application (once per platform)

1. Open <https://discord.com/developers/applications> and create an
   application named **Hubra**. Give it the Hubra logo.
2. **General Information**: copy the *Application ID* and the *Public Key*.
3. **OAuth2**: reset and copy the *Client Secret*.
   Under *Redirects*, add both:
   - `https://api.hubra.club/api/v1/apps/callback/discord` (a club connects its server)
   - `https://api.hubra.club/api/v1/account/linked-accounts/discord/callback` (a member links their account)
4. **Bot**: reset and copy the *Token*.
   - Leave **Public Bot** on, or clubs can't add it to their servers.
   - Leave **Requires OAuth2 Code Grant** off.
   - Leave all three **Privileged Gateway Intents** off. The bot doesn't
     read messages or member lists.
5. In manage, open **Platform settings › Discord**, paste the four values
   and save. They take effect at once, no restart. (Platform managers only;
   the secret and the token are never shown again.)

6. Then set **General Information ›
   Interactions Endpoint URL** to
   `https://api.hubra.club/api/v1/discord/interactions`. Discord checks the
   URL when you save, so the backend must already be up.

Without them the Discord app shows as "not set up on this platform"
and nothing else changes.

## Platform log (the platform's own server)

The same bot can post platform events to a channel on the platform's own
Discord server. Set it up in manage › Platform settings › Discord ›
Platform log:

1. Click **Add the bot to the platform server** (it asks only for View
   Channels, Send Messages and Embed Links) and pick your server.
2. In Discord, turn on Developer Mode (User Settings › Advanced), right-click
   the log channel › **Copy Channel ID**, and paste it into **Platform log
   channel**. Save.
3. Pick what is posted and click **Send test message**.

Categories:

| Category | What |
| --- | --- |
| clubs | Club created, changed, suspended, deleted; modules turned on or off; custom domains unverified or expired |
| requests | Club requests submitted, approved, rejected |
| access | Platform roles, club owners and admins added or removed, impersonation |
| members | Members added to a club or accepting an invite (off by default: one post per member) |
| plugins | Plugins installed, updated, rolled back, removed; plugin repositories |
| backups | Backups created, verified, restored, deleted |
| platform | Platform settings, encryption keys, mail server, translations |
| alerts | System alerts: failed Celery tasks, API error rate, disk/Redis/Postgres checks |

Every platform audit entry (`global_audit_logs`) is posted after its change
is committed, by a Celery task, with the club, who did it, the target and the
entry's details. Values whose key looks like a secret (password, token, key,
secret, code) are shown as `***`. Alerts replace the old
`DISCORD_WEBHOOK_URL` setting, which is gone.

## What the bot may do on a club's server

It asks for View Channels, Send Messages, Embed Links and Manage Roles, plus
slash commands. It never asks for Administrator. Manage Roles only works on
roles below the bot's own role, and Hubra only changes roles the club mapped.
