import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Group,
  Paper,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useElementSize } from '@mantine/hooks'
import { tr } from '@/lang'
import {
  getTenantTrends,
  type TenantTrends as Trends,
  type TrendMetric,
  type TrendRange,
} from '@/api/tenants'

type Chart = {
  metric: TrendMetric
  label: () => string
  /** What a bucket's number is, for the tooltip. */
  note?: (t: Trends, i: number) => string
}

const CHARTS: Chart[] = [
  { metric: 'logins', label: () => tr('Anmeldungen', 'Sign-ins') },
  {
    metric: 'active_members',
    label: () => tr('Aktive Mitglieder', 'Active members'),
  },
  {
    metric: 'members',
    label: () => tr('Mitglieder', 'Members'),
    note: (t, i) =>
      t.series.new_members[i] ? tr(`+${t.series.new_members[i]} neu`, `+${t.series.new_members[i]} new`) : '',
  },
  { metric: 'events', label: () => tr('Anlässe', 'Events') },
  {
    metric: 'invoices',
    label: () => tr('Rechnungen', 'Invoices'),
    note: (t, i) => (t.series.invoices[i] ? `CHF ${chf(t.series.invoice_total[i])}` : ''),
  },
  { metric: 'mails', label: () => tr('Mails', 'Mails') },
]

const num = (n: number) => n.toLocaleString('de-CH')
const chf = (n: number) =>
  n.toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function bucketLabel(t: Trends, i: number, short = false) {
  const d = new Date(`${t.buckets[i]}T00:00:00`)
  if (t.unit === 'month') {
    return d.toLocaleDateString('de-CH', { month: short ? 'short' : 'long', year: 'numeric' })
  }
  const day = d.toLocaleDateString('de-CH', { day: 'numeric', month: short ? 'numeric' : 'short' })
  return short ? day : tr(`Woche ab ${day}`, `Week of ${day}`)
}

/** A clean top for the y axis: 1, 2, 5 × 10^n at or above max. */
function niceMax(max: number) {
  if (max <= 4) return Math.max(1, max)
  const p = 10 ** Math.floor(Math.log10(max))
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= max) return m * p
  return 10 * p
}

const H = 120
const AXIS = 18
/** Room left of the bars for the y-axis numbers. */
const GUTTER = 34

function Columns({ trends, metric, note }: { trends: Trends; metric: TrendMetric; note?: Chart['note'] }) {
  const { ref, width } = useElementSize()
  const [hover, setHover] = useState<number | null>(null)
  const values = trends.series[metric]
  const top = niceMax(Math.max(...values, 0))
  const n = values.length
  const plot = Math.max(0, width - GUTTER)
  const slot = plot / Math.max(n, 1)
  const bar = Math.max(2, Math.min(24, slot - 2))
  const y = (v: number) => H - (v / top) * H
  const last = n - 1

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {width > 0 && (
        <svg width={width} height={H + AXIS} role="img" aria-label={tr('Verlauf', 'Trend')}>
          <line x1={GUTTER} x2={width} y1={H + 0.5} y2={H + 0.5} stroke="var(--mantine-color-default-border)" />
          <line
            x1={GUTTER}
            x2={width}
            y1={0.5}
            y2={0.5}
            stroke="var(--mantine-color-default-border)"
            strokeOpacity={0.6}
          />
          <text x={GUTTER - 6} y={9} fontSize={11} textAnchor="end" fill="var(--mantine-color-dimmed)">
            {num(top)}
          </text>
          <text x={GUTTER - 6} y={H} fontSize={11} textAnchor="end" fill="var(--mantine-color-dimmed)">
            0
          </text>
          {values.map((v, i) => {
            const h = H - y(v)
            const x = GUTTER + i * slot + (slot - bar) / 2
            const r = Math.min(4, h, bar / 2)
            const d =
              h <= 0
                ? ''
                : `M${x},${H} V${H - h + r} Q${x},${H - h} ${x + r},${H - h} H${x + bar - r} Q${x + bar},${H - h} ${x + bar},${H - h + r} V${H} Z`
            return (
              <g key={i}>
                {d && (
                  <path
                    d={d}
                    fill="var(--mantine-primary-color-filled)"
                    fillOpacity={i === last ? 0.45 : hover === null || hover === i ? 1 : 0.55}
                  />
                )}
                <rect
                  x={GUTTER + i * slot}
                  y={0}
                  width={slot}
                  height={H}
                  fill="transparent"
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                  onTouchStart={() => setHover(i)}
                />
              </g>
            )
          })}
          <text x={GUTTER} y={H + 13} fontSize={11} fill="var(--mantine-color-dimmed)">
            {bucketLabel(trends, 0, true)}
          </text>
          <text x={width} y={H + 13} fontSize={11} textAnchor="end" fill="var(--mantine-color-dimmed)">
            {bucketLabel(trends, last, true)}
          </text>
        </svg>
      )}
      {hover !== null && width > 0 && (
        <Paper
          withBorder
          shadow="sm"
          px={8}
          py={4}
          radius="sm"
          style={{
            position: 'absolute',
            top: Math.max(0, y(values[hover]) - 44),
            left: Math.min(Math.max(0, GUTTER + hover * slot + slot / 2 - 70), width - 140),
            width: 140,
            pointerEvents: 'none',
            zIndex: 2,
          }}
        >
          <Text size="xs" c="dimmed">
            {bucketLabel(trends, hover)}
            {hover === last ? tr(' (läuft)', ' (so far)') : ''}
          </Text>
          <Text size="sm" fw={600}>
            {num(values[hover])}
            {note?.(trends, hover) ? (
              <Text span size="xs" c="dimmed" fw={400}>
                {' · '}
                {note(trends, hover)}
              </Text>
            ) : null}
          </Text>
        </Paper>
      )}
    </div>
  )
}

