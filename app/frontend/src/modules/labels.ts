import i18n from 'i18next'
import type { ModuleInfo } from '@/api/modules'

// The backend describes modules in English. Shipped modules and the plugins
// shipped with Hubra get German defaults here and can be overridden per
// language under modules.<code>.*; other plugins keep their manifest's texts.
const DE: Record<string, { name: string; description: string; settings?: Record<string, [string, string]> }> = {
  bindings: { name: 'Verknüpfungen', description: 'Vereinsdaten mit externen Schnittstellen abgleichen' },
  codes: { name: 'Codes', description: 'Verschlüsselte Türcodes und Zugangscodes' },
  core: { name: 'Basis', description: 'Anmeldung, Konten, Einstellungen, Dashboard, Protokoll und Mitteilungen' },
  events: {
    name: 'Anlässe',
    description: 'Anlässe, Workshops und Treffen mit Anmeldung',
    settings: {
      notify_members: [
        'Mitglieder über neue Anlässe informieren',
        'Eine Mitteilung in der App an alle Mitglieder, sobald ein Anlass veröffentlicht ist',
      ],
      event_types: [
        'Anlass-Typen',
        'Die Typen zur Auswahl, mit Komma getrennt (zum Beispiel Training, Match, Versammlung). Leer: Workshop, Geselliges, Einführung und Sitzung.',
      ],
    },
  },
  finance: {
    name: 'Finanzen',
    description: 'Buchungen, Rechnungen mit Schweizer QR-Rechnung und Mahnungen',
    settings: {
      payment_term_days: [
        'Zahlungsfrist (Tage)',
        'Fälligkeit neuer Rechnungen und von Sammelrechnungen ohne Datum',
      ],
      email_new_invoices: ['Neue Rechnungen per E-Mail senden', 'Mit dem QR-Einzahlungsschein im Anhang'],
      reminders_enabled: ['Zahlungserinnerungen senden', ''],
      first_reminder_days: ['Erste Erinnerung (Tage nach Fälligkeit)', ''],
      second_reminder_days: ['Zweite Erinnerung (Tage nach Fälligkeit)', ''],
      bill_on_join_date: [
        'Jedes Mitglied an seinem Eintrittsdatum verrechnen',
        'Sonst werden alle am Stichtag unten verrechnet',
      ],
      fee_anchor_month: ['Stichtag: Monat', ''],
      fee_anchor_day: ['Stichtag: Tag', ''],
      prorate_first_fee: [
        'Ersten Beitrag bei Eintritt während des Jahres kürzen',
        'Nach verbleibenden Monaten, der Eintrittsmonat zählt ganz',
      ],
    },
  },
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
  // Plugins shipped with Hubra
  'finance.bank': {
    name: 'Bankimport',
    description:
      'Kontoauszüge importieren (camt.053/054, MT940, CSV); Zahlungen werden Rechnungen zugeordnet, andere Buchungen kommen in die Buchhaltung',
  },
  'finance.budgets': { name: 'Budgets', description: 'Jahresbudgets pro Kategorie, verglichen mit den Buchungen' },
  discord: {
    name: 'Discord',
    description: 'Neue Anlässe, Beiträge und Umfragen in einem Discord-Kanal ankündigen',
    settings: {
      webhook_url: ['Webhook-URL', 'Discord: Kanaleinstellungen › Integrationen › Webhooks › URL kopieren'],
      announce_events: ['Neue Anlässe', ''],
      announce_posts: ['Neue Beiträge', ''],
      announce_polls: ['Neue Umfragen', ''],
      mention: ['Erwähnung', 'Optional, z. B. @everyone oder <@&Rollen-ID>'],
    },
  },
  'inventory.guides': { name: 'Anleitungen', description: 'Anleitungen für Maschinen und Werkzeuge (Markdown oder ein Link)' },
  inbox: {
    name: 'Gemeinsamer Posteingang',
    description: 'Die Postfächer des Vereins (IMAP) in Hubra lesen, jedes für eine Gruppe sichtbar',
  },
  'inventory.keys': {
    name: 'Schlüssel',
    description: 'Schlüssel, Karten und Badges: wer welchen hat, mit Übergabeprotokoll',
  },
}

export function localizeModule(m: ModuleInfo): ModuleInfo {
  const de = DE[m.code]
  if (!de) return m
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
