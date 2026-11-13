import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'backup-retention',
  keys: [
    'backup.keep_daily',
    'backup.keep_weekly',
    'backup.keep_monthly',
    'backup.keep_manual_days',
    'backup.keep_deleted_club_days',
  ],
  builtIn: [
    'backup.keep_daily',
    'backup.keep_weekly',
    'backup.keep_monthly',
    'backup.keep_manual_days',
    'backup.keep_deleted_club_days',
  ],
  title: () => tr('Aufbewahrung', 'Retention'),
  desc: () =>
    tr(
      'Jede Nacht um 3 Uhr entsteht ein globales Backup und eines pro Verein, sonntags zusätzlich ein wöchentliches, am 1. ein monatliches. Danach löscht Hubra, was diese Regeln nicht mehr behalten, auch im Bucket. Gezählt wird pro Satz, also für jeden Verein für sich. Fehlgeschlagene Backups zählen nicht.',
      'Every night at 3:00 Hubra makes a global backup and one per club, plus a weekly one on Sundays and a monthly one on the 1st. Afterwards it deletes what these rules no longer keep, in the bucket too. Counts are per set, so each club on its own. Failed backups do not count.',
    ),
  de: {
    'backup.keep_daily': [
      'Tägliche Backups behalten',
      'So viele der neuesten täglichen Backups bleiben pro Satz (das globale und das jedes Vereins), 1 bis 365',
    ],
    'backup.keep_weekly': [
      'Wöchentliche Backups behalten',
      'So viele der neuesten wöchentlichen Backups (Sonntag) bleiben pro Satz, 1 bis 365',
    ],
    'backup.keep_monthly': [
      'Monatliche Backups behalten',
      'So viele der neuesten monatlichen Backups (am 1.) bleiben pro Satz, 1 bis 365',
    ],
    'backup.keep_manual_days': [
      'Manuelle Backups behalten (Tage)',
      'So viele Tage bleibt ein von Hand erstelltes Backup; 0 behält es, bis es jemand löscht',
    ],
    'backup.keep_deleted_club_days': [
      'Backups gelöschter Vereine behalten (Tage)',
      'So viele Tage bleibt jedes Backup eines endgültig gelöschten Vereins, ab dem Tag, an dem es erstellt wurde; 0 behält sie wie die jedes anderen Vereins',
    ],
  },
})
