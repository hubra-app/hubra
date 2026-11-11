import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Anchor, Badge, Button, Group, Paper, Text, Tooltip } from '@mantine/core'
import {
  IconCalendarEvent,
  IconInfoCircle,
  IconLogin,
  IconLogout,
  IconRepeat,
  IconUsers,
  IconWorld,
} from '@tabler/icons-react'
import { colorText } from '@hubra/ui'
import { EVENT_TYPE_COLORS } from '@/constants'
import { useT } from '@/locales/i18n'
import { useAuth } from '@/context/AppContext'
import { useEvents, useMyJoinedEvents } from '@/data/lists'
import { qk } from '@/data/keys'
import { listParticipants } from '@/api/events'
import { Avatar, LoadingSpinner } from '@/components/ui'
import {
  DetailBack,
  DetailFact,
  DetailHeader,
  DetailNotFound,
  DetailRow,
  DetailSection,
} from '@/components/detail'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { formatDate } from '@/format'
import type { ClubEvent } from '@/types'
import { isPastEvent } from './eventDates'
import { hasOpenSignUp, useMaybeEvent, useToggleJoinEvent } from './useEventActions'
import { EventOrganiserMenu } from './EventOrganiserMenu'
import { DeleteEventModal } from './DeleteEventModal'
import { GroupBadge } from './ContentGroupFields'
import { useContentGroups } from './contentGroups'
import { useEventPerms } from './eventPerms'

const LIST = '/app/operations/events'

/** The date as a calendar sheet: day, month. */
function DateTile({ ev }: { ev: ClubEvent }) {
  const { i18n } = useT()
  const d = new Date(`${ev.date}T00:00:00`)
  const color = ev.color || EVENT_TYPE_COLORS[ev.type] || 'var(--mantine-primary-color-filled)'
  return (
    <div
      aria-hidden
      style={{
        width: 64,
        height: 64,
        borderRadius: 14,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: `color-mix(in srgb, ${color} 14%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 40%, transparent)`,
      }}
    >
      <span className="num" style={{ fontSize: 26, fontWeight: 700, lineHeight: 1, color: 'var(--hb-text)' }}>
        {d.getDate()}
      </span>
      <span
        style={{
          fontSize: 'var(--mantine-font-size-xs)',
          fontWeight: 600,
          letterSpacing: '0.08em',
          color: 'var(--hb-text-2)',
        }}
      >
        {d.toLocaleString(i18n.language, { month: 'short' }).toUpperCase()}
      </span>
    </div>
  )
}

/** Who is coming, and who said "Vielleicht". */
function Participants({ ev }: { ev: ClubEvent }) {
  const { t } = useT()
  // The list changes when the viewer signs up or off, so it reloads then.
  const { data = [], isLoading } = useQuery({
    queryKey: [...qk.eventParticipants(ev.id), ev.myStatus ?? '', ev.placesTaken ?? 0],
    queryFn: () => listParticipants(ev.id),
  })
  const coming = data.filter((p) => p.status === 'coming')
  const maybe = data.filter((p) => p.status === 'maybe')
  const row = (p: (typeof data)[number]) => (
    <div
      key={p.memberId}
      style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 16px', borderBottom: '1px solid var(--hb-border)' }}
    >
      <Avatar name={p.name} color={p.avatarColor} size={28} />
      <Text size="sm" style={{ flex: 1, minWidth: 0 }} truncate>
        {p.name}
      </Text>
      {p.guests > 0 && (
        <Text size="xs" c="dimmed">
          {t('events.detail.guests', '+{{count}} Gäste', { count: p.guests })}
        </Text>
      )}
    </div>
  )
  return (
    <DetailSection
      icon={<IconUsers size={16} />}
      title={t('events.detail.coming', 'Wer kommt')}
      right={
        <Text size="xs" c="dimmed" className="num">
          {ev.placesTaken ?? coming.length}
          {ev.maxAttendees ? ` / ${ev.maxAttendees}` : ''}
        </Text>
      }
    >
      <div data-testid="event-participants">
        {isLoading ? (
          <LoadingSpinner />
        ) : coming.length === 0 && maybe.length === 0 ? (
          <Text size="sm" c="dimmed" p="md">
            {t('events.detail.nobody', 'Noch niemand angemeldet. Sei die erste Person!')}
          </Text>
        ) : (
          <>
            {coming.map(row)}
            {maybe.length > 0 && (
              <>
                <Text size="xs" fw={600} c="dimmed" px={16} pt={10} pb={4}>
                  {t('events.detail.maybe', 'Vielleicht ({{count}})', { count: maybe.length })}
                </Text>
                {maybe.map(row)}
              </>
            )}
          </>
        )}
      </div>
    </DetailSection>
  )
}

