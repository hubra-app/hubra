import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  MultiSelect,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { DateTimeField } from '@hubra/ui'
import { Modal as SharedModal } from '@/components/ui'
import { IconCalendarTime } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { formatDateTime } from '@/format'
import { tr } from '@/lang'
import {
  cancelMaintenanceWindow,
  createMaintenanceWindow,
  getMaintenanceWindows,
  type MaintenanceWindow,
} from '@/api/platform'
import { listTenants } from '@/api/tenants'

const failure = (err: unknown) => (err instanceof Error ? err.message : undefined)

const STATUS: Record<MaintenanceWindow['status'], [string, () => string]> = {
  planned: ['gray', () => tr('Geplant', 'Planned')],
  announced: ['acc', () => tr('Angekündigt', 'Announced')],
  running: ['orange', () => tr('Läuft', 'Running')],
  done: ['green', () => tr('Vorbei', 'Over')],
  cancelled: ['gray', () => tr('Abgesagt', 'Cancelled')],
}

const noticeLabel = (h: number) =>
  h === 0
    ? tr('Kein Hinweis', 'No notice')
    : h % 24 === 0
      ? tr(`${h / 24} ${h === 24 ? 'Tag' : 'Tage'} vorher`, `${h / 24} day${h === 24 ? '' : 's'} before`)
      : tr(`${h} Stunden vorher`, `${h} hours before`)

function clubsText(w: MaintenanceWindow) {
  if (!w.clubs) return tr('Alle Vereine', 'All clubs')
  return w.clubs.map((c) => c.name ?? `#${c.id}`).join(', ')
}

/** «Geplante Wartungen»: maintenance for every club or some clubs at a set
 * time, announced in the club app beforehand. */
