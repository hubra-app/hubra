import { tr } from '@/lang'
import type { EventCategory, EventLevel, PlatformEvent } from '@/api/platform'

export const categoryLabel = (c: EventCategory | 'performance'): string =>
  ({
    mail: tr('Mail', 'Mail'),
    relay: 'Relay',
    service: tr('Dienst', 'Service'),
    backup: 'Backup',
    plugin: 'Plugin',
    system: 'System',
    alert: tr('Alarm', 'Alert'),
    performance: tr('Leistung', 'Performance'),
  })[c] ?? c

const serviceName = (key?: string) =>
  key === 'db' ? tr('Datenbank', 'Database') : key === 'redis' ? 'Redis' : (key ?? '').toUpperCase()

/** The log's messages are stored in English; known kinds are told in the
 * chosen language from their details. */
export function eventText(e: PlatformEvent): string {
  const d = e.details as Record<string, string | undefined>
  const relay = d.host ?? ''
  const name = d.relay === 'fallback' ? tr('Fallback-Relay', 'Fallback relay') : tr('Haupt-Relay', 'Main relay')
  switch (e.kind) {
    case 'mail.sent':
      return tr(`Gesendet an ${d.to}: ${d.subject}`, e.message)
    case 'mail.fallback':
      return tr(`Über das Fallback-Relay an ${d.to} gesendet: ${d.subject}`, e.message)
    case 'mail.failed':
      return tr(`Nicht zugestellt an ${d.to}: ${d.subject}`, e.message)
    case 'relay.down':
      return tr(`${name} ${relay} ist ausgefallen`, e.message)
    case 'relay.up':
      return tr(`${name} ${relay} geht wieder`, e.message)
    case 'service.down':
      return tr(`${serviceName(d.service)} antwortet nicht`, e.message)
    case 'service.up':
      return tr(`${serviceName(d.service)} antwortet wieder (nach ${d.minutes} Min.)`, e.message)
    case 'backup.failed': {
      const failed = (e.details.failed as string[] | undefined) ?? []
      return tr(`Geplantes Backup fehlgeschlagen: ${failed.join(', ')}`, e.message)
    }
    default:
      return e.message
  }
}

export const LEVEL_COLOR: Record<EventLevel, string> = { info: 'gray', warning: 'orange', error: 'red' }

export const levelLabel = (l: EventLevel): string =>
  ({ info: 'Info', warning: tr('Warnung', 'Warning'), error: tr('Fehler', 'Error') })[l] ?? l

