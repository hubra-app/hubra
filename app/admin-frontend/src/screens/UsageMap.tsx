import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Badge,
  Button,
  Group,
  Paper,
  Progress,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { IconRefresh } from '@tabler/icons-react'
import { getUsage, refreshUsage, type ModuleUsage, type UsageSnapshot } from '@/api/plugins'
import { useAdmin } from '@/context/AdminContext'
import { tr } from '@/lang'

type Filter = 'all' | 'plugins' | 'idle'

const when = (iso: string) =>
  new Intl.DateTimeFormat('de-CH', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))

/**
 * Which clubs use which modules and plugins: on in how many clubs, used
 * (something written in the last 30 days) in how many, idle where, and on
 * which plugin version. Counted nightly; "Jetzt zählen" counts now.
 */
export function UsageMapView() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<Filter>('all')
  const [busy, setBusy] = useState(false)
  const query = useQuery({ queryKey: ['plugin-usage'], queryFn: getUsage })
  const usage = query.data?.usage ?? null

  const count = async () => {
    setBusy(true)
    try {
      const res = await refreshUsage()
      queryClient.setQueryData(['plugin-usage'], res)
    } catch (err) {
      notify('error', tr('Zählen fehlgeschlagen', 'Count failed'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Stack gap="md">
      <Paper withBorder p="lg">
        <Group justify="space-between" align="flex-start" wrap="wrap" gap="sm">
          <div style={{ flex: 1, minWidth: 260 }}>
            <Title order={3} mb={4}>
              {tr('Nutzung der Module und Plugins', 'Module and plugin usage')}
            </Title>
            <Text size="sm" c="dimmed">
              {tr(
                'In wie vielen Vereinen ein Modul eingeschaltet ist und in wie vielen in den letzten 30 Tagen damit gearbeitet wurde. Eingeschaltet, aber nichts geschrieben: ungenutzt. Wird jede Nacht gezählt.',
                'In how many clubs a module is on, and in how many it was used in the last 30 days. On but nothing written: unused. Counted every night.',
              )}
            </Text>
            {usage && (
              <Text size="xs" c="dimmed" mt={6}>
                {tr(
                  `Stand ${when(usage.generatedAt)} · ${usage.clubs} aktive Vereine`,
                  `As of ${when(usage.generatedAt)} · ${usage.clubs} active clubs`,
                )}
              </Text>
            )}
          </div>
          <Button
            variant="default"
            leftSection={<IconRefresh size={16} />}
            loading={busy}
            onClick={() => void count()}
            data-testid="usage-refresh"
          >
            {tr('Jetzt zählen', 'Count now')}
          </Button>
        </Group>
      </Paper>

      {query.isError && (
        <Alert color="red" variant="light">
          {(query.error as Error).message}
        </Alert>
      )}
      {query.isSuccess && !usage && (
        <Alert color="gray" variant="light">
          {tr('Noch nicht gezählt. «Jetzt zählen» oder bis morgen warten.', 'Not counted yet. "Count now" or wait until tomorrow.')}
        </Alert>
      )}
      {usage && <UsageTables usage={usage} filter={filter} setFilter={setFilter} />}
    </Stack>
  )
}

function UsageTables({
  usage,
  filter,
  setFilter,
}: {
  usage: UsageSnapshot
  filter: Filter
  setFilter: (f: Filter) => void
}) {
  const rows = usage.modules.filter((m) =>
    filter === 'plugins' ? !!m.plugin : filter === 'idle' ? (m.clubsIdle ?? 0) > 0 : true,
  )
  const unusedPlugins = usage.plugins.filter((p) => p.clubsOn === 0)
  return (
    <>
      {unusedPlugins.length > 0 && (
        <Alert color="orange" variant="light" data-testid="usage-unused-plugins">
          {tr('Installiert, aber in keinem Verein eingeschaltet: ', 'Installed but on in no club: ')}
          {unusedPlugins.map((p) => `${p.name} ${p.version ?? ''}`.trim()).join(', ')}
        </Alert>
      )}
      <SegmentedControl
        w="fit-content"
        value={filter}
        onChange={(v) => setFilter(v as Filter)}
        data={[
          { value: 'all', label: tr('Alle Module', 'All modules') },
          { value: 'plugins', label: tr('Aus Plugins', 'From plugins') },
          { value: 'idle', label: tr('Mit ungenutzten', 'With unused') },
        ]}
      />
      <Paper withBorder style={{ overflowX: 'auto' }}>
        <Table verticalSpacing="sm" miw={680} data-testid="usage-table">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{tr('Modul', 'Module')}</Table.Th>
              <Table.Th>{tr('Plugin', 'Plugin')}</Table.Th>
              <Table.Th ta="right">{tr('Ein', 'On')}</Table.Th>
              <Table.Th w={200}>{tr('Genutzt (30 Tage)', 'Used (30 days)')}</Table.Th>
              <Table.Th>{tr('Ungenutzt in', 'Unused in')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((m) => (
              <UsageRow key={m.code} m={m} clubs={usage.clubs} />
            ))}
          </Table.Tbody>
        </Table>
      </Paper>
    </>
  )
}

function UsageRow({ m, clubs }: { m: ModuleUsage; clubs: number }) {
  const share = m.clubsOn ? Math.round((m.clubsActive / m.clubsOn) * 100) : 0
  const idle = m.idle.map((c) => c.name)
  return (
    <Table.Tr data-module={m.code}>
      <Table.Td>
        <Group gap={6} wrap="nowrap">
          <Text size="sm" fw={600}>
            {m.name}
          </Text>
          {m.required && (
            <Badge size="xs" variant="light" color="gray">
              {tr('immer an', 'always on')}
            </Badge>
          )}
        </Group>
        <Text size="xs" c="dimmed" ff="monospace">
          {m.code}
        </Text>
      </Table.Td>
      <Table.Td>
        {m.plugin ? (
          <Text size="sm">
            {m.pluginName ?? m.plugin}
            {m.version && (
              <Text span size="xs" c="dimmed">
                {' '}
                {m.version}
              </Text>
            )}
          </Text>
        ) : (
          <Text size="sm" c="dimmed">
            Hubra
          </Text>
        )}
      </Table.Td>
      <Table.Td ta="right">
        <Text size="sm">
          {m.clubsOn}
          <Text span size="xs" c="dimmed">
            /{clubs}
          </Text>
        </Text>
      </Table.Td>
      <Table.Td>
        {m.measured ? (
          <Tooltip label={tr(`${m.rows} Einträge geschrieben`, `${m.rows} rows written`)}>
            <Stack gap={2}>
              <Text size="xs">
                {m.clubsActive} {tr('Vereine', 'clubs')}
                {m.clubsOn > 0 && ` · ${share} %`}
              </Text>
              <Progress value={share} size="sm" color={share >= 50 ? 'teal' : share > 0 ? 'yellow' : 'gray'} />
            </Stack>
          </Tooltip>
        ) : (
          <Text size="xs" c="dimmed">
            {tr('nicht messbar', 'not measured')}
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        {idle.length > 0 ? (
          <Text size="xs" lineClamp={2} title={idle.join(', ')}>
            {idle.join(', ')}
            {(m.clubsIdle ?? 0) > idle.length && ` +${(m.clubsIdle ?? 0) - idle.length}`}
          </Text>
        ) : (
          <Text size="xs" c="dimmed">
            –
          </Text>
        )}
      </Table.Td>
    </Table.Tr>
  )
}
