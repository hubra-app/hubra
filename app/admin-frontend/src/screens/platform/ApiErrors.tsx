import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Checkbox,
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
import { IconAlertTriangle, IconCircleCheck, IconRefresh, IconX } from '@tabler/icons-react'
import { StatGrid, StatTile } from '@/components/ui'
import { formatDateTime } from '@/format'
import { tr } from '@/lang'
import { getApiErrors, type ApiErrorSlot, type ApiErrorRoute } from '@/api/platform'

const num = (v: number) => v.toLocaleString('de-CH')
const pct = (v: number | null | undefined) =>
  v == null ? '–' : `${(v * 100).toLocaleString('de-CH', { maximumFractionDigits: 1 })} %`
const time = (iso: string) =>
  new Date(iso).toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' })

/** Short names for the codes people see here most. */
const CODE_NAMES: Record<string, [string, string]> = {
  '400': ['Ungültige Anfrage', 'Bad request'],
  '401': ['Nicht angemeldet', 'Not signed in'],
  '403': ['Keine Berechtigung', 'Forbidden'],
  '404': ['Nicht gefunden', 'Not found'],
  '409': ['Konflikt', 'Conflict'],
  '413': ['Zu gross', 'Too large'],
  '422': ['Nicht verarbeitbar', 'Unprocessable'],
  '429': ['Zu viele Anfragen', 'Too many requests'],
  '500': ['Interner Fehler', 'Internal error'],
  '502': ['Bad Gateway', 'Bad gateway'],
  '503': ['Nicht verfügbar', 'Unavailable'],
  '504': ['Zeitüberschreitung', 'Gateway timeout'],
}

function codeLabel(code: string) {
  const warm = code.startsWith('w')
  const c = warm ? code.slice(1) : code
  const name = CODE_NAMES[c]
  const base = name ? `${c} ${tr(name[0], name[1])}` : c
  return warm ? `${base} (${tr('beim Start', 'starting')})` : base
}

function codeColor(code: string) {
  if (code.startsWith('w')) return 'gray'
  return code.startsWith('5') ? 'red' : 'orange'
}

function CodeBadges({ codes, size = 'xs' }: { codes: Record<string, number>; size?: 'xs' | 'sm' }) {
  return (
    <Group gap={4}>
      {Object.entries(codes).map(([c, n]) => (
        <Badge
          key={c}
          size={size}
          variant="light"
          color={codeColor(c)}
          style={{ textTransform: 'none' }}
        >
          {size === 'sm' ? codeLabel(c) : c.startsWith('w') ? `${c.slice(1)}*` : c} · {num(n)}
        </Badge>
      ))}
    </Group>
  )
}

/** Error answers per ten minutes as stacked bars: server errors (red), errors
 * while starting (grey) and, when shown, client errors (orange). Click a bar
 * to see that window's routes. */
