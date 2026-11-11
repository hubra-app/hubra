import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ActionIcon, Button, Group, Paper, Text, UnstyledButton } from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import { EVENT_TYPE_COLORS } from '@/constants'
import { useT } from '@/locales/i18n'
import type { ClubEvent } from '@/types'

const pad = (n: number) => String(n).padStart(2, '0')
const isoDay = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const typeColor = (ev: ClubEvent) => ev.color || EVENT_TYPE_COLORS[ev.type] || 'var(--mantine-primary-color-filled)'

/** The days an event covers (from its date to its end date), as ISO days. */
function daysOf(ev: ClubEvent): string[] {
  if (!ev.endDate || ev.endDate <= ev.date) return [ev.date]
  const out: string[] = []
  const d = new Date(`${ev.date}T00:00:00`)
  const end = new Date(`${ev.endDate}T00:00:00`)
  // A long event shows on at most six weeks of days.
  for (let i = 0; d <= end && i < 42; i++) {
    out.push(isoDay(d))
    d.setDate(d.getDate() + 1)
  }
  return out
}

/** One event in a day cell: its colour, time and title; opens its page. */
function EventChip({ ev }: { ev: ClubEvent }) {
  const color = typeColor(ev)
  return (
    <Link
      to={`/app/operations/events?event=${ev.id}`}
      title={ev.time ? `${ev.time} · ${ev.title}` : ev.title}
      data-testid="month-event"
      style={{
        display: 'block',
        fontSize: 'var(--mantine-font-size-xs)',
        lineHeight: 1.35,
        padding: '2px 6px',
        borderRadius: 6,
        borderLeft: `3px solid ${color}`,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        color: ev.cancelledAt ? 'var(--hb-text-3)' : 'var(--hb-text)',
        textDecoration: ev.cancelledAt ? 'line-through' : 'none',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
    >
      {ev.time && <span className="num" style={{ color: 'var(--hb-text-2)' }}>{ev.time.split(/[–-]/)[0]} </span>}
      {ev.title}
    </Link>
  )
}

/**
 * Anlässe as a month: a grid from Monday to Sunday with each day's events.
 * On a phone the days show coloured dots, and the picked day's events are
 * listed under the grid.
 */
export function EventsMonth({ events }: { events: ClubEvent[] }) {
  const { t, i18n } = useT()
  const phone = useMediaQuery('(max-width: 48em)')
  const today = isoDay(new Date())
  const [month, setMonth] = useState(() => {
    const d = new Date()
    return new Date(d.getFullYear(), d.getMonth(), 1)
  })
  const [picked, setPicked] = useState<string>(today)

  const byDay = useMemo(() => {
    const map = new Map<string, ClubEvent[]>()
    for (const ev of events) {
      for (const day of daysOf(ev)) {
        const list = map.get(day) ?? []
        list.push(ev)
        map.set(day, list)
      }
    }
    for (const list of map.values()) list.sort((a, b) => (a.time || '').localeCompare(b.time || ''))
    return map
  }, [events])

  // Six rows at most, from the Monday on or before the 1st.
  const cells = useMemo(() => {
    const start = new Date(month)
    start.setDate(1 - ((start.getDay() + 6) % 7))
    const out: Date[] = []
    const d = new Date(start)
    do {
      for (let i = 0; i < 7; i++) {
        out.push(new Date(d))
        d.setDate(d.getDate() + 1)
      }
    } while (d.getMonth() === month.getMonth())
    return out
  }, [month])

  const weekdays = useMemo(() => {
    // 2024-01-01 was a Monday.
    return Array.from({ length: 7 }, (_, i) =>
      new Date(2024, 0, 1 + i).toLocaleString(i18n.language, { weekday: 'short' }),
    )
  }, [i18n.language])

  const shift = (by: number) => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + by, 1))
  const title = month.toLocaleString(i18n.language, { month: 'long', year: 'numeric' })
  const pickedEvents = byDay.get(picked) ?? []
  const maxChips = 3

  return (
    <Paper withBorder p={phone ? 'sm' : 'md'} data-testid="events-month">
      <Group justify="space-between" mb="sm" wrap="nowrap">
        <Group gap={4} wrap="nowrap">
          <ActionIcon variant="subtle" color="gray" onClick={() => shift(-1)} aria-label={t('events.month.prev', 'Vorheriger Monat')}>
            <IconChevronLeft size={18} />
          </ActionIcon>
          <Text fw={700} size="lg" style={{ textTransform: 'capitalize', minWidth: phone ? 0 : 180, textAlign: 'center' }}>
            {title}
          </Text>
          <ActionIcon variant="subtle" color="gray" onClick={() => shift(1)} aria-label={t('events.month.next', 'Nächster Monat')}>
            <IconChevronRight size={18} />
          </ActionIcon>
        </Group>
        <Button
          variant="default"
          size="xs"
          onClick={() => {
            const d = new Date()
            setMonth(new Date(d.getFullYear(), d.getMonth(), 1))
            setPicked(today)
          }}
        >
          {t('events.month.today', 'Heute')}
        </Button>
      </Group>
      <div
        role="grid"
        aria-label={title}
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(7, minmax(0, 1fr))',
          border: '1px solid var(--hb-border)',
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        {weekdays.map((wd) => (
          <div
            key={wd}
            role="columnheader"
            style={{
              fontSize: 'var(--mantine-font-size-xs)',
              fontWeight: 600,
              color: 'var(--hb-text-3)',
              textAlign: 'center',
              padding: '6px 0',
              background: 'var(--hb-surface-2)',
              borderBottom: '1px solid var(--hb-border)',
            }}
          >
            {wd}
          </div>
        ))}
        {cells.map((d, i) => {
          const day = isoDay(d)
          const inMonth = d.getMonth() === month.getMonth()
          const list = byDay.get(day) ?? []
          const isToday = day === today
          const isPicked = phone && day === picked
          const border = {
            borderTop: i >= 7 ? '1px solid var(--hb-border)' : undefined,
            borderLeft: i % 7 ? '1px solid var(--hb-border)' : undefined,
          }
          const number = (
            <span
              className="num"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                minWidth: 24,
                height: 24,
                borderRadius: 12,
                fontSize: 'var(--mantine-font-size-xs)',
                fontWeight: isToday ? 700 : 500,
                color: isToday ? 'var(--mantine-color-white)' : inMonth ? 'var(--hb-text)' : 'var(--hb-text-3)',
                background: isToday ? 'var(--mantine-primary-color-filled)' : undefined,
              }}
            >
              {d.getDate()}
            </span>
          )
          if (phone) {
            return (
              <UnstyledButton
                key={day}
                role="gridcell"
                aria-selected={isPicked}
                aria-label={`${d.toLocaleDateString(i18n.language)}: ${list.length}`}
                onClick={() => setPicked(day)}
                style={{
                  ...border,
                  minHeight: 52,
                  padding: 4,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 4,
                  background: isPicked
                    ? 'color-mix(in srgb, var(--mantine-primary-color-filled) 12%, transparent)'
                    : inMonth
                      ? undefined
                      : 'var(--hb-surface-2)',
                }}
              >
                {number}
                <span style={{ display: 'flex', gap: 3, flexWrap: 'wrap', justifyContent: 'center' }}>
                  {list.slice(0, 4).map((ev) => (
                    <span
                      key={ev.id}
                      style={{ width: 6, height: 6, borderRadius: 3, background: typeColor(ev), opacity: ev.cancelledAt ? 0.4 : 1 }}
                    />
                  ))}
                </span>
              </UnstyledButton>
            )
          }
          return (
            <div
              key={day}
              role="gridcell"
              style={{
                ...border,
                minHeight: 112,
                padding: 6,
                display: 'flex',
                flexDirection: 'column',
                gap: 3,
                minWidth: 0,
                background: isToday
                  ? 'color-mix(in srgb, var(--mantine-primary-color-filled) 6%, transparent)'
                  : inMonth
                    ? undefined
                    : 'var(--hb-surface-2)',
              }}
            >
              {number}
              {list.slice(0, maxChips).map((ev) => (
                <EventChip key={ev.id} ev={ev} />
              ))}
              {list.length > maxChips && (
                <Text size="xs" c="dimmed" pl={6}>
                  {t('events.month.more', '+{{count}} weitere', { count: list.length - maxChips })}
                </Text>
              )}
            </div>
          )
        })}
      </div>
      {phone && (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Text size="sm" fw={600}>
            {new Date(`${picked}T00:00:00`).toLocaleDateString(i18n.language, {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
            })}
          </Text>
          {pickedEvents.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t('events.month.none', 'Keine Anlässe an diesem Tag.')}
            </Text>
          ) : (
            pickedEvents.map((ev) => <EventChip key={ev.id} ev={ev} />)
          )}
        </div>
      )}
    </Paper>
  )
}
