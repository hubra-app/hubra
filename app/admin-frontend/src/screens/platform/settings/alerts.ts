import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'alerts',
  keys: [
    'alerts.cooldown_minutes',
    'alerts.retention_days',
    'alerts.manage_url',
  ],
  builtIn: [
    'alerts.cooldown_minutes',
    'alerts.retention_days',
  ],
  title: () => tr('Versand der Warnungen', 'Alert delivery'),
  desc: () =>
    tr(
      'Warnmails gehen an Plattform-Admins (Superadmins und Rollen mit Plattform-Einstellungen), nicht an Support. Jede Person wählt unter Warnungen › Meine Warnungen, welche sie bekommt.',
      'Alert mails go to platform admins (superadmins and roles with platform settings), not to Support. Each person picks which ones they get under Alerts › My alerts.',
    ),
  de: {
    'alerts.cooldown_minutes': [
      'Pause zwischen Warnmails (Minuten)',
      'So lange kommt dieselbe Art Warnung nicht noch einmal per Mail. 0: jedes Mal. Ausfälle und Wiederherstellungen kommen immer',
    ],
    'alerts.retention_days': [
      'Ereignisprotokoll aufbewahren (Tage)',
      'So lange bleiben gesendete und fehlgeschlagene Mails, Ausfälle und Warnungen im Protokoll (1 bis 365)',
    ],
    'alerts.manage_url': [
      'Adresse von manage',
      'Für den Knopf «Warnungen öffnen» in Warnmails, z. B. https://manage.hubra.club. Leer: kein Knopf',
    ],
  },
})
