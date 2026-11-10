import { useMemo, useState } from 'react'
import { ActionIcon, Badge, Button, Chip, Group, Paper, SegmentedControl, Stack, Text, UnstyledButton } from '@mantine/core'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { qk } from '@/data/keys'
import { getCalendar, type CalendarItem } from '@/api/calendar'
import { ErrorBanner, PageHead } from '@/components/ui'
import { formatMonthYear, formatWeekdayShort, formatDate } from '@/format'
import { useT } from '@/locales/i18n'
import { isoDay, itemsOn, monthWeeks, timeOf, viewRange, weekDays } from './calendarGrid'

type View = 'month' | 'week'
// How many items a month cell lists before "+n".
const PER_CELL = 3
const KIND_COLORS: Record<string, string> = { event: 'violet', booking: 'teal', fixture: 'orange', duty: 'gray' }

function shift(d: Date, view: View, n: number): Date {
  return view === 'month'
    ? new Date(d.getFullYear(), d.getMonth() + n, 1)
    : new Date(d.getFullYear(), d.getMonth(), d.getDate() + 7 * n)
}

/** The club calendar: events, bookings, fixtures and duties of every module
 * the member may see, by month or week, filtered by kind. */
export function CalendarScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const [view, setView] = useState<View>('month')
  const [anchor, setAnchor] = useState(() => new Date())
  const [hidden, setHidden] = useState<string[]>([])

  const weeks = useMemo(() => (view === 'month' ? monthWeeks(anchor) : [weekDays(anchor)]), [view, anchor])
  const range = viewRange(weeks.flat())
  const { data, error } = useQuery({
    queryKey: qk.calendar(range.start, range.end),
    queryFn: ({ signal }) => getCalendar(range.start, range.end, signal),
  })
  const items = data?.items ?? []
  const kinds = [...new Set(items.map((i) => i.kind))].sort()
  const shown = items.filter((i) => !hidden.includes(i.kind))
  const today = isoDay(new Date())
  const kindLabel = (kind: string) => t(`calendar.kind.${kind}`, kind)

  const open = (item: CalendarItem) => {
    if (item.path) navigate(item.path)
  }
  const chip = (item: CalendarItem, full: boolean) => (
    <UnstyledButton
      key={item.id}
      onClick={() => open(item)}
      disabled={!item.path}
      title={[timeOf(item), item.title, item.location].filter(Boolean).join(' · ')}
      data-testid="calendar-item"
      style={{ display: 'block', width: '100%' }}
    >
      <Badge
        variant={item.all_day ? 'filled' : 'light'}
        color={item.color ?? KIND_COLORS[item.kind] ?? 'blue'}
        radius="sm"
        fullWidth
        styles={{ label: { textTransform: 'none', fontWeight: 500, textAlign: 'left', width: '100%' } }}
        td={item.cancelled ? 'line-through' : undefined}
      >
        {timeOf(item) && `${timeOf(item)} `}
        {item.title}
        {full && item.location ? ` · ${item.location}` : ''}
      </Badge>
    </UnstyledButton>
  )

  const title =
    view === 'month'
      ? formatMonthYear(anchor)
      : `${formatDate(weeks[0][0])} – ${formatDate(weeks[0][6])}`

  return (
    <div>
      <PageHead
        title={t('shell.nav.calendar', 'Kalender')}
        actions={
          <SegmentedControl
            value={view}
            onChange={(v) => setView(v as View)}
            data={[
              { value: 'month', label: t('calendar.month', 'Monat') },
              { value: 'week', label: t('calendar.week', 'Woche') },
            ]}
          />
        }
      />
      {error && <ErrorBanner message={error.message} />}
      {data && data.failed.length > 0 && (
        <Text size="sm" c="dimmed" mb="xs">
          {t('calendar.failed', 'Nicht alles geladen: {{modules}} antwortet gerade nicht.', {
            modules: data.failed.join(', '),
          })}
        </Text>
      )}
      <Group justify="space-between" mb="sm" wrap="wrap">
        <Group gap="xs">
          <ActionIcon variant="default" onClick={() => setAnchor(shift(anchor, view, -1))} aria-label={t('calendar.previous', 'Zurück')}>
            <IconChevronLeft size={18} />
          </ActionIcon>
          <Button variant="default" size="xs" onClick={() => setAnchor(new Date())}>
            {t('calendar.today', 'Heute')}
          </Button>
          <ActionIcon variant="default" onClick={() => setAnchor(shift(anchor, view, 1))} aria-label={t('calendar.next', 'Weiter')}>
            <IconChevronRight size={18} />
          </ActionIcon>
          <Text fw={600} ml="xs" data-testid="calendar-title">
            {title}
          </Text>
        </Group>
        {kinds.length > 1 && (
          <Chip.Group
            multiple
            value={kinds.filter((k) => !hidden.includes(k))}
            onChange={(on) => setHidden(kinds.filter((k) => !on.includes(k)))}
          >
            <Group gap="xs">
              {kinds.map((k) => (
                <Chip key={k} value={k} size="xs" color={KIND_COLORS[k] ?? 'blue'}>
                  {kindLabel(k)}
                </Chip>
              ))}
            </Group>
          </Chip.Group>
        )}
      </Group>

      <div style={{ overflowX: 'auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(110px, 1fr))', gap: 4, minWidth: 770 }}>
          {weeks[0].map((d) => (
            <Text key={`h${d.getDay()}`} size="xs" c="dimmed" ta="center" fw={600}>
              {formatWeekdayShort(d)}
            </Text>
          ))}
          {weeks.flat().map((d) => {
            const day = isoDay(d)
            const list = itemsOn(shown, day)
            const outside = view === 'month' && d.getMonth() !== anchor.getMonth()
            const limit = view === 'month' ? PER_CELL : list.length
            return (
              <Paper
                key={day}
                withBorder
                p={4}
                radius="sm"
                style={{
                  minHeight: view === 'month' ? 110 : 320,
                  opacity: outside ? 0.5 : 1,
                  borderColor: day === today ? 'var(--mantine-primary-color-filled)' : undefined,
                }}
                data-testid={`calendar-day-${day}`}
              >
                <Text size="xs" fw={day === today ? 700 : 500} c={day === today ? 'var(--mantine-primary-color-filled)' : undefined}>
                  {d.getDate()}
                </Text>
                <Stack gap={2} mt={2}>
                  {list.slice(0, limit).map((item) => chip(item, view === 'week'))}
                  {list.length > limit && (
                    <UnstyledButton
                      onClick={() => {
                        setAnchor(d)
                        setView('week')
                      }}
                    >
                      <Text size="xs" c="dimmed">
                        {t('calendar.more', '+{{count}} weitere', { count: list.length - limit })}
                      </Text>
                    </UnstyledButton>
                  )}
                </Stack>
              </Paper>
            )
          })}
        </div>
      </div>
      {data && items.length === 0 && (
        <Text size="sm" c="dimmed" mt="sm">
          {t('calendar.empty', 'In diesem Zeitraum steht nichts im Kalender.')}
        </Text>
      )}
    </div>
  )
}
