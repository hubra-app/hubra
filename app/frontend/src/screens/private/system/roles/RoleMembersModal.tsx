import { useState } from 'react'
import { Checkbox, Group, ScrollArea, Select, Stack, Text, TextInput } from '@mantine/core'
import { IconSearch } from '@tabler/icons-react'
import { useQueryClient } from '@tanstack/react-query'
import { updateMember } from '@/api/members'
import type { Role } from '@/api/settings'
import { Modal, LoadingSpinner } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useMemberSearch } from '@/data/members'
import { useT } from '@/locales/i18n'
import { roleLabel } from '@/roles'
import type { Member } from '@/types'

/** Gives members a role or takes it away, one checkbox per member. */
export function RoleMembersModal({
  role,
  roles,
  onRoleChange,
  onClose,
}: {
  role: Role | null
  /** The roles that can be picked in the dialog. */
  roles: Role[]
  onRoleChange: (role: Role) => void
  onClose: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const { data: page } = useMemberSearch(search, { enabled: !!role })
  const members = page?.members

  const toggle = async (member: Member, role: Role, add: boolean) => {
    const current = member.roles ?? []
    const roleNames = add ? [...current, role.name] : current.filter((r) => r !== role.name)
    try {
      await updateMember(member.id, { roleNames })
      queryClient.invalidateQueries({ queryKey: qk.members.all })
    } catch (err: unknown) {
      notify(
        'error',
        t('roles.assignFailed', 'Rolle konnte nicht zugewiesen werden'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  return (
    <Modal
      open={!!role}
      onClose={onClose}
      title={t('roles.members', 'Rollenmitglieder')}
      subtitle={
        role
          ? t('roles.assignTo', 'Mitgliedern die Rolle {{role}} geben', {
              role: roleLabel(role.name),
            })
          : ''
      }
      wide
    >
      <Stack gap={12}>
        {roles.length > 0 && (
          <Select
            label={t('roles.role', 'Rolle')}
            data={roles.map((r) => ({
              value: r.id,
              label: roleLabel(r.name) + (r.isAdmin ? ' (Admin)' : ''),
            }))}
            value={role?.id ?? ''}
            onChange={(v) => {
              const next = roles.find((r) => r.id === v)
              if (next) onRoleChange(next)
            }}
            size="sm"
          />
        )}
        {role && (
          <TextInput
            size="sm"
            leftSection={<IconSearch size={14} />}
            placeholder={t('roles.searchMembers', 'Mitglied suchen …')}
            aria-label={t('roles.searchMembers', 'Mitglied suchen …')}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
          />
        )}
        {role && (
          <ScrollArea.Autosize mah={400} offsetScrollbars>
            <Stack gap={6}>
              {(members ?? []).map((member) => (
                <Group
                  key={member.id}
                  justify="space-between"
                  p="xs"
                  style={{ borderBottom: '1px solid #f1eff7' }}
                >
                  <Group gap={10}>
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: '50%',
                        background: member.avatarColor || '#3a1e78',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                        fontWeight: 700,
                        fontSize: 13,
                        flexShrink: 0,
                      }}
                    >
                      {member.firstName[0]}
                      {member.lastName[0]}
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 'sm' }}>{member.name}</div>
                      <div style={{ fontSize: 'var(--mantine-font-size-xs)', color: 'var(--hb-text-3)' }}>
                        {member.email}
                      </div>
                    </div>
                  </Group>
                  <Checkbox
                    checked={member.roles?.includes(role.name) ?? false}
                    disabled={role.isAdmin}
                    aria-label={member.name}
                    onChange={(e) => toggle(member, role, e.currentTarget.checked)}
                    size="sm"
                  />
                </Group>
              ))}
              {members && members.length === 0 && (
                <Text c="dimmed" ta="center" py="lg">
                  {t('roles.noMembers', 'Keine Mitglieder gefunden.')}
                </Text>
              )}
              {!members && (
                <LoadingSpinner
                  compact
                  message={t('roles.loadingMembers', 'Mitglieder werden geladen …')}
                />
              )}
            </Stack>
          </ScrollArea.Autosize>
        )}
      </Stack>
    </Modal>
  )
}
