/** German names of the shipped modules (the API describes them in English),
 *  as the club app shows them (app/frontend/src/modules/labels.ts). */
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
}
