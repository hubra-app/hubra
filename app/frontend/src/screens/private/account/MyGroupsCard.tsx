import { useState } from 'react'
import { Button, Group, Paper, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconUsersGroup } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { joinGroup, leaveGroup, listJoinableGroups } from '@/api/groups'

/** Interest groups the member can join or leave without asking anyone. */
export function MyGroupsCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState<number | null>(null)
  const { data: groups = [] } = useQuery({
    queryKey: ['groups', 'joinable'],
    queryFn: listJoinableGroups,
  })
  if (groups.length === 0) return null

  const toggle = async (id: number, joined: boolean) => {
    setBusy(id)
    try {
      await (joined ? leaveGroup(id) : joinGroup(id))
      await queryClient.invalidateQueries({ queryKey: ['groups'] })
    } catch (err) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError'),
      )
    } finally {
      setBusy(null)
    }
  }

  return (
    <Paper withBorder shadow="sm" radius="lg">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
        <IconUsersGroup size={16} style={{ color: '#6b7480' }} />
        <Text fw={700} fz="md">
          {t('account.interestGroups', 'Interest groups')}
        </Text>
      </Group>
      {groups.map((g) => (
        <Group
          key={g.id}
          justify="space-between"
          wrap="nowrap"
          px="md"
          py="sm"
          style={{ borderBottom: '1px solid var(--mantine-color-gray-2)' }}
        >
          <div style={{ minWidth: 0 }}>
            <Text fw={600} fz="sm">
              <span
                style={{
                  display: 'inline-block',
                  width: 8,
                  height: 8,
                  borderRadius: 4,
                  marginRight: 8,
                  background: g.color ?? '#99a2ac',
                }}
              />
              {g.name}
            </Text>
            <Text fz="xs" c="dimmed" lineClamp={2}>
              {g.description ||
                t('account.groupMembers', '{{count}} members', {
                  count: g.memberCount,
                })}
            </Text>
          </div>
          <Button
            size="xs"
            variant={g.joined ? 'default' : 'filled'}
            loading={busy === g.id}
            onClick={() => toggle(g.id, g.joined)}
          >
            {g.joined ? t('account.leaveGroup', 'Leave') : t('account.joinGroup', 'Join')}
          </Button>
        </Group>
      ))}
    </Paper>
  )
}
