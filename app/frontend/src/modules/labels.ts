import i18n from 'i18next'
import type { ModuleInfo } from '@/api/modules'

// The backend describes modules in English. Shipped modules get German
// defaults here and can be overridden per language under modules.<code>.*;
// plugins keep whatever their manifest says.
const DE: Record<string, { name: string; description: string; settings?: Record<string, [string, string]> }> = {
  bindings: { name: 'Verknüpfungen', description: 'Vereinsdaten mit externen Schnittstellen abgleichen' },
  codes: { name: 'Codes', description: 'Verschlüsselte Türcodes und Zugangscodes' },
  core: { name: 'Basis', description: 'Anmeldung, Konten, Einstellungen, Dashboard, Protokoll und Mitteilungen' },
  events: { name: 'Anlässe', description: 'Anlässe, Workshops und Treffen mit Anmeldung' },
  finance: { name: 'Finanzen', description: 'Buchungen, Rechnungen mit Schweizer QR-Rechnung und Mahnungen' },
  functions: { name: 'Funktionen', description: 'Vereinsämter und wer sie innehat' },
  groups: { name: 'Gruppen', description: 'Teams, Kommissionen und Interessengruppen' },
  inventory: {
    name: 'Inventar',
    description: 'Werkzeuge, Maschinen und Material, Ausleihen und Einführungen',
    settings: {
      checkout_max_days: ['Längste Ausleihe (Tage)', 'Standard-Rückgabefrist für neue Ausleihen'],
      require_induction: [
        'Nur eingeführte Mitglieder dürfen ausleihen',
        'Gilt für Gegenstände, die eine Einführung brauchen',
      ],
      block_when_overdue: [
        'Ausleihen sperren, solange eine Rechnung überfällig ist',
        'Mehr als 7 Tage überfällig; braucht das Modul Finanzen',
      ],
    },
  },
  mail: { name: 'Mail', description: 'Vereinspostfächer und Aliasse (braucht den eigenen Mailserver)' },
  members: { name: 'Mitglieder', description: 'Mitgliederverzeichnis, Profile, Anträge und Mitgliedschaftsstufen' },
  polls: { name: 'Umfragen', description: 'Umfragen und Abstimmungen unter Mitgliedern' },
  posts: { name: 'Beiträge', description: 'Vereinsmitteilungen und Beiträge aus der Community' },
  roles: { name: 'Rollen und Berechtigungen', description: 'Rollen und die Berechtigungen, die sie vergeben' },
}

export function localizeModule(m: ModuleInfo): ModuleInfo {
  const de = DE[m.code]
  if (!de || m.plugin) return m
  const key = `modules.${m.code}`
  return {
    ...m,
    name: i18n.t(`${key}.name`, de.name),
    description: i18n.t(`${key}.description`, de.description),
    settings: m.settings.map((f) => {
      const s = de.settings?.[f.key]
      if (!s) return f
      return {
        ...f,
        label: i18n.t(`${key}.settings.${f.key}.label`, s[0]),
        description: f.description ? i18n.t(`${key}.settings.${f.key}.description`, s[1]) : f.description,
      }
    }),
  }
}
