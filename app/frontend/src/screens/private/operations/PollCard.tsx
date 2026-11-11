import { useState, type ReactNode } from 'react'
import { ActionIcon, Badge, Button, Group, Menu, Paper, Progress, Text, UnstyledButton } from '@mantine/core'
import { IconBell, IconCheck, IconDotsVertical, IconPencil, IconTrash } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import type { Poll } from '@/types'
import { GroupBadge } from './ContentGroupFields'

/** "endet in 3 Tagen", "endet morgen", "endet am 23. Nov." or "beendet". */
function closingText(poll: Poll, t: ReturnType<typeof useT>['t'], locale: string) {
  if (poll.status === 'closed') {
    return poll.closesAt
      ? t('polls.closedOn', 'beendet am {{date}}', {
          date: new Date(poll.closesAt).toLocaleDateString(locale, { day: 'numeric', month: 'short' }),
        })
      : t('polls.statusClosed', 'Beendet')
  }
  if (!poll.closesAt) return t('polls.noEnd', 'ohne Enddatum')
  const days = Math.ceil((new Date(poll.closesAt).getTime() - Date.now()) / 86_400_000)
  if (days <= 0) return t('polls.closesToday', 'endet heute')
  if (days === 1) return t('polls.closesTomorrow', 'endet morgen')
  if (days <= 7) return t('polls.closesInDays', 'endet in {{count}} Tagen', { count: days })
  return t('polls.closesOn', 'endet am {{date}}', {
    date: new Date(poll.closesAt).toLocaleDateString(locale, { day: 'numeric', month: 'short' }),
  })
}

/**
 * One poll. Before voting the options are plain choices, so nobody votes
 * along with the crowd; after voting (or once the poll ends) the results
 * show as bars, and "Stimme ändern" brings the choices back while it is open.
 * Whoever runs the poll sees the results all along.
 */