export function MaintenanceWindowsCard() {
  const { notify, hasGlobalPermission } = useAdmin()
  const queryClient = useQueryClient()
  const canChange = hasGlobalPermission('platform.settings')
  const query = useQuery({ queryKey: ['maintenance-windows'], queryFn: getMaintenanceWindows })
  const [planning, setPlanning] = useState(false)
  const [showPast, setShowPast] = useState(false)
  const [busy, setBusy] = useState<number | null>(null)

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['maintenance-windows'] })
    queryClient.invalidateQueries({ queryKey: ['alerts-overview'] })
  }

  const cancel = async (w: MaintenanceWindow) => {
    setBusy(w.id)
    try {
      await cancelMaintenanceWindow(w.id)
      notify(
        'success',
        w.status === 'running'
          ? tr('Wartung beendet', 'Maintenance ended')
          : tr('Wartung abgesagt', 'Maintenance cancelled'),
      )
      refresh()
    } catch (err) {
      notify('error', tr('Nicht geändert', 'Not changed'), failure(err))
    } finally {
      setBusy(null)
    }
  }

  const rows = showPast ? (query.data?.past ?? []) : (query.data?.current ?? [])

  return (
    <Paper withBorder p="lg">
      <Group justify="space-between" mb={6} wrap="wrap">
        <Group gap={10}>
          <IconCalendarTime size={20} />
          <Title order={4}>{tr('Geplante Wartungen', 'Planned maintenance')}</Title>
        </Group>
        {canChange && (
          <Button variant="light" onClick={() => setPlanning(true)}>
            {tr('Wartung planen', 'Plan maintenance')}
          </Button>
        )}
      </Group>
      <Text size="sm" c="dimmed" mb={12}>
        {tr(
          'Für alle oder einzelne Vereine. Die Vereins-App zeigt vorher einen Hinweis mit Zeit und Text und während der Wartung die Wartungsseite. Gilt sie für alle Vereine, pausieren auch die Warnungen.',
          'For every club or some clubs. The club app shows a notice with the time and text beforehand, and the maintenance page while it runs. For every club, alerts pause too.',
        )}
      </Text>
      <SegmentedControl
        size="xs"
        mb={10}
        value={showPast ? 'past' : 'current'}
        onChange={(v) => setShowPast(v === 'past')}
        data={[
          { value: 'current', label: tr('Anstehend', 'Upcoming') },
          { value: 'past', label: tr('Vergangen', 'Past') },
        ]}
      />
      {rows.length === 0 ? (
        <Text size="sm" c="dimmed">
          {showPast
            ? tr('Noch keine vergangenen Wartungen.', 'No past maintenance yet.')
            : tr('Keine Wartung geplant.', 'No maintenance planned.')}
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={640}>
          <Table verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{tr('Zeit', 'When')}</Table.Th>
                <Table.Th>{tr('Vereine', 'Clubs')}</Table.Th>
                <Table.Th>{tr('Hinweis', 'Notice')}</Table.Th>
                <Table.Th>{tr('Status', 'Status')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((w) => (
                <Table.Tr key={w.id}>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>
                    <Text size="sm">{formatDateTime(w.starts_at)}</Text>
                    <Text size="xs" c="dimmed">
                      {tr('bis', 'to')} {formatDateTime(w.ends_at)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{clubsText(w)}</Text>
                    {w.message && (
                      <Text size="xs" c="dimmed" lineClamp={2}>
                        «{w.message}»
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>
                    <Text size="sm">{noticeLabel(w.notice_hours)}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={STATUS[w.status][0]} miw="max-content">
                      {STATUS[w.status][1]()}
                    </Badge>
                  </Table.Td>
                  <Table.Td ta="right">
                    {canChange && !showPast && (
                      <Button
                        size="xs"
                        variant="subtle"
                        color={w.status === 'running' ? 'orange' : 'gray'}
                        loading={busy === w.id}
                        onClick={() => cancel(w)}
                      >
                        {w.status === 'running' ? tr('Jetzt beenden', 'End now') : tr('Absagen', 'Cancel')}
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {planning && (
        <PlanModal
          noticeHours={query.data?.notice_hours ?? [0, 24, 48, 72, 168]}
          onClose={() => setPlanning(false)}
          onDone={() => {
            setPlanning(false)
            refresh()
          }}
        />
      )}
    </Paper>
  )
}

/** "2026-11-02T22:00" for a datetime-local input, in local time. */
function localInput(d: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function PlanModal({
  noticeHours,
  onClose,
  onDone,
}: {
  noticeHours: number[]
  onClose: () => void
  onDone: () => void
}) {
  const { notify } = useAdmin()
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  tomorrow.setHours(22, 0, 0, 0)
  const [start, setStart] = useState(localInput(tomorrow))
  const [end, setEnd] = useState(localInput(new Date(tomorrow.getTime() + 60 * 60_000)))
  const [message, setMessage] = useState('')
  const [scope, setScope] = useState<'all' | 'some'>('all')
  const [clubs, setClubs] = useState<string[]>([])
  const [notice, setNotice] = useState('24')
  const [saving, setSaving] = useState(false)
  const tenants = useQuery({
    queryKey: ['tenants-for-maintenance'],
    queryFn: () => listTenants({ per_page: 200 }),
    enabled: scope === 'some',
  })

  const startAt = new Date(start)
  const endAt = new Date(end)
  const invalid =
    Number.isNaN(startAt.getTime()) ||
    Number.isNaN(endAt.getTime()) ||
    endAt <= startAt ||
    (scope === 'some' && clubs.length === 0)

  const save = async () => {
    setSaving(true)
    try {
      await createMaintenanceWindow({
        starts_at: startAt.toISOString(),
        ends_at: endAt.toISOString(),
        message: message.trim(),
        tenant_ids: scope === 'all' ? null : clubs.map(Number),
        notice_hours: Number(notice),
      })
      notify('success', tr('Wartung geplant', 'Maintenance planned'))
      onDone()
    } catch (err) {
      notify('error', tr('Nicht geplant', 'Not planned'), failure(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <SharedModal
      open
      onClose={onClose}
      title={tr('Wartung planen', 'Plan maintenance')}
      wide
      onSubmit={(e) => {
        e?.preventDefault()
        // Enter submits too, so the button's rule applies here as well.
        if (invalid) return
        void save()
      }}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button color="orange" loading={saving} disabled={invalid} type="submit">
            {tr('Planen', 'Plan')}
          </Button>
        </>
      }
    >
      <Stack gap="md">
        <Group grow align="flex-start" wrap="wrap">
          <DateTimeField
            label={tr('Beginn', 'Start')}
            value={start}
            onChange={(v) => setStart(v)}
            miw={200}
          />
          <DateTimeField
            label={tr('Ende', 'End')}
            value={end}
            onChange={(v) => setEnd(v)}
            error={endAt <= startAt ? tr('Nach dem Beginn', 'After the start') : undefined}
            miw={200}
          />
        </Group>
        <Stack gap={6}>
          <Text size="sm" fw={500}>
            {tr('Vereine', 'Clubs')}
          </Text>
          <SegmentedControl
            value={scope}
            onChange={(v) => setScope(v as 'all' | 'some')}
            data={[
              { value: 'all', label: tr('Alle Vereine', 'All clubs') },
              { value: 'some', label: tr('Ausgewählte', 'Selected') },
            ]}
          />
          {scope === 'some' && (
            <MultiSelect
              aria-label={tr('Vereine', 'Clubs')}
              placeholder={tr('Vereine wählen', 'Pick clubs')}
              searchable
              data={(tenants.data?.tenants ?? []).map((t) => ({
                value: String(t.id),
                label: t.name,
              }))}
              value={clubs}
              onChange={setClubs}
            />
          )}
        </Stack>
        <Select
          label={tr('Hinweis in der Vereins-App', 'Notice in the club app')}
          value={notice}
          onChange={(v) => setNotice(v ?? '24')}
          allowDeselect={false}
          data={noticeHours.map((h) => ({ value: String(h), label: noticeLabel(h) }))}
        />
        <TextInput
          label={tr('Text für Mitglieder (optional)', 'Text for members (optional)')}
          placeholder={tr(
            'In dieser Zeit ist die App nicht erreichbar.',
            'The app is not available during this time.',
          )}
          value={message}
          onChange={(e) => setMessage(e.currentTarget.value)}
          maxLength={500}
        />
      </Stack>
    </SharedModal>
  )
}
