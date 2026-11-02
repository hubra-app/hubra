import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
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
} from '@mantine/core'
import { IconRefresh } from '@tabler/icons-react'
import { StatGrid, StatTile } from '@/components/ui'
import { tr } from '@/lang'
import { getPerformance, type PerfRoute } from '@/api/platform'

const ms = (v: number | null | undefined) => (v == null ? '–' : `${v.toLocaleString('de-CH')} ms`)

type Sort = 'total' | 'p95' | 'requests' | 'errors'

const SORTS: Record<Sort, (r: PerfRoute) => number> = {
  total: (r) => r.totalMs,
  p95: (r) => r.p95 ?? 0,
  requests: (r) => r.requests,
  errors: (r) => r.status['5xx'] ?? 0,
}

function StatusBadges({ status }: { status: PerfRoute['status'] }) {
  const color = { '2xx': 'green', '3xx': 'blue', '4xx': 'orange', '5xx': 'red' } as const
  return (
    <Group gap={4} wrap="nowrap">
      {(['2xx', '3xx', '4xx', '5xx'] as const)
        .filter((c) => status[c])
        .map((c) => (
          <Badge key={c} size="xs" variant="light" color={color[c]}>
            {c} {status[c]}
          </Badge>
        ))}
    </Group>
  )
}

/** How fast the API answers, per route, and which database queries are slow.
 * Only route patterns and query shapes are kept, never paths, values or who
 * asked (services/perf_monitor.py). */
