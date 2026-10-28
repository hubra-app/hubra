/** German names of the shipped modules and plugins (the API describes them
 *  in English), as the club app shows them (app/frontend/src/modules/labels.ts). */
export const MODULE_DE: Record<string, [name: string, description: string]> = {
  bindings: ['Verknüpfungen', 'Vereinsdaten mit externen Schnittstellen abgleichen'],
  codes: ['Codes', 'Verschlüsselte Türcodes und Zugangscodes'],
  core: ['Basis', 'Anmeldung, Konten, Einstellungen, Dashboard, Protokoll und Mitteilungen'],
  events: ['Anlässe', 'Anlässe, Workshops und Treffen mit Anmeldung'],
  finance: ['Finanzen', 'Buchungen, Rechnungen mit Schweizer QR-Rechnung und Mahnungen'],
  functions: ['Funktionen', 'Vereinsämter und wer sie innehat'],
  groups: ['Gruppen', 'Teams, Kommissionen und Interessengruppen'],
  inventory: ['Inventar', 'Werkzeuge, Maschinen und Material, Ausleihen und Einführungen'],
  mail: ['Mail', 'Vereinspostfächer und Aliasse (braucht den eigenen Mailserver)'],
  members: ['Mitglieder', 'Mitgliederverzeichnis, Profile, Anträge und Mitgliedschaftsstufen'],
  polls: ['Umfragen', 'Umfragen und Abstimmungen unter Mitgliedern'],
  posts: ['Beiträge', 'Vereinsmitteilungen und Beiträge aus der Community'],
  roles: ['Rollen und Berechtigungen', 'Rollen und die Berechtigungen, die sie vergeben'],
  // Modules of the plugins shipped with Hubra
  'finance.bank': ['Bankimport', 'Kontoauszüge importieren (camt.053/054, MT940, CSV); Zahlungen werden Rechnungen zugeordnet, andere Buchungen kommen in die Buchhaltung'],
  'finance.budgets': ['Budgets', 'Jahresbudgets pro Kategorie, verglichen mit den Buchungen'],
  discord: ['Discord', 'Neue Anlässe, Beiträge und Umfragen in einem Discord-Kanal ankündigen'],
  'inventory.guides': ['Anleitungen', 'Anleitungen für Maschinen und Werkzeuge (Markdown oder ein Link)'],
  inbox: ['Gemeinsamer Posteingang', 'Die Postfächer des Vereins (IMAP) in Hubra lesen, jedes für eine Gruppe sichtbar'],
  'inventory.keys': ['Schlüssel', 'Schlüssel, Karten und Badges: wer welchen hat, mit Übergabeprotokoll'],
}

/** German name and description of the plugins shipped with Hubra, by plugin id. */
export const PLUGIN_DE: Record<string, [name: string, description: string]> = {
  'bank-import': [
    'Bankimport',
    'Kontoauszüge importieren (camt.053, camt.054, MT940 oder CSV). Zahlungen werden Rechnungen zugeordnet und als bezahlt markiert, andere Buchungen kommen nach deinen Regeln in die Buchhaltung, zuerst als Probelauf.',
  ],
  budgets: [
    'Budgets',
    'Ein Jahresbudget pro Buchungskategorie, verglichen mit dem Gebuchten. Genehmigen und sperren, und ins nächste Jahr übernehmen.',
  ],
  discord: [
    'Discord',
    'Neue Anlässe, Beiträge und Umfragen über einen Webhook in einem Discord-Kanal ankündigen, wahlweise mit Erwähnung.',
  ],
  guides: [
    'Anleitungen',
    'Eine Anleitung pro Maschine oder Werkzeug, in Markdown oder als Link zu Handbuch oder Video, beim Inventarobjekt angezeigt.',
  ],
  'imap-inbox': [
    'Gemeinsamer Posteingang (IMAP)',
    'Vereinspostfächer bei einem beliebigen Anbieter (Infomaniak, Hostpoint, Gmail mit App-Passwort …) in Hubra lesen. Standardmässig nur lesen, jedes Postfach für eine Gruppe sichtbar, Passwörter verschlüsselt gespeichert.',
  ],
  keys: [
    'Schlüssel',
    'Schlüssel, Karten und Badges: wer welchen hat, mit Übergabeprotokoll. Mitglieder sehen ihre Schlüssel auf ihrer Kontoseite.',
  ],
}
