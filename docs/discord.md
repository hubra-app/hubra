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

One Discord application serves every club. Below, `https://api.hubra.club`
stands for your API address (`API_PUBLIC_URL`). manage › Diagnostics ›
Discord shows the exact addresses for your instance under **Values for the
Developer Portal**.

### 1. Create the application

Open <https://discord.com/developers/applications>, click **New
Application**, name it **Hubra** and give it the Hubra logo.

### 2. Copy four values into Hubra

| Developer Portal | Hubra field (manage › Platform settings › Discord) |
| --- | --- |
| General Information › **Application ID** | Discord application ID |
| General Information › **Public Key** | Discord public key |
| OAuth2 › **Client Secret** (click *Reset Secret*) | Discord client secret |
| Bot › **Token** (click *Reset Token*) | Discord bot token |

Save in manage. The values take effect at once, with no restart. The secret
and the token are stored encrypted and never shown again; only platform
managers can change them.

### 3. Redirect URIs (OAuth2 › Redirects)

Add **both**. They must match character for character, including
`https` and with no trailing slash:

| Redirect | Used when |
| --- | --- |
| `https://api.hubra.club/api/v1/apps/callback/discord` | a club admin adds the bot to the club's server (Einstellungen › Verbundene Apps) |
| `https://api.hubra.club/api/v1/account/linked-accounts/discord/callback` | a member links their Discord account (Mein Konto › Verknüpfungen) |

If one is missing, Discord shows "Invalid OAuth2 redirect_uri" at that step.

### 4. Bot settings (Bot page)

| Setting | Value | Why |
| --- | --- | --- |
| Public Bot | **on** | otherwise only you could add it, and no club could |
| Requires OAuth2 Code Grant | **off** | Hubra adds the bot with its own OAuth flow |
| Presence Intent | **off** | not needed |
| Server Members Intent | **off** | the bot never reads member lists |
| Message Content Intent | **off** | the bot never reads messages |

The bot uses no gateway connection. It answers over HTTP (step 5) and calls
the REST API, so it never shows as "online" in Discord, and that is normal.

### 5. Interactions Endpoint URL

General Information › **Interactions Endpoint URL**:
`https://api.hubra.club/api/v1/discord/interactions`

Discord sends a signed test request when you save, so the backend must be
up, the Discord plugin installed, and the public key from step 2 saved in
Hubra first. Slash commands and buttons arrive here.

### 6. Permissions

You don't tick permissions in the portal. Hubra asks for them in the link
it builds when a server adds the bot, and only for what the club allowed.
It never asks for Administrator.

| Server | OAuth2 scopes | Permissions | When |
| --- | --- | --- | --- |
| A club's server | `bot`, `applications.commands` | Change Nickname | always (the bot takes the club's name) |
| | | View Channels, Send Messages, Embed Links | the club allows "announce" or "commands" |
| | | Manage Roles | the club allows "roles" |
| The platform's own server (platform log) | `bot` | View Channels, Send Messages, Embed Links (`19456`) | always |
| Member account link | `identify` | none | a member links their account |

On a club's server the bot shows the club's name, logo and a short bio
(plugin 2.1+, per server, so other servers still see Hubra). The app's own
name, icon and description in the Developer Portal are what every other
place shows: give it the Hubra mark (square PNG, 512 px or more) and a line
such as "The Hubra bot for your club: events, posts, polls, reminders,
sign-ups and roles that follow your groups."

Manage Roles only works on roles **below the bot's own role** in the server's
role list. Drag the Hubra role above the roles the club maps.

### 7. Check it

Open manage › **Diagnostics › Discord** and click **Check now**. It shows:

- whether the bot token signs in, and as which bot;
- how many servers the bot is on;
- whether the Interactions Endpoint URL matches;
- the platform log channel and its last post;
- every club server and its last error.

A failing check also shows on manage › Alerts.

Without the application ID and bot token, the Discord app shows as "not set
up on this platform" to clubs, and nothing else changes.

### Troubleshooting

| You see | Fix |
| --- | --- |
| "Invalid OAuth2 redirect_uri" | add the exact redirect from step 3 |
| Bot sign-in: Discord refused the bot token (401) | reset the token in the portal and save the new one in Hubra |
| Interactions URL can't be saved in the portal | the backend is unreachable, the plugin is not installed, or the public key in Hubra is wrong |
| "Bot not on server" for a club | someone removed the bot; the club connects it again under Verbundene Apps |
| Roles don't change | move the Hubra role above the mapped roles; check the club allowed "roles" |
| Platform log: the bot cannot see the channel | add the bot to the platform server (link in Platform settings › Discord) and allow it to view the channel |

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
