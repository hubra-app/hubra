# Discord

Hubra has one Discord bot for every club on the platform. A club adds it to
its own Discord server under **Einstellungen › Verbundene Apps** (the
`discord` plugin must be installed and switched on). Members link their own
Discord account on the SSO account page (**Mein Konto › Verknüpfungen**), so
the bot can recognise them.

The bot token stays in the platform's secret. Clubs never see or paste a
token; what Hubra stores per club is only the link (Discord server id,
channel, role mapping).

## Set up the Discord application (once per platform)

1. Open <https://discord.com/developers/applications> and create an
   application named **Hubra**. Give it the Hubra logo.
2. **General Information**: copy the *Application ID* (`DISCORD_CLIENT_ID`)
   and the *Public Key* (`DISCORD_PUBLIC_KEY`).
3. **OAuth2**: reset and copy the *Client Secret* (`DISCORD_CLIENT_SECRET`).
   Under *Redirects*, add both:
   - `https://api.hubra.club/api/v1/apps/callback/discord` (a club connects its server)
   - `https://api.hubra.club/api/v1/account/linked-accounts/discord/callback` (a member links their account)
4. **Bot**: reset and copy the *Token* (`DISCORD_BOT_TOKEN`).
   - Leave **Public Bot** on, or clubs can't add it to their servers.
   - Leave **Requires OAuth2 Code Grant** off.
   - Leave all three **Privileged Gateway Intents** off. The bot doesn't
     read messages or member lists.
5. Put the values into the backend's environment (for hubra.club: the SOPS
   secret `hubra-env`) together with `API_PUBLIC_URL`, then restart the
   backend and the worker:

   ```
   API_PUBLIC_URL=https://api.hubra.club
   DISCORD_CLIENT_ID=...
   DISCORD_CLIENT_SECRET=...
   DISCORD_BOT_TOKEN=...
   DISCORD_PUBLIC_KEY=...
   ```

6. Once the backend runs with these values, set **General Information ›
   Interactions Endpoint URL** to
   `https://api.hubra.club/api/v1/discord/interactions`. Discord checks the
   URL when you save, so the backend must already be up.

Without these values the Discord app shows as "not set up on this platform"
and nothing else changes.

## What the bot may do on a club's server

It asks for View Channels, Send Messages, Embed Links and Manage Roles, plus
slash commands. It never asks for Administrator. Manage Roles only works on
roles below the bot's own role, and Hubra only changes roles the club mapped.
