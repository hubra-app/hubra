import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'mcp',
  keys: [
    'mcp.url',
  ],
  title: () => tr('Adresse des Connectors', 'Connector address'),
  desc: () =>
    tr(
      'Wo der MCP-Server (Image mcp) läuft. Er hat keinen Datenbankzugriff und keine eigenen Zugangsdaten: jede Anfrage nutzt das Token der Person.',
      'Where the MCP server (the mcp image) runs. It has no database access and no credentials of its own: every request uses the person\'s token.',
    ),
  de: {
    'mcp.url': [
      'Adresse des Claude-Connectors',
      'Wo der MCP-Server (app/mcp) erreichbar ist; manage zeigt damit den Befehl zum Verbinden (https://mcp.hubra.club). Leer: nicht eingerichtet',
    ],
  },
})
