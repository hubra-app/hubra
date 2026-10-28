import { useMemo, useState } from 'react'
import { Button, Group, Select, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconCheck } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import type { Poll } from '@/types'
import { castVote, getProxy, grantProxy, revokeProxy } from '@/api/polls'
import { listMembers } from '@/api/members'

/** Proxy voting on one poll: give your vote to someone, take it back, or
 * vote for the members whose proxy you hold. */
export function ProxyPanel({
  poll,
  hasVoted,
  onPollUpdated,
}: {
  poll: Poll
  hasVoted: boolean
  onPollUpdated: (poll: Poll) => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const { currentUser } = useAuth()
  const queryClient = useQueryClient()
  const key = ['poll-proxy', poll.id]
  const { data: state } = useQuery({
    queryKey: key,
    queryFn: () => getProxy(poll.id),
  })
  const [giving, setGiving] = useState(false)
  const [holderId, setHolderId] = useState<string | null>(null)
  const [choice, setChoice] = useState<Record<number, string | null>>({})
  const { data: membersData } = useQuery({
    queryKey: ['members'],
    queryFn: () => listMembers({ pageSize: 500 }),
    enabled: giving,
  })
  const memberOptions = useMemo(
    () =>
      (membersData?.members ?? [])
        .filter((m) => m.id !== currentUser?.id)
        .map((m) => ({ value: m.id, label: m.name })),
    [membersData, currentUser],
  )

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn()
      await queryClient.invalidateQueries({ queryKey: key })
    } catch (err) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError'),
      )
    }
  }

  if (!state) return null
  const optionData = poll.options.map((o, i) => ({
    value: String(i),
    label: o.label,
  }))

  return (
    <div
      style={{
        borderTop: '1px solid var(--mantine-color-gray-2)',
        marginTop: 12,
        paddingTop: 10,
        fontSize: 'var(--mantine-font-size-sm)',
      }}
    >
      {state.given_to ? (
        <Group justify="space-between" gap="xs">
          <Text fz="sm">
            {t('polls.proxy.givenTo', 'Your vote is with {{name}}', {
              name: state.given_to.name,
            })}
          </Text>
          <Button size="xs" variant="subtle" onClick={() => run(() => revokeProxy(poll.id))}>
            {t('polls.proxy.revoke', 'Take back')}
          </Button>
        </Group>
      ) : state.holding.length === 0 && !hasVoted ? (
        giving ? (
          <Group gap="xs" wrap="nowrap">
            <Select
              style={{ flex: 1 }}
              size="xs"
              searchable
              data={memberOptions}
              value={holderId}
              onChange={setHolderId}
              placeholder={t('polls.proxy.pick', 'Who votes for you?')}
            />
            <Button
              size="xs"
              disabled={!holderId}
              onClick={() =>
                run(async () => {
                  await grantProxy(poll.id, Number(holderId))
                  setGiving(false)
                })
              }
            >
              {t('polls.proxy.give', 'Give vote')}
            </Button>
          </Group>
        ) : (
          <Button size="xs" variant="subtle" onClick={() => setGiving(true)}>
            {t('polls.proxy.giveButton', "Can't attend? Give your vote to someone")}
          </Button>
        )
      ) : null}

      {state.holding.map((g) => (
        <Group key={g.id} gap="xs" wrap="nowrap" mt={6}>
          <Text fz="sm" style={{ flex: 1 }}>
            {t('polls.proxy.for', 'For {{name}}', { name: g.name })}
            {g.voted && (
              <IconCheck
                size={14}
                style={{ marginLeft: 6, color: 'var(--mantine-color-green-7)' }}
              />
            )}
          </Text>
          <Select
            size="xs"
            w={140}
            data={optionData}
            value={choice[g.id] ?? null}
            onChange={(v) => setChoice((prev) => ({ ...prev, [g.id]: v }))}
            placeholder={t('polls.proxy.option', 'Option')}
          />
          <Button
            size="xs"
            disabled={choice[g.id] == null}
            onClick={() =>
              run(async () => {
                onPollUpdated(await castVote(poll.id, Number(choice[g.id]), g.id))
              })
            }
          >
            {t('polls.proxy.vote', 'Vote')}
          </Button>
        </Group>
      ))}
    </div>
  )
}