function Timeline({
  slots,
  showClient,
  selected,
  onSelect,
}: {
  slots: ApiErrorSlot[]
  showClient: boolean
  selected: string | null
  onSelect: (at: string | null) => void
}) {
  const value = (s: ApiErrorSlot) => s.serverErrors + s.warmup + (showClient ? s.clientErrors : 0)
  const max = Math.max(1, ...slots.map(value))
  const H = 120
  const every = slots.length > 36 ? 18 : 6
  return (
    <Box>
      <Box
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 1,
          height: H,
          borderBottom: '1px solid var(--hb-border)',
        }}
        role="list"
        aria-label={tr('Fehler pro 10 Minuten', 'Errors per 10 minutes')}
      >
        {slots.map((s) => {
          const parts = [
            { n: s.serverErrors, color: 'var(--mantine-color-red-6)' },
            { n: s.warmup, color: 'var(--mantine-color-gray-5)' },
            ...(showClient ? [{ n: s.clientErrors, color: 'var(--mantine-color-orange-4)' }] : []),
          ]
          const active = selected === s.at
          const dim = selected != null && !active
          const label = `${time(s.at)}–${time(new Date(new Date(s.at).getTime() + 600_000).toISOString())}: ${tr(
            `${num(s.requests)} Anfragen, ${num(s.serverErrors)} Serverfehler (${pct(
              s.requests ? s.serverErrors / s.requests : null,
            )}), ${num(s.clientErrors)} Client-Fehler${s.warmup ? `, ${num(s.warmup)} beim Start` : ''}`,
            `${num(s.requests)} requests, ${num(s.serverErrors)} server errors (${pct(
              s.requests ? s.serverErrors / s.requests : null,
            )}), ${num(s.clientErrors)} client errors${s.warmup ? `, ${num(s.warmup)} while starting` : ''}`,
          )}`
          return (
            <Tooltip key={s.at} label={label} withArrow openDelay={100}>
              <Box
                role="listitem"
                aria-label={label}
                onClick={() => onSelect(active ? null : s.at)}
                style={{
                  flex: 1,
                  minWidth: 2,
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column-reverse',
                  cursor: value(s) ? 'pointer' : 'default',
                  opacity: dim ? 0.35 : 1,
                  outline: active ? '2px solid var(--mantine-color-acc-6)' : undefined,
                  outlineOffset: 1,
                  borderRadius: 2,
                }}
              >
                {parts.map((p, i) =>
                  p.n ? (
                    <Box
                      key={i}
                      style={{ height: `${(p.n / max) * H}px`, minHeight: 2, background: p.color }}
                    />
                  ) : null,
                )}
              </Box>
            </Tooltip>
          )
        })}
      </Box>
      <Box style={{ display: 'flex', gap: 1, marginTop: 4 }}>
        {slots.map((s, i) => (
          <Box
            key={s.at}
            style={{ flex: 1, minWidth: 2, overflow: 'visible', whiteSpace: 'nowrap' }}
          >
            {i % every === 0 && (
              <Text size="xs" c="dimmed">
                {time(s.at)}
              </Text>
            )}
          </Box>
        ))}
      </Box>
      <Group gap={14} mt={8}>
        <Legend
          color="var(--mantine-color-red-6)"
          label={tr('Serverfehler (5xx)', 'Server errors (5xx)')}
        />
        <Legend
          color="var(--mantine-color-gray-5)"
          label={tr('5xx beim Start', '5xx while starting')}
        />
        {showClient && (
          <Legend
            color="var(--mantine-color-orange-4)"
            label={tr('Client-Fehler (4xx)', 'Client errors (4xx)')}
          />
        )}
      </Group>
    </Box>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <Group gap={6} wrap="nowrap">
      <Box style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
      <Text size="xs" c="dimmed">
        {label}
      </Text>
    </Group>
  )
}

function RouteName({ method, route }: { method: string; route: string }) {
  return (
    <>
      <Text span size="xs" fw={700} c="dimmed" mr={6}>
        {method}
      </Text>
      <Code>{route}</Code>
    </>
  )
}

/** Where API errors happen: which routes answered which status code, when,
 * and what the error-rate alert sees right now. The alert's mail and Discord
 * message link here. Only route patterns are kept, never paths or people
 * (services/perf_monitor.py). */
