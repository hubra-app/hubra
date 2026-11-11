import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Anchor, Badge, Button, CopyButton, Group, Paper, Stack, Text, Title } from '@mantine/core'
import {
  IconArrowLeft,
  IconCheck,
  IconClipboardCheck,
  IconClock,
  IconLink,
  IconLogin,
  IconLogout,
  IconMapPin,
  IconPencil,
  IconUserQuestion,
  IconUsers,
  IconVideo,
} from '@tabler/icons-react'
import { colorText } from '@hubra/ui'
import { EVENT_TYPE_COLORS } from '@/constants'
import { useT } from '@/locales/i18n'
import { useAuth } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useEvents, useListCache, useMyJoinedEvents } from '@/data/lists'
import { EmptyState, LoadingSpinner } from '@/components/ui'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { formatDate } from '@/format'
import type { ClubEvent } from '@/types'
import { listRegistrations } from '@/api/events'
import { eventTypeLabel, isPastEvent } from './eventDates'
import { hasOpenSignUp, useMaybeEvent, useToggleJoinEvent } from './useEventActions'
import { AttendanceModal } from './AttendanceModal'
import { PendingSignUpsModal } from './PendingSignUpsModal'
import { useContentGroups } from './contentGroups'

const STATUS_COLOR: Record<string, string> = {
  registered: 'green',
  approved: 'green',
  attended: 'teal',
  waitlisted: 'yellow',
  pending: 'orange',
  maybe: 'gray',
  declined: 'red',
}

const STATUS_LABEL: Record<string, string> = {
  registered: 'Angemeldet',
  approved: 'Bestätigt',
  attended: 'War da',
  waitlisted: 'Warteliste',
  pending: 'Angefragt',
  maybe: 'Vielleicht',
  declined: 'Abgelehnt',
}

/**
 * One Anlass on its own page (/app/operations/events/<id>): what, when and
 * where, the description, signing up, and a link to share. Organisers also
 * see who signed up, take the roll and handle sign-ups waiting for approval.
 */