export function PollCard({
  poll,
  voted,
  groupName,
  runs,
  voting,
  onVote,
  onRemind,
  reminding,
  onEdit,
  onDelete,
  children,
}: {
  poll: Poll
  voted: number | undefined
  groupName: string | null
  /** Asked the question or manages its group: sees results, edits it. */
  runs: boolean
  voting: boolean
  onVote: (optIdx: number) => void
  onRemind?: () => void
  reminding?: boolean
  onEdit?: () => void
  onDelete?: () => void
  /** Below the card, such as the proxy panel. */
  children?: ReactNode
}) {
  const { t, i18n } = useT()
  const [changing, setChanging] = useState(false)
  const open = poll.status === 'open'
  const hasVoted = voted !== undefined
  const mayVote = open && poll.mayVote !== false
  const choosing = mayVote && (!hasVoted || changing)
  const showResults = !choosing || runs || !open
  const max = Math.max(...poll.options.map((o) => o.votes))
  const pending = mayVote && !hasVoted

  return (
    <Paper withBorder p="lg" className="hb-poll-card" data-testid="poll-card" data-pending={pending || undefined}>
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="sm" mb="xs">
        <Text fw={650} fz="md" style={{ overflowWrap: 'anywhere' }}>
          {poll.question}
        </Text>
        {(onRemind || onEdit || onDelete) && (
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <ActionIcon
                variant="subtle"
                color="gray"
                aria-label={t('common.moreActions', 'Weitere Aktionen')}
                data-testid="poll-menu"
                style={{ flexShrink: 0 }}
              >
                <IconDotsVertical size={18} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              {onRemind && (
                <Menu.Item leftSection={<IconBell size={16} />} onClick={onRemind} disabled={reminding}>
                  {t('polls.remindOpen', 'An Abstimmung erinnern')}
                </Menu.Item>
              )}
              {onEdit && (
                <Menu.Item leftSection={<IconPencil size={16} />} onClick={onEdit}>
                  {t('common.edit', 'Bearbeiten')}
                </Menu.Item>
              )}
              {onDelete && (
                <>
                  {(onRemind || onEdit) && <Menu.Divider />}
                  <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={onDelete}>
                    {t('common.delete', 'Löschen')}
                  </Menu.Item>
                </>
              )}
            </Menu.Dropdown>
          </Menu>
        )}
      </Group>

      <Group gap={6} mb="md">
        {pending && (
          <Badge color="orange" variant="light" size="sm" style={{ textTransform: 'none' }}>
            {t('polls.notVotedYet', 'Noch nicht abgestimmt')}
          </Badge>
        )}
        {hasVoted && (
          <Badge color="green" variant="light" size="sm" style={{ textTransform: 'none' }} leftSection={<IconCheck size={12} />}>
            {t('polls.voted', 'Abgestimmt')}
          </Badge>
        )}
        {!open && (
          <Badge color="gray" variant="light" size="sm" style={{ textTransform: 'none' }}>
            {t('polls.statusClosed', 'Beendet')}
          </Badge>
        )}
        {poll.isRequired && (
          <Badge variant="light" color="orange" size="sm" style={{ textTransform: 'none' }}>
            {t('polls.requiredBadge', 'Pflicht')}
          </Badge>
        )}
        {poll.autoClose && (
          <Badge variant="light" color="violet" size="sm" style={{ textTransform: 'none' }}>
            {t('polls.resolutionBadge', 'Umlaufbeschluss')}
          </Badge>
        )}
        <GroupBadge name={groupName} />
      </Group>

      {choosing ? (
        <div className="hb-poll-options" role="group" aria-label={poll.question}>
          {poll.options.map((opt, i) => (
            <UnstyledButton
              key={`${opt.label}-${i}`}
              className="hb-poll-choice"
              data-mine={voted === i || undefined}
              disabled={voting}
              onClick={() => {
                onVote(i)
                setChanging(false)
              }}
            >
              <span className="hb-poll-radio" aria-hidden>
                {voted === i && <IconCheck size={12} />}
              </span>
              <span style={{ flex: 1 }}>{opt.label}</span>
              {runs && (
                <span className="hb-poll-count">
                  {t('polls.optionVotes', '{{count}} Stimmen', { count: opt.votes })}
                </span>
              )}
            </UnstyledButton>
          ))}
        </div>
      ) : showResults ? (
        <div className="hb-poll-options">
          {poll.options.map((opt, i) => {
            const pct = poll.totalVotes > 0 ? Math.round((opt.votes / poll.totalVotes) * 100) : 0
            const isWinner = opt.votes === max && max > 0
            const isMyVote = voted === i
            return (
              <div key={`${opt.label}-${i}`}>
                <Group justify="space-between" gap="xs" mb={4} wrap="nowrap">
                  <Text size="sm" fw={isMyVote ? 650 : 400} c={isMyVote ? 'acc.7' : undefined}>
                    {opt.label}
                    {isMyVote && (
                      <IconCheck size={14} style={{ marginLeft: 6, verticalAlign: '-2px' }} aria-label={t('polls.yourVote', 'Deine Stimme')} />
                    )}
                  </Text>
                  <Text size="sm" fw={isWinner ? 700 : 400} c={isWinner ? 'acc.7' : 'dimmed'} style={{ whiteSpace: 'nowrap' }}>
                    {pct}% · {opt.votes}
                  </Text>
                </Group>
                <Progress
                  value={pct}
                  aria-label={opt.label}
                  size="sm"
                  radius="xl"
                  color={isMyVote ? 'acc.6' : isWinner ? 'acc.4' : 'gray.5'}
                  styles={{ root: { background: 'var(--hb-surface-2)' } }}
                />
              </div>
            )
          })}
        </div>
      ) : null}

      <Group justify="space-between" gap="xs" mt="md" pt="sm" style={{ borderTop: '1px solid var(--hb-border)' }}>
        <Text size="xs" c="dimmed">
          {t('polls.votesCount', '{{count}} Stimmen', { count: poll.totalVotes })} · {closingText(poll, t, i18n.language)}
        </Text>
        {mayVote && hasVoted && !changing && (
          <Button variant="subtle" size="compact-sm" onClick={() => setChanging(true)} data-testid="change-vote">
            {t('polls.changeVote', 'Stimme ändern')}
          </Button>
        )}
        {changing && (
          <Button variant="subtle" color="gray" size="compact-sm" onClick={() => setChanging(false)}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
        )}
        {poll.mayVote === false && open && (
          <Text size="xs" c="dimmed">
            {t('polls.notForYou', 'Diese Abstimmung ist für bestimmte Gruppen oder Funktionen.')}
          </Text>
        )}
      </Group>
      {children}
    </Paper>
  )
}
