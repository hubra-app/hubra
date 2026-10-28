import { useState } from 'react'
import { Button, Group, Select, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconCheck } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import type { Poll } from '@/types'
import { castVote, getProxy, grantProxy, revokeProxy } from '@/api/polls'
import { MemberPicker } from '@/components/MemberPicker'

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
            {t('polls.proxy.givenTo', 'Deine Stimme liegt bei {{name}}', {
              name: state.given_to.name,
            })}
          </Text>
          <Button size="xs" variant="subtle" onClick={() => run(() => revokeProxy(poll.id))}>
            {t('polls.proxy.revoke', 'Zurücknehmen')}
          </Button>
        </Group>
      ) : state.holding.length === 0 && !hasVoted ? (
        giving ? (
          <Group gap="xs" wrap="nowrap">
            <MemberPicker
              style={{ flex: 1 }}
              size="xs"
              exclude={currentUser ? [currentUser.id] : undefined}
              value={holderId}
              onChange={(id) => setHolderId(id)}
              placeholder={t('polls.proxy.pick', 'Wer stimmt für dich ab?')}
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
              {t('polls.proxy.give', 'Stimme übertragen')}
            </Button>
          </Group>
        ) : (
          <Button size="xs" variant="subtle" onClick={() => setGiving(true)}>
            {t('polls.proxy.giveButton', 'Du kannst nicht dabei sein? Übertrage deine Stimme')}
          </Button>
        )
      ) : null}

      {state.holding.map((g) => (
        <Group key={g.id} gap="xs" wrap="nowrap" mt={6}>
          <Text fz="sm" style={{ flex: 1 }}>
            {t('polls.proxy.for', 'Für {{name}}', { name: g.name })}
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
            {t('polls.proxy.vote', 'Abstimmen')}
          </Button>
        </Group>
      ))}
    </div>
  )
}
