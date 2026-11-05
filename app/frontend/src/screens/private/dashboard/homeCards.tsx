import { Button, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useNav, useAuth } from '@/context/AppContext'
import { useMyVotes, usePolls } from '@/data/lists'
import { Card } from '@/components/ui'

/** "New event" and "Invite member" above the club's start page, for who may. */
export function ClubActions() {
  const { t } = useT()
  const { go } = useNav()
  const { hasPermission } = useAuth()
  const canCreateEvent = hasPermission('events.events.create')
  const canAddMember = hasPermission('members.members.create')
  if (!canCreateEvent && !canAddMember) return null
  return (
    <>
      {canCreateEvent && (
        <Button variant="default" onClick={() => go('/app/operations/events?new=1')}>
          {t('dashboard.buttons.newEvent')}
        </Button>
      )}
      {canAddMember && (
        <Button variant="filled" onClick={() => go('/app/members?invite=1')}>
          {t('members.invite.title', 'Mitglied einladen')}
        </Button>
      )}
    </>
  )
}

/** Open polls the member hasn't voted in yet; nothing when there are none. */
export function VoteNeededCard() {
  const { t, i18n } = useT()
  const { go } = useNav()
  const myVotes = useMyVotes()
  const { polls } = usePolls()
  const requiredPolls = polls.filter((p) => p.status === 'open' && myVotes[p.id] === undefined)
  if (requiredPolls.length === 0) return null
  return (
    <Card
      style={{
        border: '1.5px solid var(--mantine-color-acc-4)',
        background: 'rgba(116, 65, 224, 0.08)',
      }}
    >
      <Card.Header style={{ background: 'transparent' }}>
        <span style={{ fontSize: 'var(--mantine-font-size-md)' }}>{'\uD83D\uDDF3'}</span>
        <Text fw={700} fz="md" style={{ color: 'var(--mantine-color-acc-7)' }}>
          {t('dashboard.voteNeeded.title')}
        </Text>
        <span
          style={{
            marginLeft: 'auto',
            fontSize: 'var(--mantine-font-size-xs)',
            color: 'var(--mantine-color-acc-7)',
          }}
        >
          {t('dashboard.voteNeeded.pollsRequire', {
            count: requiredPolls.length,
          })}
        </span>
      </Card.Header>
      <div>
        {requiredPolls.map((poll) => (
          <div
            key={poll.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 16px',
              borderTop: '1px solid rgba(116, 65, 224, 0.25)',
              gap: 12,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  color: 'var(--mantine-color-ink-8)',
                }}
              >
                {poll.question}
              </div>
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: 'var(--mantine-color-acc-7)',
                }}
              >
                {poll.closesAt
                  ? t('dashboard.voteNeeded.closesOn', {
                      date: new Date(poll.closesAt).toLocaleDateString(i18n.language, {
                        day: 'numeric',
                        month: 'short',
                      }),
                    })
                  : t('dashboard.voteNeeded.closesIn', {
                      days: poll.closesIn,
                    })}
                {' \u00b7 '}
                {t('dashboard.voteNeeded.options', {
                  count: poll.options.length,
                })}
              </div>
            </div>
            <Button size="sm" variant="filled" onClick={() => go('/app/operations/polls')}>
              {t('dashboard.voteNeeded.vote')} →
            </Button>
          </div>
        ))}
      </div>
    </Card>
  )
}
