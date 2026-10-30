import i18n from 'i18next'

// Every club starts with these system roles. Their names stay English in the
// database because the backend looks them up by name; show them translated.
export const SYSTEM_ROLES = ['Owner', 'Admin', 'Treasurer', 'Member']

export function roleLabel(name: string): string {
  return SYSTEM_ROLES.includes(name) ? i18n.t(`roles.system.${name}`, name) : name
}

export function roleLabels(names: string[] | undefined): string {
  return (names ?? []).map(roleLabel).join(', ')
}