export function ApiErrorsPanel() {
  const [hours, setHours] = useState('24')
  const [at, setAt] = useState<string | null>(null)
  const [showClient, setShowClient] = useState(false)
  const query = useQuery({
    queryKey: ['api-errors', hours],
    queryFn: () => getApiErrors(Number(hours)),
    refetchInterval: 60_000,
  })
  const slotQuery = useQuery({
    queryKey: ['api-errors-slot', hours, at],
    queryFn: () => getApiErrors(Number(hours), at ?? undefined),
    enabled: at != null,
  })
  const data = query.data
  const view = at && slotQuery.data ? slotQuery.data : data
  const alert = data?.alert
  const totals = (data?.timeline ?? []).reduce(
    (a, s) => ({
      requests: a.requests + s.requests,
      server: a.server + s.serverErrors,
      client: a.client + s.clientErrors,
      warmup: a.warmup + s.warmup,
    }),
    { requests: 0, server: 0, client: 0, warmup: 0 },
  )
  const routes: ApiErrorRoute[] = (view?.routes ?? []).filter(
    (r) => showClient || r.serverErrors || r.warmup,
  )
  const groups = view?.errorGroups ?? []
  const over = alert ? alert.requests >= alert.minRequests && alert.rate > alert.threshold : false

  return (
    <Stack gap={16}>
      <Group justify="space-between" wrap="wrap">
        <Text c="dimmed" size="sm" maw={720}>
          {tr(
            'Welche API-Routen mit welchem Fehlercode antworten und wann. Die Warnung «High API Error Rate» zählt nur Serverfehler (5xx) der letzten Stunde; Client-Fehler wie abgelaufene Anmeldungen (401) zählen nicht.',
            'Which API routes answer with which error code, and when. The “High API Error Rate” alert counts only server errors (5xx) in the last hour; client errors such as expired sign-ins (401) do not count.',
          )}
        </Text>
        <Group gap={8}>
          <SegmentedControl
            size="xs"
            value={hours}
            onChange={(v) => {
              setHours(v)
              setAt(null)
            }}
            data={[
              { value: '2', label: tr('Seit letzter Stunde', 'Since last hour') },
              { value: '6', label: tr('6 Stunden', '6 hours') },
              { value: '24', label: tr('24 Stunden', '24 hours') },
            ]}
          />
          <Button
            variant="default"
            leftSection={<IconRefresh size={16} />}
            onClick={() => {
              query.refetch()
              if (at) slotQuery.refetch()
            }}
            loading={query.isFetching || slotQuery.isFetching}
          >
            {tr('Aktualisieren', 'Refresh')}
          </Button>
        </Group>
      </Group>
      {query.isError && (
        <Text c="red">{query.error instanceof Error ? query.error.message : ''}</Text>
      )}
      {data?.source === 'memory' && (
        <Text size="sm" c="orange">
          {tr(
            'Redis ist nicht erreichbar: Die Zahlen stammen nur aus diesem Prozess und sind unvollständig.',
            'Redis is unreachable: the numbers come from this process only and are incomplete.',
          )}
        </Text>
      )}

      {alert && (
        <Alert
          variant="light"
          color={alert.active || over ? 'red' : 'green'}
          icon={
            alert.active || over ? <IconAlertTriangle size={20} /> : <IconCircleCheck size={20} />
          }
          title={
            alert.active
              ? tr('Die Warnung ist aktiv', 'The alert is active')
              : over
                ? tr('Über der Grenze', 'Above the limit')
                : tr('Keine Warnung', 'No alert')
          }
        >
          <Stack gap={8}>
            <Text size="sm">
              {tr(
                `Letzte Stunde: ${num(alert.serverErrors)} Serverfehler bei ${num(alert.requests)} Anfragen (${pct(
                  alert.rate,
                )}). Gewarnt wird ab ${pct(alert.threshold)} und mindestens ${alert.minRequests} Anfragen.`,
                `Last hour: ${num(alert.serverErrors)} server errors in ${num(alert.requests)} requests (${pct(
                  alert.rate,
                )}). The alert goes out above ${pct(alert.threshold)} with at least ${alert.minRequests} requests.`,
              )}
            </Text>
            {alert.topRoutes.length > 0 && (
              <Stack gap={4}>
                <Text size="sm" fw={600}>
                  {tr('Die meisten Serverfehler:', 'Most server errors:')}
                </Text>
                {alert.topRoutes.map((r) => (
                  <Group key={`${r.method} ${r.route}`} gap={8} wrap="wrap">
                    <Box style={{ wordBreak: 'break-all' }}>
                      <RouteName method={r.method} route={r.route} />
                    </Box>
                    <CodeBadges codes={r.codes} />
                  </Group>
                ))}
              </Stack>
            )}
          </Stack>
        </Alert>
      )}

      {data && (
        <StatGrid columns={4} style={{ marginBottom: 0 }}>
          <StatTile
            label={tr(`Serverfehler (${data.hours} h)`, `Server errors (${data.hours} h)`)}
            value={num(totals.server)}
            sub={tr(
              `${pct(totals.requests ? totals.server / totals.requests : null)} von ${num(totals.requests)} Anfragen`,
              `${pct(totals.requests ? totals.server / totals.requests : null)} of ${num(totals.requests)} requests`,
            )}
            accent={totals.server ? 'var(--mantine-color-red-text)' : undefined}
          />
          <StatTile
            label={tr(`Client-Fehler (${data.hours} h)`, `Client errors (${data.hours} h)`)}
            value={num(totals.client)}
            sub={tr('4xx, zählen nicht zur Warnung', '4xx, not counted by the alert')}
          />
          <StatTile
            label={tr('5xx beim Start', '5xx while starting')}
            value={num(totals.warmup)}
            sub={tr(
              'In den ersten 2 Minuten eines Prozesses',
              'In the first 2 minutes of a process',
            )}
          />
          <StatTile
            label={tr('Routen mit Serverfehlern', 'Routes with server errors')}
            value={num((data.routes ?? []).filter((r) => r.serverErrors).length)}
            sub={tr(
              `${data.routeCount} Routen mit Fehlern insgesamt`,
              `${data.routeCount} routes with any error`,
            )}
          />
        </StatGrid>
      )}

      <Paper withBorder p="lg">
        <Group justify="space-between" mb={12} wrap="wrap">
          <Title order={4}>{tr('Verlauf (10 Minuten)', 'Timeline (10 minutes)')}</Title>
          <Checkbox
            size="xs"
            label={tr('Client-Fehler (4xx) zeigen', 'Show client errors (4xx)')}
            checked={showClient}
            onChange={(e) => setShowClient(e.currentTarget.checked)}
          />
        </Group>
        {data && (
          <Timeline slots={data.timeline} showClient={showClient} selected={at} onSelect={setAt} />
        )}
        <Text size="xs" c="dimmed" mt={6}>
          {tr(
            'Auf einen Balken klicken, um nur dieses Zeitfenster unten zu sehen.',
            'Click a bar to see only that window below.',
          )}
        </Text>
      </Paper>

      <Paper withBorder p="lg">
        <Group justify="space-between" mb={8} wrap="wrap">
          <Title order={4}>
            {at
              ? tr(
                  `Routen ${time(at)}–${time(new Date(new Date(at).getTime() + 600_000).toISOString())}`,
                  `Routes ${time(at)}–${time(new Date(new Date(at).getTime() + 600_000).toISOString())}`,
                )
              : tr('Routen mit Fehlern', 'Routes with errors')}
          </Title>
          {at && (
            <Button
              size="compact-sm"
              variant="subtle"
              leftSection={<IconX size={14} />}
              onClick={() => setAt(null)}
            >
              {tr('Ganzer Zeitraum', 'Whole period')}
            </Button>
          )}
        </Group>
        {view && Object.keys(view.codes).length > 0 && (
          <Box mb={12}>
            <CodeBadges codes={view.codes} size="sm" />
          </Box>
        )}
        {view && routes.length === 0 && (
          <Text size="sm" c="dimmed">
            {showClient
              ? tr('Keine Fehler in diesem Zeitraum.', 'No errors in this period.')
              : tr('Keine Serverfehler in diesem Zeitraum.', 'No server errors in this period.')}
          </Text>
        )}
        {routes.length > 0 && (
          <Table.ScrollContainer minWidth={760}>
            <Table highlightOnHover verticalSpacing={6} fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{tr('Route', 'Route')}</Table.Th>
                  <Table.Th ta="right">{tr('Anfragen', 'Requests')}</Table.Th>
                  <Table.Th ta="right">5xx</Table.Th>
                  <Table.Th ta="right">{tr('Anteil', 'Share')}</Table.Th>
                  <Table.Th>{tr('Codes', 'Codes')}</Table.Th>
                  <Table.Th>{tr('Zuletzt', 'Last')}</Table.Th>
                  <Table.Th>{tr('Ursache', 'Cause')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {routes.map((r) => (
                  <Table.Tr key={r.label} style={{ verticalAlign: 'top' }}>
                    <Table.Td style={{ wordBreak: 'break-all' }}>
                      <RouteName method={r.method} route={r.route} />
                    </Table.Td>
                    <Table.Td ta="right">{r.requests == null ? '–' : num(r.requests)}</Table.Td>
                    <Table.Td
                      ta="right"
                      c={r.serverErrors ? 'red.8' : undefined}
                      fw={r.serverErrors ? 600 : undefined}
                    >
                      {num(r.serverErrors)}
                    </Table.Td>
                    <Table.Td ta="right">{pct(r.serverShare)}</Table.Td>
                    <Table.Td>
                      <CodeBadges codes={r.codes} />
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                        {r.lastAt ? formatDateTime(r.lastAt) : '–'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {r.errorGroups.length > 0 ? (
                        <Anchor
                          component={Link}
                          size="xs"
                          to={`/app/platform/diagnostics/errors?q=${encodeURIComponent(r.route)}`}
                        >
                          {tr(
                            `${r.errorGroups.length} Fehler ansehen`,
                            `View ${r.errorGroups.length} error${r.errorGroups.length === 1 ? '' : 's'}`,
                          )}
                        </Anchor>
                      ) : (
                        <Text size="xs" c="dimmed">
                          {r.serverErrors
                            ? tr('Keine Ausnahme erfasst', 'No exception recorded')
                            : ''}
                        </Text>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        <Text size="xs" c="dimmed" mt={8}>
          {tr(
            '«*» hinter einem Code: beim Start eines Prozesses, zählt nicht zur Warnung. «Keine Ausnahme erfasst»: die Route hat selbst 5xx geantwortet (z. B. 502/503 von einem Dienst dahinter), ohne Absturz in Hubra.',
            '“*” after a code: while a process was starting, not counted by the alert. “No exception recorded”: the route answered 5xx itself (e.g. 502/503 from a service behind it) without a crash in Hubra.',
          )}
        </Text>
      </Paper>

      {groups.length > 0 && (
        <Paper withBorder p="lg">
          <Group justify="space-between" mb={4} wrap="wrap">
            <Title order={4}>
              {tr('Ausnahmen auf diesen Routen', 'Exceptions on these routes')}
            </Title>
            <Anchor component={Link} to="/app/platform/diagnostics/errors" size="sm">
              {tr('Alle Fehler', 'All errors')}
            </Anchor>
          </Group>
          <Text size="xs" c="dimmed" mb={12}>
            {tr(
              'Abstürze, die mit 500 geantwortet haben, gruppiert nach Typ und Stelle im Code (Diagnose › Fehler).',
              'Crashes that answered 500, grouped by type and place in the code (Diagnostics › Errors).',
            )}
          </Text>
          <Stack gap={8}>
            {groups.map((g) => (
              <Paper key={g.id} withBorder p="sm">
                <Group justify="space-between" gap={8} wrap="wrap" mb={4}>
                  <Group gap={8} wrap="wrap">
                    <Text size="sm" fw={600} ff="monospace">
                      {g.exc_type}
                    </Text>
                    <Badge size="xs" variant="light" color={g.status === 'open' ? 'red' : 'gray'}>
                      {g.status === 'open' ? tr('Offen', 'Open') : tr('Erledigt', 'Resolved')}
                    </Badge>
                    <Text size="xs" c="dimmed">
                      {tr(
                        `${num(g.count)}× · zuletzt ${formatDateTime(g.last_seen)}`,
                        `${num(g.count)}× · last ${formatDateTime(g.last_seen)}`,
                      )}
                    </Text>
                  </Group>
                  <Anchor
                    component={Link}
                    size="xs"
                    to={`/app/platform/diagnostics/errors?q=${encodeURIComponent(g.exc_type)}`}
                  >
                    {tr('Traceback ansehen', 'View traceback')}
                  </Anchor>
                </Group>
                <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }} mb={2}>
                  {g.route} · {g.location}
                </Text>
                <Text size="sm" c="red" lineClamp={2} style={{ wordBreak: 'break-word' }}>
                  {g.message}
                </Text>
              </Paper>
            ))}
          </Stack>
        </Paper>
      )}
    </Stack>
  )
}
