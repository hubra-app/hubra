import { ActionIcon, Badge, Button, Menu, Text, Tooltip } from '@mantine/core'
import {
  IconCalendarCheck,
  IconCalendarOff,
  IconClipboardCheck,
  IconClock,
  IconDotsVertical,
  IconLogin,
  IconLogout,
  IconMapPin,
  IconPencil,
  IconRepeat,
  IconTemplate,
  IconTrash,
  IconUserQuestion,
  IconUsers,
  IconWorld,
} from '@tabler/icons-react'
import { colorText } from '@hubra/ui'
import { EVENT_TYPE_COLORS } from '@/constants'
import { useT } from '@/locales/i18n'
import type { ClubEvent } from '@/types'

/** What the viewer may do with one event; undefined hides the action. */
export interface EventCardActions {
  onJoin?: () => void
  onMaybe?: () => void
  busy?: boolean
  onRoll?: () => void
  onPending?: () => void
  onEdit?: () => void
  onTemplate?: () => void
  onCancel?: () => void
  onReinstate?: () => void
  onDelete?: () => void
}

/** The heading above the events of one month ("November 2026"). */
export function MonthHeading({ month, locale }: { month: string; locale: string }) {
  const d = new Date(`${month}-01T12:00:00`)
  return (
    <div className="hb-event-month">
      {d.toLocaleString(locale, { month: 'long', year: 'numeric' })}
    </div>
  )
}

/**
 * One event in the Anlässe list: the date, what and where, how full it is,
 * and the one thing a member does here (sign up or off). What organisers do
 * (roll call, edit, cancel, delete) sits in the ⋯ menu so the row stays calm.
 */