function Delta({ trends, metric }: { trends: Trends; metric: TrendMetric }) {
  // Compare the last finished bucket with the one before it.
  const v = trends.series[metric]
  if (v.length < 3) return null
  const a = v[v.length - 2]
  const b = v[v.length - 3]
  const diff = a - b
  const unit =
    trends.unit === 'week'
      ? tr('letzte Woche ggü. Vorwoche', 'last week vs the week before')
      : tr('letzter Monat ggü. Vormonat', 'last month vs the month before')
  return (
    <Text size="xs" c="dimmed">
      {num(a)} {diff === 0 ? '' : `(${diff > 0 ? '+' : '−'}${num(Math.abs(diff))})`} · {unit}
    </Text>
  )
}

/** Usage of one club over weeks or months, from data the club already keeps. */
export function TenantTrends({ tenantId }: { tenantId: number }) {
  const [range, setRange] = useState<TrendRange>('12w')
  const [view, setView] = useState<'charts' | 'table'>('charts')
  const { data, isLoading } = useQuery({
    queryKey: ['tenant-trends', tenantId, range],
    queryFn: () => getTenantTrends(tenantId, range),
  })

  return (
    <Paper withBorder p="lg" mb={20}>
      <Group justify="space-between" mb={4} wrap="wrap" gap="sm">
        <Title order={3}>{tr('Nutzung', 'Usage')}</Title>
        <Group gap="xs" wrap="wrap">
          <SegmentedControl
            size="xs"
            value={range}
            onChange={(v) => setRange(v as TrendRange)}
            data={[
              { value: '12w', label: tr('12 Wochen', '12 weeks') },
              { value: '26w', label: tr('26 Wochen', '26 weeks') },
              { value: '12m', label: tr('12 Monate', '12 months') },
            ]}
          />
          <SegmentedControl
            size="xs"
            value={view}
            onChange={(v) => setView(v as 'charts' | 'table')}
            data={[
              { value: 'charts', label: tr('Diagramme', 'Charts') },
              { value: 'table', label: tr('Tabelle', 'Table') },
            ]}
          />
        </Group>
      </Group>
      <Text size="sm" c="dimmed" mb={16}>
        {tr(
          'Pro Woche bzw. Monat, aus den Daten des Vereins: Anmeldungen und aktive Mitglieder aus dem Vereinsprotokoll, Anlässe nach Datum, Rechnungen nach Ausstellung, Mails aus dem Ereignisprotokoll. Die laufende Woche bzw. der laufende Monat ist heller.',
          "Per week or month, from the club's own data: sign-ins and active members from the club log, events by date, invoices by issue date, mails from the event log. The current week or month is lighter.",
        )}
      </Text>
      {isLoading || !data ? (
        <Text size="sm" c="dimmed">
          {tr('Wird geladen …', 'Loading…')}
        </Text>
      ) : view === 'charts' ? (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="lg" verticalSpacing="xl">
          {CHARTS.map((c) => (
            <Stack key={c.metric} gap={6}>
              <div>
                <Text size="sm" fw={600}>
                  {c.label()}
                </Text>
                <Delta trends={data} metric={c.metric} />
              </div>
              <Columns trends={data} metric={c.metric} note={c.note} />
            </Stack>
          ))}
        </SimpleGrid>
      ) : (
        <Table.ScrollContainer minWidth={720}>
          <Table striped verticalSpacing={4} fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{data.unit === 'week' ? tr('Woche ab', 'Week of') : tr('Monat', 'Month')}</Table.Th>
                {CHARTS.map((c) => (
                  <Table.Th key={c.metric} ta="right">
                    {c.label()}
                  </Table.Th>
                ))}
                <Table.Th ta="right">CHF</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.buckets
                .map((_, i) => i)
                .reverse()
                .map((i) => (
                  <Table.Tr key={i}>
                    <Table.Td style={{ whiteSpace: 'nowrap' }}>
                      {bucketLabel(data, i, data.unit === 'week')}
                      {i === data.buckets.length - 1 ? tr(' (läuft)', ' (so far)') : ''}
                    </Table.Td>
                    {CHARTS.map((c) => (
                      <Table.Td key={c.metric} ta="right">
                        {num(data.series[c.metric][i])}
                      </Table.Td>
                    ))}
                    <Table.Td ta="right">{chf(data.series.invoice_total[i])}</Table.Td>
                  </Table.Tr>
                ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Paper>
  )
}
