import { tr } from '@/lang'

/** German names of common audit actions (platform and clubs); others
 * show as they are. */
export function actionLabel(action: string): string {
  const de: Record<string, string> = {
    'tenant.provision': 'Verein eingerichtet',
    'tenant.update': 'Verein geändert',
    'tenant.soft_delete': 'Verein archiviert',
    'tenant.delete': 'Verein gelöscht',
    'tenant.add_member': 'Mitglied hinzugefügt',
    'club_settings.update': 'Vereinseinstellungen geändert',
    'platform.settings.update': 'Plattform-Einstellungen geändert',
    'impersonation.start': 'Als Admin geöffnet',
    'impersonation.end': 'Admin-Ansicht beendet',
    'global_role.create': 'Plattform-Rolle erstellt',
    'global_role.update': 'Plattform-Rolle geändert',
    'global_role.assign': 'Plattform-Rolle vergeben',
    'global_role.remove': 'Plattform-Rolle entzogen',
    'tenant.limits': 'Limits geändert',
    'audit.export': 'Audit-Log exportiert',
    'impersonation.revoked': 'Support-Zugriff beendet',
    login: 'Anmeldung',
    change_password: 'Passwort geändert',
    create_invoice: 'Rechnung erstellt',
    update_invoice: 'Rechnung geändert',
    update_member: 'Mitglied geändert',
    soft_delete_member: 'Mitglied entfernt',
    update_role: 'Rolle geändert',
    set_role_permissions: 'Rechte einer Rolle gesetzt',
    update_transaction: 'Buchung geändert',
    update_post: 'Beitrag geändert',
    update_poll: 'Umfrage geändert',
  }
  return de[action] ? tr(de[action], action) : action
}

export function actionColor(action: string): string {
  if (action.includes('delete')) return 'red'
  if (action.includes('revoked')) return 'orange'
  if (action.includes('suspend') || action.includes('disable')) return 'orange'
  if (action.includes('provision')) return 'green'
  if (action.includes('impersonation')) return 'grape'
  return 'gray'
}