/** One event: what, when, where, who comes, and signing up. */
export function EventDetailScreen({ id }: { id: string }) {
  const { t } = useT()
  const navigate = useNavigate()
  const { currentUser } = useAuth()
  const { events, isLoading } = useEvents()
  const myJoined = useMyJoinedEvents()
  const join = useToggleJoinEvent()
  const maybe = useMaybeEvent()
  const perms = useEventPerms()
  const scope = useContentGroups('events.events.read')
  const [deleting, setDeleting] = useState<ClubEvent | null>(null)
  const ev = events.find((e) => e.id === id)

  if (isLoading) return <LoadingSpinner />
  if (!ev) {
    return (
      <DetailNotFound
        back={LIST}
        backLabel={t('shell.nav.events', 'Anlässe')}
        message={t('events.linkedGone', 'Diesen Anlass gibt es nicht mehr.')}
      />
    )
  }

  const over = isPastEvent(ev)
  const joined = hasOpenSignUp(ev, myJoined.has(ev.id))
  const typeColor = EVENT_TYPE_COLORS[ev.type]
  const full = !!ev.maxAttendees && (ev.placesTaken ?? 0) >= ev.maxAttendees
  const when =
    ev.endDate && ev.endDate !== ev.date
      ? `${formatDate(ev.date)} – ${formatDate(ev.endDate)}`
      : formatDate(ev.date)
  const typeLabel = t(`events.types.${ev.type.toLowerCase()}`, ev.type)

  const signUp = over ? (
    <Badge variant="light" color="gray" size="lg" style={{ textTransform: 'none' }}>
      {joined ? t('events.attended', 'Teilgenommen') : t('events.over', 'Vorbei')}
    </Badge>
  ) : ev.cancelledAt ? null : (
    <>
      <Button
        variant={joined ? 'default' : 'filled'}
        loading={join.isPending}
        leftSection={joined ? <IconLogout size={16} /> : <IconLogin size={16} />}
        onClick={() => join.mutate({ eventId: ev.id, eventTitle: ev.title, memberId: currentUser?.id ?? '' })}
        data-testid="event-join"
      >
        {joined
          ? ev.myStatus === 'pending'
            ? t('events.withdrawRequest', 'Anfrage zurückziehen')
            : ev.myStatus === 'waitlisted'
              ? t('events.leaveWaitlist', 'Warteliste verlassen')
              : t('events.leave', 'Abmelden')
          : full
            ? t('events.detail.joinWaitlist', 'Auf die Warteliste')
            : t('events.join', 'Teilnehmen')}
      </Button>
      {!joined && (
        <Tooltip
          label={
            ev.myStatus === 'maybe'
              ? t('events.maybeUndo', 'Vielleicht zurücknehmen')
              : t('events.maybeHint', 'Vielleicht: ohne Platz, die Organisatoren sehen es')
          }
        >
          <Button
            variant={ev.myStatus === 'maybe' ? 'light' : 'default'}
            loading={maybe.isPending}
            onClick={() => maybe.mutate({ eventId: ev.id, eventTitle: ev.title })}
          >
            {t('events.maybe', 'Vielleicht')}
          </Button>
        </Tooltip>
      )}
    </>
  )

  return (
    <div data-testid="event-detail">
      <DetailBack to={LIST} label={t('shell.nav.events', 'Anlässe')} />
      <DetailHeader
        media={<DateTile ev={ev} />}
        title={
          <span style={ev.cancelledAt ? { textDecoration: 'line-through', color: 'var(--hb-text-3)' } : undefined}>
            {ev.title}
          </span>
        }
        subtitle={[when, ev.time, ev.location].filter(Boolean).join(' · ')}
        badges={
          <>
            <Badge
              variant="light"
              style={{
                borderColor: `color-mix(in srgb, ${typeColor} 40%, transparent)`,
                color: colorText(typeColor),
                background: `color-mix(in srgb, ${typeColor} 10%, transparent)`,
              }}
            >
              {typeLabel}
            </Badge>
            {ev.cancelledAt && (
              <Badge color="red" variant="light">
                {t('events.cancel.badge', 'Abgesagt')}
              </Badge>
            )}
            {ev.myStatus === 'pending' && (
              <Badge color="orange" variant="light" style={{ textTransform: 'none' }}>
                {t('events.requested', 'Anfrage gesendet')}
              </Badge>
            )}
            {ev.myStatus === 'waitlisted' && (
              <Badge color="orange" variant="light" style={{ textTransform: 'none' }}>
                {t('events.waitlisted', 'Auf der Warteliste')}
              </Badge>
            )}
            {(ev.myStatus === 'registered' || ev.myStatus === 'approved') && (
              <Badge color="green" variant="light" style={{ textTransform: 'none' }}>
                {t('events.joined', 'Angemeldet')}
              </Badge>
            )}
            {ev.seriesId && (
              <Badge variant="default" leftSection={<IconRepeat size={12} />} style={{ textTransform: 'none' }}>
                {t('events.series.badge', 'Wiederkehrender Termin')}
              </Badge>
            )}
            {ev.isPublic && (
              <Badge variant="default" leftSection={<IconWorld size={12} />} style={{ textTransform: 'none' }}>
                {t('events.public', 'Öffentlich')}
              </Badge>
            )}
            <GroupBadge name={scope.groupName(ev.groupId)} />
          </>
        }
        actions={
          <Group gap="xs" wrap="wrap">
            {signUp}
            <EventOrganiserMenu
              ev={ev}
              onEdit={() => navigate(`${LIST}?edit=${ev.id}`)}
              onDelete={() => setDeleting(ev)}
            />
          </Group>
        }
        facts={
          <>
            <DetailFact label={t('common.date', 'Datum')}>{when}</DetailFact>
            <DetailFact label={t('events.time', 'Zeit')}>{ev.time || t('events.detail.allDay', 'Ganztägig')}</DetailFact>
            <DetailFact label={t('events.location', 'Ort')}>{ev.location || t('events.noLocation', 'Kein Ort')}</DetailFact>
            <DetailFact label={t('events.detail.places', 'Plätze')}>
              <span className={ev.maxAttendees ? 'num' : undefined}>
                {ev.maxAttendees
                  ? t('events.detail.placesLeft', '{{left}} von {{max}} frei', {
                      left: Math.max(0, ev.maxAttendees - (ev.placesTaken ?? 0)),
                      max: ev.maxAttendees,
                    })
                  : t('events.detail.noLimit', 'Ohne Begrenzung')}
              </span>
            </DetailFact>
          </>
        }
      />
      {ev.cancelledAt && (
        <Paper withBorder p="md" mb={16} style={{ borderColor: 'var(--mantine-color-red-4)' }}>
          <Text size="sm" fw={600} c="red">
            {t('events.detail.cancelled', 'Dieser Anlass ist abgesagt.')}
          </Text>
          {ev.cancelReason && (
            <Text size="sm" mt={4}>
              {ev.cancelReason}
            </Text>
          )}
        </Paper>
      )}
      <div className="detail-grid-end">
        <Paper withBorder p={{ base: 16, sm: 20 }}>
          <Group gap={8} mb={10}>
            <IconInfoCircle size={16} style={{ color: 'var(--mantine-color-acc-7)' }} />
            <Text fw={700} size="sm">
              {t('events.description', 'Beschreibung')}
            </Text>
          </Group>
          {ev.description ? (
            <div style={{ fontSize: 'var(--mantine-font-size-sm)', lineHeight: 1.6 }}>
              <MarkdownRenderer content={ev.description} />
            </div>
          ) : (
            <Text size="sm" c="dimmed">
              {t('events.detail.noDescription', 'Keine Beschreibung.')}
            </Text>
          )}
          {ev.meetingUrl && (
            <DetailRow label={t('events.detail.meeting', 'Online dabei')} borderless>
              <Anchor href={ev.meetingUrl} target="_blank" rel="noopener noreferrer" size="sm">
                {ev.meetingUrl}
              </Anchor>
            </DetailRow>
          )}
          {perms.canApprove(ev) && (ev.pendingCount ?? 0) > 0 && (
            <Group gap={6} mt="md">
              <IconCalendarEvent size={14} style={{ color: 'var(--mantine-color-orange-7)' }} />
              <Text size="sm" c="orange.8">
                {t('events.detail.pendingHint', '{{count}} Anmeldungen warten auf deine Bestätigung (Menü …).', {
                  count: ev.pendingCount,
                })}
              </Text>
            </Group>
          )}
        </Paper>
        <Participants ev={ev} />
      </div>
      <DeleteEventModal event={deleting} onClose={() => setDeleting(null)} onDeleted={() => navigate(LIST)} />
    </div>
  )
}