export function PerformancePanel() {
  const [hours, setHours] = useState('24')
  const [sort, setSort] = useState<Sort>('total')
  const query = useQuery({
    queryKey: ['alerts-performance', hours],
    queryFn: () => getPerformance(Number(hours)),
    refetchInterval: 60_000,
  })
  const data = query.data
  const t = data?.total
  const last = data?.lastHour
  const p95Limit = data?.thresholds.p95_warning_ms ?? 0
  const routes = [...(data?.routes ?? [])].sort((a, b) => SORTS[sort](b) - SORTS[sort](a)).slice(0, 25)
  const errors5 = t?.status['5xx'] ?? 0

  return (
    <Stack gap={16}>
      <Group justify="space-between" wrap="wrap">
        <Text c="dimmed" size="sm" maw={720}>
          {tr(
            'Antwortzeiten der API pro Route und langsame Datenbankabfragen. Gespeichert werden nur Routenmuster und die Form der Abfragen, keine Pfade, Werte oder Personen.',
            'API response times per route and slow database queries. Only route patterns and query shapes are kept, no paths, values or people.',
          )}
        </Text>
        <Group gap={8}>
          <SegmentedControl
            size="xs"
            value={hours}
            onChange={setHours}
            data={[
              { value: '2', label: tr('Seit letzter Stunde', 'Since last hour') },
              { value: '24', label: tr('24 Stunden', '24 hours') },
            ]}
          />
          <Button
            variant="default"
            leftSection={<IconRefresh size={16} />}
            onClick={() => query.refetch()}
            loading={query.isFetching}
          >
            {tr('Aktualisieren', 'Refresh')}
          </Button>
        </Group>
      </Group>
      {query.isError && <Text c="red">{query.error instanceof Error ? query.error.message : ''}</Text>}
      {data?.source === 'memory' && (
        <Text size="sm" c="orange">
          {tr(
            'Redis ist nicht erreichbar: Die Zahlen stammen nur aus diesem Prozess und sind unvollständig.',
            'Redis is unreachable: the numbers come from this process only and are incomplete.',
          )}
        </Text>
      )}

      {data && t && last && (
        <StatGrid columns={4} style={{ marginBottom: 0 }}>
          <StatTile
            label={tr('p95 letzte Stunde', 'p95 last hour')}
            value={ms(last.p95)}
            sub={tr(`p50 ${ms(last.p50)} · ${last.requests} Anfragen`, `p50 ${ms(last.p50)} · ${last.requests} requests`)}
            accent={p95Limit && (last.p95 ?? 0) > p95Limit ? '#c2870f' : undefined}
          />
          <StatTile
            label={tr(`p95 (${data.hours} h)`, `p95 (${data.hours} h)`)}
            value={ms(t.p95)}
            sub={tr(`p50 ${ms(t.p50)} · Mittel ${ms(t.mean)}`, `p50 ${ms(t.p50)} · mean ${ms(t.mean)}`)}
          />
          <StatTile
            label={tr(`Anfragen (${data.hours} h)`, `Requests (${data.hours} h)`)}
            value={t.requests.toLocaleString('de-CH')}
            sub={tr(
              `${t.slow} langsamer als ${ms(data.thresholds.slow_request_ms)}`,
              `${t.slow} slower than ${ms(data.thresholds.slow_request_ms)}`,
            )}
          />
          <StatTile
            label={tr(`Serverfehler (${data.hours} h)`, `Server errors (${data.hours} h)`)}
            value={errors5}
            sub={tr(
              `${t.status['4xx'] ?? 0} Client-Fehler (4xx)`,
              `${t.status['4xx'] ?? 0} client errors (4xx)`,
            )}
            accent={errors5 ? '#c0392b' : undefined}
          />
        </StatGrid>
      )}

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Group justify="space-between" mb={12} wrap="wrap">
          <Title order={4}>{tr('Routen', 'Routes')}</Title>
          <SegmentedControl
            size="xs"
            value={sort}
            onChange={(v) => setSort(v as Sort)}
            data={[
              { value: 'total', label: tr('Gesamtzeit', 'Total time') },
              { value: 'p95', label: 'p95' },
              { value: 'requests', label: tr('Anfragen', 'Requests') },
              { value: 'errors', label: '5xx' },
            ]}
          />
        </Group>
        {data && routes.length === 0 && (
          <Text size="sm" c="dimmed">
            {tr('Noch keine Anfragen in diesem Zeitraum.', 'No requests in this period yet.')}
          </Text>
        )}
        {routes.length > 0 && (
          <Table.ScrollContainer minWidth={820}>
            <Table highlightOnHover verticalSpacing={6} fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{tr('Route', 'Route')}</Table.Th>
                  <Table.Th ta="right">{tr('Anfragen', 'Requests')}</Table.Th>
                  <Table.Th ta="right">p50</Table.Th>
                  <Table.Th ta="right">p95</Table.Th>
                  <Table.Th ta="right">{tr('Datenbank', 'Database')}</Table.Th>
                  <Table.Th ta="right">{tr('Langsam', 'Slow')}</Table.Th>
                  <Table.Th>Status</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {routes.map((r) => (
                  <Table.Tr key={`${r.method} ${r.route}`}>
                    <Table.Td style={{ wordBreak: 'break-all' }}>
                      <Text span size="xs" fw={700} c="dimmed" mr={6}>
                        {r.method}
                      </Text>
                      <Code>{r.route}</Code>
                    </Table.Td>
                    <Table.Td ta="right">{r.requests.toLocaleString('de-CH')}</Table.Td>
                    <Table.Td ta="right">{ms(r.p50)}</Table.Td>
                    <Table.Td
                      ta="right"
                      c={p95Limit && (r.p95 ?? 0) > p95Limit ? 'orange.8' : undefined}
                      fw={p95Limit && (r.p95 ?? 0) > p95Limit ? 600 : undefined}
                    >
                      {ms(r.p95)}
                    </Table.Td>
                    <Table.Td ta="right">
                      {ms(r.dbMean)}
                      <Text span size="xs" c="dimmed">
                        {' '}
                        · {r.queriesMean ?? 0} {tr('Abfr.', 'q.')}
                      </Text>
                    </Table.Td>
                    <Table.Td ta="right">{r.slow || ''}</Table.Td>
                    <Table.Td>
                      <StatusBadges status={r.status} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        {data && data.routeCount > routes.length && (
          <Text size="xs" c="dimmed" mt={8}>
            {tr(
              `Die ${routes.length} obersten von ${data.routeCount} Routen. Datenbank: mittlere Zeit und Abfragen pro Anfrage.`,
              `Top ${routes.length} of ${data.routeCount} routes. Database: mean time and queries per request.`,
            )}
          </Text>
        )}
      </Paper>

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Group justify="space-between" mb={4} wrap="wrap">
          <Title order={4}>{tr('Langsame Datenbankabfragen', 'Slow database queries')}</Title>
        </Group>
        <Text size="xs" c="dimmed" mb={12}>
          {data &&
            tr(
              `Abfragen ab ${ms(data.thresholds.slow_query_ms)}, ohne Werte (jeder Wert ist «?»).`,
              `Queries taking ${ms(data.thresholds.slow_query_ms)} or more, without values (every value is "?").`,
            )}
        </Text>
        {data && data.queries.length === 0 && (
          <Text size="sm" c="dimmed">
            {tr('Keine langsamen Abfragen in diesem Zeitraum.', 'No slow queries in this period.')}
          </Text>
        )}
        <Stack gap={10}>
          {(data?.queries ?? []).map((q) => (
            <Paper key={q.id} withBorder radius="md" p="sm">
              <Group gap={12} mb={6} wrap="wrap">
                <Text size="sm" fw={600}>
                  {tr(`${q.count}×`, `${q.count}×`)}
                </Text>
                <Text size="xs" c="dimmed">
                  {tr(`Mittel ${ms(q.meanMs)} · max. ${ms(q.maxMs)}`, `mean ${ms(q.meanMs)} · max ${ms(q.maxMs)}`)}
                </Text>
                {q.where && (
                  <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                    {tr('zuletzt in', 'last in')} {q.where}
                  </Text>
                )}
              </Group>
              <Code block style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {q.sql}
              </Code>
            </Paper>
          ))}
        </Stack>
      </Paper>
    </Stack>
  )
}
