import i18n from 'i18next'
import type { PermissionEntry } from '@/api/system'

/** `members_bp` → `Mitglieder` (`Members` for an area without a translation). */
export function blueprintLabel(bp: string): string {
  const stripped = bp.replace(/_bp$/, '')
  return i18n.t(`roles.areas.${stripped}`, stripped.charAt(0).toUpperCase() + stripped.slice(1))
}

/** `transaction_categories` → `Kategorien`. */
export function resourceLabel(resource: string): string {
  return i18n.t(`roles.resources.${resource}`, resource)
}

/** A permission's name in the page language; the catalog's English name
 * (plugins bring their own) when there is no translation. */
export function permLabel(perm: Pick<PermissionEntry, 'key' | 'display_name'>): string {
  return i18n.t(`roles.perms.${perm.key.replace(/\./g, '_')}`, perm.display_name)
}
