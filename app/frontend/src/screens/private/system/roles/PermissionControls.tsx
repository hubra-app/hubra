import type { Role } from '@/api/settings'

export function SectionToggle({
  role,
  keys,
  roleSet,
  onToggle,
  canSetPermissions,
}: {
  role: Role
  keys: string[]
  roleSet: Set<string> | undefined
  onToggle: (role: Role, keys: string[], on: boolean) => void
  canSetPermissions: boolean
}) {
  const allSelected = keys.length > 0 && keys.every((k) => roleSet?.has(k))
  const someSelected = !allSelected && keys.some((k) => roleSet?.has(k))
  const disabled = role.isAdmin || !canSetPermissions
  return (
    <input
      type="checkbox"
      checked={role.isAdmin || allSelected}
      ref={(el) => {
        if (el) el.indeterminate = role.isAdmin ? false : someSelected
      }}
      onChange={() => onToggle(role, keys, !allSelected)}
      disabled={disabled}
      style={{
        width: 14,
        height: 14,
        accentColor: role.isAdmin ? 'var(--mantine-color-acc-9)' : 'var(--mantine-color-acc-6)',
        cursor: disabled ? 'default' : 'pointer',
      }}
    />
  )
}

export function PermCheckbox({
  role,
  permKey,
  roleSet,
  onToggle,
  canSetPermissions,
  size = 18,
}: {
  role: Role
  permKey: string
  roleSet: Set<string> | undefined
  onToggle: (role: Role, key: string) => void
  canSetPermissions: boolean
  size?: number
}) {
  const disabled = role.isAdmin || !canSetPermissions
  return (
    <input
      type="checkbox"
      checked={role.isAdmin || (roleSet?.has(permKey) ?? false)}
      onChange={() => onToggle(role, permKey)}
      disabled={disabled}
      style={{
        width: size,
        height: size,
        flexShrink: 0,
        marginTop: 2,
        accentColor: role.isAdmin ? 'var(--mantine-color-acc-9)' : 'var(--mantine-color-acc-6)',
        cursor: disabled ? 'default' : 'pointer',
      }}
    />
  )
}
