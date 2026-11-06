import { tr } from '@/lang'
import type { AlertType, EventCategory, EventLevel, PlatformEvent } from '@/api/platform'

export const categoryLabel = (c: EventCategory | 'performance'): string =>
  ({
    mail: tr('Mail', 'Mail'),
    relay: 'Relay',
    service: tr('Dienst', 'Service'),
    backup: 'Backup',
    plugin: 'Plugin',
    system: 'System',
    alert: tr('Alarm', 'Alert'),
    discord: 'Discord',
    performance: tr('Leistung', 'Performance'),
  })[c] ?? c

const serviceName = (key?: string) =>
  key === 'db' ? tr('Datenbank', 'Database') : key === 'redis' ? 'Redis' : (key ?? '').toUpperCase()

/** "0.3.0 (abc1234)" from an upgrade event's build, like the backend writes it. */
export function buildLabel(b: unknown): string {
  const build = (b ?? {}) as { commit?: string | null; version?: string | null }
  const version = build.version ?? '?'
  return build.commit ? `${version} (${build.commit.slice(0, 7)})` : version
}

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
    case 'backup.manual_failed':
      return tr(`Backup #${d.id} (${d.scope}) fehlgeschlagen: ${d.error}`, e.message)
    case 'backup.verify_failed':
      return tr(`Prüfung von Backup #${d.id} (${d.scope}) fehlgeschlagen: ${d.error}`, e.message)
    case 'backup.restore_failed':
      return tr(`Wiederherstellung von ${d.scope} aus Backup #${d.id} fehlgeschlagen: ${d.error}`, e.message)
    case 'backup.deleted':
      return tr(`Backup #${d.id} (${d.scope}) gelöscht von ${d.by}`, e.message)
    case 'backup.pruned': {
      const n = Object.values((e.details.deleted as Record<string, number> | undefined) ?? {}).reduce((a, b) => a + b, 0)
      return tr(`Aufbewahrung hat ${n} alte Backups entfernt`, e.message)
    }
    case 'error.new':
      return tr(`Neuer Fehler: ${d.type} in ${d.route} (${d.build})`, e.message)
    case 'error.regressed':
      return tr(`Behobener Fehler wieder da: ${d.type} in ${d.route} (${d.build})`, e.message)
    case 'upgrade.baseline':
      return tr(`Läuft: ${buildLabel(e.details.to)}`, e.message)
    case 'upgrade.started':
      return tr(`Update gestartet: ${buildLabel(e.details.from)} → ${buildLabel(e.details.to)}`, e.message)
    case 'upgrade.done':
      return tr(`Update abgeschlossen: ${buildLabel(e.details.from)} → ${buildLabel(e.details.to)}`, e.message)
    case 'upgrade.stuck':
      return tr(`Update auf ${buildLabel(e.details.to)} nach 30 Min. nicht fertig`, e.message)
    default:
      return e.message
  }
}

export const LEVEL_COLOR: Record<EventLevel, string> = { info: 'gray', warning: 'orange', error: 'red' }

export const levelLabel = (l: EventLevel): string =>
  ({ info: 'Info', warning: tr('Warnung', 'Warning'), error: tr('Fehler', 'Error') })[l] ?? l


