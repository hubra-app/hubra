import { useState } from 'react'
import { Anchor, Badge, Group, Paper, Progress, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconCalendarCheck } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { getMyAttendance, type AttendanceStatus } from '@/api/events'
import { formatDate } from '@/format'
import { qk } from '@/data/keys'

const STATUS_COLOR: Record<AttendanceStatus, string> = {
  present: 'green',
  excused: 'yellow',
  absent: 'gray',
}

/** How many dates the list shows before "Alle anzeigen". */
const SHORT = 8

/**
 * The member's own attendance this year: the trainings and events they were
 * expected at (their groups' dates and their sign-ups), what the trainer
 * recorded, and the rate. Shown once they were expected somewhere.
 */
export function MyAttendanceCard() {
  const { t } = useT()
  const [all, setAll] = useState(false)
  const { data } = useQuery({
    queryKey: qk.myAttendance,
    queryFn: () => getMyAttendance(),
    staleTime: 60_000,
  })
  if (!data || data.expected === 0) return null

  const label = (s: AttendanceStatus) =>
    s === 'present'
      ? t('events.attendance.present', 'Da')
      : s === 'excused'
        ? t('events.attendance.excused', 'Entschuldigt')
        : t('events.attendance.absent', 'Fehlt')
  // Newest first: the last training is what people look for.
  const dates = [...data.events].reverse()
  const shown = all ? dates : dates.slice(0, SHORT)
  const rate = data.rate == null ? null : Math.round(data.rate * 100)

  return (
    <Paper withBorder>
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <IconCalendarCheck size={16} style={{ color: 'var(--hb-text-2)' }} />
        <Text fw={700} fz="md">
          {t('account.myAttendance', 'Meine Anwesenheit')}
        </Text>
        <Text fz="sm" c="dimmed" ml="auto">
          {t('account.myAttendanceYear', 'Seit {{date}}', { date: formatDate(data.from) })}
        </Text>
      </Group>
      <div style={{ padding: 'var(--mantine-spacing-md)' }}>
        <Group justify="space-between" mb={6} wrap="wrap">
          <Text fz="sm">
            {t('events.attendance.count', '{{present}} von {{count}} anwesend', {
              present: data.present,
              count: data.expected,
            })}
            {data.excused > 0 &&
              ` · ${data.excused} ${t('events.attendance.excused', 'Entschuldigt').toLowerCase()}`}
          </Text>
          {rate != null && (
            <Text fz="sm" fw={700} className="num">
              {rate} %
            </Text>
          )}
        </Group>
        <Progress
          value={rate ?? 0}
          color="green"
          size="sm"
          aria-label={t('events.attendance.rate', 'Quote')}
        />
      </div>
      {shown.map((d) => (
        <Group
          key={`${d.eventId}`}
          justify="space-between"
          wrap="nowrap"
          px="md"
          py="xs"
          style={{ borderTop: '1px solid var(--hb-border)' }}
        >
          <div style={{ minWidth: 0 }}>
            <Text fz="sm" fw={600} truncate>
              {d.title}
            </Text>
            <Text fz="xs" c="dimmed" className="num">
              {formatDate(d.date)}
              {d.time ? ` · ${d.time}` : ''}
            </Text>
          </div>
          <Badge variant="light" color={STATUS_COLOR[d.status]} style={{ flexShrink: 0 }}>
            {label(d.status)}
          </Badge>
        </Group>
      ))}
      {dates.length > SHORT && (
        <Group px="md" py="sm" style={{ borderTop: '1px solid var(--hb-border)' }}>
          <Anchor component="button" type="button" fz="sm" onClick={() => setAll(!all)}>
            {all
              ? t('account.showLess', 'Weniger anzeigen')
              : t('account.showAllDates', 'Alle {{count}} Termine anzeigen', {
                  count: dates.length,
                })}
          </Anchor>
        </Group>
      )}
    </Paper>
  )
}
