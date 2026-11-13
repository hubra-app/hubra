import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'discord-app',
  keys: [
    'discord.client_id',
    'discord.public_key',
    'discord.client_secret',
    'discord.bot_token',
  ],
  title: () => tr('Discord-App', 'Discord app'),
  desc: () =>
    tr(
      'Die eine Hubra-App auf Discord: Vereine fügen damit den Bot zu ihrem Server hinzu, Mitglieder verknüpfen ihr Konto. Einrichtung in docs/discord.md. Ohne diese Werte ist Discord für Vereine nicht verfügbar.',
      'The one Hubra application on Discord: clubs add the bot to their server with it, members link their account. Setup in docs/discord.md. Without these values Discord is not available to clubs.',
    ),
  de: {
    'discord.client_id': [
      'Discord-Application-ID',
      'Developer Portal › deine App › General Information › Application ID',
    ],
    'discord.public_key': [
      'Discord-Public-Key',
      'General Information › Public Key; prüft, dass Interaktionen von Discord kommen',
    ],
    'discord.client_secret': [
      'Discord-Client-Secret',
      'OAuth2 › Client Secret. Wird verschlüsselt gespeichert',
    ],
    'discord.bot_token': ['Discord-Bot-Token', 'Bot › Token. Wird verschlüsselt gespeichert'],
  },
})
