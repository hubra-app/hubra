import { useState } from 'react'
import { ActionIcon, Badge, Group, Paper, Stack, Tabs, Text, UnstyledButton } from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import { IconArrowLeft, IconPencil, IconShield, IconTrash, IconUsers } from '@tabler/icons-react'
import type { Role } from '@/api/settings'
import type { PermissionEntry } from '@/api/system'
import { useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { roleDescription, roleLabel } from '@/roles'
import { RoleAccess } from './RoleAccess'
import { RoleMembersPanel } from './RoleMembersModal'

/**
 * The roles as a list; picking one shows what it may do and who has it.
 * On a phone the list and the role take turns.
 */
export function RolesOverview({
  roles: unordered,
  allPerms,
  rolePerms,
  canUpdate,
  canDelete,
  canSetPermissions,
  canAssign,
  onEdit,
  onDelete,
  onToggle,
  onSetKeys,
}: {
  roles: Role[]
  allPerms: PermissionEntry[]
  rolePerms: Record<string, Set<string>>
  canUpdate: boolean
  canDelete: boolean
  canSetPermissions: boolean
  canAssign: boolean
  onEdit: (role: Role) => void
  onDelete: (role: Role) => void
  onToggle: (role: Role, key: string) => void
  onSetKeys: (role: Role, area: PermissionEntry[], keys: string[]) => void
}) {
  const { t } = useT()
  const { isAdmin } = useAuth()
  const isMobile = useMediaQuery('(max-width: 48em)')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  // Owner and Admin first, then the other system roles, then the club's own.
  const rank = (r: Role) => (r.isOwner ? 0 : r.isAdmin && r.isSystem ? 1 : r.isSystem ? 2 : 3)
  const roles = [...unordered].sort(
    (a, b) => rank(a) - rank(b) || roleLabel(a.name).localeCompare(roleLabel(b.name)),
  )
  const [tab, setTab] = useState<string | null>('access')
  // Phones start on the list; wider screens show the first role straight away.
  const selected =
    roles.find((r) => r.id === selectedId) ??
    (isMobile ? null : (roles.find((r) => !r.isAdmin) ?? roles[0]))
  // Only an admin changes an admin role; system roles keep their name.
  const mayEdit = (role: Role) => canUpdate && !role.isOwner && (!role.isAdmin || isAdmin)
  const mayDelete = (role: Role) =>
    canDelete && !role.isSystem && !role.isDefault && (!role.isAdmin || isAdmin)

  const list = (
    // Stays in view while a long role is scrolled.
    <Stack gap={8} style={isMobile ? undefined : { position: 'sticky', top: 80 }}>
      {roles.map((role) => {
        const active = selected?.id === role.id
        return (
          <UnstyledButton
            key={role.id}
            onClick={() => setSelectedId(role.id)}
            aria-current={active || undefined}
            style={{
              display: 'block',
              padding: '10px 12px',
              borderRadius: 12,
              border: `1px solid ${active ? 'var(--mantine-color-acc-6)' : 'var(--hb-border)'}`,
              background: active ? 'var(--mantine-color-acc-light)' : 'var(--hb-surface)',
            }}
          >
            <Group gap={8} wrap="nowrap" justify="space-between">
              <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
                <IconShield
                  size={16}
                  style={{
                    flexShrink: 0,
                    color: role.isAdmin ? 'var(--mantine-color-acc-9)' : 'var(--hb-text-2)',
                  }}
                />
                <Text fw={600} size="sm" truncate>
                  {roleLabel(role.name)}
                </Text>
                {role.isAdmin && (
                  <Badge size="xs" variant="light">
                    Admin
                  </Badge>
                )}
              </Group>
              <Group gap={4} wrap="nowrap" c="dimmed">
                <IconUsers size={14} />
                <Text size="xs">{role.memberCount}</Text>
              </Group>
            </Group>
            {roleDescription(role) && (
              <Text size="xs" c="dimmed" mt={4} lineClamp={2}>
                {roleDescription(role)}
              </Text>
            )}
          </UnstyledButton>
        )
      })}
    </Stack>
  )

  const detail = selected && (
    <Paper withBorder radius="lg" p="md">
      <Group justify="space-between" align="flex-start" wrap="nowrap" mb={8}>
        <Group gap={8} wrap="nowrap" align="flex-start" style={{ minWidth: 0 }}>
          {isMobile && (
            <ActionIcon
              variant="subtle"
              onClick={() => setSelectedId(null)}
              aria-label={t('roles.backToList', 'Zurück zu den Rollen')}
            >
              <IconArrowLeft size={18} />
            </ActionIcon>
          )}
          <div style={{ minWidth: 0 }}>
            <Group gap={8}>
              <Text fw={700} size="lg">
                {roleLabel(selected.name)}
              </Text>
              {selected.isAdmin && <Badge variant="light">Admin</Badge>}
              {selected.isSystem && (
                <Badge variant="outline" color="gray">
                  {t('roles.systemRole', 'Systemrolle')}
                </Badge>
              )}
            </Group>
            {roleDescription(selected) && (
              <Text size="sm" c="dimmed">
                {roleDescription(selected)}
              </Text>
            )}
          </div>
        </Group>
        <Group gap={4} wrap="nowrap">
          {mayEdit(selected) && (
            <ActionIcon
              variant="subtle"
              onClick={() => onEdit(selected)}
              aria-label={t('roles.edit', 'Rolle bearbeiten')}
              title={t('roles.edit', 'Rolle bearbeiten')}
            >
              <IconPencil size={16} />
            </ActionIcon>
          )}
          {mayDelete(selected) && (
            <ActionIcon
              variant="subtle"
              color="red"
              onClick={() => onDelete(selected)}
              aria-label={t('roles.delete', 'Rolle löschen')}
              title={t('roles.delete', 'Rolle löschen')}
            >
              <IconTrash size={16} />
            </ActionIcon>
          )}
        </Group>
      </Group>
      <Tabs value={tab} onChange={setTab} keepMounted={false}>
        <Tabs.List mb={12}>
          <Tabs.Tab value="access">{t('roles.mayDo', 'Darf')}</Tabs.Tab>
          <Tabs.Tab value="members">
            {t('roles.holderCount', '{{count}} Mitglieder', { count: selected.memberCount })}
          </Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="access">
          <RoleAccess
            role={selected}
            allPerms={allPerms}
            roleSet={rolePerms[selected.id]}
            canSetPermissions={canSetPermissions}
            onToggle={onToggle}
            onSetKeys={onSetKeys}
          />
        </Tabs.Panel>
        <Tabs.Panel value="members">
          <RoleMembersPanel key={selected.id} role={selected} canAssign={canAssign} />
        </Tabs.Panel>
      </Tabs>
    </Paper>
  )

  if (isMobile) return selected ? detail : list
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(220px, 300px) 1fr',
        gap: 16,
        alignItems: 'start',
      }}
    >
      {list}
      {detail}
    </div>
  )
}
