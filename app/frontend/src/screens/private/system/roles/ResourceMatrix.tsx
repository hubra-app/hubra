import { useMemo, Fragment } from 'react'
import { IconShield } from '@tabler/icons-react'
import { Table, Paper, Group, Text, Badge } from '@mantine/core'
import { useT } from '@/locales/i18n'
import type { Role } from '@/api/settings'
import { type PermissionEntry } from '@/api/system'
import { roleLabel } from '@/roles'

import { SectionToggle } from './PermissionControls'
import { blueprintLabel, permLabel, resourceLabel } from './labels'

interface ResourceMatrixProps {
  visibleRoles: Role[]
  allPerms: PermissionEntry[]
  rolePerms: Record<string, Set<string>>
  canSetPermissions: boolean
  toggle: (role: Role, key: string) => void
  toggleAllInScope: (role: Role, keys: string[], on: boolean) => void
}

/** Roles across the top, one row per area with its actions as columns. */
export function ResourceMatrix(props: ResourceMatrixProps) {
  const { visibleRoles, allPerms, rolePerms, canSetPermissions, toggle, toggleAllInScope } = props
  const { t } = useT()
  const resourceActionMatrix = useMemo(() => {
    const resources: Record<
      string,
      {
        blueprint: string
        resource: string
        actions: Map<string, PermissionEntry>
      }
    > = {}
    for (const p of allPerms) {
      if (p.action.startsWith('update.')) continue
      const key = `${p.blueprint}:${p.resource}`
      if (!resources[key]) {
        resources[key] = {
          blueprint: p.blueprint,
          resource: p.resource,
          actions: new Map(),
        }
      }
      resources[key].actions.set(p.action, p)
    }
    return Object.entries(resources)
      .map(([key, val]) => ({ key, ...val }))
      .sort((a, b) => `${a.blueprint}.${a.resource}`.localeCompare(`${b.blueprint}.${b.resource}`))
  }, [allPerms])
  return (
    <Paper withBorder shadow="sm" radius="lg" style={{ overflowX: 'auto' }}>
      <Table highlightOnHover style={{ minWidth: 520 }}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th style={{ minWidth: 180 }}>{t('roles.resource', 'Bereich')}</Table.Th>
            {visibleRoles.map((role) => (
              <Table.Th key={role.id} style={{ textAlign: 'center', minWidth: 100 }}>
                <Group gap={6} justify="center" wrap="nowrap">
                  <IconShield
                    size={14}
                    style={{
                      color: role.isAdmin ? 'var(--mantine-color-acc-9)' : role.isDefault ? 'var(--mantine-color-acc-text)' : 'var(--hb-text-2)',
                    }}
                  />
                  <Text size="sm" fw={600}>
                    {roleLabel(role.name)}
                  </Text>
                  {role.isAdmin && (
                    <Badge size="xs" color="indigo" variant="light">
                      ADMIN
                    </Badge>
                  )}
                </Group>
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {resourceActionMatrix.map((entry) => {
            const actions = Array.from(entry.actions.entries()).sort(([a], [b]) =>
              a.localeCompare(b),
            )
            return (
              <Fragment key={entry.key}>
                <Table.Tr style={{ background: '#f9f8fc' }}>
                  <Table.Td
                    style={{
                      fontWeight: 700,
                      fontSize: 'var(--mantine-font-size-xs)',
                      color: 'var(--hb-text-3)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      padding: '10px 16px',
                    }}
                  >
                    {blueprintLabel(entry.blueprint)} / {resourceLabel(entry.resource)}
                  </Table.Td>
                  {visibleRoles.map((role) => (
                    <Table.Td key={role.id} style={{ textAlign: 'center' }}>
                      <SectionToggle
                        role={role}
                        keys={actions.map(([, p]) => p.key)}
                        roleSet={rolePerms[role.id]}
                        onToggle={toggleAllInScope}
                        canSetPermissions={canSetPermissions}
                      />
                    </Table.Td>
                  ))}
                </Table.Tr>
                {actions.map(([, perm]) => (
                  <Table.Tr key={perm.key}>
                    <Table.Td
                      style={{
                        paddingLeft: 28,
                        color: 'var(--hb-text)',
                      }}
                    >
                      <div
                        style={{
                          fontWeight: 600,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                        }}
                      >
                        {permLabel(perm)}
                      </div>
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-xs)',
                          color: 'var(--hb-text-3)',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        {perm.key}
                      </div>
                    </Table.Td>
                    {visibleRoles.map((role) => (
                      <Table.Td key={role.id} style={{ textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={role.isAdmin || (rolePerms[role.id]?.has(perm.key) ?? false)}
                          onChange={() => toggle(role, perm.key)}
                          disabled={role.isAdmin || !canSetPermissions}
                          title={role.isAdmin ? t('roles.adminLocked', 'Admin-Rollen haben alle Rechte; die einzelnen Berechtigungen gelten für sie nicht.') : undefined}
                          style={{
                            width: 16,
                            height: 16,
                            accentColor: role.isAdmin ? 'var(--mantine-color-acc-9)' : 'var(--mantine-color-acc-6)',
                            cursor: role.isAdmin ? 'default' : 'pointer',
                          }}
                        />
                      </Table.Td>
                    ))}
                  </Table.Tr>
                ))}
              </Fragment>
            )
          })}
        </Table.Tbody>
      </Table>
    </Paper>
  )
}
