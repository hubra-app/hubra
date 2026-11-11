import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Badge,
  Button,
  CopyButton,
  Group,
  Menu,
  SegmentedControl,
  Stack,
  Text,
} from '@mantine/core'
import {
  IconCheck,
  IconCopy,
  IconDots,
  IconTrash,
  IconUserPlus,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import { useInstance } from '@/context/InstanceContext'
import { URL_CLUB } from '@/clubBase'
import { qk } from '@/data/keys'
import { Card, ConfirmModal, EmptyState, ErrorBanner, LoadingSpinner } from '@/components/ui'
import {
  deleteTrial,
  inviteTrial,
  listTrials,
  setTrialStatus,
  type TrialSignup,
  type TrialStatus,
} from '@/api/events'

const STATUS_COLOR: Record<TrialStatus, string> = {
  confirmed: 'blue',
  attended: 'green',
  no_show: 'gray',
  cancelled: 'gray',
  invited: 'violet',
}

function age(birth: string | null): number | null {
  if (!birth) return null
  const b = new Date(`${birth}T00:00:00`)
  const now = new Date()
  let years = now.getFullYear() - b.getFullYear()
  if (now < new Date(now.getFullYear(), b.getMonth(), b.getDate())) years -= 1
  return years
}

/**
 * Trial trainings: people who aren't members yet booked a training on the
 * club's public trial page. The trainer marks who came and invites them as
 * a trial member with one click.
 */
/** The trial bookings, a tab of Anlässe (EventsPage has the page head). */
export function TrialsScreen() {
  const { t, i18n } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const { hasPermission } = useAuth()
  const { ssoUrl } = useInstance()
  const canManage = hasPermission('events.trials.manage')
  // Inviting someone to join also needs the members right.
  const canInvite = canManage && hasPermission('members.members.create')
  const [past, setPast] = useState(false)
  const [busy, setBusy] = useState<number | null>(null)
  const [removing, setRemoving] = useState<TrialSignup | null>(null)
  const { data, isLoading, error } = useQuery({
    queryKey: qk.trials(past),
    queryFn: () => listTrials(past),
  })
  const pageUrl = URL_CLUB ? `${ssoUrl}/clubs/${encodeURIComponent(URL_CLUB)}/trial` : ''

  const statusLabel = (s: TrialStatus) =>
    ({
      confirmed: t('events.trials.status.confirmed', 'Angemeldet'),
      attended: t('events.trials.status.attended', 'War da'),
      no_show: t('events.trials.status.noShow', 'Nicht erschienen'),
      cancelled: t('events.trials.status.cancelled', 'Abgesagt'),
      invited: t('events.trials.status.invited', 'Eingeladen'),
    })[s]

  const day = (d: string) =>
    new Date(`${d}T00:00:00Z`).toLocaleDateString(i18n.language, {
      weekday: 'short',
      day: 'numeric',
      month: 'numeric',
      timeZone: 'UTC',
    })

  const run = async (id: number, action: () => Promise<unknown>, done: string) => {
    setBusy(id)
    try {
      await action()
      await queryClient.invalidateQueries({ queryKey: qk.trialsAll })
      notify('success', done)
    } catch (err: unknown) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(null)
    }
  }

  const remove = async () => {
    if (!removing) return
    const target = removing
    setRemoving(null)
    await run(target.id, () => deleteTrial(target.id), t('events.trials.deleted', 'Buchung gelöscht'))
  }

  return (
    <div>
      <Text size="sm" c="dimmed" mb="md">
        {t(
          'events.trials.subtitle',
          'Wer noch nicht Mitglied ist, bucht ein Training auf der Schnupperseite. Schnupperplätze gibst du im Anlass an.',
        )}
      </Text>
      <Group justify="flex-end" mb={16} gap="xs" className="page-actions">
        <SegmentedControl
          value={past ? 'past' : 'upcoming'}
          onChange={(v) => setPast(v === 'past')}
          data={[
            { value: 'upcoming', label: t('events.trials.upcoming', 'Bevorstehend') },
            { value: 'past', label: t('events.trials.past', 'Vergangen') },
          ]}
        />
      </Group>

      {pageUrl && (
        <Card style={{ padding: 16, marginBottom: 16 }}>
          <Text size="sm" fw={600} mb={4}>
            {t('events.trials.page', 'Schnupperseite')}
          </Text>
          <Text size="xs" c="dimmed" mb={8}>
            {t(
              'events.trials.pageHint',
              'Verlinke sie auf der Website des Vereins. Buchungen zählen, sobald die Person ihre E-Mail-Adresse bestätigt hat.',
            )}
          </Text>
          <Group gap={6} wrap="nowrap">
            <Text ff="monospace" fz="sm" style={{ wordBreak: 'break-all' }} data-testid="trial-page-url">
              {pageUrl}
            </Text>
            <CopyButton value={pageUrl} timeout={2000}>
              {({ copied, copy }) => (
                <ActionIcon
                  color={copied ? 'teal' : 'gray'}
                  variant="subtle"
                  onClick={copy}
                  aria-label={copied ? t('common.copied') : t('common.copy')}
                >
                  {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                </ActionIcon>
              )}
            </CopyButton>
          </Group>
          {!past && data && data.events.length > 0 && (
            <Group gap={8} mt={12}>
              {data.events.map((e) => (
                <Badge key={e.id} variant="light" color={e.taken >= e.spots ? 'gray' : 'blue'}>
                  {`${day(e.date)} · ${e.title} · ${t('events.trials.taken', '{{taken}}/{{spots}} belegt', {
                    taken: e.taken,
                    spots: e.spots,
                  })}`}
                </Badge>
              ))}
            </Group>
          )}
        </Card>
      )}

      {error ? (
        <ErrorBanner message={error instanceof Error ? error.message : t('common.error')} />
      ) : isLoading || !data ? (
        <LoadingSpinner />
      ) : data.trials.length === 0 ? (
        <EmptyState
          title={t('events.trials.empty', 'Noch keine Schnupperbuchungen')}
          description={
            data.events.length === 0 && !past
              ? t(
                  'events.trials.emptyNoEvents',
                  'Gib einem Training Schnupperplätze (Anlass bearbeiten), dann erscheint es auf der Schnupperseite.',
                )
              : undefined
          }
        />
      ) : (
        <Stack gap={12}>
          {data.trials.map((s) => {
            const years = age(s.birthDate)
            const open = s.status !== 'invited'
            return (
              <Card key={s.id} style={{ padding: 16 }}>
                <Group justify="space-between" align="flex-start" wrap="nowrap" gap="sm" mb={4}>
                  <Group gap={8} style={{ minWidth: 0 }}>
                    <Text fw={600}>
                      {s.firstName} {s.lastName}
                      {years != null && (
                        <Text span c="dimmed" fw={400}>
                          {` · ${t('events.trials.age', '{{count}} Jahre', { count: years })}`}
                        </Text>
                      )}
                    </Text>
                    <Badge color={STATUS_COLOR[s.status]} variant="light">
                      {statusLabel(s.status)}
                    </Badge>
                    {s.source && (
                      <Badge color="gray" variant="outline" style={{ textTransform: 'none' }}>
                        {t('members.poster.via', 'über Plakat «{{source}}»', { source: s.source })}
                      </Badge>
                    )}
                  </Group>
                  {canManage && (
                    <Menu position="bottom-end" withinPortal>
                      <Menu.Target>
                        <ActionIcon variant="subtle" color="gray" aria-label={t('common.more', 'Mehr')}>
                          <IconDots size={16} />
                        </ActionIcon>
                      </Menu.Target>
                      <Menu.Dropdown>
                        {open &&
                          (['attended', 'no_show', 'confirmed', 'cancelled'] as TrialStatus[])
                            .filter((st) => st !== s.status)
                            .map((st) => (
                              <Menu.Item
                                key={st}
                                onClick={() => run(s.id, () => setTrialStatus(s.id, st), statusLabel(st))}
                              >
                                {statusLabel(st)}
                              </Menu.Item>
                            ))}
                        <Menu.Item
                          color="red"
                          leftSection={<IconTrash size={14} />}
                          onClick={() => setRemoving(s)}
                        >
                          {t('events.trials.delete', 'Buchung löschen')}
                        </Menu.Item>
                      </Menu.Dropdown>
                    </Menu>
                  )}
                </Group>
                <Text size="sm">
                  {day(s.eventDate)}
                  {s.eventTime ? ` ${s.eventTime}` : ''} · {s.eventTitle}
                </Text>
                <Text size="sm" c="dimmed" style={{ wordBreak: 'break-all' }}>
                  <a href={`mailto:${s.email}`}>{s.email}</a>
                  {s.phone && (
                    <>
                      {' · '}
                      <a href={`tel:${s.phone.replace(/\s/g, '')}`}>{s.phone}</a>
                    </>
                  )}
                </Text>
                {s.message && (
                  <Text size="sm" mt={6} style={{ whiteSpace: 'pre-wrap' }}>
                    {s.message}
                  </Text>
                )}
                {canInvite && open && (
                  <Button
                    mt={12}
                    size="xs"
                    variant={s.status === 'attended' ? 'filled' : 'default'}
                    loading={busy === s.id}
                    onClick={() =>
                      run(
                        s.id,
                        () => inviteTrial(s.id),
                        t('events.trials.invited', 'Einladung an {{email}} verschickt', {
                          email: s.email,
                        }),
                      )
                    }
                  >
                    <IconUserPlus size={14} />
                    {t('events.trials.invite', 'Als Schnuppermitglied einladen')}
                  </Button>
                )}
              </Card>
            )
          })}
        </Stack>
      )}
      <Text size="xs" c="dimmed" mt={16}>
        {t(
          'events.trials.retention',
          'Buchungen werden ein halbes Jahr nach dem Training gelöscht, unbestätigte nach einer Woche.',
        )}
      </Text>
      <ConfirmModal
        open={removing !== null}
        title={t('events.trials.deleteTitle', 'Buchung löschen')}
        body={t(
          'events.trials.deleteBody',
          'Die Buchung von {{name}} und ihre Angaben werden gelöscht.',
          { name: removing ? `${removing.firstName} ${removing.lastName}` : '' },
        )}
        onConfirm={remove}
        onClose={() => setRemoving(null)}
      />
    </div>
  )
}
