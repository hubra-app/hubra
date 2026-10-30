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

// The descriptions new clubs got for their system roles (older and current
// wording); while a club hasn't changed one, show it in the page language.
const SHIPPED_DESCRIPTIONS: Record<string, string[]> = {
  Owner: [
    'Full access — system role, un-lockoutable, always >=1 per tenant',
    'Full access. Only owners give or take this role; a club always has at least one.',
  ],
  Admin: [
    'Manage all features except roles deletion and global settings',
    'Full access to the club, except giving or taking the Owner role.',
  ],
  Treasurer: [
    'Manage finances, view members and audit logs',
    'Manages the finances, sees members and the audit log.',
  ],
  Member: [
    'Basic member access — read-only on public resources',
    'What every member may do: events, polls, posts. The permissions can be changed.',
  ],
}

export function roleDescription(role: { name: string; description: string | null }): string {
  const shipped = SHIPPED_DESCRIPTIONS[role.name]
  if (shipped && (!role.description || shipped.includes(role.description))) {
    return i18n.t(`roles.systemDesc.${role.name}`, role.description ?? '')
  }
  return role.description ?? ''
}
