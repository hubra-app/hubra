import { useState } from 'react'
import { ActionIcon, Anchor, Badge, Group, ScrollArea, Select, Stack, Text } from '@mantine/core'
import { IconX } from '@tabler/icons-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { listMembers, updateMember } from '@/api/members'
import { addRoleScope, listRoleScopes, removeRoleScope, type Role } from '@/api/settings'
import { lookupsQuery } from '@/api/lookups'
import { Modal, LoadingSpinner } from '@/components/ui'
import { useNav, useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useMemberSearch } from '@/data/members'
import { useT } from '@/locales/i18n'
import { roleLabel } from '@/roles'
import type { Member } from '@/types'

/**
 * Who holds a role, and giving it to members or taking it away. Members who
 * hold it through a function are listed too; that role goes with the function.
 * A role can also be given for one group only.
 */
export function RoleMembersModal({
  role,
  roles,
  canAssign,
  onRoleChange,
  onClose,
}: {
  role: Role | null
  /** The roles that can be picked in the dialog. */
  roles: Role[]
  canAssign: boolean
  onRoleChange: (role: Role) => void
  onClose: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const { go } = useNav()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  // '' = the whole club, else a group id: the role then counts in that group only.
  const [forGroup, setForGroup] = useState('')
  const { data: lookups } = useQuery(lookupsQuery)
  const { data: scopes } = useQuery({
    queryKey: qk.settings.roleScopes(role?.id),
    queryFn: () => listRoleScopes(role!.id),
    enabled: !!role,
  })
  const { data: holders } = useQuery({
    queryKey: qk.members.list('role', role?.id),
    queryFn: () => listMembers({ roleId: role!.id, pageSize: 500 }).then((r) => r.members),
    enabled: !!role,
  })
  const { data: found } = useMemberSearch(search, { enabled: !!role && canAssign })

  const change = async (member: Member, add: boolean) => {
    if (!role) return
    const current = member.roles ?? []
    const roleNames = add ? [...current, role.name] : current.filter((r) => r !== role.name)
    try {
      await updateMember(member.id, { roleNames })
      await queryClient.invalidateQueries({ queryKey: qk.members.all })
      // The member counts on the roles page.
      queryClient.invalidateQueries({ queryKey: qk.settings.rolesPermissions })
      setSearch('')
    } catch (err: unknown) {
      notify(
        'error',
        t('roles.assignFailed', 'Rolle konnte nicht zugewiesen werden'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const changeScope = async (run: () => Promise<void>) => {
    try {
      await run()
      await queryClient.invalidateQueries({ queryKey: qk.settings.roleScopes(role?.id) })
      queryClient.invalidateQueries({ queryKey: qk.members.all })
      setSearch('')
    } catch (err: unknown) {
      notify(
        'error',
        t('roles.assignFailed', 'Rolle konnte nicht zugewiesen werden'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const add = (member: Member) =>
    forGroup && role
      ? changeScope(() => addRoleScope(role.id, member.id, Number(forGroup)))
      : change(member, true)

  // Admin roles pass every check, so they are only ever club-wide.
  const groupOptions =
    role && !role.isAdmin && lookups
      ? [...lookups.groups.entries()].map(([id, g]) => ({ value: String(id), label: g.name }))
      : []
  const holderIds = new Set(
    forGroup
      ? (scopes ?? []).filter((sc) => String(sc.groupId) === forGroup).map((sc) => sc.memberId)
      : (holders ?? []).map((m) => m.id),
  )
  const candidates = (found?.members ?? []).filter((m) => !holderIds.has(m.id))

  return (
    <Modal
      open={!!role}
      onClose={onClose}
      title={t('roles.members', 'Rollenmitglieder')}
      subtitle={
        role
          ? t('roles.membersOf', 'Wer die Rolle {{role}} hat', { role: roleLabel(role.name) })
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
        {role && canAssign && groupOptions.length > 0 && (
          <Select
            label={t('roles.forScope', 'Gilt für')}
            data={[{ value: '', label: t('roles.wholeClub', 'Ganzer Verein') }, ...groupOptions]}
            value={forGroup}
            onChange={(v) => setForGroup(v ?? '')}
            allowDeselect={false}
            size="sm"
          />
        )}
        {role && canAssign && (
          <Select
            label={t('roles.addMember', 'Mitglied hinzufügen')}
            placeholder={t('roles.searchMembers', 'Mitglied suchen …')}
            searchable
            searchValue={search}
            onSearchChange={setSearch}
            data={candidates.map((m) => ({ value: m.id, label: m.name }))}
            value={null}
            onChange={(id) => {
              const member = candidates.find((m) => m.id === id)
              if (member) add(member)
            }}
            nothingFoundMessage={t('roles.noMembers', 'Keine Mitglieder gefunden.')}
            filter={({ options }) => options}
            size="sm"
          />
        )}
        {role && (
          <Group justify="space-between">
            <Text size="sm" fw={600}>
              {t('roles.holderCount', '{{count}} Mitglieder', { count: holders?.length ?? 0 })}
            </Text>
            <Anchor
              size="sm"
              onClick={() => {
                onClose()
                go(`/app/members?role=${role.id}`)
              }}
            >
              {t('roles.showInList', 'In der Mitgliederliste zeigen')}
            </Anchor>
          </Group>
        )}
        {role && (
          <ScrollArea.Autosize mah={400} offsetScrollbars>
            <Stack gap={0}>
              {(holders ?? []).map((member) => {
                const direct = member.roles.includes(role.name)
                const viaFunctions = (member.functionRoles ?? [])
                  .filter((fr) => fr.name === role.name)
                  .map((fr) => fr.function)
                return (
                  <Group
                    key={member.id}
                    justify="space-between"
                    py={8}
                    px="xs"
                    wrap="nowrap"
                    style={{ borderBottom: '1px solid var(--hb-border)' }}
                  >
                    <Group gap={10} wrap="nowrap">
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
                        <div style={{ fontWeight: 600 }}>{member.name}</div>
                        {viaFunctions.length > 0 && (
                          <Badge size="xs" variant="light" color="gray">
                            {t('roles.viaFunction', 'über {{fn}}', { fn: viaFunctions.join(', ') })}
                          </Badge>
                        )}
                      </div>
                    </Group>
                    {direct && canAssign && (
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        aria-label={t('roles.removeMember', '{{name}} die Rolle wegnehmen', {
                          name: member.name,
                        })}
                        title={t('roles.removeMember', '{{name}} die Rolle wegnehmen', {
                          name: member.name,
                        })}
                        onClick={() => change(member, false)}
                      >
                        <IconX size={16} />
                      </ActionIcon>
                    )}
                  </Group>
                )
              })}
              {holders && holders.length === 0 && (
                <Text c="dimmed" ta="center" py="lg">
                  {t('roles.noHolders', 'Noch niemand hat diese Rolle.')}
                </Text>
              )}
              {!holders && (
                <LoadingSpinner
                  compact
                  message={t('roles.loadingMembers', 'Mitglieder werden geladen …')}
                />
              )}
            </Stack>
          </ScrollArea.Autosize>
        )}
        {role && (scopes ?? []).length > 0 && (
          <Stack gap={0}>
            <Text size="sm" fw={600} mb={4}>
              {t('roles.groupHolders', 'Nur für eine Gruppe')}
            </Text>
            {(scopes ?? []).map((sc) => (
              <Group
                key={sc.id}
                justify="space-between"
                py={6}
                px="xs"
                wrap="nowrap"
                style={{ borderBottom: '1px solid var(--hb-border)' }}
              >
                <div>
                  <span style={{ fontWeight: 600 }}>{sc.memberName}</span>{' '}
                  <Badge size="xs" variant="light">
                    {t('roles.onlyGroup', 'nur {{group}}', { group: sc.groupName })}
                  </Badge>
                </div>
                {canAssign && (
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    aria-label={t('roles.removeMember', '{{name}} die Rolle wegnehmen', {
                      name: sc.memberName,
                    })}
                    title={t('roles.removeMember', '{{name}} die Rolle wegnehmen', {
                      name: sc.memberName,
                    })}
                    onClick={() => changeScope(() => removeRoleScope(role.id, sc.id))}
                  >
                    <IconX size={16} />
                  </ActionIcon>
                )}
              </Group>
            ))}
          </Stack>
        )}
      </Stack>
    </Modal>
  )
}