export function EventDetail({ id }: { id: string }) {
  const { t, i18n } = useT()
  const navigate = useNavigate()
  const { events, isLoading } = useEvents()
  const eventCache = useListCache<ClubEvent>(qk.events)
  const myJoined = useMyJoinedEvents()
  const { currentUser, hasPermission } = useAuth()
  const join = useToggleJoinEvent()
  const maybe = useMaybeEvent()
  const scope = useContentGroups('events.events.update')
  const [rollOpen, setRollOpen] = useState(false)
  const [pendingOpen, setPendingOpen] = useState(false)

  const ev = events.find((e) => e.id === id)
  const hosts = !!ev && currentUser != null && ev.createdById === Number(currentUser.id)
  const inScope = (key: string) => !!ev && hasPermission(key, ev.groupId ?? undefined)
  const organiser = hosts || inScope('events.events.add_attendee')
  const canEdit = hosts || inScope('events.events.update')

  const regs = useQuery({
    queryKey: qk.eventRegistrations(id),
    queryFn: () => listRegistrations(id),
    enabled: !!ev && organiser,
  })

  if (isLoading) return <LoadingSpinner />
  if (!ev) {
    return (
      <EmptyState
        title={t('events.linkedGone', 'Diesen Anlass gibt es nicht mehr.')}
        action={{ label: t('events.detail.back', 'Zu den Anlässen'), onClick: () => navigate('/app/operations/events') }}
      />
    )
  }

  const joined = hasOpenSignUp(ev, myJoined.has(ev.id))
  const over = isPastEvent(ev)
  const cancelled = !!ev.cancelledAt
  const taken = ev.placesTaken ?? ev.attendees.length
  const full = !!ev.maxAttendees && taken >= ev.maxAttendees
  const typeColor = EVENT_TYPE_COLORS[ev.type]
  const d = new Date(`${ev.date}T12:00:00`)
  const longDate = d.toLocaleDateString(i18n.language, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
  const link = `${window.location.origin}${window.location.pathname}`
  const visible = (regs.data ?? []).filter((r) => !r.cancelledAt)

  return (
    <Stack gap="md">
      <div>
        <Button
          variant="subtle"
          size="compact-sm"
          leftSection={<IconArrowLeft size={16} />}
          component={Link}
          to="/app/operations/events"
        >
          {t('events.detail.back', 'Zu den Anlässen')}
        </Button>
      </div>

      <Paper withBorder p="lg">
        <Group align="flex-start" gap="lg" wrap="nowrap" className="hb-event-detail-head">
          <div className="hb-event-date" aria-hidden>
            <span className="hb-event-date-wd">{d.toLocaleString(i18n.language, { weekday: 'short' })}</span>
            <span className="hb-event-date-day num">{d.getDate()}</span>
            <span className="hb-event-date-mon">{d.toLocaleString(i18n.language, { month: 'short' })}</span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <Group gap={8} mb={6}>
              <Title order={2} fz="h3" td={cancelled ? 'line-through' : undefined} style={{ overflowWrap: 'anywhere' }}>
                {ev.title}
              </Title>
              {cancelled && (
                <Badge color="red" variant="light">
                  {t('events.cancel.badge', 'Abgesagt')}
                </Badge>
              )}
              {joined && !cancelled && (
                <Badge color="green" variant="light">
                  {over ? t('events.attended', 'Teilgenommen') : t('events.status.joined', 'Angemeldet')}
                </Badge>
              )}
            </Group>
            <div className="hb-event-meta">
              <span>
                <IconClock size={14} aria-hidden />
                {longDate}
                {ev.allDay || !ev.time ? ` · ${t('events.allDay', 'Ganztägig')}` : ` · ${ev.time}`}
                {ev.endDate && ev.endDate !== ev.date ? ` – ${formatDate(ev.endDate)}` : ''}
              </span>
              {ev.location && (
                <span>
                  <IconMapPin size={14} aria-hidden />
                  {ev.location}
                </span>
              )}
              <span>
                <IconUsers size={14} aria-hidden />
                {ev.maxAttendees
                  ? t('events.places', '{{taken}} von {{max}}', { taken, max: ev.maxAttendees })
                  : t('events.signedUp', '{{count}} angemeldet', { count: taken })}
                {(ev.maybeCount ?? 0) > 0 && ` · ${t('events.maybeCount', '+{{count}} vielleicht', { count: ev.maybeCount })}`}
              </span>
              {ev.meetingUrl && (
                <span>
                  <IconVideo size={14} aria-hidden />
                  <Anchor href={ev.meetingUrl} target="_blank" rel="noopener noreferrer" size="sm">
                    {t('events.detail.meeting', 'Online teilnehmen')}
                  </Anchor>
                </span>
              )}
            </div>
            <Group gap={6} mt="sm">
              <Badge
                variant="light"
                size="sm"
                style={{ color: colorText(typeColor), background: `color-mix(in srgb, ${typeColor} 12%, transparent)` }}
              >
                {eventTypeLabel(ev.type)}
              </Badge>
              {scope.groupName(ev.groupId) && (
                <Badge variant="outline" color="gray" size="sm">
                  {scope.groupName(ev.groupId)}
                </Badge>
              )}
              {ev.isPublic && (
                <Badge variant="light" color="gray" size="sm">
                  {t('events.isPublic', 'Öffentlicher Anlass')}
                </Badge>
              )}
            </Group>
            {cancelled && ev.cancelReason && (
              <Text size="sm" c="red.7" mt="sm">
                {ev.cancelReason}
              </Text>
            )}
          </div>
        </Group>

        <Group gap="xs" mt="lg" className="hb-event-detail-actions">
          {!over && !cancelled && (
            <Button
              variant={joined ? 'default' : 'filled'}
              leftSection={joined ? <IconLogout size={16} /> : <IconLogin size={16} />}
              disabled={join.isPending}
              onClick={() =>
                join.mutate(
                  { eventId: ev.id, eventTitle: ev.title, memberId: currentUser?.id ?? '' },
                  // The organisers' list below changes with it.
                  { onSettled: () => void regs.refetch() },
                )
              }
            >
              {joined
                ? ev.myStatus === 'pending'
                  ? t('events.withdrawRequest', 'Anfrage zurückziehen')
                  : ev.myStatus === 'waitlisted'
                    ? t('events.leaveWaitlist', 'Warteliste verlassen')
                    : t('events.leave', 'Abmelden')
                : full
                  ? t('events.joinWaitlist', 'Auf die Warteliste')
                  : t('events.join', 'Teilnehmen')}
            </Button>
          )}
          {!over && !cancelled && !joined && (
            <Button
              variant={ev.myStatus === 'maybe' ? 'light' : 'default'}
              disabled={maybe.isPending}
              onClick={() => maybe.mutate({ eventId: ev.id, eventTitle: ev.title }, { onSettled: () => void regs.refetch() })}
            >
              {ev.myStatus === 'maybe' ? t('events.maybeUndo', 'Vielleicht zurücknehmen') : t('events.maybe', 'Vielleicht')}
            </Button>
          )}
          <CopyButton value={link}>
            {({ copied, copy }) => (
              <Button
                variant="subtle"
                color={copied ? 'green' : 'gray'}
                leftSection={copied ? <IconCheck size={16} /> : <IconLink size={16} />}
                onClick={copy}
              >
                {copied ? t('events.detail.copied', 'Link kopiert') : t('events.detail.copyLink', 'Link kopieren')}
              </Button>
            )}
          </CopyButton>
          {canEdit && (
            <Button
              variant="subtle"
              color="gray"
              leftSection={<IconPencil size={16} />}
              onClick={() => navigate(`/app/operations/events?event=${ev.id}&edit=1`)}
            >
              {t('common.edit', 'Bearbeiten')}
            </Button>
          )}
        </Group>
      </Paper>

      {ev.description && (
        <Paper withBorder p="lg">
          <Text fw={650} mb="xs">
            {t('events.detail.about', 'Beschreibung')}
          </Text>
          <MarkdownRenderer content={ev.description} />
        </Paper>
      )}

      {organiser && (
        <Paper withBorder p="lg" data-testid="event-registrations">
          <Group justify="space-between" mb="sm">
            <Text fw={650}>
              {t('events.detail.signUps', 'Anmeldungen')} ({visible.length})
            </Text>
            <Group gap="xs">
              {(ev.pendingCount ?? 0) > 0 && (
                <Button size="xs" variant="light" color="orange" leftSection={<IconUserQuestion size={14} />} onClick={() => setPendingOpen(true)}>
                  {t('events.pendingCount', '{{count}} offen', { count: ev.pendingCount })}
                </Button>
              )}
              {inScope('events.events.add_attendee') && (
                <Button size="xs" variant="default" leftSection={<IconClipboardCheck size={14} />} onClick={() => setRollOpen(true)}>
                  {t('events.attendance.take', 'Anwesenheit erfassen')}
                </Button>
              )}
            </Group>
          </Group>
          {regs.isLoading ? (
            <LoadingSpinner compact />
          ) : visible.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t('events.detail.noSignUps', 'Noch niemand angemeldet.')}
            </Text>
          ) : (
            <div className="hb-signup-list">
              {visible.map((r) => (
                <div key={r.id} className="hb-signup-row">
                  <Text size="sm" fw={500} style={{ flex: 1, minWidth: 0 }} truncate>
                    {r.memberName ?? `#${r.memberId}`}
                    {r.guests > 0 && (
                      <Text span size="xs" c="dimmed">
                        {' '}
                        {t('events.detail.plusGuests', '+{{count}} Gäste', { count: r.guests })}
                      </Text>
                    )}
                  </Text>
                  <Text size="xs" c="dimmed" visibleFrom="sm">
                    {formatDate(r.registeredAt)}
                  </Text>
                  <Badge size="sm" variant="light" color={STATUS_COLOR[r.status] ?? 'gray'} style={{ textTransform: 'none', flexShrink: 0 }}>
                    {t(`events.status.${r.status}`, STATUS_LABEL[r.status] ?? r.status)}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </Paper>
      )}

      <AttendanceModal event={rollOpen ? ev : null} onClose={() => setRollOpen(false)} />
      <PendingSignUpsModal
        event={pendingOpen ? ev : null}
        onClose={() => {
          setPendingOpen(false)
          void regs.refetch()
        }}
        onDecided={(updated) => eventCache.patch(updated.id, () => updated)}
      />
    </Stack>
  )
}