/** Every alert type, with its group, label and what raises it. */
export const ALERT_TYPES: {
  id: AlertType
  group: 'mail' | 'platform'
  label: () => string
  desc: () => string
}[] = [
  {
    id: 'relay_down',
    group: 'mail',
    label: () => tr('Relay ausgefallen / wieder da', 'Relay down / back'),
    desc: () =>
      tr(
        'Wenn die automatische Prüfung ein Relay zweimal hintereinander nicht erreicht, und wenn es wieder geht.',
        'When the automatic check fails to reach a relay twice in a row, and when it works again.',
      ),
  },
  {
    id: 'fallback_used',
    group: 'mail',
    label: () => tr('Fallback benutzt', 'Fallback used'),
    desc: () =>
      tr(
        'Das Haupt-Relay hat eine Mail abgelehnt (z. B. Kontingent erreicht) und das Fallback hat sie zugestellt.',
        'The main relay refused a mail (e.g. its quota is reached) and the fallback delivered it.',
      ),
  },
  {
    id: 'delivery_failed',
    group: 'mail',
    label: () => tr('Mail nicht zugestellt', 'Mail not delivered'),
    desc: () =>
      tr(
        'Keines der Relays hat eine Mail angenommen. Abgelehnte Empfängeradressen lösen keine Warnung aus.',
        'No relay accepted a mail. Refused recipient addresses raise no alert.',
      ),
  },
  {
    id: 'service_down',
    group: 'platform',
    label: () => tr('Dienst ausgefallen / wieder da', 'Service down / back'),
    desc: () =>
      tr(
        'Datenbank, Redis oder IMAP antworten eine Minute lang nicht, und wenn sie wieder gehen. Einen Datenbank-Ausfall meldet die Mail erst danach, mit seiner Dauer.',
        'The database, Redis or IMAP do not answer for a minute, and when they work again. A database outage is mailed once it is over, with how long it lasted.',
      ),
  },
  {
    id: 'backup_failed',
    group: 'platform',
    label: () => tr('Backup fehlgeschlagen', 'Backup failed'),
    desc: () =>
      tr(
        'Ein Backup (geplant oder von Hand, global oder eines Vereins), seine Prüfung oder eine Wiederherstellung ist fehlgeschlagen.',
        'A backup (scheduled or by hand, global or a club’s), its check or a club restore failed.',
      ),
  },
  {
    id: 'backup_deleted',
    group: 'platform',
    label: () => tr('Backup gelöscht', 'Backup deleted'),
    desc: () =>
      tr(
        'Jemand hat ein Backup von Hand gelöscht; die Meldung sagt, wer und welches. Was die Aufbewahrung automatisch entfernt, steht nur im Ereignisprotokoll.',
        'Someone deleted a backup by hand; the alert says who and which one. What retention removes on its own is only logged.',
      ),
  },
  {
    id: 'plugin_updates',
    group: 'platform',
    label: () => tr('Plugin-Neuigkeiten', 'Plugin news'),
    desc: () =>
      tr(
        'Neue Plugin-Versionen, automatische Updates und zurückgezogene Plugins. Standardmässig aus.',
        'New plugin versions, automatic updates and withdrawn plugins. Off by default.',
      ),
  },
  {
    id: 'upgrades',
    group: 'platform',
    label: () => tr('Updates von Hubra', 'Hubra upgrades'),
    desc: () =>
      tr(
        'Ein neuer Build wird ausgerollt, ist überall angekommen, oder hängt nach 30 Minuten noch.',
        'A new build starts rolling out, has reached every process, or is still not done after 30 minutes.',
      ),
  },
  {
    id: 'system',
    group: 'platform',
    label: () => tr('Systemwarnungen', 'System alerts'),
    desc: () =>
      tr(
        'Speicherplatz, fehlgeschlagene Hintergrundaufgaben und hohe API-Fehlerraten.',
        'Disk space, failed background tasks and high API error rates.',
      ),
  },
  {
    id: 'support_cases',
    group: 'platform',
    label: () => tr('Neue Meldungen und Ideen', 'New reports and ideas'),
    desc: () =>
      tr(
        'Jemand hat in der App ein Problem gemeldet oder eine Idee vorgeschlagen. Bearbeitet werden sie unter Support.',
        'Someone reported a problem or suggested an idea in the app. Handled under Support.',
      ),
  },
  {
    id: 'billing',
    group: 'platform',
    label: () => tr('Zahlung eines Vereins fehlgeschlagen', 'A club payment failed'),
    desc: () =>
      tr(
        'Stripe konnte das Hubra-Abo eines Vereins nicht einziehen, oder das Abo ist überfällig oder unbezahlt.',
        "Stripe could not charge a club's Hubra subscription, or the subscription is past due or unpaid.",
      ),
  },
]

/** Platform events: the audit log categories (services/platform_discord.py). */
export const PLATFORM_EVENTS: { id: string; label: () => string }[] = [
  { id: 'clubs', label: () => tr('Vereine erstellt, geändert, gesperrt, gelöscht; Module; Domains', 'Clubs created, changed, suspended, deleted; modules; domains') },
  { id: 'requests', label: () => tr('Vereinsanfragen eingereicht, angenommen, abgelehnt (in Discord mit Knöpfen Annehmen / Ablehnen)', 'Club requests submitted, approved, rejected (in Discord with Approve / Reject buttons)') },
  { id: 'access', label: () => tr('Plattformrollen, Vereinsinhaber/-admins, Impersonation', 'Platform roles, club owners/admins, impersonation') },
  { id: 'members', label: () => tr('Mitglieder kommen zu einem Verein (viele Meldungen)', 'Members joining a club (many posts)') },
  { id: 'plugins', label: () => tr('Plugins installiert, aktualisiert, entfernt; Quellen', 'Plugins installed, updated, removed; repositories') },
  { id: 'backups', label: () => tr('Backups erstellt, geprüft, wiederhergestellt, gelöscht', 'Backups created, verified, restored, deleted') },
  { id: 'platform', label: () => tr('Plattform-Einstellungen, Schlüssel, Mailserver, Übersetzungen', 'Platform settings, keys, mail server, translations') },
  { id: 'digest', label: () => tr('Tagesübersicht um 08:00: neue Vereine, Konten, Mails, offene Probleme (nur Discord)', 'Daily overview at 08:00: new clubs, sign-ups, mail, open problems (Discord only)') },
  { id: 'releases', label: () => tr('Neue Hubra-Version läuft, mit den Neuerungen (nur Discord)', 'A new Hubra version is running, with its release notes (Discord only)') },
  { id: 'security', label: () => tr('Sicherheit: Admins auf neuem Gerät oder ohne Zwei-Faktor, viele Fehlanmeldungen, alte Schlüssel (nur Discord)', 'Security: admins on new devices or without two-factor, many failed sign-ins, old keys (Discord only)') },
]
