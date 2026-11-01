import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Button, Group, Select, Text, TextInput } from '@mantine/core'
import { IconArrowLeft, IconDownload } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { Card, EmptyState, Field, PageHead } from '@/components/ui'
import { listGroups } from '@/api/groups'
import {
  downloadAttendanceCSV,
  getAttendanceOverview,
  type AttendanceStatus,
} from '@/api/events'

const PERM = 'events.events.add_attendee'

const CELL: Record<AttendanceStatus, { label: string; color: string }> = {
  present: { label: '✓', color: 'var(--mantine-color-green-text)' },
  excused: { label: 'E', color: 'var(--mantine-color-yellow-text)' },
  absent: { label: '·', color: 'var(--hb-text-3)' },
}

/** Attendance per member over a period, per group, with a CSV for J+S. */
export function AttendanceScreen() {
  const { t, i18n } = useT()
  const { notify } = useToast()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const clubWide = hasPermission(PERM)
  const today = new Date().toISOString().slice(0, 10)
  const [from, setFrom] = useState(`${today.slice(0, 4)}-01-01`)
  const [to, setTo] = useState(today)
  const { data: allGroups = [] } = useQuery({ queryKey: qk.groups.all, queryFn: listGroups })
  // A trainer of one group sees that group's events only.
  const groups = allGroups.filter((g) => hasPermission(PERM, g.id))
  const [groupId, setGroupId] = useState<string>('')
  const group = clubWide ? groupId : groupId || groups[0]?.id || ''
  const filter = { from, to, groupId: group || undefined }
  const valid = !!from && !!to && from <= to && (clubWide || !!group)
  const { data, isLoading, error } = useQuery({
    queryKey: qk.attendanceOverview(from, to, group),
    queryFn: () => getAttendanceOverview(filter),
    enabled: valid,
  })

  const day = (d: string) =>
    new Date(`${d}T00:00:00Z`).toLocaleDateString(i18n.language, {
      day: 'numeric',
      month: 'numeric',
      timeZone: 'UTC',
    })
  const pct = (rate: number | null) => (rate == null ? '–' : `${Math.round(rate * 100)} %`)

  const download = async () => {
    try {
      await downloadAttendanceCSV(filter)
    } catch (err: unknown) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    }
  }

  const cellStyle: React.CSSProperties = {
    padding: '6px 8px',
    borderBottom: '1px solid var(--hb-border)',
    whiteSpace: 'nowrap',
    fontSize: 'var(--mantine-font-size-sm)',
  }
  const sticky: React.CSSProperties = {
    ...cellStyle,
    position: 'sticky',
    left: 0,
    background: 'var(--hb-surface)',
    zIndex: 1,
  }

  return (
    <div>
      <PageHead title={t('events.attendance.overview', 'Anwesenheit')} />
      <Group justify="space-between" mb={16} gap="xs" className="page-actions">
        <Button variant="subtle" onClick={() => navigate('/app/operations/events')}>
          <IconArrowLeft size={16} />
          {t('shell.nav.events')}
        </Button>
        <Button variant="default" onClick={download} disabled={!valid}>
          <IconDownload size={16} />
          {t('events.attendance.csv', 'CSV für J+S')}
        </Button>
      </Group>
      <Group align="flex-end" gap={12} mb={16} wrap="wrap">
        <Field label={t('events.attendance.from', 'Von')}>
          <TextInput type="date" value={from} onChange={(e) => setFrom(e.currentTarget.value)} />
        </Field>
        <Field label={t('events.attendance.to', 'Bis')}>
          <TextInput type="date" value={to} onChange={(e) => setTo(e.currentTarget.value)} />
        </Field>
        <Field label={t('events.group', 'Gruppe')}>
          <Select
            data={[
              ...(clubWide ? [{ value: '', label: t('events.attendance.allEvents', 'Alle Anlässe') }] : []),
              ...groups.map((g) => ({ value: g.id, label: g.name })),
            ]}
            value={group}
            onChange={(v) => setGroupId(v ?? '')}
            allowDeselect={false}
            searchable
            style={{ minWidth: 220 }}
          />
        </Field>
      </Group>

      {error ? (
        <Text c="red" size="sm">
          {error instanceof Error ? error.message : t('common.error')}
        </Text>
      ) : isLoading || !data ? null : data.events.length === 0 ? (
        <EmptyState
          title={t('events.attendance.noEvents', 'Keine Anlässe in diesem Zeitraum')}
          description={t(
            'events.attendance.noEventsHint',
            'Gib Trainings eine Gruppe, dann zählen ihre Mitglieder hier.',
          )}
        />
      ) : (
        <Card style={{ padding: 16 }}>
          <Group gap={24} mb={12}>
            <Text size="sm">
              {t('events.attendance.events', '{{count}} Anlässe', { count: data.events.length })}
            </Text>
            <Text size="sm">
              {t('events.attendance.average', 'Ø Anwesenheit {{rate}}', {
                rate: pct(data.total.rate),
              })}
            </Text>
          </Group>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ ...sticky, textAlign: 'left' }}>{t('common.name', 'Name')}</th>
                  <th style={{ ...cellStyle, textAlign: 'right' }}>
                    {t('events.attendance.rate', 'Quote')}
                  </th>
                  <th style={{ ...cellStyle, textAlign: 'right' }}>
                    {t('events.attendance.presentShort', 'Da')}
                  </th>
                  <th style={{ ...cellStyle, textAlign: 'right' }}>
                    {t('events.attendance.excusedShort', 'Ent.')}
                  </th>
                  {data.events.map((e) => (
                    <th
                      key={e.id}
                      title={`${e.title}${e.time ? ` · ${e.time}` : ''}`}
                      style={{
                        ...cellStyle,
                        textAlign: 'center',
                        fontWeight: 500,
                        color: e.recorded ? undefined : 'var(--hb-text-3)',
                      }}
                    >
                      {day(e.date)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.members.map((m) => (
                  <tr key={m.memberId}>
                    <td style={sticky}>{m.name}</td>
                    <td className="num" style={{ ...cellStyle, textAlign: 'right', fontWeight: 600 }}>
                      {pct(m.rate)}
                    </td>
                    <td className="num" style={{ ...cellStyle, textAlign: 'right' }}>
                      {m.present}/{m.expected}
                    </td>
                    <td className="num" style={{ ...cellStyle, textAlign: 'right' }}>
                      {m.excused}
                    </td>
                    {data.events.map((e) => {
                      const s = m.statuses[String(e.id)]
                      return (
                        <td
                          key={e.id}
                          style={{
                            ...cellStyle,
                            textAlign: 'center',
                            color: s ? CELL[s].color : undefined,
                            fontWeight: 600,
                          }}
                        >
                          {s ? CELL[s].label : ''}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Text size="xs" c="dimmed" mt={8}>
            {t(
              'events.attendance.legend',
              '✓ anwesend · E entschuldigt · · gefehlt oder nicht erfasst · leer: nicht erwartet',
            )}
          </Text>
        </Card>
      )}
    </div>
  )
}
