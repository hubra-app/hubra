import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Code,
  Group,
  Paper,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { IconPlayerPlay, IconRefresh, IconTrash } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { StatGrid, StatTile } from '@/components/ui'
import { formatDateTime } from '@/format'
import { tr, useLang } from '@/lang'
import { dismissJob, getJobs, retryJob, type FailedJob } from '@/api/platform'

const MONO = "'JetBrains Mono', monospace"

/** hubra.core.tasks.email_tasks.send_email_task → email_tasks.send_email_task */
function shortTask(name: string) {
  return name.split('.').slice(-2).join('.')
}

function failureText(err: unknown) {
  return err instanceof Error ? err.message : String(err)
}

function FailedRow({
  job,
  canChange,
  onChanged,
}: {
  job: FailedJob
  canChange: boolean
  onChanged: () => void
}) {
  const { notify } = useAdmin()
  const { tr } = useLang()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState<'retry' | 'dismiss' | null>(null)

  const run = async (what: 'retry' | 'dismiss') => {
    setBusy(what)
    try {
      if (what === 'retry') {
        await retryJob(job.id)
        notify('success', tr('Job erneut gestartet', 'Job started again'), shortTask(job.task))
      } else {
        await dismissJob(job.id)
      }
      onChanged()
    } catch (err) {
      notify('error', tr('Hat nicht geklappt', 'That did not work'), failureText(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Table.Tr style={{ verticalAlign: 'top', cursor: 'pointer' }} onClick={() => setOpen(!open)}>
      <Table.Td fz="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
        {formatDateTime(job.time)}
      </Table.Td>
      <Table.Td>
        <Text fz="sm" ff={MONO} style={{ wordBreak: 'break-all' }}>
          {shortTask(job.task)}
        </Text>
        <Text fz="sm" c="red" style={{ wordBreak: 'break-word' }}>
          {job.error || tr('Unbekannter Fehler', 'Unknown error')}
        </Text>
        {job.retried_at && (
          <Badge size="sm" variant="light" color="green" mt={4}>
            {tr(
              `Erneut gestartet am ${formatDateTime(job.retried_at)} von ${job.retried_by}`,
              `Started again on ${formatDateTime(job.retried_at)} by ${job.retried_by}`,
            )}
          </Badge>
        )}
        {open && (
          <Stack gap={6} mt={8}>
            {job.args !== null && (
              <Text fz="xs" c="dimmed" style={{ wordBreak: 'break-word' }}>
                <Code>args</Code> {JSON.stringify(job.args)} <Code>kwargs</Code>{' '}
                {JSON.stringify(job.kwargs)}
              </Text>
            )}
            {job.traceback && (
              <Code block fz="xs" style={{ whiteSpace: 'pre-wrap', maxHeight: 260, overflow: 'auto' }}>
                {job.traceback}
              </Code>
            )}
            <Text fz="xs" c="dimmed">
              Task-ID {job.task_id}
              {job.retries ? ` · ${tr(`${job.retries}× wiederholt`, `retried ${job.retries}×`)}` : ''}
            </Text>
          </Stack>
        )}
      </Table.Td>
      <Table.Td fz="sm">{job.club ?? '–'}</Table.Td>
      <Table.Td onClick={(e) => e.stopPropagation()}>
        {canChange && (
          <Group gap={6} wrap="nowrap" justify="flex-end">
            <Tooltip
              label={
                job.can_retry
                  ? tr('Mit denselben Angaben noch einmal ausführen', 'Run again with the same arguments')
                  : tr('Die Angaben waren zu gross, um sie aufzubewahren', 'The arguments were too large to keep')
              }
              withArrow
            >
              <Button
                size="xs"
                variant="light"
                leftSection={<IconPlayerPlay size={14} />}
                disabled={!job.can_retry}
                loading={busy === 'retry'}
                onClick={() => run('retry')}
              >
                {tr('Erneut ausführen', 'Retry')}
              </Button>
            </Tooltip>
            <Tooltip label={tr('Aus der Liste entfernen', 'Remove from the list')} withArrow>
              <Button
                size="xs"
                variant="subtle"
                color="gray"
                aria-label={tr('Entfernen', 'Remove')}
                loading={busy === 'dismiss'}
                onClick={() => run('dismiss')}
              >
                <IconTrash size={14} />
              </Button>
            </Tooltip>
          </Group>
        )}
      </Table.Td>
    </Table.Tr>
  )
}

/** Queued, running, failed and retried background jobs (Celery), with
 * one-click retry of failed jobs (services/job_monitor.py). */
export function JobsPanel() {
  const { hasGlobalPermission } = useAdmin()
  const canChange = hasGlobalPermission('platform.settings')
  const queryClient = useQueryClient()
  const [hours, setHours] = useState('24')
  const query = useQuery({
    queryKey: ['platform-jobs', hours],
    queryFn: () => getJobs(Number(hours)),
    refetchInterval: 15_000,
  })
  const data = query.data
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['platform-jobs'] })
  const open = data?.failed.filter((f) => !f.retried_at).length ?? 0

  return (
    <Stack gap={20}>
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Text c="dimmed" size="sm" maw={720}>
          {tr(
            `Was im Hintergrund läuft: Mails, Rechnungen, Backups, Abgleiche. Fehlgeschlagene Jobs bleiben ${data?.failed_keep_days ?? 7} Tage hier und lassen sich mit denselben Angaben noch einmal ausführen.`,
            `What runs in the background: mail, invoices, backups, syncs. Failed jobs stay here for ${data?.failed_keep_days ?? 7} days and can be run again with the same arguments.`,
          )}
        </Text>
        <Group gap="xs">
          <SegmentedControl
            size="xs"
            value={hours}
            onChange={setHours}
            data={[
              { value: '1', label: tr('1 Std.', '1 h') },
              { value: '6', label: tr('6 Std.', '6 h') },
              { value: '24', label: tr('24 Std.', '24 h') },
              { value: '48', label: tr('48 Std.', '48 h') },
            ]}
          />
          <Button
            variant="subtle"
            size="xs"
            leftSection={<IconRefresh size={14} />}
            onClick={() => query.refetch()}
            loading={query.isFetching}
          >
            {tr('Aktualisieren', 'Refresh')}
          </Button>
        </Group>
      </Group>

      {query.isError && <Text c="red">{failureText(query.error)}</Text>}

      <StatGrid columns={4} style={{ marginBottom: 0 }}>
        <StatTile
          label={tr('In der Warteschlange', 'Queued')}
          value={data?.queued == null ? '–' : String(data.queued)}
          sub={
            data?.reserved
              ? tr(`${data.reserved} bei Workern reserviert`, `${data.reserved} reserved by workers`)
              : data && data.queued == null
                ? tr('Broker nicht erreichbar', 'Broker not reachable')
                : undefined
          }
        />
        <StatTile label={tr('Laufen gerade', 'Running')} value={String(data?.running.length ?? '–')} />
        <StatTile
          label={tr('Fehlgeschlagen', 'Failed')}
          value={String(data?.totals.failed ?? '–')}
          sub={tr(`letzte ${hours} Std.`, `last ${hours} h`)}
        />
        <StatTile
          label={tr('Wiederholt', 'Retried')}
          value={String(data?.totals.retried ?? '–')}
          sub={tr(
            `${data?.totals.done ?? 0} erledigt von ${data?.totals.sent ?? 0} gesendet`,
            `${data?.totals.done ?? 0} done of ${data?.totals.sent ?? 0} sent`,
          )}
        />
      </StatGrid>

      <Paper withBorder radius="lg" p="md">
        <Group justify="space-between" mb="sm">
          <Title order={4}>
            {tr('Fehlgeschlagene Jobs', 'Failed jobs')}
            {open > 0 && (
              <Badge ml={8} color="red" variant="light">
                {open}
              </Badge>
            )}
          </Title>
        </Group>
        {data && data.failed.length === 0 ? (
          <Text c="dimmed" size="sm">
            {tr('Keine fehlgeschlagenen Jobs.', 'No failed jobs.')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={640}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={150}>{tr('Zeit', 'Time')}</Table.Th>
                  <Table.Th>{tr('Job und Fehler', 'Job and error')}</Table.Th>
                  <Table.Th w={150}>{tr('Verein', 'Club')}</Table.Th>
                  <Table.Th w={200} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data?.failed.map((job) => (
                  <FailedRow key={job.id} job={job} canChange={canChange} onChanged={refresh} />
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Paper>

      {data && data.running.length > 0 && (
        <Paper withBorder radius="lg" p="md">
          <Title order={4} mb="sm">
            {tr('Laufen gerade', 'Running now')}
          </Title>
          <Table>
            <Table.Tbody>
              {data.running.map((r) => (
                <Table.Tr key={r.id}>
                  <Table.Td ff={MONO} fz="sm">
                    {shortTask(r.task)}
                  </Table.Td>
                  <Table.Td fz="sm">{r.club ?? '–'}</Table.Td>
                  <Table.Td fz="sm" c="dimmed" ta="right">
                    {tr(`seit ${r.seconds} s`, `for ${r.seconds} s`)}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}

      <Paper withBorder radius="lg" p="md">
        <Title order={4} mb="sm">
          {tr('Jobs nach Art', 'Jobs by type')}
        </Title>
        {data && data.tasks.length === 0 ? (
          <Text c="dimmed" size="sm">
            {tr('In dieser Zeit lief nichts.', 'Nothing ran in this period.')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={600}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{tr('Job', 'Job')}</Table.Th>
                  <Table.Th ta="right">{tr('Gesendet', 'Sent')}</Table.Th>
                  <Table.Th ta="right">{tr('Erledigt', 'Done')}</Table.Th>
                  <Table.Th ta="right">{tr('Fehler', 'Failed')}</Table.Th>
                  <Table.Th ta="right">{tr('Wiederholt', 'Retried')}</Table.Th>
                  <Table.Th ta="right">{tr('Ø Dauer', 'Avg time')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data?.tasks.map((t) => (
                  <Table.Tr key={t.task}>
                    <Table.Td ff={MONO} fz="sm" title={t.task}>
                      {shortTask(t.task)}
                    </Table.Td>
                    <Table.Td className="num" ta="right">
                      {t.sent}
                    </Table.Td>
                    <Table.Td className="num" ta="right">
                      {t.done}
                    </Table.Td>
                    <Table.Td className="num" ta="right" c={t.failed ? 'red' : undefined}>
                      {t.failed}
                    </Table.Td>
                    <Table.Td className="num" ta="right" c={t.retried ? 'orange' : undefined}>
                      {t.retried}
                    </Table.Td>
                    <Table.Td className="num" ta="right" c="dimmed">
                      {t.avg_ms == null ? '–' : `${t.avg_ms.toLocaleString('de-CH')} ms`}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Paper>
    </Stack>
  )
}