export function EventCard({
  ev,
  joined,
  over,
  groupName,
  typeLabel,
  actions,
}: {
  ev: ClubEvent
  joined: boolean
  over: boolean
  groupName: string | null
  typeLabel: string
  actions: EventCardActions
}) {
  const { t, i18n } = useT()
  const d = new Date(`${ev.date}T12:00:00`)
  const typeColor = EVENT_TYPE_COLORS[ev.type]
  const taken = ev.placesTaken ?? ev.attendees.length
  const full = !!ev.maxAttendees && taken >= ev.maxAttendees
  const cancelled = !!ev.cancelledAt

  const status =
    ev.myStatus === 'pending'
      ? { label: t('events.status.pending', 'Angefragt'), color: 'orange' }
      : ev.myStatus === 'waitlisted'
        ? { label: t('events.status.waitlisted', 'Warteliste'), color: 'yellow' }
        : ev.myStatus === 'maybe'
          ? { label: t('events.maybe', 'Vielleicht'), color: 'gray' }
          : joined
            ? {
                label: over ? t('events.attended', 'Teilgenommen') : t('events.status.joined', 'Angemeldet'),
                color: 'green',
              }
            : null

  const menuItems = [
    actions.onRoll && (
      <Menu.Item key="roll" leftSection={<IconClipboardCheck size={16} />} onClick={actions.onRoll}>
        {t('events.attendance.take', 'Anwesenheit erfassen')}
      </Menu.Item>
    ),
    actions.onPending && (
      <Menu.Item key="pending" leftSection={<IconUserQuestion size={16} />} onClick={actions.onPending}>
        {t('events.pending.open', 'Offene Anmeldungen')}
      </Menu.Item>
    ),
    actions.onEdit && (
      <Menu.Item key="edit" leftSection={<IconPencil size={16} />} onClick={actions.onEdit}>
        {t('common.edit', 'Bearbeiten')}
      </Menu.Item>
    ),
    actions.onTemplate && (
      <Menu.Item
        key="template"
        leftSection={<IconTemplate size={16} />}
        onClick={actions.onTemplate}
        data-testid="save-template"
      >
        {t('events.templates.saveTitle', 'Als Vorlage speichern')}
      </Menu.Item>
    ),
    actions.onCancel && (
      <Menu.Item
        key="cancel"
        leftSection={<IconCalendarOff size={16} />}
        onClick={actions.onCancel}
        data-testid="cancel-event"
      >
        {t('events.cancel.action', 'Absagen')}
      </Menu.Item>
    ),
    actions.onReinstate && (
      <Menu.Item
        key="reinstate"
        leftSection={<IconCalendarCheck size={16} />}
        onClick={actions.onReinstate}
        data-testid="reinstate-event"
      >
        {t('events.cancel.reinstate', 'Doch durchführen')}
      </Menu.Item>
    ),
  ].filter(Boolean)

  return (
    <div className="hb-event-card" data-testid="event-card" data-cancelled={cancelled || undefined}>
      <div className="hb-event-date" aria-hidden>
        <span className="hb-event-date-wd">{d.toLocaleString(i18n.language, { weekday: 'short' })}</span>
        <span className="hb-event-date-day num">{d.getDate()}</span>
        <span className="hb-event-date-mon">{d.toLocaleString(i18n.language, { month: 'short' })}</span>
      </div>

      <div className="hb-event-body">
        <div className="hb-event-title-row">
          <Text
            fw={650}
            fz="md"
            c={cancelled ? 'dimmed' : undefined}
            td={cancelled ? 'line-through' : undefined}
            className="hb-event-title"
          >
            {ev.title}
          </Text>
          {cancelled && (
            <Badge color="red" variant="light" data-testid="event-cancelled">
              {t('events.cancel.badge', 'Abgesagt')}
            </Badge>
          )}
          {status && !cancelled && (
            <Badge color={status.color} variant="light" data-testid="event-my-status">
              {status.label}
            </Badge>
          )}
        </div>
        <div className="hb-event-meta">
          <span>
            <IconClock size={14} aria-hidden />
            {ev.allDay || !ev.time ? t('events.allDay', 'Ganztägig') : ev.time}
          </span>
          {ev.location && (
            <span>
              <IconMapPin size={14} aria-hidden />
              {ev.location}
            </span>
          )}
          <span>
            <IconUsers size={14} aria-hidden />
            <span>
              {ev.maxAttendees
                ? t('events.places', '{{taken}} von {{max}}', { taken, max: ev.maxAttendees })
                : t('events.signedUp', '{{count}} angemeldet', { count: taken })}
            </span>
            {(ev.maybeCount ?? 0) > 0 && (
              <span className="hb-event-dim">
                {t('events.maybeCount', '+{{count}} vielleicht', { count: ev.maybeCount })}
              </span>
            )}
            {full && !over && !cancelled && (
              <Badge size="xs" color="gray" variant="light">
                {t('events.full', 'Voll')}
              </Badge>
            )}
          </span>
        </div>
        <div className="hb-event-tags">
          <Badge
            variant="light"
            size="sm"
            style={{
              color: colorText(typeColor),
              background: `color-mix(in srgb, ${typeColor} 12%, transparent)`,
            }}
          >
            {typeLabel}
          </Badge>
          {groupName && (
            <Badge variant="outline" color="gray" size="sm">
              {groupName}
            </Badge>
          )}
          {ev.isPublic && (
            <Tooltip label={t('events.isPublic', 'Öffentlicher Anlass')}>
              <IconWorld size={15} aria-label={t('events.isPublic', 'Öffentlicher Anlass')} className="hb-event-dim" />
            </Tooltip>
          )}
          {ev.seriesId && (
            <Tooltip label={t('events.series.badge', 'Wiederkehrender Termin')}>
              <IconRepeat size={15} aria-label={t('events.series.badge', 'Wiederkehrender Termin')} className="hb-event-dim" />
            </Tooltip>
          )}
          {actions.onPending && (ev.pendingCount ?? 0) > 0 && (
            <Badge variant="light" color="orange" size="sm" style={{ cursor: 'pointer' }} onClick={actions.onPending}>
              {t('events.pendingCount', '{{count}} offen', { count: ev.pendingCount })}
            </Badge>
          )}
        </div>
        {cancelled && ev.cancelReason && (
          <Text size="sm" c="red.7" mt={6}>
            {ev.cancelReason}
          </Text>
        )}
        {!cancelled && ev.description && (
          <Text size="sm" c="dimmed" lineClamp={2} mt={6}>
            {ev.description}
          </Text>
        )}
      </div>

      <div className="hb-event-actions">
        {!over && !cancelled && actions.onJoin && (
          <Button
            size="sm"
            variant={joined ? 'default' : 'filled'}
            disabled={actions.busy}
            leftSection={joined ? <IconLogout size={16} /> : <IconLogin size={16} />}
            onClick={actions.onJoin}
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
        {!over && !cancelled && !joined && actions.onMaybe && (
          <Button
            size="sm"
            variant={ev.myStatus === 'maybe' ? 'light' : 'subtle'}
            color={ev.myStatus === 'maybe' ? undefined : 'gray'}
            disabled={actions.busy}
            onClick={actions.onMaybe}
          >
            {ev.myStatus === 'maybe' ? t('events.maybeUndo', 'Vielleicht zurücknehmen') : t('events.maybe', 'Vielleicht')}
          </Button>
        )}
        {(menuItems.length > 0 || actions.onDelete) && (
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                aria-label={t('common.moreActions', 'Weitere Aktionen')}
                data-testid="event-menu"
              >
                <IconDotsVertical size={18} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              {menuItems}
              {actions.onDelete && (
                <>
                  {menuItems.length > 0 && <Menu.Divider />}
                  <Menu.Item
                    color="red"
                    leftSection={<IconTrash size={16} />}
                    onClick={actions.onDelete}
                    data-testid="delete-event"
                  >
                    {t('common.delete', 'Löschen')}
                  </Menu.Item>
                </>
              )}
            </Menu.Dropdown>
          </Menu>
        )}
      </div>
    </div>
  )
}
